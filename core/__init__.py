"""
智哥选型 - 核心引擎
整合：材料筛选、评分推荐、强度校核、温度档位、数据库访问
"""

import json, re, sqlite3, math
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "materials.db"
WEIGHTS_PATH = ROOT / "rules" / "weights.json"

METRICS = ["strength","hardness","stiffness","stability","fatigue","wear","toughness","impact","ductility","elasticity","corrosion","lightweight","machinability","weldability","casting","forging","stamping","heat_treatment","surface_treatment","cost","maintenance_cost","high_temp","low_temp","conductivity","thermal_conductivity","thermal_expansion","insulation","magnetic"]

FIELD_MAP = {
    "strength": "tensile_strength_mpa", "hardness": "hardness", "stiffness": "elastic_modulus_gpa",
    "high_temp": "temperature_max_c", "lightweight": "density_g_cm3", "fatigue": "fatigue_strength_mpa",
    "thermal_conductivity": "thermal_conductivity_w_mk", "thermal_expansion": "thermal_expansion_um_mk",
    "conductivity": "electrical_conductivity_iacs", "ductility": "elongation_percent",
}

METRIC_NAMES = {
    "strength":"强度","hardness":"硬度","stiffness":"刚度","stability":"稳定性","fatigue":"疲劳性能",
    "wear":"耐磨性","toughness":"韧性","impact":"抗冲击性能","ductility":"延展性","elasticity":"弹性",
    "corrosion":"耐腐蚀性","lightweight":"轻量化","machinability":"加工性能","weldability":"焊接性能",
    "casting":"铸造性能","forging":"锻造性能","stamping":"冲压性能","heat_treatment":"热处理性能",
    "surface_treatment":"表面处理性能","cost":"成本","maintenance_cost":"维护成本","high_temp":"高温性能",
    "low_temp":"低温性能","conductivity":"导电性能","thermal_conductivity":"导热性能",
    "thermal_expansion":"热膨胀性能","insulation":"绝缘性能","magnetic":"无磁性能",
}

def _num(v):
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)): return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v or ""))
    return float(m.group()) if m else None

def load_weights(path=WEIGHTS_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def effective_weights(req, weights):
    result = dict(weights["base"])
    result.update(weights.get("part_types", {}).get(req.get("part_type",""), {}))
    for load in req.get("loads", []):
        for k, v in weights.get("loads", {}).get(load, {}).items():
            result[k] = min(5, result.get(k, 0) + v)
    for k, v in req.get("weights", {}).items():
        if k in METRICS: result[k] = int(v)
    return {k: v for k, v in result.items() if v > 0}

def _source_values(materials, conn=None):
    """以材料表字段为基础，用已采纳的参数级来源覆盖（若有）。"""
    values = [{f: _num(m.get(f)) for f in FIELD_MAP.values()} for m in materials]
    if conn is not None:
        rows = conn.execute(
            "select material_id, parameter_key, normalized_value "
            "from parameter_sources where status='accepted'"
        ).fetchall()
        accepted = {(mid, key): value for mid, key, value in rows}
        for i, m in enumerate(materials):
            for f in FIELD_MAP.values():
                v = _num(accepted.get((m.get("id"), f)))
                if v is not None:
                    values[i][f] = v
    return {i: {f: v for f, v in vals.items() if v is not None} for i, vals in enumerate(values)}

def hard_filter(materials, requirements):
    kept, rejected = [], []
    temp = requirements.get("temperature")
    temp = None if temp in (None, "", "未填写") else float(temp)
    required = set(requirements.get("must_have", []))
    checks = [
        (("weldability" in required or "焊接" in requirements.get("processes", [])), "weldability", "焊接性能无法满足"),
        (("corrosion" in required), "corrosion_resistance", "耐腐蚀性能无法满足"),
        (("wear" in required), "wear_resistance", "耐磨性能无法满足"),
    ]
    for m in materials:
        reason = None
        if temp is not None and m.get("temperature_max_c") is not None and m["temperature_max_c"] < temp:
            reason = f"最高工作温度 {m['temperature_max_c']}℃ 低于要求 {temp}℃"
        for active, field, msg in checks:
            if active and str(m.get(field) or "").strip() in ("差","较差","不耐腐蚀","不耐磨","不适合"):
                reason = msg
        if "high_temp" in required and temp is None and m.get("temperature_max_c") is not None and m["temperature_max_c"] < 450:
            reason = "最高工作温度低于高温零件初步要求"
        if "lightweight" in required and m.get("density_g_cm3") is not None and m["density_g_cm3"] > 7.8:
            reason = "密度偏高，不满足轻量化初步要求"
        (rejected if reason else kept).append({"material": m, "reason": reason} if reason else m)
    return kept, rejected

def score_materials(materials, req, weights, conn=None):
    w = effective_weights(req, weights)
    vals = _source_values(materials, conn)
    ranges = {}
    for f in FIELD_MAP.values():
        pool = [item[f] for item in vals.values() if f in item]
        if pool:
            ranges[f] = (min(pool), max(pool))
    total_w = sum(w.values())
    ranked = []
    for i, m in enumerate(materials):
        details, missing, ws, ew = [], [], 0.0, 0
        for metric, weight in w.items():
            f = FIELD_MAP.get(metric)
            v = vals[i].get(f) if f else None
            if v is None or f not in ranges:
                missing.append(metric); continue
            lo, hi = ranges[f]
            s = 50.0 if hi == lo else (v - lo) / (hi - lo) * 100
            if metric == "lightweight": s = 100 - s
            s = max(0.0, min(100.0, s))
            details.append({"metric": metric, "raw_value": str(v), "score": round(s,1), "weight": weight, "contribution": round(s*weight,1)})
            ws += s * weight; ew += weight
        perf = ws / total_w if total_w else 0.0
        comp = ew / total_w * 100 if total_w else 0.0
        ranked.append({
            "material": m, "score": round(perf,1), "performance_score": round(perf,1),
            "details": details, "missing": missing, "effective_weight": ew, "total_weight": total_w,
            "completeness": round(comp,1), "confidence": round(comp/100,2),
            "low_confidence": comp < 50,
            "verified_metrics": sorted(vals[i]),
            "data_risk": "参数级来源不足" if missing else "参数级来源完整",
        })
    return sorted(ranked, key=lambda x: (-x["score"], -x["completeness"], x["material"].get("name",""))), w

def explain(result, req=None):
    good = sorted(result["details"], key=lambda x: x["contribution"], reverse=True)
    strengths = "、".join(METRIC_NAMES.get(x["metric"], x["metric"]) for x in good if x["score"] >= 60) or "当前有数据的指标"
    m = result["material"]
    r = f"{m['name']}（{m.get('grade') or '牌号未记录'}）基于已核验参数的匹配评分 {result['score']}/100，数据完整度 {result.get('completeness',0)}%，主要优势为{strengths}。"
    if result["missing"]:
        r += " 数据库缺少：" + "、".join(METRIC_NAMES.get(k,k) for k in result["missing"]) + "，建议在定案前确认。"
    return r

def result_sections(result, req=None):
    details = sorted(result["details"], key=lambda x: x["contribution"], reverse=True)
    return {
        "advantages": [METRIC_NAMES.get(x["metric"], x["metric"]) for x in details[:3]],
        "limitations": [METRIC_NAMES.get(k,k)+"：暂无数据" for k in result["missing"][:3]],
        "reason": explain(result, req),
        "calculation": details,
    }

def temp_tiers(conn):
    if isinstance(conn, (str, Path)):
        c = sqlite3.connect(str(conn))
        vals = sorted(r[0] for r in c.execute("select temperature_max_c from materials where temperature_max_c is not null"))
        c.close()
    else:
        vals = sorted(r[0] for r in conn.execute("select temperature_max_c from materials where temperature_max_c is not null"))
    def band(lo, hi, name):
        items = [v for v in vals if lo <= v <= hi]
        label = f"{name}（≤{int(hi)}℃）" if lo == 0 else f"{name}（{int(lo)+1}~{int(hi)}℃）"
        if items: label += f" · 库内 {int(min(items))}~{int(max(items))}℃"
        return {"label": label, "value": hi}
    return [
        band(0, 100, "低温"), band(100, 250, "常用温度"), band(250, 450, "中温"),
        band(450, 700, "高温"), band(700, max(int(max(vals or [930])), 700), "超高温"),
    ]

def get_materials(db_path=DB_PATH):
    conn = sqlite3.connect(str(db_path)); conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("select * from materials order by section,id")]
    conn.close()
    return rows

# ================= 强度校核 =================
@dataclass
class CheckResult:
    part_type: str
    check_item: str
    calculated_stress: float
    allowable_stress: float
    safety_factor: float
    passed: bool
    formula: str
    note: str

def _sigma_allow(material, sf_req=1.5):
    sy = material.get("yield_strength_mpa"); st = material.get("tensile_strength_mpa")
    if sy and sy > 0: return sy / sf_req
    if st and st > 0: return st / 2.5
    return None

def shaft_torsion(material, torque_nm, diameter_mm, sf_req=1.5, keyway_factor=1.0):
    d = diameter_mm
    if d <= 0: return CheckResult("轴","扭转强度",0,0,0,False,"","直径必须大于0")
    T = torque_nm * 1000.0
    tau = 16.0 * T / (math.pi * d**3) * keyway_factor
    sa = _sigma_allow(material, sf_req)
    if sa is None: return CheckResult("轴","扭转强度",tau,0,0,False,"τ=16T/(πd³)·K","材料缺少强度参数")
    ta = sa * 0.5
    sf = ta / tau if tau > 0 else float("inf")
    return CheckResult("轴","扭转强度",round(tau,2),round(ta,2),round(sf,2),sf>=sf_req,"τ=16T/(πd³)·K","已考虑键槽应力集中" if keyway_factor>1 else "光轴")

def bolt_tension(material, axial_load_n, diameter_mm, sf_req=2.0, root_factor=0.75):
    d = diameter_mm
    if d <= 0: return CheckResult("螺栓","拉伸强度",0,0,0,False,"","直径必须大于0")
    A = math.pi/4 * (d*root_factor)**2
    sig = axial_load_n / A
    sa = _sigma_allow(material, sf_req)
    if sa is None: return CheckResult("螺栓","拉伸强度",sig,0,0,False,"","材料缺少强度参数")
    sf = sa / sig if sig > 0 else float("inf")
    return CheckResult("螺栓","轴向拉伸强度",round(sig,2),round(sa,2),round(sf,2),sf>=sf_req,"σ=F/A_eff, A_eff=π/4·(0.75d)²","未考虑预紧力、弯曲与松动")

def beam_bending(material, load_n, span_mm, section_modulus_mm3, sf_req=1.5):
    if span_mm <= 0 or section_modulus_mm3 <= 0: return CheckResult("梁/连杆","弯曲强度",0,0,0,False,"","跨度或抗弯模量必须大于0")
    M = load_n * span_mm / 4.0
    sig = M / section_modulus_mm3
    sa = _sigma_allow(material, sf_req)
    if sa is None: return CheckResult("梁/连杆","弯曲强度",sig,0,0,False,"","材料缺少强度参数")
    sf = sa / sig if sig > 0 else float("inf")
    return CheckResult("梁/连杆","弯曲强度",round(sig,2),round(sa,2),round(sf,2),sf>=sf_req,"σ=M/W, M=F·L/4","简支梁跨中集中力，未考虑自重与剪切")

def run_checks(material, checks):
    out = []
    for c in checks:
        t = c.get("type"); sf_req = c.get("safety_factor_req", 1.5)
        if t == "shaft_torsion":
            out.append(shaft_torsion(material, c["torque_nm"], c["diameter_mm"], sf_req, c.get("keyway_factor",1.0)))
        elif t == "bolt_tension":
            out.append(bolt_tension(material, c["axial_load_n"], c["diameter_mm"], sf_req, c.get("thread_root_factor",0.75)))
        elif t == "beam_bending":
            out.append(beam_bending(material, c["load_n"], c["span_mm"], c["section_modulus_mm3"], sf_req))
    return out

def recommend(db_path=DB_PATH, weights_path=WEIGHTS_PATH, req=None):
    if req is None: req = {}
    weights = load_weights(weights_path)
    materials = get_materials(db_path)
    kept, rejected = hard_filter(materials, req)
    conn = sqlite3.connect(str(db_path))
    ranked, w = score_materials(kept, req, weights, conn)
    conn.close()
    return ranked[:3], rejected, w
