# FlowHMR · Windows

v0.1.3 在模型页分别显示必需的中性 SMPL-H 和可选的 MANO v1.2，标明官网条目、压缩包名、解压目录和缺失文件。Windows 便携包自带 FBX 导出组件。

下载 `FlowHMR-Windows.zip`，完整解压到可写的目录。打开其中的 `FlowHMR` 文件夹，双击 `FlowHMR.exe`。

从旧版升级时，先退出程序，再将新版 `FlowHMR` 文件夹中的内容覆盖到原安装目录。模型、运行环境和任务历史仍保留在原目录。若 v0.1.0 关窗后后台仍在运行，先双击旧目录的 `stop-web.cmd`。

基础包包含 Python 3.10 和界面组件。开始生成前，在右上角 **运行环境** 下载并启用一个版本：CUDA 12.8（推荐）、12.9 或 12.6。软件会校验安装文件并测试 GPU。已有的版本可以切换，模型和任务历史继续使用原目录。RTX 50 系列请选择 12.8 或 12.9。需要 64 位 Windows 10 / 11 和兼容的 NVIDIA 驱动。

点 **模型** 下载公开模型。登录 [MANO 官网下载页](https://mano.is.tue.mpg.de/download.php) 后，按下表直接解压官方压缩包：

| 用途 | 官网下载项 | 解压到 |
| --- | --- | --- |
| **必需**：生成动作 | **Extended SMPL+H model**（AMASS，`smplh.tar.xz`） | `models/body_models/smplh/` |
| **可选**：手指精修、体型切换 | **Models & Code**（`mano_v1_2.zip`） | `models/` |

解压后的中性模型在 `models/body_models/smplh/neutral/model.npz`。更多目录见 `models/README.md`。缺少 WebView2 或 VC++ 运行库时，使用包内的微软安装程序。

`SHA256SUMS.txt` 用于检查下载完整性。源码、补丁和 `FFmpeg-9.0.2-Source.tar.gz` 供开发者使用。第三方组件许可见解包目录的 `THIRD_PARTY_NOTICES.md`。
