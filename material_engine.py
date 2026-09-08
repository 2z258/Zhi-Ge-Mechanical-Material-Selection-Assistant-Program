import json
import re
import sqlite3
from pathlib import Path

METRICS = ["strength", "hardness", "stiffness", "stability", "fatigue", "wear", "toughness", "impact", "ductility", "elasticity", "corrosion", "lightweight", "machinability", "weldability", "casting", "forging", "stamping", "heat_treatment", "surface_treatment", "cost", "maintenance_cost", "high_temp", "low_temp", "conductivity", "thermal_conductivity", "thermal_expansion", "insulation", "magnetic"]
FIELD_MAP = {"strength": "tensile_strength_mpa", "hardness": "hardness", "stiffness": "elastic_modulus_gpa", "high_temp": "temperature_max_c", "lightweight": "density_g_cm3", "fatigue": "fatigue_strength_mpa", "thermal_conductivity": "thermal_conductivity_w_mk", "thermal_expansion": "thermal_expansion_um_mk", "conductivity": "electrical_conductivity_iacs", "ductility": "elongation_percent"}
SOURCE_FIELD_MAP = {"hardness": "hardness_brinell"}
METRIC_NAMES = {"strength":"强度", "hardness":"硬度", "stiffness":"刚度", "stability":"稳定性", "fatigue":"疲劳性能", "wear":"耐磨性", "toughness":"韧性", "impact":"抗冲击性能", "ductility":"延展性", "elasticity":"弹性", "corrosion":"耐腐蚀性", "lightweight":"轻量化", "machinability":"加工性能", "weldability":"焊接性能", "casting":"铸造性能", "forging":"锻造性能", "stamping":"冲压性能", "heat_treatment":"热处理性能", "surface_treatment":"表面处理性能", "cost":"成本", "maintenance_cost":"维护成本", "high_temp":"高温性能", "low_temp":"低温性能", "conductivity":"导电性能", "thermal_conductivity":"导热性能", "thermal_expansion":"热膨胀性能", "insulation":"绝缘性能", "magnetic":"无磁性能"}

def _number(value):
    if isinstance(value, bool): return None
    if isinstance(value, (int, float)): return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    return float(match.group()) if match else None

def effective_weights(req, rules_path):
    rules = json.loads(Path(rules_path).read_text(encoding="utf-8")); result = dict(rules["base"])
    result.update(rules.get("part_types", {}).get(req.get("part_type", ""), {}))
    for load in req.get("loads", []):
        for key, value in rules.get("loads", {}).get(load, {}).items(): result[key] = min(5, result.get(key, 0) + value)
    for key, value in req.get("weights", {}).items():
        if key in METRICS: result[key] = int(value)
    return {key: value for key, value in result.items() if value > 0}

def _source_values(materials, source_db):
    if source_db is None:
        return {i: {field: _number(material.get(field)) for field in FIELD_MAP.values() if _number(material.get(field)) is not None} for i, material in enumerate(materials)}
    conn = sqlite3.connect(source_db) if isinstance(source_db, (str, bytes, Path)) else source_db
    rows = conn.execute("select material_id,parameter_key,normalized_value from parameter_sources where status='accepted'").fetchall()
    if isinstance(source_db, (str, bytes, Path)): conn.close()
    indexed = {(material_id, key): value for material_id, key, value in rows}; result = {}
    for i, material in enumerate(materials):
        values = {}
        for field in FIELD_MAP.values():
            value = _number(indexed.get((material.get("id"), SOURCE_FIELD_MAP.get(field, field))))
            if value is not None: values[field] = value
        result[i] = values
    return result

def hard_filter(materials, requirements):
    kept, rejected = [], []; temp = requirements.get("temperature")
    temp = None if temp in (None, "", "未填写") else float(temp); required = set(requirements.get("must_have", []))
    checks = [("焊接" in requirements.get("processes", []) or "weldability" in required or requirements.get("weldability_required"), "weldability", "焊接性能无法满足当前制造要求"), ("corrosion" in required, "corrosion_resistance", "耐腐蚀性能无法满足当前制造要求"), ("wear" in required, "wear_resistance", "耐磨性能无法满足当前制造要求")]
    for material in materials:
        reason = None
        if temp is not None and material.get("temperature_max_c") is not None and material["temperature_max_c"] < temp: reason = f"最高工作温度 {material['temperature_max_c']}℃ 低于要求 {temp}℃"
        for active, field, message in checks:
            if active and str(material.get(field) or "").strip() in ("差", "较差", "不耐腐蚀", "不耐磨", "不适合"): reason = message
        if "high_temp" in required and temp is None and material.get("temperature_max_c") is not None and material["temperature_max_c"] < 450: reason = "已知最高工作温度低于高温零件的初步要求"
        if "lightweight" in required and material.get("density_g_cm3") is not None and material["density_g_cm3"] > 7.8: reason = "已知密度偏高，不满足轻量化的初步要求"
        (rejected if reason else kept).append({"material": material, "reason": reason} if reason else material)
    return kept, rejected

def score_materials(materials, req, rules_path, source_db=None):
    weights = effective_weights(req, rules_path); values = _source_values(materials, source_db); pools = {field: [item[field] for item in values.values() if field in item] for field in FIELD_MAP.values()}; total_weight = sum(weights.values()); ranked = []
    for index, material in enumerate(materials):
        details, missing, weighted_sum, effective_weight = [], [], 0.0, 0
        for metric, weight in weights.items():
            field = FIELD_MAP.get(metric); value = values[index].get(field) if field else None
            if value is None: missing.append(metric); continue
            low, high = min(pools[field]), max(pools[field]); score = 50.0 if high == low else (value - low) / (high - low) * 100
            if metric == "lightweight": score = 100 - score
            score = max(0.0, min(100.0, score)); contribution = score * weight
            details.append({"metric": metric, "raw_value": str(value), "score": round(score, 1), "weight": weight, "contribution": round(contribution, 1)}); weighted_sum += contribution; effective_weight += weight
        performance = weighted_sum / total_weight if total_weight else 0.0; completeness = effective_weight / total_weight * 100 if total_weight else 0.0
        ranked.append({"material": material, "score": round(performance, 1), "performance_score": round(performance, 1), "details": details, "missing": missing, "effective_weight": effective_weight, "total_weight": total_weight, "completeness": round(completeness, 1), "confidence": round(completeness / 100, 2), "low_confidence": completeness < 50, "verified_metrics": sorted(values[index]), "data_risk": "参数级来源不足，不能据此确认" if missing else "参数级来源完整"})
    return sorted(ranked, key=lambda item: (-item["score"], -item["completeness"], item["material"].get("name", ""))), weights

def explain(result, req=None):
    good = sorted(result["details"], key=lambda item: item["contribution"], reverse=True); strengths = "、".join(METRIC_NAMES.get(item["metric"], item["metric"]) for item in good if item["score"] >= 60) or "当前有数据的指标"; material = result["material"]
    reason = f"{material['name']}（{material.get('grade') or '牌号未记录'}）基于已核验参数的匹配评分 {result['score']}/100，数据完整度 {result.get('completeness', 0)}%，主要优势为{strengths}。"
    if result["missing"]: reason += " 数据库缺少：" + "、".join(METRIC_NAMES.get(key, key) for key in result["missing"]) + "，建议在定案前确认。"
    return reason

def result_sections(result, req=None):
    details = sorted(result["details"], key=lambda item: item["contribution"], reverse=True)
    return {"advantages": [METRIC_NAMES.get(item["metric"], item["metric"]) for item in details[:3]], "limitations": [METRIC_NAMES.get(key, key) + "：暂无数据" for key in result["missing"][:3]], "reason": explain(result, req), "calculation": details}
