"""Windows inference runtimes are downloaded into isolated, switchable slots."""

import csv
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Event, Lock, Thread
from urllib.parse import quote
from uuid import uuid4
from zipfile import ZipFile

from .model_downloads import ACTIVE_DOWNLOAD, DownloadCancelled, DownloadError, _failure_message, download_file


ROOT = Path(__file__).resolve().parents[1]
TORCH_VERSION = "2.8.0"
VISION_VERSION = "0.23.0"
SUPPORTED = sys.platform == "win32" and sys.version_info[:2] == (3, 10) and struct.calcsize("P") == 8
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class Wheel:
    package: str
    release: str
    variant: str
    size: int
    sha256: str

    @property
    def relative(self):
        return f"{self.package}-{self.release}+{self.variant}-cp310-cp310-win_amd64.whl"

    @property
    def urls(self):
        path = f"/whl/{self.variant}/{quote(self.relative)}"
        return ("https://download-r2.pytorch.org" + path, "https://download.pytorch.org" + path)


# Windows CPython 3.10 wheels from the official PyTorch indices.
_SOURCES = {
    "cu126": (2915462477, "3b43acaa40ac87495d858bb1dbe574aaaff4e60e9da6221825ece694fd1d2b80",
              6227571, "089d3fbeabf273a7f138c7fa2486289313ec57b002a4856f47eba52dace35e96"),
    "cu128": (3461427674, "43938e9a174c90e5eb9e906532b2f1e21532bbfa5a61b65193b4f54714d34f9e",
              7540139, "8ec6f2281ef5d52471b01b99eb04243d0c2cccb1972ba43217085025fe5a6c3f"),
    "cu129": (3571817490, "e4adcc3d44089d4a696e6a2ca4233d1ddad7614adc1d48ec8a8cfb95ba235ea1",
              8147730, "eaec7f8dd6f50f7516d4290c865ef4c9149034983523ebed83ebbd6023b5bf72"),
}
WHEELS = {key: (Wheel("torch", TORCH_VERSION, key, ts, th), Wheel("torchvision", VISION_VERSION, key, vs, vh))
          for key, (ts, th, vs, vh) in _SOURCES.items()}
VERSIONS = ("cu128", "cu129", "cu126")
DRIVER_RECOMMENDED = {"cu126": "561.17", "cu128": "572.61", "cu129": "576.57"}


def _atomic_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(content, ensure_ascii=False).encode("utf-8"))
            stream.close()
            temporary.replace(path)
        finally:
            stream.close()
            temporary.unlink(missing_ok=True)


def _read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _system_cuda():
    try:
        torch = version("torch")
        version("torchvision")
        match = re.search(r"\+(cu\d+)", torch)
        return match[1] if match else None
    except PackageNotFoundError:
        return None


def cuda_label(variant):
    digits = variant.removeprefix("cu")
    return f"CUDA {digits[:-1]}.{digits[-1]}"


@lru_cache(maxsize=1)
def gpu_info():
    if not SUPPORTED:
        return None
    executable = shutil.which("nvidia-smi")
    if not executable:
        system = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/nvidia-smi.exe"
        executable = str(system) if system.is_file() else None
    if not executable:
        return None
    try:
        result = subprocess.run([executable, "--query-gpu=name,driver_version,compute_cap", "--format=csv,noheader"],
                                capture_output=True, encoding="utf-8", errors="replace", timeout=4,
                                creationflags=subprocess.CREATE_NO_WINDOW, check=True)
        name, driver, capability = [part.strip() for part in next(csv.reader(result.stdout.splitlines()))]
        return {"name": name, "driver": driver, "capability": capability}
    except (OSError, ValueError, StopIteration, subprocess.SubprocessError):
        return None


def _wheel_members(archive, wheel):
    allow = ({"torch", "torchgen", "functorch"} if wheel.package == "torch"
             else {"torchvision", "torchvision.libs"})
    allow.add(f"{wheel.package}-{wheel.release}+{wheel.variant}.dist-info")
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts or "\\" in info.filename or ":" in info.filename:
            raise DownloadError("运行环境包中有无效路径。")
        if info.is_dir() or not path.parts or path.parts[0] not in allow:
            continue
        if path.parts[:2] in {("torch", "include"), ("torch", "share")} or path.suffix.lower() == ".lib":
            continue  # Runtime does not compile C++ extensions.
        yield info, path


class RuntimeEnvironments:
    def __init__(self, root, logger=None):
        self.root = Path(root).resolve()
        self.directory = self.root / "runtime/environments"
        self.downloads = self.root / ".cache/runtime-downloads"
        self.preference = self.directory / "selected.json"
        self.system = _system_cuda() if SUPPORTED else None
        self.active = "system" if self.system else None
        self.logger = logger
        self.lock = Lock()
        self.cancel = Event()
        self.transfer = {"id": None, "status": "idle"}

    def installed(self, name):
        if name not in WHEELS:
            return None
        slot = self.directory / name
        site = slot / "site-packages"
        mark = _read_json(slot / "installed.json")
        if (mark.get("sha256") == [item.sha256 for item in WHEELS[name]]
                and site.resolve().is_relative_to(self.directory.resolve())
                and (site / "torch/lib/torch_cuda.dll").is_file()
                and (site / "torchvision/_C.pyd").is_file()):
            return site
        return None

    def selected(self):
        name = _read_json(self.preference).get("version")
        if isinstance(name, str) and self.installed(name) is not None:
            return name
        return "system" if self.system else None

    def configure_process(self):
        if not SUPPORTED:
            return
        self.active = self.selected()
        site = self.installed(self.active)
        if site is not None:
            sys.path.insert(0, str(site))
            # Windows spawn and external Python workers need the same PyTorch build.
            os.environ["PYTHONPATH"] = str(site)

    def summary(self):
        selected = self.selected() if SUPPORTED else None
        pending = SUPPORTED and selected != self.active
        return {"supported": SUPPORTED, "ready": not SUPPORTED or (self.active is not None and not pending),
                "active": self.active, "selected": selected, "pending_restart": pending,
                "label": cuda_label(self.system if self.active == "system" else self.active) if self.active else None}

    def snapshot(self):
        with self.lock:
            return dict(self.transfer)

    def details(self):
        data = self.summary()
        gpu = gpu_info()
        options = []
        if self.system:
            options.append({"id": "system", "label": cuda_label(self.system), "detail": "现有项目环境",
                            "installed": True, "bytes": 0, "compatible": True})
        if SUPPORTED:
            for name in VERSIONS:
                unavailable = name == "cu126" and gpu and (gpu["name"].find("RTX 50") >= 0 or
                              gpu["capability"].split(".", 1)[0].isdigit() and int(gpu["capability"].split(".", 1)[0]) >= 12)
                options.append({"id": name, "label": cuda_label(name), "installed": self.installed(name) is not None,
                                "bytes": sum(wheel.size for wheel in WHEELS[name]), "compatible": not bool(unavailable),
                                "detail": "RTX 50 系列请选 CUDA 12.8 或 12.9" if unavailable else
                                          f"PyTorch {TORCH_VERSION} · 建议驱动 {DRIVER_RECOMMENDED[name]} 或更新",
                                "recommended": name == "cu128",
                                "source": f"https://download.pytorch.org/whl/{name}/torch/"})
        return {**data, "gpu": gpu, "options": options, "directory": str(self.directory), "download": self.snapshot()}

    def select(self, name):
        if not SUPPORTED or not (name == "system" and self.system or self.installed(name) is not None):
            raise DownloadError("请先下载并安装此运行环境。")
        _atomic_json(self.preference, {"version": name})
        return self.summary()

    def start(self, name):
        if not SUPPORTED or name not in WHEELS:
            raise DownloadError("此系统不支持所选运行环境。")
        if not next(option for option in self.details()["options"] if option["id"] == name)["compatible"]:
            raise DownloadError("此显卡请使用 CUDA 12.8 或 12.9。")
        with self.lock:
            if self.transfer["status"] in ACTIVE_DOWNLOAD or self.installed(name) is not None:
                return dict(self.transfer)
            self.cancel.clear()
            self.transfer = {"id": uuid4().hex, "status": "running", "version": name, "phase": "download",
                             "file": "", "bytes": 0, "total": 0}
            Thread(target=self._run, args=(name,), name="flowhmr-runtime-download", daemon=True).start()
            return dict(self.transfer)

    def stop(self, token):
        with self.lock:
            if self.transfer["id"] == token and self.transfer["status"] == "running":
                self.cancel.set()
                self.transfer["status"] = "stopping"
            return dict(self.transfer)

    def _run(self, name):
        def check():
            if self.cancel.is_set():
                raise DownloadCancelled()

        def progress(phase, filename, size, total):
            with self.lock:
                self.transfer.update(phase=phase, file=filename, bytes=size, total=total)

        try:
            self.install(name, progress, check)
            state = {"status": "done"}
        except DownloadCancelled:
            state = {"status": "cancelled"}
        except Exception as error:
            if self.logger:
                self.logger.exception("Failed to install Windows GPU runtime %s", name)
            state = {"status": "failed", "error": _failure_message(error, "运行环境")}
        with self.lock:
            self.transfer.update(state)

    def install(self, name, progress, check):
        folder = self.downloads / name
        if any(not path.resolve().is_relative_to(self.root) for path in (folder, self.directory)):
            raise DownloadError("运行环境目录必须位于 FlowHMR 文件夹内。")
        self.directory.mkdir(parents=True, exist_ok=True)
        folder.mkdir(parents=True, exist_ok=True)
        wheels = [(wheel, download_file(wheel, folder / wheel.relative, folder, progress, check,
                                       subject="运行环境", verify_existing=True)) for wheel in WHEELS[name]]
        with TemporaryDirectory(prefix=f".{name}-", dir=self.directory) as temporary:
            stage = Path(temporary)
            site = stage / "site-packages"
            for wheel, package in wheels:
                with ZipFile(package) as archive:
                    members = list(_wheel_members(archive, wheel))
                    total = sum(info.file_size for info, _ in members)
                    if shutil.disk_usage(stage).free < total + 64 * 1024 ** 2:
                        raise DownloadError("磁盘空间不足，无法解包运行环境。")
                    written = 0
                    progress("install", wheel.package, 0, total)
                    for info, relative in members:
                        check()
                        destination = site.joinpath(*relative.parts)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(info) as source, destination.open("xb") as target:
                            while data := source.read(_CHUNK):
                                check()
                                target.write(data)
                                written += len(data)
                                progress("install", wheel.package, written, total)
            check()
            progress("test", "GPU", 0, 0)
            probe = self.root / "tools/windows/probe_cuda.py"
            result = subprocess.run([sys.executable, "-I", "-B", str(probe), str(site), name], cwd=self.root,
                                    capture_output=True, encoding="utf-8", errors="replace", timeout=75,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                if self.logger:
                    self.logger.warning("GPU probe %s: %s", name, (result.stderr or result.stdout)[-4000:])
                raise DownloadError("GPU 验证失败。请检查显卡驱动或选择其他 CUDA 版本。下载文件已保留。")
            check()
            _atomic_json(stage / "installed.json", {"sha256": [wheel.sha256 for wheel, _ in wheels]})
            destination = self.directory / name
            if destination.exists():
                raise DownloadError("目标版本目录已存在且未通过检查，请移走该目录后重试。")
            stage.rename(destination)
        for _, package in wheels:
            try:
                package.unlink()
            except OSError:
                pass  # The installed environment is valid even if a download is open elsewhere.


RUNTIME = RuntimeEnvironments(ROOT)
