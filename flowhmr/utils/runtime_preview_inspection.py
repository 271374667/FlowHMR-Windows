"""CPU-only skeleton and floor data for completed SMPL-H jobs."""

import json
from pathlib import Path
from threading import Lock

import numpy as np

from flowhmr.model_files import SMPLH_FILES, file_present, resolve_model

_VERSION = 1
_JOINT_COUNT = 52


def _estimate_floor(heights, ankles, contacts, fps):
    """Use quiet, low stance feet where possible; fall back to the lower sole envelope."""
    lowest = heights.min(axis=1)
    if contacts is not None and contacts.shape == (len(heights), 4) and np.isfinite(contacts).all():
        xz = ankles[..., [0, 2]]
        speed = np.linalg.norm(np.diff(xz, axis=0, prepend=xz[:1]), axis=-1) * fps
        vertical = np.abs(np.diff(heights, axis=0, prepend=heights[:1])) * fps
        confidence = contacts.reshape(-1, 2, 2).max(axis=2)
        planted = ((confidence >= 0.6) & (speed < 0.5) & (vertical < 0.5)
                   & (heights < lowest[:, None] + 0.10))
        if planted.sum() >= 3:
            return {"height_m": float(np.quantile(heights[planted], 0.15)), "source": "contacts"}
    return {"height_m": float(np.quantile(lowest, 0.10)), "source": "soles"}


class PreviewInspection:
    def __init__(self, model_path=None):
        self._model_path = Path(model_path) if model_path is not None else None
        self._geometry = None
        self._lock = Lock()

    def _body_geometry(self):
        # Old results without a skeleton cache can rebuild it entirely on the CPU.
        if self._geometry is None:
            path = self._model_path or resolve_model(SMPLH_FILES["neutral"])
            if not file_present(path):
                raise FileNotFoundError(path)
            from flowhmr.core.bodymodels.smpl_skeleton import SMPLSkeleton

            skeleton = SMPLSkeleton(str(path)).cpu().eval()
            parents = skeleton.parents.tolist()
            with np.load(path, allow_pickle=False) as model:
                weights = model["weights"]
            feet = [np.flatnonzero(weights[:, ankle] + weights[:, toe] > 0.6)
                    for ankle, toe in ((7, 10), (8, 11))]
            if not all(len(foot) for foot in feet):
                raise ValueError("SMPL-H sole vertices are unavailable")
            self._geometry = skeleton, parents, feet
        return self._geometry

    def load(self, directory):
        root = Path(directory)
        mesh_dir = root / "mesh"
        stream = mesh_dir / "joints.bin"
        sidecar = mesh_dir / "inspection.json"
        with self._lock:
            meta = json.loads((mesh_dir / "meta.json").read_text(encoding="utf-8"))
            frames, vertices = int(meta["num_frames"]), int(meta["num_vertices"])
            expected = frames * _JOINT_COUNT * 3 * 4
            try:
                info = json.loads(sidecar.read_text(encoding="utf-8"))
                parents = info["parents"]
                if (info["version"] == _VERSION and info["frames"] == frames
                        and isinstance(parents, list) and len(parents) == _JOINT_COUNT and parents[0] == -1
                        and all(type(parent) is int and 0 <= parent < i for i, parent in enumerate(parents[1:], 1))
                        and stream.stat().st_size == expected):
                    return stream, info
            except (OSError, ValueError, KeyError, TypeError):
                pass

            skeleton, parents, feet = self._body_geometry()
            import torch

            with np.load(root / "motion.npz", allow_pickle=False) as data:
                poses = torch.from_numpy(np.asarray(data["poses"], dtype=np.float32)).reshape(frames, -1, 3)
                trans = torch.from_numpy(np.asarray(data["trans"], dtype=np.float32))
                shapes = torch.from_numpy(np.asarray(data["betas"], dtype=np.float32)).reshape(1, -1)
                contacts = data.get("foot_contacts")
            joints = np.empty((frames, len(parents), 3), dtype="<f4")
            heights = np.empty((frames, 2), dtype=np.float32)
            # Read only the feet from the existing float16 mesh file, without loading the whole sequence.
            meshes = np.memmap(mesh_dir / "vertices.bin", dtype="<f2", mode="r", shape=(frames, vertices, 3))
            try:
                with torch.inference_mode():
                    for first in range(0, frames, 256):
                        batch = slice(first, min(first + 256, frames))
                        joints[batch] = skeleton({"poses": poses[batch], "shapes": shapes,
                                                  "trans": trans[batch]})["keypoints3d"].numpy()
                        for side, foot in enumerate(feet):
                            heights[batch, side] = meshes[batch, foot, 1].min(axis=1)
            finally:
                del meshes
            if not np.isfinite(joints).all() or not np.isfinite(heights).all():
                raise ValueError("Non-finite preview geometry")

            info = {"version": _VERSION, "parents": parents, "frames": frames,
                    "ground": _estimate_floor(heights, joints[:, [7, 8]], contacts, float(meta["fps"]))}
            pending = stream.with_suffix(".bin.part")
            joints.tofile(pending)
            pending.replace(stream)
            pending_meta = sidecar.with_suffix(".json.part")
            pending_meta.write_text(json.dumps(info, allow_nan=False), encoding="utf-8")
            pending_meta.replace(sidecar)
            return stream, info
