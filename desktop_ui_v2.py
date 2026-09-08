import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from desktop_bridge import temp_tiers
from core.material_engine import hard_filter, METRIC_NAMES, explain, score_materials

PARTS = ["轴", "齿轮", "齿轮轴", "销轴", "连杆", "曲轴", "凸轮", "丝杠", "蜗杆", "底板", "支架", "框架", "机架", "法兰", "套筒", "轴承座", "滑块", "导轨", "外壳", "箱体", "螺栓", "螺母", "弹簧", "焊接结构件", "铸件", "锻件", "冲压件", "耐磨件", "高温件", "低温件", "其他", "自定义…"]
LOADS = ["拉伸", "压缩", "弯曲", "扭转", "剪切", "冲击", "振动", "疲劳", "接触", "摩擦", "静载", "动载", "综合载荷"]
PROCESSES = ["机加工", "车削", "铣削", "磨削", "钻削", "焊接", "铸造", "锻造", "冲压", "热处理", "表面处理"]
LEVELS = ["不考虑", "较低", "一般", "较高", "很高"]
LEVEL_WEIGHTS = {"不考虑": 0, "较低": 1, "一般": 2, "较高": 4, "很高": 5}
HARD_OPTIONS = ["必须耐高温", "必须耐腐蚀", "必须可焊接", "必须满足强度", "必须耐磨", "必须轻量化"]
CHOICES = {"载荷类型": LOADS, "制造方式": PROCESSES}
GROUPS = {"力学性能": [("strength", "强度"), ("hardness", "硬度"), ("stiffness", "刚度"), ("stability", "稳定性"), ("fatigue", "疲劳"), ("toughness", "韧性"), ("impact", "抗冲击"), ("ductility", "延展性")], "环境性能": [("wear", "耐磨"), ("corrosion", "耐腐蚀"), ("lightweight", "轻量化"), ("high_temp", "高温"), ("low_temp", "低温"), ("conductivity", "导电"), ("thermal_conductivity", "导热"), ("insulation", "绝缘")], "工艺性能": [("machinability", "加工"), ("weldability", "焊接"), ("casting", "铸造"), ("forging", "锻造"), ("stamping", "冲压"), ("heat_treatment", "热处理"), ("surface_treatment", "表面处理")], "经济性": [("cost", "材料成本"), ("maintenance_cost", "维护成本")]}

class DesktopApp(tk.Tk):
    def __init__(self, db_path, rules_path):
        super().__init__(); self.db_path=str(db_path); self.rules_path=str(rules_path); self.title("智哥选型"); self.geometry("1260x850"); self.minsize(1000,680); self.results=[]; self.compare=[]; self.current_request={}; self._style(); self._build()
    def _style(self):
        s=ttk.Style(self); s.theme_use("clam"); s.configure("App.TFrame",background="#f3f6f9"); s.configure("Header.TFrame",background="#173b5c"); s.configure("Header.TLabel",background="#173b5c",foreground="white",font=("Microsoft YaHei UI",16,"bold")); s.configure("Sub.TLabel",background="#173b5c",foreground="#c8d7e4",font=("Microsoft YaHei UI",9)); s.configure("Section.TLabelframe",background="#f3f6f9"); s.configure("Section.TLabelframe.Label",foreground="#173b5c",font=("Microsoft YaHei UI",10,"bold")); s.configure("Accent.TButton",background="#1677b8",foreground="white",font=("Microsoft YaHei UI",10,"bold"),padding=(16,8)); s.configure("Treeview",rowheight=30); s.configure("Treeview.Heading",font=("Microsoft YaHei UI",9,"bold"))
    def materials(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; rows=[dict(r) for r in c.execute("select * from materials order by section,id")]; c.close(); return rows
    def _build(self):
        h=ttk.Frame(self,style="Header.TFrame",padding=(22,9)); h.pack(fill="x"); ttk.Label(h,text="智哥选型",style="Header.TLabel").pack(anchor="w"); ttk.Label(h,text="基于材料数据库的初步筛选与可解释推荐 · 缺失数据显示为暂无数据",style="Sub.TLabel").pack(anchor="w")
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill="both",expand=True,padx=12,pady=12); self.pick=ttk.Frame(self.tabs,style="App.TFrame",padding=12); self.dbtab=ttk.Frame(self.tabs,style="App.TFrame",padding=12); self.tabs.add(self.pick,text="材料选型"); self.tabs.add(self.dbtab,text="材料数据库"); self._selection(); self._database()
    def _selection(self):
        tab = self.pick
        canvas = tk.Canvas(tab, background="#f3f6f9", highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        content = ttk.Frame(canvas, style="App.TFrame", padding=2)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", self._scroll_selection))
        canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))
        self.pick = content
        self.pick.columnconfigure(0,weight=1); self.pick.rowconfigure(2,weight=1); form=ttk.LabelFrame(self.pick,text="使用需求",padding=10); form.grid(row=0,column=0,sticky="ew",pady=(0,8)); form.columnconfigure(1,weight=1); form.columnconfigure(4,weight=1)
        ttk.Label(form,text="零件样式 *").grid(row=0,column=0,sticky="w",padx=5,pady=4); self.part=tk.StringVar(value="轴"); ttk.Combobox(form,textvariable=self.part,values=PARTS,state="readonly").grid(row=0,column=1,sticky="ew",padx=5); self.custom_part=ttk.Entry(form); self.custom_part.grid(row=0,column=2,sticky="ew",padx=5); self.custom_part.insert(0,"自定义零件样式"); self.custom_part.configure(state="disabled")
        ttk.Label(form,text="工作温度 *").grid(row=0,column=3,sticky="w",padx=5); tiers=temp_tiers(self.db_path); self.tier=[None]+[x["value"] for x in tiers]; self.temp=tk.StringVar(value="请选择温度档位"); self.tempbox=ttk.Combobox(form,textvariable=self.temp,values=["请选择温度档位"]+[x["label"] for x in tiers]+["自定义…"],state="readonly"); self.tempbox.grid(row=0,column=4,sticky="ew",padx=5); self.custom_temp=ttk.Entry(form,width=10); self.custom_temp.grid(row=0,column=5,padx=5); self.custom_temp.insert(0,"℃"); self.custom_temp.configure(state="disabled"); self.part.trace_add("write",lambda *_:self._toggle()); self.temp.trace_add("write",lambda *_:self._toggle())
        self.tagvars={}
        for row, name in enumerate(CHOICES, 1):
            ttk.Label(form,text=name).grid(row=row,column=0,sticky="nw",padx=5,pady=4); box=ttk.Frame(form); box.grid(row=row,column=1,columnspan=5,sticky="ew",padx=5)
            self.tagvars[name]={}
            for i,v in enumerate(CHOICES[name]): self.tagvars[name][v]=tk.BooleanVar(); ttk.Checkbutton(box,text=v,variable=self.tagvars[name][v]).grid(row=i//6,column=i%6,sticky="w",padx=7,pady=2)
        ttk.Label(form,text="硬性条件").grid(row=3,column=0,sticky="nw",padx=5); hard_frame=ttk.Frame(form); hard_frame.grid(row=3,column=1,columnspan=5,sticky="ew",padx=5); self.hardvars={}
        for i, option in enumerate(HARD_OPTIONS):
            self.hardvars[option]=tk.BooleanVar(); ttk.Checkbutton(hard_frame,text=option,variable=self.hardvars[option]).grid(row=i//3,column=i%3,sticky="w",padx=7,pady=2)
        ttk.Label(form,text="补充条件（可选）").grid(row=5,column=0,sticky="w",padx=5); self.must=ttk.Entry(form); self.must.grid(row=5,column=1,columnspan=5,sticky="ew",padx=5); ttk.Label(form,text="示例：特定标准、供应状态；多个条件用逗号分隔",foreground="#6b7c8d").grid(row=6,column=1,columnspan=5,sticky="w",padx=5)
        perf=ttk.LabelFrame(self.pick,text="性能要求（按档位选择）",padding=8); perf.grid(row=1,column=0,sticky="ew",pady=(0,8)); self.metric={}
        for i,(group,items) in enumerate(GROUPS.items()):
            box=ttk.LabelFrame(perf,text=group,padding=5); box.grid(row=1+i//2,column=i%2,sticky="ew",padx=5,pady=3); perf.columnconfigure(i%2,weight=1)
            for j,(key,label) in enumerate(items):
                self.metric[key]=tk.StringVar(value="不考虑")
                ttk.Label(box,text=label,width=9).grid(row=j,column=0,sticky="w",padx=4,pady=2)
                ttk.Combobox(box,textvariable=self.metric[key],values=LEVELS,state="readonly",width=7).grid(row=j,column=1,sticky="w",padx=4,pady=2)
        out=ttk.Frame(self.pick,style="App.TFrame"); out.grid(row=2,column=0,sticky="nsew"); out.columnconfigure(0,weight=1); out.rowconfigure(1,weight=1); ttk.Label(out,text="推荐结果",font=("Microsoft YaHei UI",12,"bold"),foreground="#173b5c").grid(row=0,column=0,sticky="w",pady=4)
        frame=ttk.Frame(out,relief="solid",borderwidth=1,padding=6); frame.grid(row=1,column=0,sticky="nsew"); frame.columnconfigure(0,weight=1); frame.rowconfigure(0,weight=1);
        self.tree=ttk.Treeview(frame,columns=("rank","material","score","complete","confidence","reason"),show="headings");
        for k,t,w in [("rank","排名",55),("material","材料 / 牌号",190),("score","匹配度",80),("complete","完整度",80),("confidence","可信度",80),("reason","推荐理由",600)]: self.tree.heading(k,text=t); self.tree.column(k,width=w)
        self.tree.grid(row=0,column=0,sticky="nsew"); ttk.Scrollbar(frame,orient="vertical",command=self.tree.yview).grid(row=0,column=1,sticky="ns"); self.tree.bind("<Double-1>",lambda e:self.detail())
        buttons=ttk.Frame(out,style="App.TFrame"); buttons.grid(row=2,column=0,sticky="e",pady=6); ttk.Button(buttons,text="查看详情",command=self.detail).pack(side="left",padx=4); ttk.Button(buttons,text="加入对比",command=self.add_compare).pack(side="left",padx=4); ttk.Button(buttons,text="查看对比",command=self.show_compare).pack(side="left",padx=4); ttk.Button(buttons,text="开始推荐",style="Accent.TButton",command=self.recommend).pack(side="left",padx=8); self.status=ttk.Label(out,text="请选择条件后开始推荐。",foreground="#6b7c8d"); self.status.grid(row=3,column=0,sticky="w")
    def _scroll_selection(self, event):
        event.widget.yview_scroll(int(-event.delta / 120), "units")
    def _toggle(self): self.custom_part.configure(state="normal" if self.part.get()=="自定义…" else "disabled"); self.custom_temp.configure(state="normal" if self.temp.get()=="自定义…" else "disabled")
    def _selected(self,name): return [x for x,v in self.tagvars[name].items() if v.get()]
    def _req(self):
        p=self.custom_part.get().strip() if self.part.get()=="自定义…" else self.part.get();
        if not p: raise ValueError("请输入零件样式")
        if self.temp.get()=="自定义…":
            try: temp=float(self.custom_temp.get().replace("℃","").strip())
            except ValueError: raise ValueError("工作温度请输入数字，例如 185")
        elif self.tempbox.current()>0: temp=self.tier[self.tempbox.current()]
        else: temp=None
        checked=[k for k,v in self.metric.items() if v.get()!="不考虑"]; loads=self._selected("载荷类型"); processes=self._selected("制造方式"); must=[x.strip() for x in self.must.get().replace("，",",").split(",") if x.strip()]
        hard_map={"必须耐高温":"high_temp","必须耐腐蚀":"corrosion","必须可焊接":"weldability","必须满足强度":"strength","必须耐磨":"wear","必须轻量化":"lightweight"}
        must.extend(hard_map[k] for k,v in self.hardvars.items() if v.get())
        weights={k:LEVEL_WEIGHTS.get(self.metric[k].get(), 0) for k in checked};
        if checked: weights.update({k:0 for k in self.metric if k not in checked})
        return {"part_type":p,"temperature":temp,"loads":loads,"processes":processes,"must_have":must,"weights":weights}
    def recommend(self):
        try: req=self._req()
        except ValueError as e: messagebox.showwarning("输入需要确认",str(e)); return
        try:
            kept,rejected=hard_filter(self.materials(),req); ranked,_=score_materials(kept,req,self.rules_path,self.db_path); self.results=ranked[:3]
        except Exception as error:
            self.status.configure(text=f"推荐失败：{error}",foreground="#b04444")
            messagebox.showerror("推荐失败", f"推荐计算未完成：{error}")
            return
        for x in self.tree.get_children(): self.tree.delete(x)
        self.current_request=req
        for i,x in enumerate(self.results,1):
            confidence="需核实" if x["low_confidence"] else ("高" if x["completeness"]>=80 else "中")
            self.tree.insert("","end",iid=str(i-1),values=(i,f"{x['material']['name']} / {x['material'].get('grade') or '牌号未记录'}",f"{x['score']}/100",f"{x['completeness']}%",confidence,explain(x,req)))
        if not self.results: self.tree.insert("","end",values=("-","暂无匹配材料","-","-","-","没有材料明确满足当前条件，请检查温度或硬性条件")); self.status.configure(text="无匹配结果，请放宽筛选条件。",foreground="#b04444")
        else: self.status.configure(text=f"已筛选 {len(kept)} 种；本结果用于材料初步筛选，最终选型仍需结合载荷计算、尺寸、寿命、热处理、供应状态和相关标准确认。")
    def _current(self):
        s=self.tree.selection(); return self.results[int(s[0])] if s and s[0].isdigit() and int(s[0])<len(self.results) else None
    def _val(self,m,k): return "暂无数据" if m.get(k) in (None,"") else str(m[k])
    def _source(self,id):
        c=sqlite3.connect(self.db_path); r=c.execute("select source_name,material_condition,retrieved_date from parameter_sources where material_id=? order by id desc limit 1",(id,)).fetchone(); c.close(); return "；".join(map(str,r)) if r else "DOCX 原文 / 暂无参数级来源"
    def detail(self):
        x=self._current();
        if not x:return
        m=x["material"]; w=tk.Toplevel(self); w.title("材料详情"); w.geometry("760x600"); text=tk.Text(w,wrap="word",font=("Microsoft YaHei UI",10)); text.pack(fill="both",expand=True,padx=15,pady=15); lines=[f"{m['name']}（{m.get('grade') or '牌号未记录'}）",f"匹配分数：{x['score']}/100",f"数据完整度：{x['completeness']}%",f"推荐理由：{explain(x,self.current_request)}","","关键参数："]
        for k,l in [("tensile_strength_mpa","抗拉强度"),("yield_strength_mpa","屈服强度"),("elastic_modulus_gpa","弹性模量"),("density_g_cm3","密度"),("temperature_max_c","最高工作温度"),("hardness","硬度"),("fatigue_strength_mpa","疲劳强度"),("thermal_conductivity_w_mk","热导率"),("thermal_expansion_um_mk","热膨胀系数")]: lines.append(f"{l}：{self._val(m,k)}")
        lines += ["",f"适用制造工艺：{self._val(m,'machinability')}",f"典型用途/限制：{self._val(m,'typical_uses')}",f"数据来源：{self._source(m['id'])}"]; text.insert("1.0","\n".join(lines)); text.configure(state="disabled")
    def add_compare(self):
        x=self._current()
        if not x:
            messagebox.showinfo("加入对比", "请先选择一条推荐材料。")
            return
        if x not in self.compare:
            self.compare.append(x)
        self.status.configure(text=f"已加入对比 {len(self.compare)} 种材料")

    def show_compare(self):
        if not self.compare:
            messagebox.showinfo("材料对比", "请先从推荐结果中加入材料。")
            return
        window=tk.Toplevel(self); window.title("材料横向对比"); window.geometry("1000x560")
        frame=ttk.Frame(window,padding=10); frame.pack(fill="both",expand=True)
        columns=["parameter"]+[str(i) for i in range(len(self.compare))]
        tree=ttk.Treeview(frame,columns=columns,show="headings"); tree.heading("parameter",text="参数"); tree.column("parameter",width=160)
        for i,result in enumerate(self.compare):
            material=result["material"]; tree.heading(str(i),text=f"{material['name']} / {material.get('grade') or '无牌号'}"); tree.column(str(i),width=220)
        rows=[("匹配度","score"),("数据完整度","completeness"),("抗拉强度","tensile_strength_mpa"),("屈服强度","yield_strength_mpa"),("弹性模量","elastic_modulus_gpa"),("密度","density_g_cm3"),("最高工作温度","temperature_max_c"),("硬度","hardness"),("耐腐蚀性","corrosion_resistance"),("加工性能","machinability"),("焊接性能","weldability")]
        for label,key in rows:
            values=[]
            for result in self.compare:
                values.append(result.get(key) if key in result else self._val(result["material"],key))
            tree.insert("", "end", values=(label,*values))
        tree.pack(fill="both",expand=True)
    def _database(self):
        self.dbtab.columnconfigure(0,weight=1); self.dbtab.rowconfigure(1,weight=1); bar=ttk.Frame(self.dbtab); bar.grid(row=0,column=0,sticky="ew",pady=(0,8)); self.query=tk.StringVar(); ttk.Label(bar,text="搜索").pack(side="left"); ttk.Entry(bar,textvariable=self.query,width=28).pack(side="left",padx=6); ttk.Button(bar,text="刷新",command=self.refresh).pack(side="left"); ttk.Button(bar,text="查看详情",command=self.db_detail).pack(side="right")
        frame=ttk.Frame(self.dbtab); frame.grid(row=1,column=0,sticky="nsew"); frame.columnconfigure(0,weight=1); frame.rowconfigure(0,weight=1); self.dbtree=ttk.Treeview(frame,columns=("id","name","grade","category","temp","source"),show="headings")
        for k,t,w in [("id","ID",50),("name","材料",180),("grade","牌号",120),("category","类别",180),("temp","最高温度",100),("source","数据来源",300)]: self.dbtree.heading(k,text=t); self.dbtree.column(k,width=w)
        self.dbtree.grid(row=0,column=0,sticky="nsew"); ttk.Scrollbar(frame,orient="vertical",command=self.dbtree.yview).grid(row=0,column=1,sticky="ns"); self.refresh()
    def refresh(self):
        for x in self.dbtree.get_children():self.dbtree.delete(x)
        q=self.query.get().lower();
        for m in self.materials():
            if q and q not in f"{m['name']} {m.get('grade') or ''}".lower():continue
            self.dbtree.insert("","end",iid=str(m['id']),values=(m['id'],m['name'],m.get('grade') or "暂无数据",m.get('category') or "暂无数据",self._val(m,'temperature_max_c'),self._source(m['id'])))
    def db_detail(self):
        s=self.dbtree.selection();
        if not s:return
        m=next((x for x in self.materials() if str(x['id'])==s[0]),None)
        if not m:return
        w=tk.Toplevel(self); w.title("材料详情"); w.geometry("760x600"); text=tk.Text(w,wrap="word"); text.pack(fill="both",expand=True,padx=15,pady=15); text.insert("1.0",f"材料：{m['name']}\n牌号：{m.get('grade') or '暂无数据'}\n类别：{m.get('category') or '暂无数据'}\n\n典型用途：{self._val(m,'typical_uses')}\n来源：{self._source(m['id'])}"); text.configure(state="disabled")

def launch(db_path,rules_path): DesktopApp(db_path,rules_path).mainloop()
