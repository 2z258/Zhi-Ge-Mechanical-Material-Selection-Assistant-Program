"""
智哥选型 - 报告生成器
输出 HTML（浏览器可打印为 PDF）和 CSV，方便导入 Excel/SolidWorks
"""

import csv, json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import List, Optional, Any
from core import explain

def _e(v): return escape(str(v) if v is not None else "")

def generate_html(material, req, results: List[dict], strength_results: Optional[List[Any]] = None, output_path: str = "选型报告.html") -> str:
    rows = ""
    for r in results:
        m = r["material"]
        reason = r.get("reason") or explain(r, req)
        rows += (
            "<tr>"
            f"<td>{_e(m.get('name'))}</td>"
            f"<td>{_e(m.get('grade') or '暂无')}</td>"
            f"<td>{r.get('score',0)}/100</td>"
            f"<td>{r.get('completeness',0)}%</td>"
            f"<td>{_e(reason[:180])}...</td>"
            "</tr>"
        )

    strength_html = ""
    if strength_results:
        for s in strength_results:
            status = '<span style="color:green">✓ 通过</span>' if s.passed else '<span style="color:red">✗ 未通过</span>'
            strength_html += (
                "<tr>"
                f"<td>{s.part_type}</td><td>{s.check_item}</td>"
                f"<td>{s.calculated_stress} MPa</td><td>{s.allowable_stress} MPa</td>"
                f"<td>{s.safety_factor}</td><td>{status}</td><td>{_e(s.note)}</td>"
                "</tr>"
            )

    strength_section = ""
    if strength_results:
        strength_section = (
            "<h2>3. 强度校核（选定材料）</h2><table>"
            "<tr><th>零件</th><th>校核项目</th><th>计算应力</th><th>许用应力</th>"
            "<th>安全系数</th><th>判定</th><th>备注</th></tr>"
            f"{strength_html}</table>"
        )

    html = (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>材料选型报告</title>"
        "<style>body{font-family:'Microsoft YaHei UI',sans-serif;max-width:950px;margin:30px auto;padding:20px;color:#222}"
        "table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #ccc;padding:8px;text-align:left}"
        "th{background:#eef3f7}h1{color:#173b5c}h2{color:#1c5d94;border-bottom:2px solid #1c5d94;padding-bottom:4px}"
        ".note{color:#666;font-size:12px;margin-top:30px}</style></head><body>"
        "<h1>机械材料选型报告</h1>"
        f"<p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        "<h2>1. 选型条件</h2><ul>"
        f"<li>零件类型：{_e(req.get('part_type',''))}</li>"
        f"<li>工作温度：{req.get('temperature','未填写')} ℃</li>"
        f"<li>载荷类型：{', '.join(req.get('loads',[])) or '未填写'}</li>"
        f"<li>制造方式：{', '.join(req.get('processes',[])) or '未填写'}</li>"
        f"<li>硬性条件：{', '.join(req.get('must_have',[])) or '无'}</li>"
        "</ul>"
        "<h2>2. TOP 3 推荐材料</h2>"
        "<table><tr><th>材料/牌号</th><th>匹配度</th><th>完整度</th><th>推荐理由（摘要）</th></tr>"
        f"{rows}</table>"
        f"{strength_section}"
        "<p class=\"note\">注：本报告由“智哥选型”辅助系统生成，仅用于材料初步筛选，"
        "最终选型需结合载荷计算、尺寸、寿命、标准及供应商数据确认。</p>"
        "</body></html>"
    )
    Path(output_path).write_text(html, encoding="utf-8")
    return str(Path(output_path).resolve())

def export_csv(results: List[dict], output_path: str = "选型结果.csv") -> str:
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["排名","材料","牌号","匹配度","完整度","抗拉强度(MPa)","屈服强度(MPa)","弹性模量(GPa)","密度(g/cm³)","最高温度(℃)"])
        for i, r in enumerate(results, 1):
            m = r["material"]
            w.writerow([i, m.get("name",""), m.get("grade") or "", r.get("score",0), r.get("completeness",0),
                        m.get("tensile_strength_mpa",""), m.get("yield_strength_mpa",""),
                        m.get("elastic_modulus_gpa",""), m.get("density_g_cm3",""), m.get("temperature_max_c","")])
    return str(Path(output_path).resolve())

def export_json(results: List[dict], req: dict, output_path: str = "选型结果.json") -> str:
    payload = {"generated_at": datetime.now().isoformat(), "request": req, "recommendations": results}
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(Path(output_path).resolve())
