# FlowHMR 模型文件

打开 FlowHMR 右上角的 **模型**，点 **下载缺失模型**，公开模型会下载、校验并放到对应目录。停止下载后可继续。缺项旁也有手动链接；手动放好文件后点 **刷新**。桌面推理使用本目录的模型，开始生成时才加载。

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
├── mano_v1_2/          ← 官方下载的整个文件夹，保留原目录结构
└── hamer/
    ├── hamer.ckpt
    ├── model_config.yaml
    └── mano_mean_params.npz
```

`download-models.cmd` 下载公共文件。其中 [SAM 3D Body DINOv3](https://www.modelscope.cn/models/facebook/sam-3d-body-dinov3) 和 [VGGT-Omega](https://www.modelscope.cn/models/facebook/VGGT-Omega) 从魔搭下载并校验 SHA-256，无需 Hugging Face 授权。两者都须安装；固定机位跳过 VGGT 推理。

从 [MANO 官网](https://mano.is.tue.mpg.de/download.php) 登录下载 `mano_v1_2` 后，整包放入 `models`。FlowHMR 推理使用的 AMASS 中性 SMPL-H 是同站另外一项下载（`smplh_amass_neutral`），其中的 `neutral/model.npz` 放在上图位置。程序直接读取官方包的身体和手部文件。

HaMeR 支持自动下载和安装。也可从 [作者的大学直链](https://www.cs.utexas.edu/~pavlakos/hamer/data/hamer_demo_data.tar.gz) 下载 `hamer_demo_data.tar.gz`，在项目目录运行：

```powershell
.\runtime\python.exe tools\windows\install_hamer.py --weights-archive <官方压缩包路径>
```

源码环境使用 `.\.venv\Scripts\python.exe`。安装器只提取用于精修的三个模型文件，并安装固定版本的官方推理代码。手指精修使用项目的 Python 环境和 NVIDIA GPU。
