"""
智哥选型 - 材料导入工具
支持 DOCX 材料文档和 XLS 材料属性表导入到 SQLite 数据库。
纯标准库实现（XLS 读取需系统已安装 Excel，通过 win32com 调用）。
"""

import re, sqlite3, zipfile, shutil
from xml.etree import ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

# ---------------------------------------------------------------------------
# 公共路径
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parent
DEFAULT_DB = DATA_DIR / "materials.db"
BACKUP_DIR = DATA_DIR / "backups"

# ---------------------------------------------------------------------------
# DOCX 导入
# ---------------------------------------------------------------------------
MATERIAL_RE = re.compile(r"^第\s*(1[3-9]|[2-4][0-9]|5[0-2])\s*节\s*(.+)$")
SECTION_VARIANTS: Dict[int, List[Tuple[str, str]]] = {
    16: [("301", "奥氏体不锈钢"), ("303", "奥氏体不锈钢"), ("304", "奥氏体不锈钢"), ("316", "奥氏体不锈钢")],
    17: [("420", "马氏体/铁素体不锈钢"), ("430", "马氏体/铁素体不锈钢"), ("440", "马氏体/铁素体不锈钢")],
    29: [("ASP23", "粉末冶金高速钢"), ("ASP60", "粉末冶金高速钢")],
    52: [("红钢纸", "绝缘复合材料"), ("多晶莫来石纤维", "高温纤维材料")],
}
FIELD_PATTERNS = {
    "temperature_max_c": [r"(?:使用|工作|耐热|可承受|约)\s*(?:温度)?\s*(-?\d+)\s*℃"],
    "density_g_cm3": [r"密度[^0-9]{0,12}(\d+(?:\.\d+)?)"],
    "tensile_strength_mpa": [r"(?:抗拉|拉伸)强度[^0-9]{0,12}(\d+(?:\.\d+)?)", r"强度[^0-9]{0,8}(\d{3,4})\s*MPa"],
    "yield_strength_mpa": [r"屈服强度[^0-9]{0,12}(\d+(?:\.\d+)?)"],
    "elastic_modulus_gpa": [r"弹性模量[^0-9]{0,12}(\d+(?:\.\d+)?)"],
    "hardness": [r"硬度[^0-9]{0,12}([A-ZＡ-Ｚ]{0,3}\s*\d+(?:\.\d+)?)"],
}
TEXT_FIELDS = {
    "toughness": ["韧性", "抗冲击", "冲击"],
    "wear_resistance": ["耐磨", "磨损"],
    "corrosion_resistance": ["耐腐蚀", "耐化学", "耐酸", "耐碱"],
    "machinability": ["加工性", "加工性能", "易加工", "加工较好"],
    "weldability": ["焊接", "可焊", "不适合焊接"],
    "heat_treatment": ["热处理", "淬火", "回火"],
    "cost": ["价格", "成本", "便宜", "昂贵", "高价", "低成本"],
}


def _parse_numeric(text: str, patterns: List[str]) -> Optional[float]:
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return m.group(1).strip()
    return None


def _parse_text_feature(text: str, keywords: List[str]) -> Optional[str]:
    sentences = re.split(r"[。！？；\n]", text)
    hits = [s.strip() for s in sentences if any(k in s for k in keywords)]
    return "；".join(hits[:2]) if hits else None


def extract_records(docx_path: str) -> List[dict]:
    """从 DOCX 提取材料记录列表。"""
    with zipfile.ZipFile(docx_path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for p in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in p.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    starts = [(i, m.group(2).strip(), m.group(1)) for i, p in enumerate(paragraphs) if (m := MATERIAL_RE.match(p))]
    records = []
    for n, (idx, title, section) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(paragraphs)
        body = "\n".join(x for x in paragraphs[idx + 1:end] if x)
        name = title
        grade = ""
        if " " in title:
            first, rest = title.split(" ", 1)
            if re.search(r"[A-Za-z0-9]", first):
                grade, name = first, rest
        if not grade:
            m = re.search(r"\b([A-Z][A-Za-z0-9-]{1,15})\b", body)
            grade = m.group(1) if m else ""
        category = "金属材料" if any(x in title for x in ("铝", "钢", "铸铁", "黄铜", "模具", "轴承")) else "工程塑料/复合材料"
        fields = {k: _parse_numeric(body, v) for k, v in FIELD_PATTERNS.items()}
        fields.update({k: _parse_text_feature(body, v) for k, v in TEXT_FIELDS.items()})
        use_sentences = re.split(r"[。！？；\n]", body)
        use_hits = [s.strip() for s in use_sentences if any(x in s for x in ("适合", "用于", "应用", "用途"))]
        fields["typical_uses"] = "；".join(use_hits)[:600] or None
        variants = SECTION_VARIANTS.get(int(section), [(grade, name)])
        for variant_grade, variant_name in variants:
            records.append({
                "section": int(section), "name": variant_name, "grade": variant_grade,
                "category": category, "raw_text": body, **fields,
            })
    return records


def init_db(conn: sqlite3.Connection) -> None:
    """初始化数据库表结构。"""
    conn.execute("""CREATE TABLE IF NOT EXISTS materials (
      id INTEGER PRIMARY KEY, section INTEGER, name TEXT NOT NULL, grade TEXT, category TEXT,
      tensile_strength_mpa REAL, yield_strength_mpa REAL, elastic_modulus_gpa REAL,
      hardness TEXT, density_g_cm3 REAL, temperature_max_c REAL,
      fatigue_strength_mpa REAL, thermal_conductivity_w_mk REAL,
      thermal_expansion_um_mk REAL, electrical_conductivity_iacs REAL,
      elongation_percent REAL,
      toughness TEXT, wear_resistance TEXT, corrosion_resistance TEXT, machinability TEXT,
      weldability TEXT, heat_treatment TEXT, cost TEXT, typical_uses TEXT, raw_text TEXT NOT NULL,
      source TEXT NOT NULL)""")
    conn.commit()
    conn.execute("""CREATE TABLE IF NOT EXISTS external_properties (
      id INTEGER PRIMARY KEY, material_grade TEXT NOT NULL, property_key TEXT NOT NULL,
      value REAL, unit TEXT, condition TEXT NOT NULL, source_url TEXT NOT NULL,
      source_title TEXT NOT NULL, accessed_at TEXT NOT NULL,
      UNIQUE(material_grade, property_key, condition, source_url))""")
    conn.commit()


def _insert(conn: sqlite3.Connection, record: dict) -> None:
    """按表中实际存在的列插入一条材料记录。"""
    columns = [r[1] for r in conn.execute("PRAGMA table_info(materials)")]
    cols = [c for c in columns if c in record]
    sql = f"INSERT INTO materials({','.join(cols)}) VALUES({','.join('?' * len(cols))})"
    conn.execute(sql, [record[c] for c in cols])


def import_docx(docx_path: str, db_path: str = str(DEFAULT_DB)) -> str:
    """导入 DOCX 材料文档。"""
    records = extract_records(docx_path)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.execute("DELETE FROM materials")
    for r in records:
        _insert(conn, {**r, "source": str(docx_path)})
    conn.commit(); conn.close()
    return f"已导入 {len(records)} 种材料"


# ---------------------------------------------------------------------------
# XLS 导入
# ---------------------------------------------------------------------------
def _parse_name_grade(raw: str) -> Tuple[str, str]:
    """从 'KTH300-06 (GB) ' 拆分 name='KTH300-06 (GB)', grade='KTH300-06'"""
    if not raw:
        return "", ""
    s = str(raw).strip()
    if "(" in s and ")" in s:
        left = s.split("(", 1)[0].strip()
        return s, left or s
    return s, s


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def import_xls(xls_path: str, db_path: str = str(DEFAULT_DB), backup: bool = True) -> Tuple[int, int]:
    """从 XLS 批量导入材料到 SQLite 数据库（需系统已安装 Excel）。
    单位换算：N/m^2 -> MPa(GPa)，kg/m^3 -> g/cm^3，/Kelven -> um/(m·K)。
    """
    import win32com.client

    xls_path = str(xls_path)
    db_path = str(db_path)
    if backup and Path(db_path).exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        bak = BACKUP_DIR / f"materials_backup_before_xls_import_{date.today().isoformat()}.db"
        shutil.copy2(db_path, bak)
        print(f"已备份数据库：{bak}")

    xl = win32com.client.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Open(xls_path)
    ws = wb.Worksheets(1)

    n_rows = ws.UsedRange.Rows.Count
    print(f"Excel 读取：{n_rows} 行，{ws.UsedRange.Columns.Count} 列")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    inserted = 0
    skipped = 0

    for r in range(2, n_rows + 1):
        name_raw = ws.Cells(r, 1).Value
        if not name_raw:
            continue
        name, grade = _parse_name_grade(name_raw)

        e_mod = _num(ws.Cells(r, 2).Value)
        poisson = _num(ws.Cells(r, 3).Value)
        density = _num(ws.Cells(r, 4).Value)
        tensile = _num(ws.Cells(r, 5).Value)
        yield_s = _num(ws.Cells(r, 6).Value)
        fatigue = _num(ws.Cells(r, 7).Value)
        exp_coef = _num(ws.Cells(r, 8).Value)
        heat_cap = _num(ws.Cells(r, 9).Value)
        therm_cond = _num(ws.Cells(r, 10).Value)

        cur.execute("SELECT id FROM materials WHERE grade=? OR name=? LIMIT 1", (grade or name, name))
        if cur.fetchone():
            skipped += 1
            continue

        _insert(conn, {
            "section": 99, "name": name, "grade": grade or None, "category": "金属材料",
            "tensile_strength_mpa": tensile / 1e6 if tensile else None,
            "yield_strength_mpa": yield_s / 1e6 if yield_s else None,
            "elastic_modulus_gpa": e_mod / 1e9 if e_mod else None,
            "density_g_cm3": density / 1000 if density else None,
            "fatigue_strength_mpa": fatigue / 1e6 if fatigue and fatigue > 0 else None,
            "thermal_expansion_um_mk": exp_coef * 1e6 if exp_coef else None,
            "thermal_conductivity_w_mk": therm_cond,
            "raw_text": (f"弹性模量={e_mod} N/m^2, 泊松比={poisson}, 密度={density} kg/m^3, "
                         f"抗拉={tensile} N/m^2, 屈服={yield_s} N/m^2, 疲劳={fatigue} N/m^2, "
                         f"热膨胀={exp_coef}/K, 比热={heat_cap} J/(kg.K), 热导={therm_cond} W/(m.k)"),
            "source": f"XLS 导入：{Path(xls_path).name}",
        })
        inserted += 1

    conn.commit(); conn.close()
    wb.Close(False); xl.Quit()
    print(f"导入完成：新增 {inserted} 条，跳过重复 {skipped} 条")
    return inserted, skipped


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法：")
        print("  python data/import_data.py docx <文件.docx> [数据库.db]")
        print("  python data/import_data.py xls <文件.xls> [数据库.db]")
        sys.exit(1)
    fmt = sys.argv[1].lower()
    file_path = sys.argv[2]
    out_db = sys.argv[3] if len(sys.argv) > 3 else str(DEFAULT_DB)
    if fmt == "docx":
        print(import_docx(file_path, out_db))
    elif fmt == "xls":
        import_xls(file_path, out_db)
    else:
        print("未知格式，支持：docx / xls")
