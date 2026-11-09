"""Validate the pinned Windows FBX binding; optionally install it for source builds."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile


WHEEL_SHA256 = "be7e898ed5749e8534db6cfa16d4b7ea97078f1b277bf8d6a3fa7cfc9b5ef978"
WHEEL_NAME = "fbxsdkpy-2020.1.post2-cp310-none-win_amd64.whl"
WHEEL_URL = f"https://gitlab.inria.fr/api/v4/projects/18692/packages/pypi/files/{WHEEL_SHA256}/{WHEEL_NAME}"


def binding_from_wheel(wheel: bytes) -> bytes:
    if sha256(wheel).hexdigest() != WHEEL_SHA256:
        raise ValueError("Upstream FBX wheel SHA-256 did not match")
    with ZipFile(BytesIO(wheel)) as archive:
        binding = archive.read("fbx.pyd")
    if not binding.startswith(b"MZ"):
        raise ValueError("The FBX wheel does not contain a Windows runtime binding")
    return binding


def install_fbx():
    target = Path(sys.prefix) / "Lib/site-packages"
    if (target / "fbx.pyd").is_file():
        return
    with urlopen(WHEEL_URL, timeout=15) as response:
        wheel = response.read(16 * 1024 * 1024 + 1)
    binding = binding_from_wheel(wheel)
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fbx-", dir=target) as temporary:
        path = Path(temporary) / "fbx.pyd"
        path.write_bytes(binding)
        path.replace(target / path.name)


if __name__ == "__main__":
    install_fbx()
