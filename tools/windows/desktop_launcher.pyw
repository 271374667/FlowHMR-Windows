"""Start the desktop with CPython's GUI executable and FlowHMR's private packages."""

import ctypes
from pathlib import Path
import runpy
import site
import traceback


ROOT = Path(__file__).resolve().parents[2]
try:
    if not (ROOT / "runtime/pythonw.exe").is_file():
        site.addsitedir(str(ROOT / ".venv/Lib/site-packages"))
    runpy.run_path(str(ROOT / "tools/windows/desktop.py"), run_name="__main__")
except Exception:
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    with (logs / "desktop.log").open("a", encoding="utf-8") as log:
        traceback.print_exc(file=log)
    ctypes.windll.user32.MessageBoxW(None, "启动失败，请查看 logs/desktop.log。", "FlowHMR", 0x10)
