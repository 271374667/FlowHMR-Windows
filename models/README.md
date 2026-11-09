# FlowHMR 模型文件

打开 FlowHMR 右上角的 **模型**，点 **下载缺失模型**，公开模型会下载、校验并放到对应目录。停止下载后可继续。缺项旁也有手动链接；手动放好文件后点 **刷新**。桌面推理使用本目录的模型，开始生成时才加载。

登录 [MANO 官网下载页](https://mano.is.tue.mpg.de/download.php)，按下表选择条目，把压缩包直接解压到指定目录并保留包内结构。

| 用途 | 官网条目和压缩包 | 解压到 | 解压后的位置 |
| --- | --- | --- | --- |
| **必需**：生成动作 | **Extended SMPL+H model**（用于 AMASS 数据集），`smplh.tar.xz` | `models/body_models/smplh/` | `models/body_models/smplh/neutral/model.npz` |
| **可选**：手指精修、体型切换 | **Models & Code**（模型和代码），`mano_v1_2.zip` | `models/` | `models/mano_v1_2/models/` 内的 `.pkl` |

这两个需登录的包中，基础动捕只需要 `smplh.tar.xz`。`mano_v1_2.zip` 不含中性 `model.npz`。`models/body_models/smpl_neutral_J_regressor.pt` 是公开文件，由软件的自动下载提供。

```text
models/
├── flowhmr_latest/
│   ├── flowhmr_latest.ckpt
│   └── config.yml
├── yolox/
│   └── yolox_l.pth
├── sam-3d-body-dinov3/
│   ├── model.ckpt
│   ├── model_config.yaml
│   └── assets/mhr_model.pt
├── vggt-omega/
│   └── vggt_omega_1b_512.pt
├── body_models/
│   ├── smpl_neutral_J_regressor.pt
│   └── smplh/neutral/model.npz
├── mano_v1_2/models/  ← 可选，保留官方压缩包的目录结构
└── hamer/
    ├── hamer.ckpt
    ├── model_config.yaml
    └── mano_mean_params.npz
```

`download-models.cmd` 下载公共文件。其中 [SAM 3D Body DINOv3](https://www.modelscope.cn/models/facebook/sam-3d-body-dinov3) 和 [VGGT-Omega](https://www.modelscope.cn/models/facebook/VGGT-Omega) 从魔搭下载并校验 SHA-256，无需 Hugging Face 授权。两者都须安装；固定机位跳过 VGGT 推理。

手指精修还需要 HaMeR。软件可从[作者提供的 `hamer_demo_data.tar.gz`](https://www.cs.utexas.edu/~pavlakos/hamer/data/hamer_demo_data.tar.gz) 自动下载并安装所需文件。手指精修使用项目的 Python 环境和 NVIDIA GPU。
