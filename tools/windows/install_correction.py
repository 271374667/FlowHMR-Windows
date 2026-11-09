"""Install FlowHMR's optional correction from a verified project-local wheel."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
NATIVE_NAME = "_motion_correction.cp310-win_amd64.pyd"
NATIVE_SHA256 = "46fea913e302fafa2281842e8b081ba34cfcbc572e2d2f36ac107bc89ed22638"
WHEEL_TAG = "cp310-cp310-win_amd64"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cache = ROOT / ".cache/correction"
    parser.add_argument("--wheel", type=Path, default=cache / f"motion_correction-1.0.0-{WHEEL_TAG}.whl")
    args = parser.parse_args()
    if (Path(sys.prefix).resolve() != ROOT / ".venv" or sys.version_info[:2] != (3, 10)
            or sysconfig.get_platform() != "win-amd64"):
        parser.error("Run this installer with FlowHMR's Windows x64 .venv/Scripts/python.exe (CPython 3.10).")

    wheel = args.wheel.resolve()
    if not wheel.is_file():
        parser.error(f"The project-local correction wheel is missing: {wheel}")
    with ZipFile(wheel) as archive:
        binary = archive.read(f"motion_correction/{NATIVE_NAME}")
    if hashlib.sha256(binary).hexdigest() != NATIVE_SHA256:
        parser.error("The correction wheel does not match the expected native build SHA-256.")
    temporary = cache / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **dict.fromkeys(("TMPDIR", "TEMP", "TMP"), str(temporary))}
    subprocess.run([
        sys.executable, "-m", "pip", "--disable-pip-version-check", "install", "--no-index", "--no-deps",
        "--no-build-isolation", str(wheel), str(ROOT / "third_party/RGBMocapCorrection"),
    ], check=True, env=env)
    subprocess.run([
        sys.executable, "-c", "from rgbmocap_correction.correction import backend; "
        "assert backend().rgb_mocap_anatomical_version == 1; print('Native contact correction is ready.')",
    ], check=True)


if __name__ == "__main__":
    main()
