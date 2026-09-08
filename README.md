# 智哥选型

机械材料智能选型辅助系统。软件根据零件类型、载荷、工作温度、性能要求、制造方式和硬性条件，从材料数据库中筛选并推荐候选材料。

## 软件定位

本软件用于材料初步筛选和方案比较，不替代正式工程设计、强度计算、疲劳寿命分析、失效分析或标准审查。

最终选型需要结合实际载荷、结构尺寸、安全系数、热处理状态、供应状态、寿命要求、相关标准和供应商数据确认。

## 快速启动

Windows 下双击项目目录中的：

```text
启动机械材料选型.bat
```

也可以运行：

```powershell
python run.py
```

程序默认打开“智哥选型”桌面界面，使用本地 SQLite 数据库，不需要联网。

如需启动 Web 调试页面：

```powershell
python run.py --web
```

然后打开 `http://127.0.0.1:8765`。也可以使用其他端口：

```powershell
python run.py --web --port 9000
```

### 环境要求

- Windows 10 或更高版本
- Python 3.10 或更高版本
- 桌面版需要 Python 包含 Tcl/Tk 运行库
- 项目提供 `vendor/` 本地依赖目录

如果出现 `init.tcl` 或 Tcl/Tk 错误，请安装带 Tk 支持的 Python。

## 主要功能

- 按零件类型、载荷和工作温度筛选材料
- 支持强度、硬度、刚度、疲劳、韧性、耐磨、耐腐蚀、轻量化等性能要求
- 支持焊接、机加工、铸造、锻造、冲压和热处理等制造方式
- 支持硬性条件筛选
- 输出 TOP 3 推荐结果
- 显示匹配分数、数据完整度、数据风险和推荐理由
- 支持材料详情、数据来源和横向对比
- 支持材料数据库浏览
- 保留 DOCX 原始内容、参数来源和更新日志

## 推荐逻辑

推荐结果由 `core/material_engine.py` 统一生成：

```text
用户需求 → 工程规则解释 → 硬性筛选 → 参数来源校验
→ 指标归一化 → 权重计算 → 综合评分 → TOP 3 推荐
```

重要规则：

- 缺失数据不会被当作 0 分或高分
- 只有具有参数级来源且状态为 `accepted` 的数值参与正式评分
- DOCX 文字描述不会直接转换为核心评分
- 已知明确不满足硬性条件的材料会被淘汰
- 数据未知时显示“暂无数据”或“需核实”
- 综合评分和数据完整度分开显示

## 数据库

唯一运行数据库为：

```text
data/materials.db
```

主要表：

- `materials`：材料主体信息
- `parameter_sources`：参数级来源和核验状态
- `external_properties`：外部数据导入暂存记录
- `material_update_log`：材料更新日志
- `material_update_runs`：更新批次记录

当前数据库中的材料和来源不应通过普通程序运行删除。修改材料数据前应先备份 `data/backups/`。

## DOCX 导入

```powershell
python run.py --import-doc "C:\路径\材料文档.docx"
```

导入器会保存材料原文，并仅提取文档中能够可靠识别的字段。无法确认的参数保持缺失状态，不会自动编造数据。

## 联网更新

更新服务位于 `services/material_update.py`，应遵循：

```text
查询来源 → 提取参数 → 核验牌号/标准/状态 → 生成预览
→ 确认采用 → 自动备份 → 写入数据库 → 记录日志
```

不同标准、热处理状态、供应状态或测试条件的数据不能直接混用。

## 项目结构

```text
qin/
├─ 启动机械材料选型.bat   Windows 启动脚本
├─ run.py                  程序入口
├─ desktop_ui_v2.py       Tkinter 桌面主界面
├─ desktop_bridge.py      桌面界面与核心引擎桥接
├─ ui.py                   本地 Web 调试界面
├─ core/material_engine.py 唯一材料筛选、评分和推荐引擎
├─ rules/engineering_rules.py 工程规则入口
├─ rules/weights.json      零件、载荷和指标权重
├─ services/material_update.py 数据更新和备份服务
├─ data/materials.db       唯一运行数据库
├─ data/import_docx.py      DOCX 导入工具
├─ data/backups/            数据库备份
└─ tests/test_core.py       核心流程测试
```

`work/` 目录中的文件主要用于联网检索、数据解析和人工核验，不属于核心运行模块，也不会提交到 GitHub。

## GitHub 项目结构

```text
智哥选型/
├─ README.md                 项目说明
├─ requirements.txt          依赖说明
├─ run.py                    程序入口
├─ desktop_ui_v2.py          Tkinter 桌面主界面
├─ desktop_bridge.py         桌面界面与核心引擎桥接
├─ ui.py                     本地 Web 调试界面
├─ core/                     材料筛选与评分引擎
├─ rules/                    工程规则和评分权重
├─ services/                 数据更新和备份服务
├─ data/                     运行数据库及导入工具
└─ tests/                    自动化测试
```

本仓库通过 `.gitignore` 排除 Python 缓存、临时检索资料、数据库备份、运行输出和本地 vendored 依赖。

## 测试

```powershell
python -m unittest discover -s tests -v
```

测试覆盖温度筛选、硬性条件、缺失数据、数据完整度、数值评分排序、文字描述不直接加分和 TOP 3 推荐。

检查数据库完整性：

```powershell
python -c "import sqlite3; print(sqlite3.connect('data/materials.db').execute('pragma integrity_check').fetchone()[0])"
```

正常结果为：

```text
ok
```

## 常见问题

### 点击推荐后没有结果

请确认使用项目目录中的 `启动机械材料选型.bat`，关闭旧窗口后重新启动，并检查温度和硬性条件是否冲突。

### 为什么材料分数不高

系统不会为缺失参数补默认分。材料有效参数越少，数据完整度越低，最终可得分上限也会受到影响。

### 为什么文字描述没有直接提高分数

文字描述只能作为参考和风险提示。为避免误推荐，正式评分只采用有明确参数级来源的数据。

## 工程声明

本软件是材料选型辅助工具，不是最终工程设计结论。涉及承载能力、疲劳寿命、稳定性、耐温、耐腐蚀、焊接质量和安全系数的设计，必须结合具体结构、载荷计算、尺寸、制造状态、试验和相关标准进一步确认。
