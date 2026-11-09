# FlowHMR · Windows

下载 `FlowHMR-Windows.zip`，完整解压到可写的目录。打开其中的 `FlowHMR` 文件夹，双击 `FlowHMR.exe`。

基础包包含 Python 3.10 和界面组件。开始生成前，在右上角 **运行环境** 下载并启用一个版本：CUDA 12.8（推荐）、12.9 或 12.6。软件会校验安装文件并测试 GPU。已有的版本可以切换，模型和任务历史继续使用原目录。RTX 50 系列请选择 12.8 或 12.9。需要 64 位 Windows 10 / 11 和兼容的 NVIDIA 驱动。

点 **模型** 下载公开模型，并按 `models/README.md` 放入官方 SMPL-H / MANO 文件。FBX 导出组件在首次启动后自动尝试下载。缺少 WebView2 或 VC++ 运行库时，使用包内的微软安装程序。

`SHA256SUMS.txt` 用于检查下载完整性。源码、补丁和 `FFmpeg-9.0.2-Source.tar.gz` 供开发者使用。第三方组件许可见解包目录的 `THIRD_PARTY_NOTICES.md`。
