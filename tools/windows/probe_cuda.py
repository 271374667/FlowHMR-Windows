"""Validate a freshly installed Windows PyTorch environment in a clean process."""

from pathlib import Path
import sys


def main():
    directory = Path(sys.argv[1]).resolve()
    variant = sys.argv[2]
    sys.path.insert(0, str(directory))

    import torch
    import torchvision

    for module, release in ((torch, "2.8.0"), (torchvision, "0.23.0")):
        if not Path(module.__file__).resolve().is_relative_to(directory) or module.__version__ != f"{release}+{variant}":
            raise RuntimeError(f"Unexpected module origin or version: {module.__file__} {module.__version__}")
    expected = f"{variant[2:-1]}.{variant[-1]}"
    if torch.version.cuda != expected or not torch.cuda.is_available():
        raise RuntimeError(f"CUDA {expected} is unavailable")
    device = torch.device("cuda:0")
    x = torch.ones((128, 128), device=device)
    assert (x @ x)[0, 0].item() == 128
    image = torch.ones((1, 3, 32, 32), device=device)
    weight = torch.ones((8, 3, 3, 3), device=device)
    assert torch.nn.functional.conv2d(image, weight)[0, 0, 0, 0].item() == 27
    boxes = torch.tensor([[0., 0., 10., 10.], [1., 1., 9., 9.]], device=device)
    scores = torch.tensor([0.9, 0.8], device=device)
    assert torchvision.ops.nms(boxes, scores, 0.5).tolist() == [0]
    torch.cuda.synchronize()
    print(torch.cuda.get_device_name(0), torch.__version__)


if __name__ == "__main__":
    main()
