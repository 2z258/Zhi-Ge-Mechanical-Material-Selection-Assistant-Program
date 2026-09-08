import json
import sys
from pathlib import Path
from data.import_docx import init_db
import sqlite3
from core.material_engine import hard_filter, score_materials, explain, result_sections

ROOT = Path(__file__).parent

def temp_tiers(db):
    """按材料库温度范围分五档，档位值取区间上限用于硬性筛选。"""
    conn = sqlite3.connect(db)
    vals = sorted(r[0] for r in conn.execute(
        "select temperature_max_c from materials where temperature_max_c is not null"))
    conn.close()
    def band(lo, hi, name):
        items = [v for v in vals if lo <= v <= hi]
        label = f"{name}（≤{int(hi)}℃）" if lo == 0 else f"{name}（{int(lo) + 1}~{int(hi)}℃）"
        if items:
            label += f" · 库内 {int(min(items))}~{int(max(items))}℃"
        return {"label": label, "value": hi}
    return [
        band(0, 100, "低温"),
        band(100, 250, "常用温度"),
        band(250, 450, "中温"),
        band(450, 700, "高温"),
        band(700, max(int(max(vals or [930])), 700), "超高温"),
    ]

def materials(db):
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("select * from materials order by section")]
    conn.close(); return rows

def main():
    db = ROOT / "data" / "materials.db"
    if "--materials" in sys.argv:
        print(json.dumps(materials(db), ensure_ascii=True)); return
    if "--temp-tiers" in sys.argv:
        print(json.dumps({"tiers": temp_tiers(db)}, ensure_ascii=True)); return
    req = json.load(sys.stdin)
    kept, rejected = hard_filter(materials(db), req)
    ranked, _ = score_materials(kept, req, ROOT / "rules" / "weights.json", db)
    result = [{"rank": i, "name": x["material"]["name"], "grade": x["material"].get("grade") or "牌号未记录", "score": x["score"], "performance_score": x["performance_score"], "completeness": x["completeness"], "low_confidence": x["low_confidence"], "effective_weight": x["effective_weight"], "total_weight": x["total_weight"], "reason": explain(x, req), "missing": x["missing"], **result_sections(x, req)} for i,x in enumerate(ranked[:3], 1)]
    print(json.dumps({"ranked": result, "rejected": [{"name": x["material"]["name"], "reason": x["reason"]} for x in rejected]}, ensure_ascii=True))

if __name__ == "__main__": main()
