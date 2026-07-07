#!/usr/bin/env python3
"""从 Markdown 精读报告中提取结构化元数据，供飞书 Base 记录使用。"""

import argparse
import json
import re
from pathlib import Path
from typing import Any


def read_report(path: Path) -> str:
   if not path.exists():
       raise FileNotFoundError(f"Report not found: {path}")
   return path.read_text(encoding="utf-8")


def extract_section(text: str, heading: str, level: int = 2) -> str:
   """逐行提取 Markdown 中指定标题下的内容，直到下一个同层级或更高层级标题。"""
   lines = text.splitlines()
   prefix = "#" * level + " "
   start = None
   for i, line in enumerate(lines):
       if line.startswith(prefix) and line[len(prefix):].strip() == heading:
           start = i + 1
           break
   if start is None:
       return ""

   result = []
   lower_prefix = "#" * (level + 1)
   for line in lines[start:]:
       if line.startswith("#"):
           # 同层级或更高层级标题则停止；更低层级标题继续收集
           if not line.startswith(lower_prefix):
               break
       result.append(line)
   return "\n".join(result).strip()


def extract_table_field(text: str, field_name: str) -> str:
   """从基本信息表格中提取指定字段的值。"""
   pattern = rf"^\|\s*{re.escape(field_name)}\s*\|\s*(.*?)\s*\|"
   for line in text.splitlines():
       match = re.search(pattern, line)
       if match:
           return match.group(1).strip()
   return ""


def extract_tldr(text: str) -> str:
   """从一屏精炼卡片提取 TL;DR 一句话（`> **TL;DR（一句话）**：...`）。"""
   for line in text.splitlines():
       stripped = line.strip().lstrip(">").strip()
       m = re.match(r"\*\*TL;DR[^*]*\*\*[：:]\s*(.+)", stripped)
       if m:
           return m.group(1).strip()
   return ""


def extract_card_field(text: str, keyword: str) -> str:
   """从一屏精炼卡片的两列表格里，按行首关键字提取该行的值。

   卡片行形如 `| 💡 **核心洞见 / 最关键的一招** | 值 |`。
   """
   for line in text.splitlines():
       if not line.strip().startswith("|"):
           continue
       cells = [c.strip() for c in line.strip().strip("|").split("|")]
       if len(cells) < 2:
           continue
       label = cells[0]
       if keyword in label:
           value = cells[1].strip()
           if value and not set(value) <= {"-"}:  # 跳过分隔行
               return value
   return ""


def extract_one_sentence_insight(text: str) -> str:
   """『一句话 Insight』= 卡片里的核心洞见；退化到 TL;DR。"""
   insight = extract_card_field(text, "核心洞见")
   if insight:
       return insight
   tldr = extract_tldr(text)
   if tldr:
       return tldr
   # 向后兼容旧版报告的 `## 0. 一句话总览`
   legacy = extract_section(text, "0. 一句话总览", level=2)
   for line in legacy.splitlines():
       if line.strip():
           return line.strip()
   return ""


def extract_enlightenment(text: str) -> str:
   """提取『10. 认知启示与应用拓展』的浓缩摘要，供 Base 记录使用。"""
   section = extract_section(text, "10. 认知启示与应用拓展（Enlightened · 编者视角）", level=2)
   if not section:
       # 容错：标题文案可能被 LLM 轻微改写，退化为前缀匹配
       for heading in ("10. 认知启示与应用拓展", "认知启示与应用拓展"):
           lines = text.splitlines()
           for i, line in enumerate(lines):
               if line.startswith("## ") and heading in line:
                   section = extract_section(text, line[3:].strip(), level=2)
                   break
           if section:
               break
   if not section:
       return ""
   bullets = [b for b in extract_bullet_list(section) if len(b) > 4]
   return "\n".join(f"- {b}" for b in bullets[:6])


def extract_bullet_list(text: str) -> list[str]:
   """把一段以 '- ' 或 '* ' 开头的列表转成字符串列表。"""
   items = []
   for line in text.splitlines():
       line = line.strip()
       if line.startswith(("- ", "* ")):
           items.append(line[2:].strip())
   return items


def extract_innovations(text: str) -> list[str]:
   """提取 6. 创新点逐条拆解 下的逐条内容。"""
   section = extract_section(text, "6. 创新点逐条拆解", level=2)
   blocks = re.split(r"(?:^|\n)### 创新点 \d+：", section)
   results = []
   for block in blocks[1:]:
       lines = [ln.strip("- ").strip() for ln in block.splitlines() if ln.strip().startswith("-")]
       summary = "；".join(lines[:3]) if lines else block.strip().split("\n")[0]
       results.append(summary)
   return results


def extract_limitations(text: str) -> list[str]:
   """提取 7. 局限性与开放问题 下的列表项。"""
   section = extract_section(text, "7. 局限性与开放问题", level=2)
   return extract_bullet_list(section)


def extract_topic_type(text: str) -> str:
   """从基本信息表格的话题类型字段提取，或根据标题/内容推断。"""
   topic = extract_table_field(text, "话题类型")
   if topic:
       candidates = [t.strip() for t in re.split(r"[/,|]", topic) if t.strip()]
       return candidates[0]
   return "Other"


def extract_venue_year(text: str) -> tuple[str, str]:
   """从发表信息中提取 venue 和 year。"""
   pub = extract_table_field(text, "发表信息")
   year_match = re.search(r"20\d{2}", pub)
   year = year_match.group(0) if year_match else ""
   venue = pub.replace(year, "").strip(", ") if year else pub
   return venue, year


def extract_topic_tags(text: str) -> list[str]:
    """从基本信息表格提取关键词。支持中英文新旧字段名。"""
    tags_str = extract_table_field(text, "Key Topics / 论文关键词")
    if not tags_str:
        tags_str = extract_table_field(text, "Key Topics")
    if not tags_str:
        tags_str = extract_table_field(text, "论文关键词")
    if not tags_str:
        tags_str = extract_table_field(text, "核心话题标签")
    if not tags_str:
        tags_str = extract_table_field(text, "话题类型")
    if not tags_str:
        return []
    parts = re.split(r"[/,|、]", tags_str)
    return [t.strip() for t in parts if t.strip()]


def parse_report(path: Path) -> dict[str, Any]:
   text = read_report(path)
   venue, year = extract_venue_year(text)
   innovations = extract_innovations(text)
   limitations = extract_limitations(text)

   return {
       "论文标题": extract_table_field(text, "标题"),
       "作者": extract_table_field(text, "作者"),
       "发表信息": extract_table_field(text, "发表信息"),
       "Key Topics": ", ".join(extract_topic_tags(text)),
       "论文话题类型": extract_topic_type(text),
       "一句话 Insight": extract_one_sentence_insight(text),
       "认知启示": extract_enlightenment(text),
       "核心方法": extract_table_field(text, "核心方法"),
       "主要结论": extract_table_field(text, "主要结论"),
       "创新点": "\n".join(f"{i+1}. {item}" for i, item in enumerate(innovations)) if innovations else "",
       "局限性": "\n".join(f"{i+1}. {item}" for i, item in enumerate(limitations)) if limitations else "",
       "Venue": venue,
       "Year": year,
       "年份": year,
       "本地报告路径": str(path.resolve()),
   }


def main():
   parser = argparse.ArgumentParser(description="Extract paper metadata from a deep-reading Markdown report.")
   parser.add_argument("--report", required=True, type=Path, help="Path to the Markdown report.")
   parser.add_argument("--json", action="store_true", help="Print extracted metadata as JSON.")
   args = parser.parse_args()

   meta = parse_report(args.report)
   if args.json:
       print(json.dumps(meta, ensure_ascii=False, indent=2))
   else:
       for key, value in meta.items():
           print(f"{key}: {value}")


if __name__ == "__main__":
   main()
