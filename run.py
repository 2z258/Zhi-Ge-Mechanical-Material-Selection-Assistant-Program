r"""
智哥选型 - 程序入口
用法：
  python run.py                  启动桌面界面
  python run.py --web            启动本地 Web 调试界面 (http://127.0.0.1:8765)
  python run.py --web --port 9000
  python run.py --import-doc "C:\路径\材料文档.docx"   导入 DOCX 材料库
  python run.py --import-xls "C:\路径\500种材料属性表.xls"   导入 XLS 材料库
"""

import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="机械材料智能选型辅助系统")
    parser.add_argument("--import-doc", metavar="DOCX", help="导入 DOCX 材料文档")
    parser.add_argument("--import-xls", metavar="XLS", help="导入 XLS 材料属性表")
    parser.add_argument("--web", action="store_true", help="启动本地 Web 调试界面")
    parser.add_argument("--port", type=int, default=8765, help="Web 端口")
    args = parser.parse_args()

    if args.import_doc:
        from data.import_data import import_docx
        db = ROOT / "data" / "materials.db"
        print(import_docx(args.import_doc, str(db)))
        sys.exit(0)

    if args.import_xls:
        from data.import_data import import_xls
        import_xls(args.import_xls, str(ROOT / "data" / "materials.db"))
        sys.exit(0)

    if args.web:
        from web import serve
        serve(str(ROOT / "data" / "materials.db"), str(ROOT / "rules" / "weights.json"), args.port)
        sys.exit(0)

    # 默认启动桌面
    from desktop import App
    App().mainloop()
