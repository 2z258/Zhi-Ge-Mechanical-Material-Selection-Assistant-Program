import shutil
import sqlite3
from datetime import date
from pathlib import Path

def backup_database(db_path, backup_dir=None):
    db_path = Path(db_path); backup_dir = Path(backup_dir or db_path.parent / "backups"); backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"database_backup_before_update_{date.today().isoformat()}.db"
    if not target.exists(): shutil.copy2(db_path, target)
    return target

def preview_parameter_updates(db_path, updates):
    conn = sqlite3.connect(db_path); preview = []
    try:
        for item in updates:
            row = conn.execute(f"select {item['field']} from materials where id=?", (item['material_id'],)).fetchone()
            if row is None: raise ValueError(f"material id not found: {item['material_id']}")
            preview.append({**item, "old_value": row[0], "action": "accept" if row[0] in (None, "") else "review"})
    finally: conn.close()
    return preview

def apply_confirmed_updates(db_path, updates, program_version="material-update"):
    backup = backup_database(db_path); conn = sqlite3.connect(db_path); changed = 0
    try:
        for item in updates:
            if item.get("action") != "accept": continue
            cursor = conn.execute(f"update materials set {item['field']}=? where id=? and ({item['field']} is null or {item['field']}='')", (item["value"], item["material_id"]))
            changed += cursor.rowcount
        conn.commit()
    finally: conn.close()
    return {"backup": str(backup), "updated": changed, "program_version": program_version}
