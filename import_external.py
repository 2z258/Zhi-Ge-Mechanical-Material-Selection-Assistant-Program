import json
import sqlite3
from pathlib import Path
from data.import_docx import init_db

ROOT = Path(__file__).parent
MATERIAL_COLUMNS = {"tensile_strength_mpa", "yield_strength_mpa", "elastic_modulus_gpa", "density_g_cm3", "temperature_max_c", "fatigue_strength_mpa", "thermal_conductivity_w_mk", "thermal_expansion_um_mk", "electrical_conductivity_iacs", "elongation_percent"}
PROPERTY_COLUMN_MAP = {"hardness_brinell": "hardness"}

def import_external(db_path, data_path=ROOT / "external_properties.json"):
    entries = json.loads(Path(data_path).read_text(encoding="utf-8"))
    conn = sqlite3.connect(db_path); init_db(conn); inserted = 0; updated = 0
    columns = {row[1] for row in conn.execute("pragma table_info(materials)")}
    for column in MATERIAL_COLUMNS - columns:
        conn.execute(f"alter table materials add column {column} REAL")
    for entry in entries:
        grade = entry["material_grade"]
        for key, item in entry["properties"].items():
            conn.execute("""INSERT OR REPLACE INTO external_properties
              (material_grade,property_key,value,unit,condition,source_url,source_title,accessed_at)
              VALUES(?,?,?,?,?,?,?,?)""", (grade, key, item["value"], item["unit"], entry["condition"], entry["source_url"], entry["source_title"], entry["accessed_at"]))
            inserted += 1
            column = key if key in MATERIAL_COLUMNS else PROPERTY_COLUMN_MAP.get(key)
            if column:
                # 中文名称材料（如 40Cr/黄铜/硅胶）在库里 grade 为空、名称存在 name 列，
                # 所以按 grade 或 name 匹配；只在空缺时补写，保留 DOC 已有数据。
                result = conn.execute(
                    f"UPDATE materials SET {column}=? WHERE ({column} IS NULL) AND (grade=? OR name=?)",
                    (item["value"], grade, grade),
                )
                updated += result.rowcount
                # 硬度误把牌号数字当作数值（如 430 不锈钢硬度写成 430、65Mn 写成 65），
                # 用外部真实数据覆盖这类明显的牌号误读，避免评分被错误值带偏。
                if column == "hardness":
                    grade_prefix = "".join(ch for ch in str(grade) if ch.isdigit())
                    if grade_prefix:
                        result = conn.execute(
                            "UPDATE materials SET hardness=? WHERE hardness=? AND (grade=? OR name=?)",
                            (item["value"], str(float(grade_prefix)), grade, grade),
                        )
                        updated += result.rowcount
    conn.commit(); conn.close()
    return {"external_properties": inserted, "material_fields_updated": updated}

if __name__ == "__main__":
    import sys
    print(import_external(sys.argv[1] if len(sys.argv) > 1 else ROOT / "materials.db"))
