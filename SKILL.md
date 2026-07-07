---
name: paper-deep-read
description: 英文技术论文精读并同步到飞书。把 PDF / arXiv 论文读成「专业研究者水平」的结构化中文报告——开场一屏精炼卡片、WHAT/WHY/HOW/EXPERIMENT 主体（figure/table 精确裁剪后按语义嵌入、关键判断带证据锚点）、结尾认知启示（技术迁移 + 业界应用 + 二阶思考 + 可延伸 idea），再通过 lark-cli 导入飞书文档（含嵌入截图）并写入「论文阅读记录」多维表格。当用户给出论文 PDF / arXiv 链接 / 论文标题，要求精读、写精读报告、拆解论文、或把论文记录到飞书时使用。
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

## 飞书目录与 Base

- **报告文件夹**：`https://my.feishu.cn/drive/folder/DviafuRlll7FvGdz1a3c36Mhnzh`（`config.toml` 中的 `folder_token`）
- **论文阅读记录 Base**：`https://my.feishu.cn/base/GHMSbT7JkawLXNstXU9cR6YJnAf?table=tblmuM8acOv8fP4L`
- 报告导入时会自动上传 figure 截图并嵌入文档
- Base 中通过「Key Topics / 论文关键词」字段按方向筛选论文

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
   - **Key Topics / 论文关键词**：在读论文的过程中确定 2–4 个具体关键词（不是 CV/NLP 这种大概念，而是细分方向，如 `articulated objects`, `part mobility analysis`），精读结束后通过 `--key-topics` 参数传入发布脚本写入 Base

5. **自检**：对照 `report.md` 末尾的完整性自检表逐项核对。

6. **同步飞书**：
   ```bash
   python scripts/publish_to_feishu.py --config config.toml \
     --report reports/<SLUG>/report.md --figures reports/<SLUG>/figures \
     --key-topics "articulated objects, part mobility analysis"
   ```
   脚本会自动：
   - 上传 figures/ 中的图片到飞书 Drive
   - 替换本地图片路径为飞书 URL
   - 按 `{日期}_{发表地}_{年份}_{短标题}` 格式导入为 docx（含嵌入截图）
   - 写入或更新 Base 阅读记录

   首次或预览时先加 `--dry-run`。

## 注意

- 不编造论文未给出的内容；不确定标 `(Not clearly stated in the paper)`。
- Base 的「Key Topics / 论文关键词」使用细分方向词（如 `articulated objects`），方便按话题检索。
- 详细原理、目录结构见 [README.md](README.md)。
