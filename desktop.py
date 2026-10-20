"""
智哥选型 - 桌面界面 (Tkinter)
精简版：合并布局，减少冗余样式，功能与原版一致
"""

import sqlite3, tkinter as tk, webbrowser
from tkinter import messagebox, ttk
from tkinter.filedialog import asksaveasfilename

from core import (
    get_materials, temp_tiers, hard_filter, score_materials,
    explain, load_weights, run_checks,
)
from report import generate_html, export_csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "materials.db"
WEIGHTS = ROOT / "rules" / "weights.json"

PARTS = ["轴","齿轮","齿轮轴","销轴","连杆","曲轴","凸轮","丝杠","蜗杆","底板","支架","框架","机架","法兰","套筒","轴承座","滑块","导轨","外壳","箱体","螺栓","螺母","弹簧","焊接结构件","铸件","锻件","冲压件","耐磨件","高温件","低温件","其他","自定义…"]
LOADS = ["拉伸","压缩","弯曲","扭转","剪切","冲击","振动","疲劳","接触","摩擦","静载","动载","综合载荷"]
PROCESSES = ["机加工","车削","铣削","磨削","钻削","焊接","铸造","锻造","冲压","热处理","表面处理"]
LEVELS = ["不考虑","较低","一般","较高","很高"]
LEVEL_W = {"不考虑":0,"较低":1,"一般":2,"较高":4,"很高":5}
HARD = ["必须耐高温","必须耐腐蚀","必须可焊接","必须满足强度","必须耐磨","必须轻量化"]
HARD_MAP = {"必须耐高温":"high_temp","必须耐腐蚀":"corrosion","必须可焊接":"weldability","必须满足强度":"strength","必须耐磨":"wear","必须轻量化":"lightweight"}

GROUPS = {
    "力学性能":[("strength","强度"),("hardness","硬度"),("stiffness","刚度"),("stability","稳定性"),("fatigue","疲劳"),("toughness","韧性"),("impact","抗冲击"),("ductility","延展性")],
    "环境性能":[("wear","耐磨"),("corrosion","耐腐蚀"),("lightweight","轻量化"),("high_temp","高温"),("low_temp","低温"),("conductivity","导电"),("thermal_conductivity","导热"),("insulation","绝缘")],
    "工艺性能":[("machinability","加工"),("weldability","焊接"),("casting","铸造"),("forging","锻造"),("stamping","冲压"),("heat_treatment","热处理"),("surface_treatment","表面处理")],
    "经济性":[("cost","材料成本"),("maintenance_cost","维护成本")],
}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("智哥选型"); self.geometry("1280x860"); self.minsize(1000,680)
        self.results=[]; self.compare=[]; self.req={}; self.last_ranked=[]
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.pick = ttk.Frame(nb, padding=10); self.dbtab = ttk.Frame(nb, padding=10)
        nb.add(self.pick, text="材料选型"); nb.add(self.dbtab, text="材料数据库")
        self._sel(); self._db()

    def _sel(self):
        p = self.pick
        p.columnconfigure(0, weight=1); p.rowconfigure(0, weight=1)
        canvas = tk.Canvas(p, highlightthickness=0)
        vbar = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        canvas.grid(row=0, column=0, sticky="nsew"); vbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vbar.set)
        p.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta/120), "units")))
        p.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        content = ttk.Frame(canvas, padding=10)
        canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))

        frm = ttk.LabelFrame(content, text="使用需求", padding=8); frm.grid(row=0, column=0, sticky="ew", pady=(0,6))
        for i in range(6): frm.columnconfigure(i, weight=1)

        ttk.Label(frm, text="零件样式 *").grid(row=0, column=0, sticky="w")
        self.part = tk.StringVar(value="轴")
        cb = ttk.Combobox(frm, textvariable=self.part, values=PARTS, state="readonly", width=14)
        cb.grid(row=0, column=1, sticky="w")
        self.custom_part = ttk.Entry(frm); self.custom_part.insert(0, "自定义零件样式"); self.custom_part.configure(state="disabled")
        self.custom_part.grid(row=0, column=2, sticky="ew")

        ttk.Label(frm, text="工作温度 *").grid(row=0, column=3, sticky="w")
        conn = sqlite3.connect(str(DB)); tiers = temp_tiers(conn); conn.close()
        self.tiers = tiers
        self.temp = tk.StringVar(value="请选择温度档位")
        self.tempbox = ttk.Combobox(frm, textvariable=self.temp, values=["请选择温度档位"]+[t["label"] for t in tiers]+["自定义…"], state="readonly", width=20)
        self.tempbox.grid(row=0, column=4, sticky="w")
        self.custom_temp = ttk.Entry(frm, width=8); self.custom_temp.insert(0, "℃"); self.custom_temp.configure(state="disabled")
        self.custom_temp.grid(row=0, column=5, sticky="w")

        ttk.Label(frm, text="载荷类型").grid(row=1, column=0, sticky="nw")
        lf = ttk.Frame(frm); lf.grid(row=1, column=1, columnspan=5, sticky="ew")
        self.tagvars = {}
        for i, v in enumerate(LOADS):
            self.tagvars[v] = tk.BooleanVar(); ttk.Checkbutton(lf, text=v, variable=self.tagvars[v]).grid(row=i//7, column=i%7, sticky="w", padx=4)

        ttk.Label(frm, text="制造方式").grid(row=2, column=0, sticky="nw")
        pf = ttk.Frame(frm); pf.grid(row=2, column=1, columnspan=5, sticky="ew")
        for i, v in enumerate(PROCESSES):
            self.tagvars[v] = tk.BooleanVar(); ttk.Checkbutton(pf, text=v, variable=self.tagvars[v]).grid(row=i//7, column=i%7, sticky="w", padx=4)

        ttk.Label(frm, text="硬性条件").grid(row=3, column=0, sticky="nw")
        hf = ttk.Frame(frm); hf.grid(row=3, column=1, columnspan=5, sticky="ew")
        self.hardvars = {}
        for i, o in enumerate(HARD):
            self.hardvars[o] = tk.BooleanVar(); ttk.Checkbutton(hf, text=o, variable=self.hardvars[o]).grid(row=i//3, column=i%3, sticky="w", padx=4)

        ttk.Label(frm, text="补充条件").grid(row=4, column=0, sticky="w")
        self.must = ttk.Entry(frm); self.must.grid(row=4, column=1, columnspan=5, sticky="ew")
        ttk.Label(frm, text="示例：特定标准、供应状态；多个条件用逗号分隔", foreground="#666").grid(row=5, column=1, columnspan=5, sticky="w")

        perf = ttk.LabelFrame(content, text="性能要求（按档位选择）", padding=6)
        perf.grid(row=1, column=0, sticky="ew", pady=(0,6))
        self.metric = {}
        for i, (g, items) in enumerate(GROUPS.items()):
            box = ttk.LabelFrame(perf, text=g, padding=4)
            box.grid(row=i//2, column=i%2, sticky="ew", padx=4, pady=3)
            perf.columnconfigure(i%2, weight=1)
            for j, (k, lab) in enumerate(items):
                self.metric[k] = tk.StringVar(value="不考虑")
                ttk.Label(box, text=lab, width=8).grid(row=j, column=0, sticky="w", padx=3)
                ttk.Combobox(box, textvariable=self.metric[k], values=LEVELS, state="readonly", width=7).grid(row=j, column=1, sticky="w", padx=3)

        sf = ttk.LabelFrame(content, text="强度校核参数（选中材料后计算）", padding=6)
        sf.grid(row=2, column=0, sticky="ew", pady=(0,6))
        for i in range(6): sf.columnconfigure(i, weight=1)
        ttk.Label(sf, text="类型").grid(row=0, column=0, sticky="w")
        self.check_type = tk.StringVar(value="轴扭转")
        ttk.Combobox(sf, textvariable=self.check_type, values=["轴扭转","螺栓拉伸","梁弯曲"], state="readonly", width=10).grid(row=0, column=1, sticky="w")
        ttk.Label(sf, text="载荷 N").grid(row=0, column=2, sticky="w")
        self.sf_load = ttk.Entry(sf, width=10); self.sf_load.insert(0, "1000"); self.sf_load.grid(row=0, column=3, sticky="w")
        ttk.Label(sf, text="尺寸 mm").grid(row=0, column=4, sticky="w")
        self.sf_dim = ttk.Entry(sf, width=10); self.sf_dim.insert(0, "20"); self.sf_dim.grid(row=0, column=5, sticky="w")
        ttk.Label(sf, text="安全系数").grid(row=1, column=0, sticky="w")
        self.sf_req = ttk.Entry(sf, width=10); self.sf_req.insert(0, "1.5"); self.sf_req.grid(row=1, column=1, sticky="w")
        ttk.Button(sf, text="计算校核", command=self.strength_check).grid(row=1, column=2, sticky="w")

        out = ttk.Frame(content); out.grid(row=3, column=0, sticky="nsew"); out.columnconfigure(0, weight=1); out.rowconfigure(1, weight=1)
        ttk.Label(out, text="推荐结果", font=("Microsoft YaHei UI", 12, "bold"), foreground="#173b5c").grid(row=0, column=0, sticky="w", pady=3)
        frame = ttk.Frame(out, relief="solid", borderwidth=1, padding=6)
        frame.grid(row=1, column=0, sticky="nsew"); frame.columnconfigure(0, weight=1); frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(frame, columns=("rank","material","score","complete","confidence","reason"), show="headings")
        for k, t, wdt in [("rank","排名",55),("material","材料/牌号",190),("score","匹配度",80),("complete","完整度",80),("confidence","可信度",80),("reason","推荐理由",600)]:
            self.tree.heading(k, text=t); self.tree.column(k, width=wdt)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview).grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda e: self.detail())

        btns = ttk.Frame(out); btns.grid(row=2, column=0, sticky="e", pady=5)
        ttk.Button(btns, text="查看详情", command=self.detail).pack(side="left", padx=3)
        ttk.Button(btns, text="加入对比", command=self.add_compare).pack(side="left", padx=3)
        ttk.Button(btns, text="查看对比", command=self.show_compare).pack(side="left", padx=3)
        ttk.Button(btns, text="开始推荐", command=self.recommend).pack(side="left", padx=6)
        ttk.Button(btns, text="导出HTML报告", command=self.export_html).pack(side="left", padx=3)
        ttk.Button(btns, text="导出CSV", command=self.export_csv).pack(side="left", padx=3)
        self.status = ttk.Label(out, text="请选择条件后开始推荐。", foreground="#666"); self.status.grid(row=3, column=0, sticky="w")

        self.part.trace_add("write", lambda *_: self._toggle())
        self.temp.trace_add("write", lambda *_: self._toggle())

    def _toggle(self):
        self.custom_part.configure(state="normal" if self.part.get()=="自定义…" else "disabled")
        self.custom_temp.configure(state="normal" if self.temp.get()=="自定义…" else "disabled")

    def _req(self):
        p = self.custom_part.get().strip() if self.part.get()=="自定义…" else self.part.get()
        if not p: raise ValueError("请输入零件样式")
        if self.temp.get() == "自定义…":
            try: temp = float(self.custom_temp.get().replace("℃","").strip())
            except ValueError: raise ValueError("工作温度请输入数字，例如 185")
        elif self.tempbox.current() > 0:
            temp = self.tiers[self.tempbox.current()]["value"]
        else:
            temp = None
        checked = [k for k, v in self.metric.items() if v.get() != "不考虑"]
        loads = [v for v in LOADS if self.tagvars[v].get()]
        processes = [v for v in PROCESSES if self.tagvars[v].get()]
        must = [x.strip() for x in self.must.get().replace("，", ",").split(",") if x.strip()]
        must.extend(HARD_MAP[k] for k, v in self.hardvars.items() if v.get())
        weights = {k: LEVEL_W.get(self.metric[k].get(), 0) for k in checked}
        if checked: weights.update({k: 0 for k in self.metric if k not in checked})
        return {"part_type": p, "temperature": temp, "loads": loads, "processes": processes, "must_have": must, "weights": weights}

    def recommend(self):
        try: req = self._req()
        except ValueError as e: messagebox.showwarning("输入需要确认", str(e)); return
        try:
            kept, _ = hard_filter(get_materials(str(DB)), req)
            with sqlite3.connect(str(DB)) as conn:
                ranked, _ = score_materials(kept, req, load_weights(str(WEIGHTS)), conn)
            self.results = ranked[:3]; self.last_ranked = ranked; self.req = req
        except Exception as e:
            self.status.configure(text=f"推荐失败：{e}", foreground="#b04444"); messagebox.showerror("推荐失败", str(e)); return
        for x in self.tree.get_children(): self.tree.delete(x)
        for i, x in enumerate(self.results, 1):
            conf = "需核实" if x["low_confidence"] else ("高" if x["completeness"] >= 80 else "中")
            self.tree.insert("", "end", iid=str(i-1), values=(i, f"{x['material']['name']} / {x['material'].get('grade') or '牌号未记录'}", f"{x['score']}/100", f"{x['completeness']}%", conf, explain(x, req)))
        if not self.results:
            self.tree.insert("", "end", values=("-", "暂无匹配材料", "-", "-", "-", "没有材料明确满足当前条件"))
            self.status.configure(text="无匹配结果，请放宽筛选条件。", foreground="#b04444")
        else:
            self.status.configure(text=f"已筛选 {len(kept)} 种；可在下方输入尺寸进行强度校核，或点击导出报告。")

    def _current(self):
        s = self.tree.selection()
        return self.results[int(s[0])] if s and s[0].isdigit() and int(s[0]) < len(self.results) else None

    def _text_window(self, title, text, geometry="760x600"):
        win = tk.Toplevel(self); win.title(title); win.geometry(geometry)
        win.columnconfigure(0, weight=1); win.rowconfigure(0, weight=1)
        txt = tk.Text(win, wrap="word", font=("Microsoft YaHei UI", 10))
        txt.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        bar = ttk.Scrollbar(win, orient="vertical", command=txt.yview)
        bar.grid(row=0, column=1, sticky="ns", pady=15)
        txt.configure(yscrollcommand=bar.set)
        txt.insert("1.0", text); txt.configure(state="disabled")
        return win

    PARAM_LABELS = [
        ("tensile_strength_mpa", "抗拉强度"), ("yield_strength_mpa", "屈服强度"),
        ("elastic_modulus_gpa", "弹性模量"), ("density_g_cm3", "密度"),
        ("temperature_max_c", "最高工作温度"), ("hardness", "硬度"),
        ("fatigue_strength_mpa", "疲劳强度"), ("thermal_conductivity_w_mk", "热导率"),
        ("thermal_expansion_um_mk", "热膨胀系数"),
    ]

    def detail(self):
        x = self._current()
        if not x: return
        m = x["material"]
        lines = [f"{m['name']}（{m.get('grade') or '牌号未记录'}）",
                 f"匹配分数：{x['score']}/100", f"数据完整度：{x['completeness']}%",
                 f"推荐理由：{explain(x, self.req)}", "", "关键参数："]
        for key, label in self.PARAM_LABELS:
            v = m.get(key)
            lines.append(f"{label}：{v if v not in (None, '') else '暂无数据'}")
        lines += ["", f"适用制造工艺：{m.get('machinability') or '暂无数据'}",
                  f"典型用途/限制：{m.get('typical_uses') or '暂无数据'}"]
        self._text_window("材料详情", "\n".join(lines))

    def add_compare(self):
        x = self._current()
        if not x: messagebox.showinfo("加入对比", "请先选择一条推荐材料。"); return
        if x not in self.compare: self.compare.append(x)
        self.status.configure(text=f"已加入对比 {len(self.compare)} 种材料")

    def show_compare(self):
        if not self.compare: messagebox.showinfo("材料对比", "请先从推荐结果中加入材料。"); return
        win = tk.Toplevel(self); win.title("材料横向对比"); win.geometry("1000x560")
        win.columnconfigure(0, weight=1); win.rowconfigure(0, weight=1)
        frame = ttk.Frame(win, padding=10); frame.grid(row=0, column=0, sticky="nsew"); frame.columnconfigure(0, weight=1); frame.rowconfigure(0, weight=1)
        cols = ["parameter"] + [str(i) for i in range(len(self.compare))]
        tree = ttk.Treeview(frame, columns=cols, show="headings"); tree.heading("parameter", text="参数"); tree.column("parameter", width=160)
        for i, r in enumerate(self.compare):
            m = r["material"]; tree.heading(str(i), text=f"{m['name']} / {m.get('grade') or '无牌号'}"); tree.column(str(i), width=220)
        rows = [("匹配度","score"),("完整度","completeness"),("抗拉强度","tensile_strength_mpa"),("屈服强度","yield_strength_mpa"),("弹性模量","elastic_modulus_gpa"),("密度","density_g_cm3"),("最高温度","temperature_max_c"),("硬度","hardness")]
        for lab, key in rows:
            vals = []
            for r in self.compare:
                vals.append(r.get(key) if key in r else (r["material"].get(key) if r["material"].get(key) not in (None,"") else "暂无数据"))
            tree.insert("", "end", values=(lab, *vals))
        tree.grid(row=0, column=0, sticky="nsew")
        vbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview); vbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=vbar.set)

    def strength_check(self):
        if not self.last_ranked:
            messagebox.showwarning("强度校核", "请先进行材料推荐。"); return
        m = self.last_ranked[0]["material"]
        try:
            load = float(self.sf_load.get()); dim = float(self.sf_dim.get()); sf_req = float(self.sf_req.get())
        except ValueError:
            messagebox.showerror("输入错误", "载荷、尺寸和安全系数必须为数字。"); return
        ctype = self.check_type.get()
        if ctype == "轴扭转":
            checks = [{"type":"shaft_torsion","torque_nm":load,"diameter_mm":dim,"safety_factor_req":sf_req,"keyway_factor":1.3}]
        elif ctype == "螺栓拉伸":
            checks = [{"type":"bolt_tension","axial_load_n":load,"diameter_mm":dim,"safety_factor_req":sf_req}]
        else:
            checks = [{"type":"beam_bending","load_n":load,"span_mm":dim,"section_modulus_mm3":max(dim*dim*10,1.0),"safety_factor_req":sf_req}]
        res = run_checks(m, checks)[0]
        lines = [
            f"材料：{m.get('name','')} / {m.get('grade') or '牌号未记录'}",
            f"校核项目：{res.check_item}",
            f"计算应力：{res.calculated_stress} MPa",
            f"许用应力：{res.allowable_stress} MPa",
            f"安全系数：{res.safety_factor}（要求 ≥ {sf_req}）",
            f"判定：{'通过 ✓' if res.passed else '未通过 ✗'}",
            f"公式：{res.formula}",
            f"备注：{res.note}",
            "",
            "注：以上为初步估算，最终设计需结合详细载荷谱、应力集中及相关标准。",
        ]
        self._text_window("强度校核结果", "\n".join(lines), "620x420")

    def export_html(self):
        if not self.results: messagebox.showwarning("导出报告", "请先进行材料推荐。"); return
        path = asksaveasfilename(defaultextension=".html", filetypes=[("HTML 文件", "*.html")], initialfile="选型报告.html")
        if not path: return
        try:
            generate_html(self.results[0]["material"], self.req, self.results, output_path=path)
            messagebox.showinfo("导出成功", f"HTML 报告已保存：\n{path}")
            if messagebox.askyesno("打开报告", "是否现在在浏览器中打开？"): webbrowser.open(path)
        except Exception as e: messagebox.showerror("导出失败", str(e))

    def export_csv(self):
        if not self.results: messagebox.showwarning("导出 CSV", "请先进行材料推荐。"); return
        path = asksaveasfilename(defaultextension=".csv", filetypes=[("CSV 文件", "*.csv")], initialfile="选型结果.csv")
        if not path: return
        try:
            export_csv(self.results, output_path=path)
            messagebox.showinfo("导出成功", f"CSV 已保存：\n{path}")
        except Exception as e: messagebox.showerror("导出失败", str(e))

    def _db(self):
        t = self.dbtab; t.columnconfigure(0, weight=1); t.rowconfigure(1, weight=1)
        bar = ttk.Frame(t); bar.grid(row=0, column=0, sticky="ew", pady=(0,6))
        ttk.Label(bar, text="搜索").pack(side="left")
        self.q = tk.StringVar(); ttk.Entry(bar, textvariable=self.q, width=28).pack(side="left", padx=6)
        ttk.Button(bar, text="刷新", command=self._refresh).pack(side="left")
        ttk.Button(bar, text="查看详情", command=self._db_detail).pack(side="right")
        frame = ttk.Frame(t); frame.grid(row=1, column=0, sticky="nsew"); frame.columnconfigure(0, weight=1); frame.rowconfigure(0, weight=1)
        self.dbtree = ttk.Treeview(frame, columns=("id","name","grade","temp","source"), show="headings")
        for k, tt, wdt in [("id","ID",50),("name","材料",180),("grade","牌号",120),("temp","最高温度",100),("source","数据来源",300)]:
            self.dbtree.heading(k, text=tt); self.dbtree.column(k, width=wdt)
        self.dbtree.grid(row=0, column=0, sticky="nsew"); ttk.Scrollbar(frame, orient="vertical", command=self.dbtree.yview).grid(row=0, column=1, sticky="ns")
        self._refresh()

    def _refresh(self):
        for x in self.dbtree.get_children(): self.dbtree.delete(x)
        q = self.q.get().lower()
        for m in get_materials(str(DB)):
            if q and q not in f"{m['name']} {m.get('grade') or ''}".lower(): continue
            self.dbtree.insert("", "end", iid=str(m['id']), values=(m['id'], m['name'], m.get('grade') or "暂无数据", m.get('temperature_max_c') or "暂无数据", m.get('source') or "暂无数据"))

    def _db_detail(self):
        s = self.dbtree.selection()
        if not s: return
        m = next((x for x in get_materials(str(DB)) if str(x['id']) == s[0]), None)
        if not m: return
        text = (f"材料：{m['name']}\n牌号：{m.get('grade') or '暂无数据'}\n"
                f"类别：{m.get('category') or '暂无数据'}\n\n"
                f"典型用途：{m.get('typical_uses') or '暂无数据'}\n"
                f"来源：{m.get('source') or '暂无数据'}")
        self._text_window("材料详情", text)

if __name__ == "__main__":
    App().mainloop()
