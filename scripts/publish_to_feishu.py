#!/usr/bin/env python3
"""把 Markdown 精读报告同步到飞书：嵌入截图，导入为 docx + 写入 Base 阅读记录。

工作流：
 1. 上传 figures/ 目录中的图片到飞书 Drive
 2. 替换 Markdown 中的本地图片路径为飞书 URL
 3. 将替换后的 Markdown 导入为飞书 docx
 4. 在 Base 中写入/更新阅读记录

文档按 `{日期}_{发表地}_{年份}_{短标题}` 命名归档到 config.toml 中 folder_token
对应的飞书云盘目录下。
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

try:
   import tomllib
except ModuleNotFoundError:
   import tomli as tomllib

from extract_paper_meta import parse_report


def load_config(path: Path) -> dict[str, Any]:
   with open(path, "rb") as f:
       return tomllib.load(f)


def run_lark_cli(*args: str) -> dict[str, Any]:
   """运行 lark-cli 命令并解析 JSON 输出。"""
   cmd = ["lark-cli", *args]
   print(f"$ {' '.join(cmd)}", file=sys.stderr)
   result = subprocess.run(cmd, capture_output=True, text=True)
   if result.returncode != 0:
       print(f"lark-cli error: {result.stderr}", file=sys.stderr)
       raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
   # lark-cli 输出 JSON 在 stderr 中
   output = result.stderr.strip()
   # upload 命令第一行是进度信息，JSON 在最后一行
   for line in reversed(output.splitlines()):
       try:
           return json.loads(line)
       except json.JSONDecodeError:
           continue
   print(f"Non-JSON output: {result.stderr[:200]}", file=sys.stderr)
   return {"raw": result.stderr}


def create_docx_and_insert_images(
    report_path: Path, name: str, figures_dir: Path | None = None, folder_token: str = ""
) -> dict[str, Any]:
   """用 docs +create 建原生 docx，再用 +media-insert 插入图片。

   drive +import --type docx 不支持嵌入远程图片，改用 docs +create 原生 docx。
   图片通过 docs +media-insert 从本地文件上传为文档内嵌媒体。
   """
   import os as _os

   # 1) 读取 markdown，找到所有本地图片引用，替换为文字占位符
   text = report_path.read_text(encoding="utf-8")
   figures = []
   def _replace_img(m):
       alt, path = m.group(1), m.group(2)
       if path.startswith("figures/") or path.startswith("./figures/"):
           basename = path.replace("./figures/", "").replace("figures/", "")
           figures.append({"alt": alt, "basename": basename})
           return f"[图：{alt}]"
       return m.group(0)
   text_no_img = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _replace_img, text)

   # Write temp file for @file content (large content exceeds arg limit)
   tmp_md = report_path.parent / '_tmp_no_img.md'
   tmp_md.write_text(text_no_img, encoding="utf-8")

   # 2) docs +create 建原生 docx（指定目标文件夹）
   create_args = ["lark-cli", "docs", "+create", "--as", "user",
        "--title", name, "--content", f"@{tmp_md}", "--format", "json"]
   if folder_token:
       create_args += ["--parent-token", folder_token]
   result = subprocess.run(
       create_args,
       capture_output=True, text=True,
   )
   tmp_md.unlink(missing_ok=True)
   output = (result.stderr + result.stdout).strip()
   data = {}
   # Try parsing entire output first (multi-line JSON when using @file),
   # then fall back to line-by-line (single-line JSON from CLI direct)
   try:
       data = json.loads(output)
   except json.JSONDecodeError:
       for line in reversed(output.splitlines()):
           if not line.strip():
               continue
           try:
               data = json.loads(line)
               break
           except json.JSONDecodeError:
               continue
   if not data.get("ok"):
       print(f"docs +create failed: {result.stderr[:500]}", file=sys.stderr)
       return {"ok": False, "error": result.stderr[:500]}

   doc = data.get("data", {}).get("document", {})
   doc_url = doc.get("url", "")
   doc_id = doc.get("document_id", "")
   if not doc_id:
       print(f"docs +create returned no document_id", file=sys.stderr)
       return {"ok": False, "error": "no document_id"}

   print(f"  Created docx: {doc_url}", file=sys.stderr)

   # 3) 插入图片
   if figures_dir and figures_dir.exists() and figures:
       print(f"  Inserting {len(figures)} images...", file=sys.stderr)
       cwd = _os.getcwd()
       for fg in figures:
           img_path = figures_dir / fg["basename"]
           if not img_path.exists():
               print(f"    SKIP {fg['basename']}: file not found", file=sys.stderr)
               continue
           caption = fg["alt"][:100]
           _os.chdir(str(figures_dir))
           try:
               result2 = subprocess.run(
                   ["lark-cli", "docs", "+media-insert", "--as", "user",
                    "--doc", doc_url, "--file", fg["basename"],
                    "--caption", caption, "--align", "center", "--format", "json"],
                   capture_output=True, text=True,
               )
               out2 = (result2.stderr + result2.stdout).strip()
               try:
                   json.loads(out2)
               except json.JSONDecodeError:
                   for line2 in reversed(out2.splitlines()):
                       if not line2.strip():
                           continue
                       try:
                           json.loads(line2)
                           break
                       except json.JSONDecodeError:
                           continue
               # Capture block_id for repositioning
               for line2 in reversed(out2.splitlines()):
                   if not line2.strip():
                       continue
                   try:
                       d2 = json.loads(line2)
                       if d2.get("ok"):
                           fg["img_block_id"] = d2.get("data", {}).get("block_id", "")
                       break
                   except json.JSONDecodeError:
                       continue
               print(f"    OK  {fg['basename']}", file=sys.stderr)
           except Exception as e:
               print(f"    FAIL {fg['basename']}: {e}", file=sys.stderr)
           finally:
               _os.chdir(cwd)

   # 4) Reposition images: move each image after its sentinel text block
   if figures and figures_dir and figures_dir.exists():
       print(f"  Repositioning images...", file=sys.stderr)
       # Fetch document content as XML (default format) with IDs
       result3 = subprocess.run(
           ["lark-cli", "docs", "+fetch", "--as", "user",
            "--doc", doc_url, "--detail", "with-ids", "--format", "json"],
           capture_output=True, text=True,
       )
       out3 = (result3.stderr + result3.stdout).strip()
       try:
           tree = json.loads(out3)
       except json.JSONDecodeError:
           tree = {}
       xml_content = tree.get("data", {}).get("document", {}).get("content", "")

       # Extract sentinel block IDs (the <p> blocks containing [图：)
       sentinel_ids = []
       for match in re.finditer(r'<p\s+id="([^"]+)"[^>]*>\s*\[图：([^\]]*)\]\s*</p>', xml_content):
           sentinel_ids.append(match.group(1))
       
       # Extract image block IDs (in order they appear)
       img_ids = []
       for match in re.finditer(r'<img\s+id="([^"]+)"', xml_content):
           img_ids.append(match.group(1))

       print(f"  Found {len(sentinel_ids)} sentinels, {len(img_ids)} images", file=sys.stderr)

       # Move images and delete sentinels
       moved = 0
       for i in range(min(len(sentinel_ids), len(img_ids))):
           s_id = sentinel_ids[i]
           img_id = img_ids[i]
           basename = figures[i]["basename"] if i < len(figures) else "?"
           
           subprocess.run(
               ["lark-cli", "docs", "+update", "--as", "user",
                "--doc", doc_url, "--command", "block_move_after",
                "--block-id", s_id, "--src-block-ids", img_id, "--format", "json"],
               capture_output=True, text=True,
           )
           subprocess.run(
               ["lark-cli", "docs", "+update", "--as", "user",
                "--doc", doc_url, "--command", "block_delete",
                "--block-id", s_id, "--format", "json"],
               capture_output=True, text=True,
           )
           moved += 1
           print(f"    {basename} -> after {s_id}", file=sys.stderr)
       
       print(f"  Repositioned {moved}/{len(figures)} images", file=sys.stderr)

   return {"ok": True, "url": doc_url, "data": {"url": doc_url, "token": doc_id, "type": "docx"}}


def build_docx_name(meta: dict[str, Any]) -> str:
    """构造带日期的 docx 文件名：{日期}_{发表地}_{年份}_{短标题}"""
    today = datetime.now().strftime("%Y-%m-%d")
    venue = (meta.get("发表信息", "") or "").split(" ")[0] if meta.get("发表信息") else ""
    year = meta.get("年份", "")
    short_title = meta.get("短标题", "") or meta.get("论文标题", "") or "untitled"
    if len(short_title) > 60:
        short_title = short_title[:57] + "..."
    parts = [today]
    if venue:
        parts.append(venue)
    if year:
        parts.append(str(year))
    parts.append(short_title)
    name = "_".join(parts)
    return sanitize_docx_name(f"论文精读：{name}")


def build_base_record(meta: dict[str, Any], doc_url: str | None, key_topics_str: str = "") -> dict[str, Any]:
   """构造 Base 记录 payload。Key Topics 从 CLI --key-topics 传入。"""
   key_topics = key_topics_str or meta.get("Key Topics", "") or meta.get("核心话题标签", "") or meta.get("核心话题关键词", "")
   if isinstance(key_topics, list):
       key_topics = ", ".join(key_topics)

   record = {
       "论文标题": meta.get("论文标题", ""),
       "作者": meta.get("作者", ""),
       "发表信息": meta.get("发表信息", ""),
       "Key Topics": key_topics,
       "阅读日期": datetime.now().strftime("%Y-%m-%d %H:%M"),
       "一句话 Insight": meta.get("一句话 Insight", ""),
       "认知启示": meta.get("认知启示", ""),
       "核心方法": meta.get("核心方法", ""),
       "主要结论": meta.get("主要结论", ""),
       "创新点": meta.get("创新点", ""),
       "局限性": meta.get("局限性", ""),
       "复现难度": "中",
       "阅读状态": "已精读",
       "本地报告路径": meta.get("本地报告路径", ""),
   }
   if doc_url:
       record["飞书文档"] = doc_url

   code_or_link = meta.get("代码", "") or meta.get("代码 / 数据", "") or ""
   status_tags = []
   if code_or_link and code_or_link.lower() not in ("unknown", "n/a"):
       status_tags.append("有代码")
   status_tags.append("可借鉴")
   if status_tags:
       record["标签"] = status_tags
   return record


def write_base_record(base_token: str, table_id: str, record: dict[str, Any]) -> dict[str, Any]:
   payload = json.dumps(record, ensure_ascii=False)
   return run_lark_cli(
       "base", "+record-upsert",
       "--base-token", base_token,
       "--table-id", table_id,
       "--json", payload,
       "--as", "user",
       "--format", "json",
   )


def sanitize_docx_name(name: str) -> str:
   return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "论文精读报告"


def main():
   parser = argparse.ArgumentParser(description="Publish a Markdown paper-reading report to Feishu.")
   parser.add_argument("--config", required=True, type=Path, help="Path to config.toml.")
   parser.add_argument("--report", required=True, type=Path, help="Path to the Markdown report.")
   parser.add_argument("--figures", type=Path, default=None, help="Directory containing figure images (will be embedded).")
   parser.add_argument("--key-topics", type=str, default="",
                       help="Comma-separated key topic keywords (e.g. 'articulated objects, part mobility analysis').")
   parser.add_argument("--dry-run", action="store_true", help="Print actions without executing.")
   args = parser.parse_args()

   config = load_config(args.config)
   feishu_cfg = config.get("feishu", {})
   folder_token = feishu_cfg.get("folder_token", "")
   base_token = feishu_cfg.get("base_token", "")
   table_id = feishu_cfg.get("table_id", "")

   if not base_token or not table_id:
       print("ERROR: base_token and table_id must be set in config.toml", file=sys.stderr)
       sys.exit(1)

   meta = parse_report(args.report)
   
   # Key Topics from CLI argument (these go into Base, not report markdown)
   key_topics_str = args.key_topics
   if not key_topics_str and args.figures:
       key_topics_str = meta.get("Key Topics", "") or ""
   docx_name = build_docx_name(meta)
   doc_url: str | None = None

   # Read report text
   report_text = args.report.read_text(encoding="utf-8")

   # Create docx with images (docs +create + +media-insert)
   if args.dry_run:
       png_count = len(list(args.figures.glob("*.png"))) if (args.figures and args.figures.exists()) else 0
       print(f"[DRY-RUN] Would create docx '{docx_name}' with {png_count} images", file=sys.stderr)
       if folder_token:
           print(f"[DRY-RUN]   in folder '{folder_token}'", file=sys.stderr)
   else:
       import_result = create_docx_and_insert_images(
           args.report, docx_name, args.figures, folder_token
       )
       print(json.dumps(import_result, ensure_ascii=False, indent=2), file=sys.stderr)
       doc_url = import_result.get("url")
       if not doc_url:
           doc_url = import_result.get("data", {}).get("url") or import_result.get("result", {}).get("url")
       if not doc_url:
           token = import_result.get("data", {}).get("token") or import_result.get("result", {}).get("token")
           if token:
               doc_url = f"https://my.feishu.cn/docx/{token}"

   record = build_base_record(meta, doc_url, key_topics_str)
   if args.dry_run:
       print(f"[DRY-RUN] Would write Base record:", file=sys.stderr)
       print(json.dumps(record, ensure_ascii=False, indent=2))
   else:
       base_result = write_base_record(base_token, table_id, record)
       print("Base record written:", json.dumps(base_result, ensure_ascii=False, indent=2))

   output = {
       "report_path": str(args.report.resolve()),
       "docx_name": docx_name,
       "docx_url": doc_url,
       "base_record": record if args.dry_run else base_result.get("record", {}),
   }
   print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
   main()
