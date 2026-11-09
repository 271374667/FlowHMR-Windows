"""Optional SMPL-H skin templates fitted to the job's original bind skeleton."""

from pathlib import Path

import numpy as np

from ...model_files import SMPLH_FILES, file_present, resolve_model
from .licensed_data import read_registered_arrays


def available_variants():
    return [name for name, relative in SMPLH_FILES.items() if file_present(resolve_model(relative))]


def model_path(name):
    if name not in SMPLH_FILES:
        raise ValueError("请选择中性、女性或男性 SMPL-H 体型。")
    path = resolve_model(SMPLH_FILES[name])
    if not file_present(path):
        raise ValueError("本机未安装所选 SMPL-H 体型。")
    return path


def fitted_skin(variant_path, neutral_vertices, neutral_joints, weights, faces, parents):
    """Fit the official mean template to the captured skeleton without using its betas."""
    keys = ("v_template", "weights", "J_regressor", "kintree_table", "f")
    if Path(variant_path).suffix == ".pkl":
        variant = read_registered_arrays(variant_path, keys)
    else:
        with np.load(variant_path, allow_pickle=False) as source:
            variant = {key: source[key] for key in keys}
    vertices = np.asarray(variant["v_template"], dtype=np.float32)
    variant_weights = np.asarray(variant["weights"], dtype=np.float32)
    regressor = np.asarray(variant["J_regressor"], dtype=np.float32)
    tree = np.asarray(variant["kintree_table"][0], dtype=np.int64)
    if (vertices.shape != neutral_vertices.shape or variant_weights.shape != weights.shape
            or regressor.shape != (len(parents), len(vertices))
            or not np.array_equal(tree[1:], parents[1:])
            or not np.array_equal(variant["f"], faces)):
        raise ValueError("所选体型与本机 AMASS SMPL-H 骨架不兼容。")

    joints = regressor @ vertices
    fitted = vertices + variant_weights @ (neutral_joints - joints)
    # Keep the original foot surfaces around the joints used for ground contact.
    foot = weights[:, [7, 8, 10, 11]].sum(axis=1)
    blend = np.clip(foot / .6, 0., 1.)[:, None]
    fitted = np.where(blend >= 1., neutral_vertices, fitted + (neutral_vertices - fitted) * blend)
    if not np.isfinite(fitted).all():
        raise ValueError("所选 SMPL-H 体型包含无效顶点。")
    return fitted


def write_preview_vertices(motion_path, variant_path, stream):
    """Write the same float16 vertex stream as the neutral preview, on CPU."""
    import torch

    from .lbs_function import batch_rigid_transform, batch_rodrigues

    with np.load(motion_path, allow_pickle=False) as motion:
        poses = torch.from_numpy(motion["poses"].astype(np.float32)).reshape(-1, 52, 3)
        trans = torch.from_numpy(motion["trans"].astype(np.float32))
        betas = motion["betas"].astype(np.float32).reshape(1, -1)[0]
    with np.load(model_path("neutral"), allow_pickle=False) as neutral:
        shape = np.asarray(neutral["shapedirs"], dtype=np.float32)
        betas = betas[:shape.shape[-1]]
        vertices = np.asarray(neutral["v_template"], dtype=np.float32) + shape[..., :len(betas)] @ betas
        joints = np.asarray(neutral["J_regressor"], dtype=np.float32) @ vertices
        weights = np.asarray(neutral["weights"], dtype=np.float32)
        parents = np.asarray(neutral["kintree_table"][0], dtype=np.int64).copy()
        parents[0] = -1
        surface = fitted_skin(variant_path, vertices, joints, weights, neutral["f"], parents)

    weights = torch.from_numpy(weights)
    parents = torch.from_numpy(parents)
    joints = torch.from_numpy(joints)[None]
    points = torch.from_numpy(surface)
    points = torch.cat((points, torch.ones((len(points), 1), dtype=points.dtype)), dim=-1)
    with torch.inference_mode():
        for first in range(0, len(poses), 32):
            batch = poses[first:first + 32]
            matrices = batch_rodrigues(batch)
            _, transforms = batch_rigid_transform(matrices, joints.expand(len(batch), -1, -1), parents)
            skin = (weights @ transforms.flatten(2)).view(len(batch), len(points), 4, 4)
            vertices = (skin @ points[..., None])[..., :3, 0] + trans[first:first + len(batch), None]
            vertices.numpy().astype("<f2").tofile(stream)
