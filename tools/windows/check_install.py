"""Check the Windows environment and required local inference assets."""
import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
os.environ.setdefault("TORCH_HOME", str(ROOT / ".cache/torch"))

from flowhmr.model_files import MODEL_ROOT, VGGT, core_model_paths, file_present, missing_model_paths, resolve_model
from flowhmr.runtime_environments import RUNTIME


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-only", action="store_true")
    parser.add_argument("--models-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    result = {"python": sys.version.split()[0], "errors": [], "optional": {}}
    RUNTIME.configure_process()
    result["runtime"] = RUNTIME.summary()
    if not args.models_only and not result["runtime"]["ready"]:
        result["errors"].append("请在 FlowHMR 右上角「运行环境」下载并启用 CUDA。")
    if not args.models_only and result["runtime"]["ready"]:
        for name in ["torch", "torchvision", "numpy", "cv2", "flask", "yolox",
                     "supervision", "flowhmr.pipeline.v2m_inference",
                     "flowhmr.utils.runtime_sam_features", "flowhmr.utils.runtime_vggt_camera"]:
            try:
                importlib.import_module(name)
            except Exception as exc:
                result["errors"].append(f"{name}: {type(exc).__name__}: {exc}")
        try:
            import torch
            import torchvision
            result["torch"] = torch.__version__
            result["cuda_runtime"] = torch.version.cuda
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is unavailable")
            result["gpu"] = torch.cuda.get_device_name(0)
            result["gpu_capability"] = list(torch.cuda.get_device_capability(0))
            x = torch.randn(256, 256, device="cuda")
            assert torch.isfinite(x @ x).all().item()
            boxes = torch.tensor([[0., 0., 10., 10.], [1., 1., 9., 9.]], device="cuda")
            scores = torch.tensor([0.9, 0.8], device="cuda")
            assert torchvision.ops.nms(boxes, scores, 0.5).tolist() == [0]
            torch.cuda.synchronize()
            result["cuda_matmul_and_nms"] = "passed"
        except Exception as exc:
            result["errors"].append(f"GPU: {type(exc).__name__}: {exc}")
        result["ffmpeg"] = shutil.which("ffmpeg")
        if result["ffmpeg"] is None:
            try:
                import imageio_ffmpeg
                result["ffmpeg"] = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception as exc:
                result["errors"].append(f"FFmpeg: {exc}")
        for name in ["fbx", "motion_correction", "rgbmocap_correction"]:
            try:
                importlib.import_module(name)
                result["optional"][name] = "available"
            except Exception as exc:
                result["optional"][name] = f"unavailable: {type(exc).__name__}: {exc}"
        if result["optional"]["rgbmocap_correction"] == "available":
            from flowhmr.utils.runtime_capabilities import native_correction_available
            result["optional"]["contact_correction"] = "available" if native_correction_available() else "native solver unavailable"
    if not args.environment_only:
        from flowhmr.model_inventory import model_inventory

        result["model_directory"] = str(MODEL_ROOT)
        result["missing_models"] = missing_model_paths(core_model_paths())
        result["moving_camera_model"] = "available" if file_present(resolve_model(VGGT)) else "missing (required)"
        result["model_files"] = model_inventory("cuda")["items"]
    result["ready"] = not result["errors"] and not result.get("missing_models")
    report = json.dumps(result, ensure_ascii=False, indent=2)
    print(report)
    if not args.models_only:
        (ROOT / "logs").mkdir(exist_ok=True)
        (ROOT / "logs/install-check.json").write_text(report + "\n", encoding="utf-8")
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
