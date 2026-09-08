import argparse
import subprocess
from pathlib import Path
from data.import_docx import import_docx
from desktop_ui_v2 import launch
from ui import serve

ROOT = Path(__file__).parent
DB = ROOT / "data" / "materials.db"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--import-doc", metavar="DOCX")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--web", action="store_true", help="启动本地 Web 调试界面")
    args = parser.parse_args()
    if args.import_doc:
        print(import_docx(args.import_doc, DB))
    if args.web:
        serve(DB, args.port)
    else:
        try:
            launch(DB, ROOT / "rules" / "weights.json")
        except Exception as error:
            if "init.tcl" in str(error) or "TclError" in type(error).__name__:
                subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "desktop_ui.ps1")], cwd=ROOT)
            else:
                raise
