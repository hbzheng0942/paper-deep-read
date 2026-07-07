# 论文精读 + 飞书文档 / Base 记录工作流

一个可本地运行的英文技术论文精读工作流：把 PDF 转成结构化的 Markdown 精读报告（WHAT / WHY / HOW / EXPERIMENT），自动抽取并嵌入论文 figure/table，再通过飞书 CLI 同步到飞书文档和「论文阅读记录」多维表格。

## 这个方案借鉴了什么

| 项目 | 借鉴点 | 为什么值得用 |
|---|---|---|
| [MoonKirito/evidence-grounded-paper-deep-read](https://github.com/MoonKirito/evidence-grounded-paper-deep-read) | **核心骨架**：结构化报告模板、证据锚点、figure/table 精确裁剪与嵌入、分阶段生成避免一次性塞入全文 | 最贴近「WHAT/WHY/HOW/EXPERIMENT + figure 自然嵌入」的需求；已经把报告写成"不看原论文也能懂"的级别 |
| [c-narcissus/agent-paper-grounded-reading](https://github.com/c-narcissus/agent-paper-grounded-reading) | **Evidence grounding**：claim ID、traceability manifest、research-generative lens | 如果后续需要把报告 claim 回查到 PDF 原文段落，或想从论文里提炼新 idea，可以直接叠加 |
| [LazyDreamingDog/paper-reading-workflow](https://github.com/LazyDreamingDog/paper-reading-workflow) | **轻量 Git-backed 工作流**：.agent 触发、笔记命名规范、毒舌评论 | 适合维护长期个人/团队论文库；命名规范 `【VENUE‘YEAR】short-title.md` 可直接复用 |
| [chtc66/academic-skills](https://github.com/chtc66/academic-skills) | **飞书集成思路**：paper-feishu-digest 用脚本 + webhook 推送到飞书 | 证明了本地脚本 + 飞书 CLI 是可行的；我们把它改成"Markdown → docx + Base 记录" |
| [HughYau/AcademicForge](https://github.com/HughYau/AcademicForge) | **Skill 组织方式**：按场景拆 skill、用 registry 管理 | 如果将来要把这个工作流封装成 Codex skill，可以参考它的目录结构和安装脚本 |
| [Xueyang-Song/paper-pilot](https://github.com/Xueyang-Song/paper-pilot) | **桌面端完整体验**：PDF 阅读、chat、artifact 联动 | 它证明了很多自动化方向（本地 agent、artifact 管理），但它是 Electron 应用，不适合本次"CLI + 飞书"的目标 |

**选型结论**：以 `evidence-grounded-paper-deep-read` 的模板和分阶段生成为核心，保留 figure/table 嵌入与证据锚点；用本地 Python 脚本补齐「Markdown → 飞书 docx」和「Base 阅读记录」两个缺口；把 `agent-paper-grounded-reading` 的 traceability manifest 和 research lens 作为可选增强层；用 `paper-reading-workflow` 的文件命名和 Git 习惯做长期笔记管理。

## 工作流概览

```text
PDF / arXiv URL / 标题
  ├─ 阶段 1: 提取（文本、figure、table、caption、公式）
  ├─ 阶段 2: 建索引（WHAT / WHY / HOW / EXPERIMENT 证据卡）
  ├─ 阶段 3: 分阶段生成 Markdown 报告
  │    ├─ WHAT：作者做了什么（任务、贡献、与已有工作差异）
  │    ├─ WHY：为什么做（背景、gap、动机、重要性）
  │    ├─ HOW：具体怎么做（方法总览、模块拆解、公式、实现细节）
  │    └─ EXPERIMENT：如何验证（数据集、指标、baseline、结果、消融）
  ├─ 阶段 4: 验证报告完整性
  └─ 阶段 5: 飞书同步
       ├─ Markdown → lark-cli drive +import --type docx → 飞书文档
       └─ 元数据 → lark-cli base +record-upsert → 论文阅读记录 Base
```

## 目录结构

```text
paper-reading-workflow/
├── README.md                        # 本文件
├── SKILL.md                         # Skill 入口：给 Agent 的执行步骤
├── config.example.toml              # 飞书 token / folder / Base / LLM 配置示例
├── requirements.txt                 # Python 依赖
├── templates/
│   ├── report_template.md           # 一屏卡片 + WHAT/WHY/HOW/EXPERIMENT + 认知启示 模板
│   ├── evidence_card_template.md    # 证据卡模板
│   └── base_schema.json             # 论文阅读记录 Base 字段 schema
├── scripts/
│   ├── extract_figures.py           # 精确裁剪 figure/table（pdffigures2 / PyMuPDF）
│   ├── generate_report.py           # PDF → 分阶段生成 Markdown 精读报告（LLM）
│   ├── extract_paper_meta.py        # 从 report.md 提取元数据（含认知启示）
│   ├── publish_to_feishu.py         # Markdown → 飞书 docx + Base 记录
│   └── setup_base.py                # 一键创建/初始化阅读记录 Base（可选）
└── examples/
    └── example-report.md            # 示例报告
```

## 报告结构

最终 `report.md` 采用 **WHAT / WHY / HOW / EXPERIMENT** 四段式，同时保留证据锚点和 figure/table 自然嵌入。

```markdown
# 论文精读报告：<Paper Title>

## 🎯 一屏精炼卡片          # TL;DR + 核心洞见 + 关键结果 + 精读者评级，脱离正文可独立读懂
## 1. 论文基本信息
## WHAT · 作者做了什么
  ### 2.1 核心任务
  ### 2.2 主要贡献
  ### 2.3 与已有工作的关键差异
## WHY · 作者为什么要做这件事
  ### 3.1 背景问题
  ### 3.2 现有方法不足
  ### 3.3 作者动机
  ### 3.4 问题重要性
## HOW · 作者具体怎么做
  ### 4.1 方法总览
  ### 4.2 流程逐步拆解
  ### 4.3 模块级细读
  ### 4.4 公式与关键技术细节
  ### 4.5 训练 / 优化 / 推理细节
  ### 4.6 实现细节
## EXPERIMENT · 作者如何验证
  ### 5.1 实验要回答的问题
  ### 5.2 数据集
  ### 5.3 评价指标
  ### 5.4 对比方法
  ### 5.5 主要结果
  ### 5.6 消融实验
  ### 5.7 额外分析
  ### 5.8 实验证明了什么 / 没有证明什么
## 6. 创新点逐条拆解
## 7. 局限性与开放问题
## 8. 初学者背景补充
## 9. 复现与进一步阅读建议
## 10. 认知启示与应用拓展（Enlightened）  # 编者视角：技术迁移 / 业界应用 / 二阶思考 / 可延伸 idea
## 11. 完整性自检
```

> **两处关键增量**（区别于「论文摘要」）：
> - **一屏精炼卡片**：开场即给出可扫读的 TL;DR 卡，30 秒抓全文，可独立分享。
> - **认知启示（Enlightened）**：报告末尾从论文内部跳出，做技术迁移、业界落地、二阶思考与可延伸 idea——这是「专业研究者精读」与「机械转述」的分水岭，也是唯一显式允许并鼓励延展推断的章节。

### Figure / Table 嵌入规则

- **不要**单独开"图表附录"或"Figure Reading"章节。
- 把 figure/table 放到它被用作证据的位置：
  - 任务定义图 → `WHAT`
  - motivation/gap 图 → `WHY`
  - 架构/算法/公式图 → `HOW`
  - 结果表、消融表、可视化 → `EXPERIMENT`
- 使用相对路径引用本地裁剪图：
  ```markdown
  ![Figure 1: Overall framework](figures/figure-001-overall-framework.png)
  ```
- 每个图/表后面用 1-3 段解释：它显示什么、如何读、支撑哪个 claim、初学者可能误解什么。

### 证据锚点规则

```markdown
(Evidence: Sec. 3.2, Fig. 2, p. 5)
(Inference from Sec. 4.1 and Table 3)
(Not clearly stated in the paper)
```

- 不编造 motivation、baseline、数据集、指标、消融、局限性。
- 不确定的内容标记为 `Not clearly stated in the paper`。
- 推断内容标注 `(Inference ...)`。

## 安装依赖

### 1. 飞书 CLI

确保已安装并登录：

```bash
lark-cli auth login
lark-cli auth status
```

### 2. Python 依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`requirements.txt` 至少包含：

```text
pymupdf>=1.24.0
markdown>=3.6
requests
```

### 3. figure/table 抽取（可选但推荐）

`scripts/extract_figures.py` 有两个后端，**默认无需额外依赖**：

- **PyMuPDF（内置 fallback）**：按「Figure 标题在图下方、Table 标题在表上方」的排版惯例，caption 锚定裁剪出图区（含表格），精度够用，产出真实图区而非整页截图。开箱即用。
- **pdffigures2（推荐，精确）**：需 Java + 构建 jar，然后在 `config.toml` 配 `[figure].pdffigures2_jar`：

  ```bash
  git clone https://github.com/allenai/pdffigures2.git
  cd pdffigures2 && sbt assembly   # 生成 target/scala-*/pdffigures2.jar
  ```

  ```bash
  python scripts/extract_figures.py --pdf paper.pdf --output reports/slug \
    --method pdffigures2 --jar /path/to/pdffigures2.jar
  ```

`--method auto`（默认）会在 jar 可用时走 pdffigures2，否则自动退回 PyMuPDF。

## 使用方法

### 快速开始：已有 Markdown 报告，直接推到飞书

1. 复制配置示例并填写：

   ```bash
   cp config.example.toml config.toml
   ```

2. 编辑 `config.toml`：

   ```toml
   [feishu]
   # 目标文件夹 token（空表示根目录）
   folder_token = "fldcxxxxxxxx"
   # 论文阅读记录 Base token
   base_token = "Basexxxxxx"
   # 数据表 ID 或表名
   table_id = "tblxxxxxxxxx"
   ```

3. 运行同步脚本：

   ```bash
   python scripts/publish_to_feishu.py \
     --config config.toml \
     --report reports/【NeurIPS‘2024】xxx/report.md \
     --figures reports/【NeurIPS‘2024】xxx/figures
   ```

脚本会：

- 解析 `report.md` 提取标题、作者、venue、年份、topic、insight 等字段。
- 调用 `lark-cli drive +import --type docx` 把 Markdown 导入成飞书文档。
- 调用 `lark-cli base +record-upsert` 在阅读记录 Base 中新增一行。

### 完整流程：从 PDF 到飞书

```bash
# 1. 准备 PDF（本地或 arXiv 下载）
mkdir -p papers && mv paper.pdf papers/

# 2. 精确裁剪 figure/table → figures/ + figure_manifest.json
#    配了 [figure].pdffigures2_jar 用 pdffigures2 精确裁剪；否则自动退回 PyMuPDF caption 锚定裁剪
python scripts/extract_figures.py \
  --pdf papers/paper.pdf --output reports/paper-slug --config config.toml

# 3. 分阶段生成报告（复用第 2 步的 figure_manifest.json；需 OPENAI_API_KEY）
#    默认按 WHAT/WHY → HOW → EXPERIMENT → 创新/局限/背景/复现 → 认知启示 → 一屏卡片 分阶段生成再拼装
python scripts/generate_report.py \
  --pdf papers/paper.pdf --output reports/paper-slug --config config.toml
#    单次生成（短论文/省 token）：加 --single-shot
#    或让 Codex / Claude Code 读 templates/report_template.md + extracted_text.txt 亲自逐段写

# 4. 验证报告（对照 report.md 第 11 节完整性自检表：卡片可独立读懂、认知启示具体可行动、图表已嵌入）

# 5. 同步到飞书
python scripts/publish_to_feishu.py \
  --config config.toml \
  --report reports/paper-slug/report.md \
  --figures reports/paper-slug/figures
```

> 作为 Skill 使用时，上述步骤已固化在 [SKILL.md](SKILL.md)，Agent 会自动串起「裁图 → 生成 → 自检 → 同步」。

## Base「论文阅读记录」Schema

见 [`templates/base_schema.json`](templates/base_schema.json)。核心字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| 论文标题 | text | 英文标题 |
| 作者 | text | 作者列表 |
| 发表信息 | text | `Venue Year` 或 `arXiv:xxxx` |
| 论文话题类型 | select | 如：LLM / Agent / RAG / CV / NLP / System / Theory |
| 阅读日期 | datetime | 本次精读完成时间 |
| 飞书文档 | url | 导入后的 docx 链接 |
| 一句话 Insight | text | 对该论文最核心的判断（取自一屏卡片的「核心洞见」） |
| 认知启示 | text | 技术迁移 / 业界应用 / 二阶思考 / 可延伸 idea 的浓缩摘要 |
| 核心方法 | text | 一句话概括方法 |
| 主要结论 | text | 一句话概括实验结论 |
| 创新点 | text | 逐条摘要 |
| 局限性 | text | 逐条摘要 |
| 复现难度 | select | 高 / 中 / 低 |
| 阅读状态 | select | 已精读 / 速读 / 待读 |
| 标签 | multiselect | 自定义标签 |
| 本地报告路径 | text | Markdown 报告本地路径 |

## 配置示例

```toml
[feishu]
# 目标 Drive 文件夹 token，空字符串表示"我的空间"根目录
folder_token = "fldcnxxxxxxxx"
# Base token（从 Base 分享链接或 lark-cli base +url-resolve 获取）
base_token = "Basexxxxxx"
# 数据表 ID（从 lark-cli base +table-list 获取）
table_id = "tblxxxxxxxx"

[report]
# 默认报告语言
language = "zh"
# 图片最大宽度（飞书 docx 用）
image_max_width = 800
```

## 进阶：叠加 Evidence Traceability

如果需要把报告 claim 回查到 PDF 原文，可叠加 `agent-paper-grounded-reading` 的做法：

1. 在报告中给每个关键 claim 加 ID：
   ```markdown
   - [C2.1] 作者提出 xxx 来解决 yyy 问题。 (Evidence: Sec. 1, p. 2)
   ```
2. 生成 `traceability_manifest.json`，把 claim ID 映射到 PDF 段落或 figure。
3. 用 `scripts/build_reader_bundle.py` 构建静态 evidence reader（可选）。

本工作流默认不强制生成 traceability bundle，但模板中的 evidence marker 已经兼容该扩展。

## 进阶：批量处理多篇论文

```bash
python scripts/batch_publish.py \
  --config config.toml \
  --reports-dir reports/ \
  --max-workers 2
```

批量脚本会串行写入 Base（避免 1254291 并发冲突），并对每篇报告执行 `drive +import`。

## 常见问题

### 1. `drive +import` 导入后图片丢失

当前版本 `publish_to_feishu.py` 尚未自动上传本地相对路径图片。飞书 `drive +import` 导入 Markdown 时，本地图片通常不会随文档一起导入。建议：
- 在本地 Markdown 中保留完整带图版本；
- 或先把图片上传到图床 / 可公开访问的 URL，再在 Markdown 中使用网络图片链接；
- 后续可扩展为自动上传图片到 Drive 并替换链接。

### 2. Base 字段名和脚本里的不一致

首次使用请运行 `python scripts/setup_base.py --config config.toml`，它会根据 `templates/base_schema.json` 创建 Base 和表。如果 Base 已存在，脚本会列出当前字段并提示差异。

### 3. 如何获取 folder_token / base_token / table_id？

```bash
# 从 Base 分享链接解析 token
lark-cli base +url-resolve --url "https://xxx.feishu.cn/base/xxxxx"

# 列出 Base 里的表
lark-cli base +table-list --base-token <base_token> --as user

# 搜索 Drive 文件夹
lark-cli drive +search --query "论文精读" --doc-types folder --as user
```

## 许可证

MIT License. 核心模板和流程参考自上述开源项目。
