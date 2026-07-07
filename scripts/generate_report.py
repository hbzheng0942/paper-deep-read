#!/usr/bin/env python3
"""把 PDF 论文全文提取出来，供 Agent 精读并生成结构化 Markdown 报告。

本脚本仅做素材准备，不调用外部 LLM API（由调用本 skill 的 Agent 完成撰写）。

用法：
  python scripts/generate_report.py --pdf <pdf> --output reports/<SLUG> --extract-only

产出：
  - <output>/extracted_text.txt （若已存在则跳过）
  - 校验 figure_manifest.json 是否存在；若无则打印提示
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# 提取
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    parts = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        if text.strip():
            parts.append(f"\n\n--- Page {i} ---\n\n{text}")
    doc.close()
    return "\n".join(parts)


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：中文 1 字 ≈ 1 token，英文 4 字符 ≈ 1 token。"""
    import unicodedata
    total = 0
    for ch in text:
        if unicodedata.category(ch).startswith(('Lo', 'Han')):
            total += 1
        else:
            total += 0.25
    return int(total)


def load_figure_manifest(output: Path, pdf_path: Path) -> list[dict[str, Any]]:
    """优先复用 extract_figures.py 的精确裁图清单；若无则返回空列表。"""
    manifest_path = output / "figure_manifest.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if data:
                cropped = sum(1 for m in data if m.get("image_path"))
                print(f"Reusing {manifest_path} ({cropped} cropped of {len(data)} total).", file=sys.stderr)
                return data
        except json.JSONDecodeError:
            pass
    print("WARNING: No figure_manifest.json found. Run extract_figures.py first.", file=sys.stderr)
    return []


def build_figures_block(manifest: list[dict[str, Any]]) -> str:
    """给 Agent 的 figure 清单：列出可嵌入的相对路径。"""
    if not manifest:
        return "未提供 figure/table 清单。请先运行 extract_figures.py。"
    lines = ["以下是可嵌入的 figure/table（只能引用 image_path 非空的项，路径必须原样使用）："]
    for m in manifest:
        tag = f"{m['type'].capitalize()} {m['number']} (p{m.get('page','?')})"
        if m.get("image_path"):
            lines.append(f"- {tag} → `![{tag}]({m['image_path']})`　caption: {m.get('caption','')[:160]}")
        else:
            lines.append(f"- {tag}（无裁图，勿嵌入图片，可在正文引用其结论）　caption: {m.get('caption','')[:160]}")
    return "\n".join(lines)


def build_prompt_block(pdf_text: str, manifest: list[dict[str, Any]]) -> str:
    """构造 Agent 使用的完整 prompt 材料块。"""
    figures_block = build_figures_block(manifest)
    est_tokens = estimate_tokens(pdf_text)
    return f"""## PDF 全文（{est_tokens:,} est. tokens）

{pdf_text}


## Figure / Table 清单

{figures_block}
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract PDF text and prepare materials for agent deep-reading.")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Output directory (e.g. reports/<slug>).")
    parser.add_argument("--extract-only", action="store_true", default=True,
                        help="Only extract text and verify figure manifest (no LLM call).")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    # 1. Extract PDF text
    text_path = args.output / "extracted_text.txt"
    if text_path.exists():
        print(f"Text already exists at {text_path}, skipping extraction.", file=sys.stderr)
    else:
        print("Extracting PDF text...", file=sys.stderr)
        pdf_text = extract_pdf_text(args.pdf)
        text_path.write_text(pdf_text, encoding="utf-8")
        est = estimate_tokens(pdf_text)
        print(f"Extracted {text_path} (~{est:,} tokens).", file=sys.stderr)

    # 2. Load figure manifest (just verify)
    manifest = load_figure_manifest(args.output, args.pdf)
    figures_block = build_figures_block(manifest)
    print(figures_block, file=sys.stderr)

    # 3. Print summary
    cropped = sum(1 for m in manifest if m.get("image_path"))
    print(f"\nDone. {cropped}/{len(manifest)} figures/tables have cropped images.", file=sys.stderr)
    print(f"Agent should now read:", file=sys.stderr)
    print(f"  - templates/report_template.md", file=sys.stderr)
    print(f"  - templates/evidence_card_template.md", file=sys.stderr)
    print(f"  - {text_path}", file=sys.stderr)
    print(f"  - {args.output / 'figure_manifest.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
