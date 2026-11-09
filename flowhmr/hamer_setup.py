"""Install only the verified HaMeR inference code and the three required model files."""

import errno
import gzip
import hashlib
import io
from pathlib import Path
import shutil
import tarfile
from tempfile import NamedTemporaryFile
import zipfile

from . import model_files as files, model_sources as sources


_INFERENCE_SOURCES = (
    "LICENSE.md", "hamer/__init__.py", "hamer/configs/__init__.py",
    "hamer/models/backbones/__init__.py", "hamer/models/backbones/vit.py",
    "hamer/models/heads/__init__.py", "hamer/models/heads/mano_head.py",
    "hamer/models/components/__init__.py", "hamer/models/components/pose_transformer.py",
    "hamer/models/components/t_cond_mlp.py", "hamer/utils/geometry.py",
)
_NAMESPACES = ("hamer/models/__init__.py", "hamer/utils/__init__.py")
_CHUNK = 1024 * 1024


class BadArchive(ValueError):
    pass


def runtime_installed():
    try:
        revision = (files.HAMER_RUNTIME / "revision.txt").read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return False
    return revision == sources.HAMER_REVISION and all(
        (files.HAMER_RUNTIME / name).is_file() for name in (*_INFERENCE_SOURCES, *_NAMESPACES))


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        tmp = Path(temporary.name)
        try:
            temporary.write(data)
            temporary.close()
            tmp.replace(path)
        finally:
            temporary.close()
            tmp.unlink(missing_ok=True)


def install_code(source_archive, *, check=lambda: None):
    data = source_archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != sources.HAMER_SOURCE_SHA256:
        raise BadArchive("HaMeR official source archive SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        prefix = f"hamer-{sources.HAMER_REVISION}/"
        for relative in _INFERENCE_SOURCES:
            check()
            _atomic_write(files.HAMER_RUNTIME / relative, archive.read(prefix + relative))
    for relative in _NAMESPACES:
        _atomic_write(files.HAMER_RUNTIME / relative, b'"""HaMeR inference modules."""\n')
    _atomic_write(files.HAMER_RUNTIME / "revision.txt", (sources.HAMER_REVISION + "\n").encode("ascii"))


class _CheckedReader:
    def __init__(self, stream, check):
        self.stream, self.check = stream, check

    def read(self, size):
        self.check()
        return self.stream.read(size)


def _install_member(archive, entry, asset, path, progress, check):
    if entry.size != asset.size:
        raise BadArchive(f"Unexpected size for {entry.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(path.parent).free < asset.size:
        raise OSError(errno.ENOSPC, "Insufficient space for HaMeR extraction")
    digest, copied = hashlib.sha256(), 0
    progress("install", path.name, copied, asset.size)
    with NamedTemporaryFile(dir=path.parent, suffix=".install.part", delete=False) as temporary:
        tmp = Path(temporary.name)
        try:
            with archive.extractfile(entry) as source:
                while chunk := source.read(_CHUNK):
                    check()
                    temporary.write(chunk)
                    digest.update(chunk)
                    copied += len(chunk)
                    progress("install", path.name, copied, asset.size)
            temporary.close()
            if copied != asset.size or digest.hexdigest() != asset.sha256:
                raise BadArchive(f"SHA-256 verification failed for {entry.name}")
            check()
            if not files.file_present(path):
                tmp.replace(path)
        finally:
            temporary.close()
            tmp.unlink(missing_ok=True)


def install_weights(archive_path, *, progress=lambda *_: None, check=lambda: None):
    pending = {name: (asset, files.resolve_model(asset.relative)) for name, asset in sources.HAMER_MEMBERS.items()
               if not files.file_present(files.resolve_model(asset.relative))}
    if not pending:
        return
    try:
        # Check cancellation even while scanning over unrelated files in the tar stream.
        with gzip.open(archive_path, "rb") as stream:
            with tarfile.open(fileobj=_CheckedReader(stream, check), mode="r|", bufsize=_CHUNK) as archive:
                for entry in archive:
                    name = entry.name.removeprefix("./")
                    if name not in pending or not entry.isfile():
                        continue
                    asset, path = pending[name]
                    _install_member(archive, entry, asset, path, progress, check)
                    pending.pop(name)
                    if not pending:
                        return
    except (tarfile.TarError, gzip.BadGzipFile, EOFError) as error:
        raise BadArchive("Unable to read the HaMeR archive") from error
    raise BadArchive("Missing official HaMeR files: " + ", ".join(pending))
