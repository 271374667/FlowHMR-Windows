"""Real-weight GPU component checks; this is not an end-to-end video test."""
import gc
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("TORCH_HOME", str(ROOT / ".cache/torch"))
os.environ.setdefault("FLOWHMR_ATTENTION_BACKEND", "query_batched")

import cv2
import torch
import yaml

torch.set_num_threads(4)

from flowhmr.network.hymotion_mmdit_for_v2m import HunyuanMotionMMDiT
from flowhmr.model_files import flowhmr_paths
from flowhmr.utils.runtime_video_processing import build_human_detector


def main():
    report = {"scope": "GPU components only; licensed assets are required for end-to-end inference"}
    detector = build_human_detector(torch.device("cuda:0"))
    capture = cv2.VideoCapture(str(ROOT / "assets/example/example.mp4"))
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise RuntimeError("Cannot decode the bundled example")
    boxes = detector.run_human_detection(frame, default_to_full_image=False)
    if boxes is None or len(boxes) == 0:
        raise RuntimeError("No real person detections in the bundled example's first frame")
    report["yolox"] = {"status": "passed", "people": len(boxes), "boxes_xyxy_score": boxes.tolist()}
    del detector
    gc.collect()
    torch.cuda.empty_cache()

    ckpt_path, config_path = flowhmr_paths()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model = HunyuanMotionMMDiT(**config["network_module_args"])
    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    state = checkpoint.get("model_state_dict", checkpoint.get("state_dict", checkpoint))
    prefix = "motion_transformer."
    network_state = {key[len(prefix):]: value for key, value in state.items() if key.startswith(prefix)}
    if not network_state:
        raise RuntimeError("No motion_transformer weights found in the official checkpoint")
    model.load_state_dict(network_state, strict=True)
    model.eval().to("cuda:0")
    del checkpoint, state, network_state
    batch, frames = 1, 16
    mask = torch.ones(batch, frames, dtype=torch.bool, device="cuda")
    start = time.perf_counter()
    with torch.inference_mode():
        output = model(
            x=torch.zeros(batch, frames, config["network_module_args"]["input_dim"], device="cuda"),
            ctxt_input={"feature": torch.zeros(batch, frames, 3072, device="cuda"),
                        "camera_R": torch.eye(3, device="cuda").reshape(1, 1, 9).expand(batch, frames, 9)},
            vtxt_input=None, timesteps=torch.tensor([0.5], device="cuda"),
            x_mask_temporal=mask, ctxt_mask_temporal=mask,
        )
        torch.cuda.synchronize()
    if not torch.isfinite(output).all().item():
        raise RuntimeError("Nonfinite FlowHMR network output")
    report["flowhmr_network"] = {"status": "passed", "weight_load": "strict",
                                  "input": "synthetic conditioning", "output_shape": list(output.shape),
                                  "elapsed_seconds": time.perf_counter() - start,
                                  "attention_backend": model.attention_backend}
    spec = importlib.util.spec_from_file_location("flowhmr_web_smoke", ROOT / "tools/web/server.py")
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    app = server.app
    with app.test_client() as client:
        for path in ("/", "/static/style.css", "/static/vendor/three/three.module.min.js"):
            response = client.get(path)
            if response.status_code != 200:
                raise RuntimeError(f"Web asset unavailable: {path}")
    report["web_static_routes"] = "passed (Flask test client; server not started)"
    (ROOT / "logs").mkdir(exist_ok=True)
    text = json.dumps(report, indent=2)
    (ROOT / "logs/component-smoke.json").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
