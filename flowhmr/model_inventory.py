"""Model catalog for the local UI. Checking it only reads file metadata."""

from . import model_files as files
from . import model_sources as sources
from .utils.runtime_hamer import hamer_model_status


def _item(key, name, paths, folder, links, *, required=True, required_paths=None, issue=None):
    paths = tuple(paths)
    missing = files.missing_model_paths(paths)
    blocking = required and bool(missing if required_paths is None else files.missing_model_paths(required_paths))
    status = "missing" if missing else "unavailable" if issue else "ready"
    return {"id": key, "name": name, "status": status, "blocking": blocking, "folder": folder,
            "issue": issue, "links": [{"label": label, "url": url} for label, url in links]}


def model_inventory(device, ckpt=None, config=None):
    hamer_paths, issue = hamer_model_status(device)
    body = tuple(map(files.resolve_model, (files.SMPLH_FILES["neutral"], files.JOINT_REGRESSOR)))
    bundle = tuple(map(files.resolve_model, (files.SMPLH_FILES["female"], files.SMPLH_FILES["male"], *files.MANO_FILES)))
    body_links = [("官方模型包（需登录）", sources.MANO_URL)]
    if not files.file_present(body[1]):
        body_links.append(("关节回归文件", sources.REGRESSOR_URL))
    body_hint = "需要 FlowHMR 使用的 AMASS SMPL-H 数据。" if not files.file_present(body[0]) else None
    if body_hint is None and files.missing_model_paths(bundle):
        body_hint = "将下载的 mano_v1_2 文件夹整包放入 models。"
    return {"directory": str(files.MODEL_ROOT), "items": [
        _item("flowhmr", "FlowHMR", files.flowhmr_paths(ckpt, config), "models/flowhmr_latest",
              [("镜像入口", f"{sources.HF_MIRROR}/{sources.FLOWHMR_REPO}/tree/main/flowhmr_latest"),
               ("官方仓库", f"{sources.HF_OFFICIAL}/{sources.FLOWHMR_REPO}/tree/main/flowhmr_latest")]),
        _item("yolox", "YOLOX-L", (files.resolve_model(files.YOLOX),), "models/yolox",
              [("官方权重", sources.YOLOX_URL)]),
        _item("sam", "SAM 3D Body · DINOv3", files.sam3d_paths(), "models/sam-3d-body-dinov3",
              [("魔搭下载", f"{sources.MODELSCOPE}/models/{sources.SAM_REPO}")]),
        _item("vggt", "VGGT-Omega", (files.resolve_model(files.VGGT),), "models/vggt-omega",
              [("魔搭下载", f"{sources.MODELSCOPE}/models/{sources.VGGT_REPO}")]),
        _item("smplh", "SMPL-H / MANO", (*body, *bundle),
              "models/body_models" if files.missing_model_paths(body) else "models/mano_v1_2", body_links,
              required_paths=body, issue=body_hint),
        _item("hamer", "HaMeR", hamer_paths, "models/hamer",
              [("作者直链", sources.HAMER_ARCHIVE_URL), ("备用下载", sources.HAMER_DEMO_URL),
               ("官方说明", sources.HAMER_PROJECT_URL)],
              required=False, issue=issue),
    ]}
