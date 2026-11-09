"""Image output through Python's path handling, including Unicode on Windows."""

from pathlib import Path

import cv2


def write_image(path, image, params=()):
    path = Path(path)
    ok, encoded = cv2.imencode(path.suffix, image, list(params))
    if not ok:
        raise OSError(f"Could not encode image: {path}")
    with path.open("wb") as output:
        output.write(encoded)
