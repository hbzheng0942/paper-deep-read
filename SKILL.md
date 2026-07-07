---
name: paper-deep-read
description: 英文技术论文精读并同步到飞书。把 PDF / arXiv 论文读成「专业研究者水平」的结构化中文报告——开场一屏精炼卡片（含精读者评级）、WHAT/WHY/HOW/EXPERIMENT 主体（figure/table 精确裁剪后按语义嵌入、关键判断带证据锚点）、结尾认知启示（技术迁移 + 业界应用 + 二阶思考 + 可延伸 idea），再通过 lark-cli 导入飞书文档（含嵌入截图）并写入「论文阅读记录」多维表格。当用户给出论文 PDF / arXiv 链接 / 论文标题，要求精读、写精读报告、拆解论文、或把论文记录到飞书时使用。
---

# 论文精读 + 飞书记录 Skill

把一篇英文技术论文读成「不看原文也能懂、且能生出新认知」的中文精读报告，并同步到飞书。

## 何时使用

- 用户给出论文 PDF、arXiv 链接或标题，要求 **精读 / 深读 / 拆解 / 写精读报告**。
- 用户要把论文 **记录 / 归档到飞书**（文档 + 多维表格）。

## 前置要求

- `lark-cli auth status` 已登录
- `pip install -r requirements.txt` 已完成
- `config.toml` 已配置飞书 Base token / table_id
- **不需要配置 LLM API key**：本 skill 由调用它的 Agent（Claude / Codex）直接完成报告撰写。

---

## 质量门禁（硬性约束 · 不可跳过）

> 以下门禁是**自动执行的二进制检查**。任何一条未通过 = 报告不合格，必须停止并重写对应部分。

### G1. 批次上限

单次调用最多处理 **2 篇**论文。超过 2 篇需分批，每批独立完成精读 + 飞书同步后再继续下一批。

### G2. 报告长度下限

`wc -l reports/<SLUG>/report.md` 输出必须 **≥ 250 行**。

### G3. 必需章节完整性

报告必须包含以下 **11 个一级章节**（`## ` 前缀），不可合并、不可省略：

- `## 🎯 一屏精炼卡片`
- `## 1. 论文基本信息`
- `## WHAT · 作者做了什么`
- `## WHY · 作者为什么要做这件事`
- `## HOW · 作者具体怎么做`
- `## EXPERIMENT · 作者如何验证`
- `## 6. 创新点逐条拆解`
- `## 7. 局限性与开放问题`
- `## 8. 初学者背景补充`
- `## 9. 复现与进一步阅读建议`
- `## 10. 认知启示与应用拓展（Enlightened · 编者视角）`
- `## 11. 完整性自检`

检查命令：`grep -c "^## " reports/<SLUG>/report.md` 输出必须 **≥ 12**。

### G4. 关键子节完整性

HOW（第 4 节）必须包含 `### 4.1` 到 `### 4.6` 中的 **至少 4 项**。
检查命令：`grep -c "^### 4\." reports/<SLUG>/report.md` 输出必须 **≥ 4**。

EXPERIMENT（第 5 节）必须包含 `### 5.1` 到 `### 5.8` 中的 **至少 5 项**（其中 5.1、5.2、5.5、5.6、5.8 为强制项）。
检查命令：`grep -c "^### 5\." reports/<SLUG>/report.md` 输出必须 **≥ 5**。

### G5. 认知启示子节完整性

第 10 节必须包含 `### 10.1` 到 `### 10.6` 中的 **至少 3 项**子节标题，且**必须有至少 1 条** `[I<n>]` 格式的可延伸 idea。
检查命令：`grep -c "^### 10\." reports/<SLUG>/report.md` ≥ 3 且 `grep -c "\[I[0-9]\]" reports/<SLUG>/report.md` ≥ 1。

### G6. 图表嵌入率

report 中引用的 `](figures/` 次数必须 ≥ `figure_manifest.json` 中 `image_path` 非空项数量的 **50%**。
检查命令：对比 `grep -c "](figures/" reports/<SLUG>/report.md` 与 `python3 -c "import json; print(sum(1 for i in json.load(open('reports/<SLUG>/figure_manifest.json')) if i['image_path']))"`

### G7. 证据锚点密度

WHAT / WHY / HOW / EXPERIMENT 四个章节中，**每个至少出现 1 次** `(Evidence: ...)` 格式的证据锚点。
检查命令：`grep -c "(Evidence:" reports/<SLUG>/report.md` 输出必须 **≥ 4**。

---



## 飞书目录与 Base

- **报告文件夹**：`https://my.feishu.cn/drive/folder/DviafuRlll7FvGdz1a3c36Mhnzh`（`config.toml` 中的 `folder_token`）
- **论文阅读记录 Base**：`https://my.feishu.cn/base/GHMSbT7JkawLXNstXU9cR6YJnAf?table=tblmuM8acOv8fP4L`
- 报告导入时会自动上传 figure 截图并嵌入文档
- Base 中通过「Key Topics」字段（细分关键词）和「精读者评级」字段（必读/值得读/速览/存档）快速筛选和评估论文

## 关键产出（区别于「论文摘要」的两处硬要求）

1. **🎯 一屏精炼卡片**：报告开头即给出可扫读的 TL;DR 卡（核心洞见 / 关键结果 / 适用场景 / 精读者评级），能脱离正文独立分享。
2. **10. 认知启示（Enlightened）**：报告结尾从论文内部跳出——技术迁移、业界应用与商业价值、二阶思考、可延伸 idea。**必须具体到能落地、能验证、能反驳，禁空话**。

## 执行步骤

设 `SLUG` 为论文短名，工作目录 `reports/<SLUG>/`，`DATE` 为当前日期 `YYYY-MM-DD`。

1. **取 PDF**：本地路径直接用；arXiv 链接 `curl -L -o /tmp/<SLUG>.pdf <pdf_url>`。

2. **精确裁剪 figure/table**：
   ```bash
   python scripts/extract_figures.py --pdf <pdf> --output reports/<SLUG> --method pymupdf
   ```
   产出 `reports/<SLUG>/figures/*.png` 与 `figure_manifest.json`。

3. **提取 PDF 全文**：
   ```bash
   python scripts/generate_report.py --pdf <pdf> --output reports/<SLUG> --extract-only
   ```
   产出 `reports/<SLUG>/extracted_text.txt`。

4. **Agent 亲自精读并撰写报告**：
   
   依次读取并撰写 `reports/<SLUG>/report.md`：
   - `templates/report_template.md` — 结构模板
   - `templates/evidence_card_template.md` — 证据卡片格式
   - `reports/<SLUG>/extracted_text.txt` — PDF 全文
   - `reports/<SLUG>/figure_manifest.json` — 图表清单

   **撰写规则**：
   - 严格按模板结构与层级
   - **必须完整写满「一屏精炼卡片」与「第 10 节 认知启示」**
   - figure 只引用 `image_path` 非空的项，路径原样使用（如 `![](figures/figure-001.png)`）
   - 每个图表后 1–3 段解释
   - 论文事实附证据锚点 `(Evidence: Sec.X, Fig.Y, p.Z)`
   - 个人推断标 `(Inference ...)`，不确定标 `(Not clearly stated in the paper)`
   - **Key Topics / 论文关键词**：在读论文的过程中确定 3–5 个细分关键词（不是 CV/NLP 这种大概念，而是细分方向，如 `articulated objects`, `part mobility analysis`, `dual-image conditioning`）。**必须写入报告 YAML frontmatter**（`Key Topics: ...`），供飞书同步时自动提取写入 Base 的「Key Topics」字段。
   - **精读者评级**：读完论文后在报告中给出评级（**必读** / **值得读** / **速览** / **存档**），置于一屏精炼卡片的「⭐ 精读者评级」行，附带一句理由。飞书同步时自动提取写入 Base 的「精读者评级」字段。

5. **硬性门禁自检**（不可跳过，任一门禁未通过则重写报告至通过）：

   逐条执行以下检查命令并输出结果。所有门禁通过后才许进入步骤 6：

   ```bash
   echo "=== G2: 行数 ===" && wc -l reports/<SLUG>/report.md
   echo "=== G3: 章节数 >= 12 ===" && grep -c "^## " reports/<SLUG>/report.md
   echo "=== G4: HOW 子节 >= 4 ===" && grep -c "^### 4\." reports/<SLUG>/report.md
   echo "=== G4: EXPERIMENT 子节 >= 5 ===" && grep -c "^### 5\." reports/<SLUG>/report.md
   echo "=== G5: 认知启示子节 >= 3 ===" && grep -c "^### 10\." reports/<SLUG>/report.md
   echo "=== G5: 可延伸 idea >= 1 ===" && grep -c "\[I[0-9]\]" reports/<SLUG>/report.md
   echo "=== G7: Evidence 锚点 >= 4 ===" && grep -c "(Evidence:" reports/<SLUG>/report.md
   echo "=== G6: 图表嵌入 ===" && echo "fig refs: $(grep -c '](figures/' reports/<SLUG>/report.md)" && echo "available: $(python3 -c "import json; print(sum(1 for i in json.load(open('reports/<SLUG>/figure_manifest.json')) if i['image_path']))")"
   ```

6. **同步飞书**：
   ```bash
   python scripts/publish_to_feishu.py --config config.toml \
     --report reports/<SLUG>/report.md --figures reports/<SLUG>/figures \
     --key-topics "articulated objects, part mobility analysis" \
     --rating "值得读"
   ```
   脚本会自动：
   - 上传 figures/ 中的图片到飞书 Drive
   - 替换本地图片路径为飞书 URL
   - 按 `{日期}_{发表地}_{年份}_{短标题}` 格式导入为 docx（含嵌入截图）
   - 写入或更新 Base 阅读记录（含「Key Topics」「精读者评级」「核心话题标签」等全部字段）

   首次或预览时先加 `--dry-run`。

## 注意

- 不编造论文未给出的内容；不确定标 `(Not clearly stated in the paper)`。
- Base 的「Key Topics」字段存储细分关键词（如 `articulated objects, part mobility analysis`），与「核心话题标签」select 字段（如 `3D Generation`）互补：前者自由文本便于搜索、后者固定选项便于筛选。
- Base 的「精读者评级」字段（select：必读/值得读/速览/存档）帮助后续按优先级排期阅读。
- 详细原理、目录结构见 [README.md](README.md)。
