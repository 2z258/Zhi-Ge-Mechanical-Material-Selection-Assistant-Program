import json, sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from core.material_engine import hard_filter, score_materials, METRICS, explain, METRIC_NAMES
from desktop_bridge import temp_tiers

HTML='''<!doctype html><meta charset="utf-8"><title>机械材料选型辅助程序</title><style>body{font-family:'Microsoft YaHei UI',Arial,sans-serif;max-width:1100px;margin:28px auto;padding:0 16px;color:#243447;background:#f4f6f9}.hero{background:linear-gradient(135deg,#193a5e,#1e5c8f);color:#fff;padding:26px 28px;border-radius:10px;margin-bottom:16px}.hero h1{margin:0 0 6px;font-size:24px}.hero p{margin:0;color:#cfe0f0;font-size:14px}nav{display:flex;gap:10px;margin-bottom:8px}nav a{text-decoration:none;color:#1c5d94;background:#fff;padding:8px 18px;border-radius:6px;border:1px solid #d7e0ea}section{background:#fff;padding:20px 22px;margin:14px 0;border-radius:10px;box-shadow:0 1px 4px rgba(30,60,90,.08)}input,select,button{padding:8px 10px;margin:4px;border:1px solid #ccd5df;border-radius:6px;font-size:14px;font-family:inherit}button{background:#1c6fae;color:#fff;border:none;cursor:pointer}button:hover{background:#185d93}table{width:100%;border-collapse:collapse}td,th{border:1px solid #e1e7ee;padding:7px;text-align:left;font-size:14px}label{display:inline-block;margin:5px 12px 5px 0}</style><div class=hero><h1>机械材料选型辅助程序</h1><p>数据来源：DOCX 原文；缺失字段不猜测，推荐结果附数据完整度。</p></div><nav><a href="/">材料选型</a><a href="/db">材料数据库</a></nav>{content}'''

def db_rows(db):
    c=sqlite3.connect(db); c.row_factory=sqlite3.Row; rows=c.execute('select * from materials order by section').fetchall(); c.close(); return rows
class Handler(BaseHTTPRequestHandler):
    db=None; rules=None
    def send(self, body): self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(body.encode())
    def do_GET(self):
        rows=db_rows(self.db)
        if self.path.startswith('/db'):
            q=parse_qs(self.path.split('?',1)[1]).get('q',[''])[0].lower(); rows=[r for r in rows if q in (r['name']+' '+(r['grade'] or '')).lower()]
            content='<section><h2>材料数据库</h2><form><input name=q placeholder="搜索名称/牌号"><button>搜索</button></form><table><tr><th>材料</th><th>牌号</th><th>类别</th><th>温度</th><th>原文</th></tr>'+''.join(f"<tr><td>{r['name']}</td><td>{r['grade'] or '暂无数据'}</td><td>{r['category']}</td><td>{r['temperature_max_c'] or '暂无数据'}</td><td><details><summary>查看</summary>{r['raw_text']}</details></td></tr>" for r in rows)+'</table></section>'
        else:
            tiers=temp_tiers(self.db)
            temp_opts='<option value="">请选择温度档位</option>'+''.join(f'<option value="{t["value"]}">{t["label"]}</option>' for t in tiers)
            content='''<section><h2>材料选型</h2><form method=post><label>零件类型 <select name=part_type><option>轴</option><option>齿轮</option><option>底板</option><option>大板</option><option>支架</option><option>框架</option><option>连接件</option><option>外壳</option><option>紧固件</option><option>其他</option></select></label><label>工作温度 <select name=temperature>'''+temp_opts+'''</select></label><label>载荷受力 <input name=loads placeholder="如：扭转,冲击"></label><label>制造方式 <input name=processes placeholder="如：焊接,车削"></label><label>硬性条件 <input name=must_have placeholder="如：焊接"></label><h3>关键性能要求（勾选=需要该性能，不勾选=不强求）</h3>'''+''.join(f'<label><input type=checkbox name=w_{x} value=1> {METRIC_NAMES.get(x, x)}</label>' for x in METRICS)+'<br><button>开始推荐</button></form></section>'
        self.send(HTML.replace('{content}', content))
    def do_POST(self):
        data=parse_qs(self.rfile.read(int(self.headers.get('Content-Length',0))).decode())
        checked=[k for k in data if k.startswith('w_')]
        weights={k[2:]:5 for k in checked}
        if weights: weights.update({k:0 for k in METRICS if k not in weights})
        processes=[x.strip() for x in data.get('processes',[''])[0].split(',') if x.strip()]
        loads=[x.strip() for x in data.get('loads',[''])[0].split(',') if x.strip()]
        must_have=[x.strip() for x in data.get('must_have',[''])[0].split(',') if x.strip()]
        temp_raw=data.get('temperature',[''])[0].strip()
        if not temp_raw and not weights and not loads and not processes and not must_have:
            self.send(HTML.replace('{content}','<section><h2>提示</h2><p>请先填写选型条件（如工作温度、性能权重、载荷受力、加工方式或硬性条件），再点击开始推荐。</p><p><a href="/">返回</a></p></section>')); return
        req={'part_type':data.get('part_type',['轴'])[0],'temperature':float(temp_raw) if temp_raw else None,'processes':processes,'loads':loads,'must_have':must_have,'weights':weights}
        mats=[dict(r) for r in db_rows(self.db)]; kept,rejected=hard_filter(mats,req); ranked,weights=score_materials(kept,req,self.rules,self.db)
        cards=''.join(f"<section><h3>#{i+1} {x['material']['name']}（{x['material']['grade'] or '牌号未记录'}）— {x['score']}/100</h3><p>{explain(x,req)}</p><p>缺失：{', '.join(x['missing']) or '无'}</p></section>" for i,x in enumerate(ranked[:3]))
        rej=''.join(f"<li>{x['material']['name']}：{x['reason']}</li>" for x in rejected) or '<li>无淘汰材料</li>'
        self.send(HTML.replace('{content}', '<section><h2>TOP 3 推荐</h2>'+cards+f'<h2>淘汰材料</h2><ul>{rej}</ul></section>'))
def serve(db,port):
    Handler.db=str(db); Handler.rules=str(__import__('pathlib').Path(__file__).parent/'rules/weights.json')
    print(f'访问 http://127.0.0.1:{port}'); HTTPServer(('127.0.0.1',port),Handler).serve_forever()
