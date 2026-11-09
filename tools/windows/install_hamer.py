"""Install standalone HaMeR inference code and optionally the official demo archive."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flowhmr.hamer_setup import install_code, install_weights, runtime_installed
from flowhmr.model_downloads import download_asset
from flowhmr.model_sources import HAMER_CODE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", type=Path)
    parser.add_argument("--weights-archive", type=Path)
    args = parser.parse_args()
    if args.source_archive:
        install_code(args.source_archive)
    elif not runtime_installed():
        source = download_asset(HAMER_CODE, lambda *_: None, lambda: None)
        install_code(source)
        source.unlink(missing_ok=True)
    if args.weights_archive:
        install_weights(args.weights_archive, progress=lambda _, name, size, total:
                        print(f"Extracted: {name}", flush=True) if size == total else None)
    print("HaMeR inference code is ready.", flush=True)


if __name__ == "__main__":
    main()
