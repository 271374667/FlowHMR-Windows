<div align="center">
<a href="https://flowhmr.github.io/"><img src="assets/FlowHMR-logo-tagline.svg" alt="FlowHMR: Physically Plausible Motion Capture from Video" width="880"></a>

<a href="https://huggingface.co/spaces/fafsaf1/FlowHMR"><img src="https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Demo-yellow" alt="Hugging Face Demo Space"></a>
<a href="https://arxiv.org/abs/2610.03691"><img src="https://img.shields.io/badge/arXiv-2610.03691-b31b1b" alt="arXiv"></a>
<a href="https://flowhmr.github.io/"><img src="https://img.shields.io/badge/Project_Page-FlowHMR-green" alt="Project Page"></a>
<a href="https://huggingface.co/fafsaf1/flowhmr-0.46B"><img src="https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model-blue" alt="Hugging Face Model"></a>
</div>

## Windows 桌面版

这是基于 [FlowHMR 上游项目](https://github.com/flowhmr/flowhmr) 的独立 Windows 桌面发行版。原项目的论文、署名和 [许可证](LICENSE) 保留于本仓库。

下载最新版 [FlowHMR-Windows.zip](https://github.com/xiaoerofficial021-collab/FlowHMR-Windows/releases/latest/download/FlowHMR-Windows.zip)，解压后双击 `FlowHMR.exe`。基础包自带 Python、界面和 FBX 导出组件。生成前从右上角 **运行环境** 下载并启用一个 CUDA 版本，再在 **模型** 中下载公开模型、补齐官方 SMPL-H / MANO 文件。

支持多人选取与同步预览、原声播放、手指精修、接触修正和多人 FBX 导出。模型在首次运行生成时才加载。见 [Windows 使用与源码构建说明](docs/windows.md) 和 [模型目录说明](models/README.md)。

## Blender 重定向插件：FlowHMR 2 MMR

**[下载 FlowHMR 2 MMR v1.3.1（ZIP）](https://github.com/xiaoerofficial021-collab/FlowHMR-Windows/releases/latest/download/FlowHMR_2_MMR_v1.3.1.zip)** · Blender 3.6 及以上 · 作者：小二, GPT

把 FlowHMR 导出的 FBX 动作重定向到 MMR 控制骨架。支持在同一场景预览和烘焙多人动作，保留各自的入场时间和相对站位。

在 Blender 的 **编辑 → 偏好设置 → 插件** 中直接安装 ZIP 并启用。回到 3D 视图按 **N**，打开 **FlowHMR 2 MMR** 页签。需要预先用 MMR 生成目标控制骨架，详见 [发布页安装说明](https://github.com/xiaoerofficial021-collab/FlowHMR-Windows/releases/latest)。

## Overview

- 🎉🎉🎉 [2026-10-31] Our [Hugging Face demo](https://huggingface.co/spaces/fafsaf1/FlowHMR) is now live!
  Reconstruct and preview 3D motion in your browser, with NPZ/FBX export.
- 🚀🚀🚀 [2026-10-30] Updated inference acceleration: approximately **10× faster SAM feature extraction**
  (with compile) and **over 5× faster end-to-end inference** (static camera, with compile) on our 300-frame A100 benchmark.
  See the [resource and performance report](docs/performance.md).
  Get started with [CLI inference](docs/inference.md) or the [Web demo](docs/web_demo.md).

We are releasing the full workflow, from data synthesis to training and evaluation, step by step.

- [x] Inference code and checkpoints ([guide](docs/inference.md), [models](#model-zoo))
- [x] Pretraining and GRPO post-training code ([guide](docs/training.md))
- [x] Web demo ([guide](docs/web_demo.md))
- [x] Synthetic data generation code ([guide](data/rendering_data/README.md))
- [x] Wild-4K evaluation clip list ([list](data/wild4k/README.md))
- [x] Hugging Face demo ([Space](https://huggingface.co/spaces/fafsaf1/FlowHMR))

## Model Zoo

| Model | Description | Params | Tracking Success ↑ | Download |
|---|---|:---:|:---:|:---:|
| `flowhmr_base` | Base model | 0.46B | 78.79% | [🤗 HF](https://huggingface.co/fafsaf1/flowhmr-0.46B/tree/main/flowhmr_base) |
| `flowhmr_latest` | `flowhmr_base` + GRPO with PHC+ physics reward **(recommended)** | 0.46B | **82.47%** | [🤗 HF](https://huggingface.co/fafsaf1/flowhmr-0.46B/tree/main/flowhmr_latest) |

*Tracking Success*: the rate at which the PHC+ controller successfully tracks the predicted motion in simulation, measured on Wild-4K.

## Getting Started

Follow the guide for each step, or paste the prompt into your coding agent.

### Installation

[Installation guide](docs/install.md)

FlowHMR supports two setups:

- **V2M**: inference, web demo, and base model training in a single environment
  (tested with Python 3.10 + PyTorch 2.5.1, cu118).
- **Full pipeline**: V2M plus the PHC+ physics simulator for GRPO post-training and
  physics tracking. The simulator runs in a separate Isaac Gym environment (tested with
  Isaac Gym Preview 4, Python 3.8 + PyTorch 1.13, cu117). The two environments share no
  imports and communicate through files on `/dev/shm`.

SMPL-family downloads require license acceptance. Use the ModelScope links in the installation guide for VGGT-Omega and SAM 3D Body.

V2M:

```text
Install FlowHMR from https://github.com/flowhmr/flowhmr following docs/install.md with the V2M setup.
```

Full pipeline:

```text
Install FlowHMR from https://github.com/flowhmr/flowhmr following docs/install.md with the full pipeline setup.
```

### Web Demo

[Web demo guide](docs/web_demo.md)

Upload a video and reconstruct its 3D motion; when several people are detected,
select one or more for reconstruction. Requires the V2M setup.

```text
Launch the FlowHMR web demo following docs/web_demo.md.
```

### Inference

[Inference guide](docs/inference.md)

Reconstruct motion from a video on the command line. The pipeline runs person detection
(YOLOX), camera estimation (VGGT-Omega), body feature extraction (SAM 3D Body), and
FlowHMR, and saves the motion as `.npz` (plus `.fbx` if FBX export is installed).

```text
Run FlowHMR on my video following docs/inference.md.
```

### Data

[Data guide](data/README.md)

- **Training data** is not bundled. Bring your own in the
  [documented format](docs/resources.md#training-inputs), or render synthetic videos
  from SMPL-H motions with the Blender toolkit in [data/rendering_data](data/rendering_data/README.md).
- **Wild-4K** is the 4182-clip in-the-wild evaluation set behind Tracking Success.
  We release the [clip list](data/wild4k/README.md) (clip IDs from Koala-36M-v1),
  not the videos.

### Training

[Training guide](docs/training.md)

Training has two stages: pretraining the base model, then GRPO post-training with a physics reward.
Prepare training data first (see [Data](#data) and [Prepare data](docs/training.md#0-prepare-data)).

**Pretraining** (V2M setup) trains the flow-matching base model, `flowhmr_base`.

```text
Train the FlowHMR base model following docs/training.md.
```

**GRPO post-training** (full pipeline setup) fine-tunes `flowhmr_base` with the PHC+
simulator as the reward: each generated motion is scored by how well the PHC+ controller
tracks it. This produces `flowhmr_latest`.

```text
Run FlowHMR GRPO post-training following docs/training.md.
```

## Acknowledgements

We thank the authors of these projects for releasing their code and models:

- [HY-Motion 1.0](https://github.com/Tencent-Hunyuan/HY-Motion-1.0): MMDiT flow-matching backbone
- [MixGRPO](https://github.com/Tencent-Hunyuan/MixGRPO): GRPO post-training for flow matching
- [PHC](https://github.com/ZhengyiLuo/PerpetualHumanoidControl): PHC+ controller for physics reward and tracking evaluation
- [GVHMR](https://github.com/zju3dv/GVHMR): world-grounded human motion recovery
- [VGGT-Omega](https://github.com/facebookresearch/vggt-omega): camera estimation
- [SAM 3D Body](https://github.com/facebookresearch/sam-3d-body): body features
- [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX): person detection
- [Kimodo](https://github.com/nv-tlabs/kimodo) and [toyxyz_RGBMocap](https://github.com/toyxyz/toyxyz_RGBMocap): motion and contact correction

## Citation

If you find FlowHMR useful in your research, please cite:

```bibtex
@misc{wang2026flowhmr,
      title={FlowHMR: Physically Plausible Motion Capture from Video},
      author={Zhanke Wang and Chengfeng Zhao and Qing Shuai and Jingzhong Lin and Heng Li and Zeyu Ling and Yuxin Wen and Jing Li and Di Kang and Chunchao Guo and Linchao Bao},
      year={2026},
      eprint={2610.03691},
      archivePrefix={arXiv},
      primaryClass={cs.CV},
      url={https://arxiv.org/abs/2610.03691},
}
```

## License

The FlowHMR source code is licensed under the Apache License 2.0. Third-party libraries and components are subject to their respective licenses. For model weights, please refer to the license specified in the [model card](https://huggingface.co/fafsaf1/flowhmr-0.46B).
