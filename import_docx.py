import re, sqlite3, json, zipfile
from xml.etree import ElementTree as ET
from pathlib import Path

MATERIAL_RE = re.compile(r"^第\s*(1[3-9]|[2-4][0-9]|5[0-2])\s*节\s*(.+)$")
SECTION_VARIANTS = {
    16: [("301", "奥氏体不锈钢"), ("303", "奥氏体不锈钢"), ("304", "奥氏体不锈钢"), ("316", "奥氏体不锈钢")],
    17: [("420", "马氏体/铁素体不锈钢"), ("430", "马氏体/铁素体不锈钢"), ("440", "马氏体/铁素体不锈钢")],
    29: [("ASP23", "粉末冶金高速钢"), ("ASP60", "粉末冶金高速钢")],
    52: [("红钢纸", "绝缘复合材料"), ("多晶莫来石纤维", "高温纤维材料")],
}
FIELD_PATTERNS = {
    "temperature_max_c": [(r"(?:使用|工作|耐热|可承受|约)\s*(?:温度)?\s*(-?\d+)\s*℃", "max")],
    "density_g_cm3": [(r"密度[^0-9]{0,12}(\d+(?:\.\d+)?)", "value")],
    "tensile_strength_mpa": [(r"(?:抗拉|拉伸)强度[^0-9]{0,12}(\d+(?:\.\d+)?)", "value"), (r"强度[^0-9]{0,8}(\d{3,4})\s*MPa", "value")],
    "yield_strength_mpa": [(r"屈服强度[^0-9]{0,12}(\d+(?:\.\d+)?)", "value")],
    "elastic_modulus_gpa": [(r"弹性模量[^0-9]{0,12}(\d+(?:\.\d+)?)", "value")],
    "hardness": [(r"硬度[^0-9]{0,12}([A-ZＡ-Ｚ]{0,3}\s*\d+(?:\.\d+)?)", "value")],
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

def _parse_numeric(text, patterns):
    for pattern, _ in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            try: return float(m.group(1))
            except ValueError: return m.group(1).strip()
    return None

def _parse_text_feature(text, keywords):
    sentences = re.split(r"[。！？；\n]", text)
    hits = [s.strip() for s in sentences if any(k in s for k in keywords)]
    return "；".join(hits[:2]) if hits else None

def extract_records(docx_path):
    with zipfile.ZipFile(docx_path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for p in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in p.findall(".//w:t", ns)).strip()
        if text: paragraphs.append(text)
    starts = [(i, m.group(2).strip(), m.group(1)) for i,p in enumerate(paragraphs) if (m := MATERIAL_RE.match(p))]
    records = []
    for n, (idx, title, section) in enumerate(starts):
        end = starts[n+1][0] if n + 1 < len(starts) else len(paragraphs)
        body = "\n".join(x for x in paragraphs[idx+1:end] if x)
        name = title; grade = ""
        if " " in title:
            first, rest = title.split(" ", 1)
            if re.search(r"[A-Za-z0-9]", first): grade, name = first, rest
        if not grade:
            m = re.search(r"\b([A-Z][A-Za-z0-9-]{1,15})\b", body)
            grade = m.group(1) if m else ""
        category = "金属材料" if any(x in title for x in ("铝", "钢", "铸铁", "黄铜", "模具", "轴承")) else "工程塑料/复合材料"
        fields = {k: _parse_numeric(body, v) for k,v in FIELD_PATTERNS.items()}
        fields.update({k: _parse_text_feature(body, v) for k,v in TEXT_FIELDS.items()})
        use_sentences = re.split(r"[。！？；\n]", body)
        use_hits = [s.strip() for s in use_sentences if any(x in s for x in ("适合", "用于", "应用", "用途"))]
        fields["typical_uses"] = "；".join(use_hits)[:600] or None
        variants = SECTION_VARIANTS.get(int(section), [(grade, name)])
        for variant_grade, variant_name in variants:
            records.append({"section": int(section), "name": variant_name, "grade": variant_grade, "category": category, "raw_text": body, **fields})
    return records

def init_db(conn):
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

def import_docx(docx_path, db_path):
    records = extract_records(docx_path)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path); init_db(conn)
    conn.execute("DELETE FROM materials")
    for r in records:
        conn.execute("""INSERT INTO materials(section,name,grade,category,tensile_strength_mpa,yield_strength_mpa,
          elastic_modulus_gpa,hardness,density_g_cm3,temperature_max_c,toughness,wear_resistance,
          corrosion_resistance,machinability,weldability,heat_treatment,cost,typical_uses,raw_text,source)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (r["section"],r["name"],r["grade"],r["category"],r["tensile_strength_mpa"],r["yield_strength_mpa"],r["elastic_modulus_gpa"],r["hardness"],r["density_g_cm3"],r["temperature_max_c"],r["toughness"],r["wear_resistance"],r["corrosion_resistance"],r["machinability"],r["weldability"],r["heat_treatment"],r["cost"],r["typical_uses"],r["raw_text"],str(docx_path)))
    conn.commit(); conn.close()
    return f"已导入 {len(records)} 种材料"

if __name__ == "__main__":
    import sys
    print(import_docx(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else "data/materials.db"))
