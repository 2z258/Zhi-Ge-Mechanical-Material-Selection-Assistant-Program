import shutil
import sqlite3
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "materials.db"
BACKUP_DIR = ROOT / "data" / "backups"
TODAY = date.today().isoformat()

UPDATES = [
    {
        "material_id": 23,
        "grade": "ASP60",
        "field": "wear_resistance",
        "value": "高；官方资料明确用于需要高耐磨性和热硬性的工况",
        "original_text": "ASP® 2060 is a very high alloyed grade for applications requiring both hot hardness and wear resistance.",
        "source_name": "Erasteel 官方 ASP® 2060 产品页",
        "source_url": "https://www.erasteel.com/products/asp-2060/",
        "source_type": "manufacturer_official",
        "standard": None,
        "condition": "ASP® 2060；具体性能随热处理和使用状态变化",
        "confidence": "高",
    },
    {
        "material_id": 23,
        "grade": "ASP60",
        "field": "toughness",
        "value": "较高；官方产品资料宣称相较 HSS Co8 具有更好的硬度和韧性",
        "original_text": "Better Hardness, Better Toughness than HSS Co8",
        "source_name": "Fuji KKK 官方 SUPER-ASP60 产品资料",
        "source_url": "https://www.fuji-bc.com/tool/tool10/SUPER-ASP60.pdf",
        "source_type": "manufacturer_official",
        "standard": None,
        "condition": "SUPER-ASP60 刀具产品资料；不等同于通用块材保证值",
        "confidence": "中",
    },
]


def update():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"database_backup_before_authoritative_update_{TODAY}.db"
    if not backup.exists():
        shutil.copy2(DB, backup)
    conn = sqlite3.connect(DB)
    updated = 0
    try:
        for item in UPDATES:
            old = conn.execute(f"select {item['field']} from materials where id=?", (item["material_id"],)).fetchone()
            if not old:
                raise RuntimeError(f"material id not found: {item['material_id']}")
            old_value = old[0]
            if old_value in (None, ""):
                conn.execute(f"update materials set {item['field']}=? where id=?", (item["value"], item["material_id"]))
                updated += 1
            source_status = "accepted" if old_value in (None, "") else "reference_only"
            existing_source = conn.execute(
                "select id from parameter_sources where material_id=? and parameter_key=? and source_url=?",
                (item["material_id"], item["field"], item["source_url"]),
            ).fetchone()
            if existing_source:
                continue
            conn.execute(
                """insert into parameter_sources
                (material_id,parameter_key,value,min_value,max_value,original_value,original_unit,
                 normalized_value,normalized_unit,source_name,source_url,source_type,standard,
                 material_condition,data_date,retrieved_date,confidence,original_text,status)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item["material_id"], item["field"], None, None, None, item["value"], None,
                 None, None, item["source_name"], item["source_url"], item["source_type"],
                 item["standard"], item["condition"], TODAY, TODAY, item["confidence"],
                 item["original_text"], source_status),
            )
            if old_value in (None, ""):
                conn.execute(
                    """insert into material_update_log
                    (update_time,material_id,parameter_key,old_value,new_value,unit,source_url,standard,
                     material_condition,action,program_version)
                    values(?,?,?,?,?,?,?,?,?,?,?)""",
                    (TODAY, item["material_id"], item["field"], old_value, item["value"], None,
                     item["source_url"], item["standard"], item["condition"],
                     "accepted", "authoritative-update-2026-09-08"),
                )
        conn.execute(
            """insert into material_update_runs
            (run_time,backup_path,status,updated_count,reference_only_count,failed_count)
            values(?,?,?,?,?,?)""",
            (TODAY, str(backup), "completed", updated, len(UPDATES) - updated, 0),
        )
        conn.commit()
    finally:
        conn.close()
    return updated


if __name__ == "__main__":
    print(f"updated_fields={update()}")
