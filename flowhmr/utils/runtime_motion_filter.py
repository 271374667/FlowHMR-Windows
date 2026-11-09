"""Optional temporal smoothing of translation and rotations before contact correction."""

import math

import numpy as np
import torch
from scipy.ndimage import gaussian_filter1d
from scipy.spatial.transform import Rotation

from flowhmr.core.math.geometry import rot6d_to_rotation_matrix


@torch.no_grad()
def smooth_motion(output, sigma_frames):
    if not math.isfinite(sigma_frames) or sigma_frames < 0:
        raise ValueError("Motion smoothing must be a finite non-negative value")
    rotations = output["rot6d"]
    batch, frames, joints, _ = rotations.shape
    if sigma_frames == 0 or frames < 2:
        return output
    radius = frames - 1 if sigma_frames >= (frames - 1) / 4 else int(sigma_frames * 4 + 0.5)
    if radius == 0:
        return output

    def filtered(values):
        return gaussian_filter1d(values, sigma_frames, axis=1, mode="nearest", radius=radius)

    matrices = rot6d_to_rotation_matrix(rotations).detach().cpu().numpy().reshape(-1, 3, 3)
    quat = Rotation.from_matrix(matrices).as_quat().reshape(batch, frames, joints, 4)
    # q and -q describe the same pose. Keep neighboring quaternion signs aligned
    # so rotations around 180 degrees do not cancel when they are averaged.
    signs = np.where(np.sum(quat[:, 1:] * quat[:, :-1], axis=-1, keepdims=True) < 0, -1.0, 1.0)
    quat[:, 1:] *= np.cumprod(signs, axis=1)
    averaged = filtered(quat)
    averaged = np.where(np.linalg.norm(averaged, axis=-1, keepdims=True) > 1e-8, averaged, quat)
    smoothed = Rotation.from_quat(averaged.reshape(-1, 4)).as_matrix()

    result = dict(output)
    result["rot6d"] = torch.as_tensor(smoothed[:, :, :2].reshape(rotations.shape), dtype=rotations.dtype, device=rotations.device)
    translation = output["trans"]
    result["trans"] = torch.as_tensor(filtered(translation.detach().float().cpu().numpy()),
                                      dtype=translation.dtype, device=translation.device)
    result["root_rot6d"] = result["rot6d"][:, :, 0]
    result["body_rot6d"] = result["rot6d"][:, :, 1:]
    for key in ("local_joints_positions", "smooth_root_pos", "pelvis_world"):
        result.pop(key, None)
    return result
