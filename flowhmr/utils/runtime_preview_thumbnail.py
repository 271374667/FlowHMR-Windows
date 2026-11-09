"""Small local thumbnails for the job history."""

import math
from pathlib import Path
from threading import Lock


_decode_lock = Lock()


def ensure_thumbnail(video, thumbnail):
    import cv2

    path = Path(thumbnail)
    if path.is_file():
        return True
    with _decode_lock:
        if path.is_file():
            return True
        capture = cv2.VideoCapture(str(video))
        try:
            if not capture.isOpened():
                return False
            count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
            if math.isfinite(count) and count > 4:
                capture.set(cv2.CAP_PROP_POS_FRAMES, min(int(count * 0.18), 90))
            ok, frame = capture.read()
            if not ok:
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = capture.read()
            if not ok or frame is None:
                return False
        finally:
            capture.release()
        height, width = frame.shape[:2]
        scale = min(1, 200 / max(height, width))
        frame = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))),
                           interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 83])
        if not ok:
            return False
        pending = path.with_suffix(".jpg.part")
        pending.write_bytes(encoded.tobytes())
        pending.replace(path)
        return True
