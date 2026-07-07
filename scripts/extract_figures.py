#!/usr/bin/env python3
"""从 PDF 精确裁剪 figure / table 并生成 figure_manifest.json。

两种后端：
  - pdffigures2（推荐，精确）：在 config.toml 的 [figure].pdffigures2_jar 配置 jar 路径，
    或用 --jar 传入。需要 Java 运行环境。
  - pymupdf（fallback，caption 锚定裁剪）：无需额外依赖，按「Figure 标题在图下方、
    Table 标题在表上方」的排版惯例，裁剪 caption 邻近的图形区域。精度不如 pdffigures2，
    但足以让报告嵌入真正的图区而非整页截图。

输出：
  <output>/figures/figure-00N.png | table-00N.png
  <output>/figure_manifest.json   （含 type/number/caption/page/image_path/bbox）

用法：
  python scripts/extract_figures.py --pdf paper.pdf --output reports/slug
  python scripts/extract_figures.py --pdf paper.pdf --output reports/slug --method pymupdf
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # py<3.11
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None

import fitz  # PyMuPDF

CAPTION_RE = re.compile(r"^\s*(Figure|Fig\.?|Table)\s*\.?\s*(\d+)", re.IGNORECASE)
RENDER_DPI = 200
ZOOM = RENDER_DPI / 72.0


def load_config(path: Path) -> dict[str, Any]:
    if not path or not path.exists() or tomllib is None:
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# 后端 1：pdffigures2
# ---------------------------------------------------------------------------

def extract_with_pdffigures2(pdf: Path, output: Path, jar: Path) -> list[dict[str, Any]]:
    figures_dir = output / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output / ".pdffigures2"
    data_dir.mkdir(parents=True, exist_ok=True)

    # -m <prefix>：渲染图片前缀；-d <prefix>：写 json；-i <dpi>
    img_prefix = str(figures_dir) + "/"
    data_prefix = str(data_dir) + "/"
    cmd = [
        "java", "-jar", str(jar), str(pdf),
        "-m", img_prefix,
        "-d", data_prefix,
        "-i", str(RENDER_DPI),
    ]
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    subprocess.run(cmd, check=True)

    manifest: list[dict[str, Any]] = []
    for data_file in sorted(data_dir.glob("*.json")):
        entries = json.loads(data_file.read_text(encoding="utf-8"))
        for e in entries:
            fig_type = (e.get("figType") or "Figure").lower()
            number = _safe_int(e.get("name"))
            render = e.get("renderURL")
            image_path = ""
            if render:
                src = Path(render)
                kind = "table" if "table" in fig_type else "figure"
                dst = figures_dir / f"{kind}-{number:03d}.png"
                if src.exists() and src.resolve() != dst.resolve():
                    shutil.move(str(src), str(dst))
                image_path = f"figures/{dst.name}"
            manifest.append({
                "type": "table" if "table" in fig_type else "figure",
                "number": number,
                "caption": (e.get("caption") or "").strip()[:400],
                "page": (e.get("page") or 0) + 1,
                "image_path": image_path,
                "bbox": e.get("regionBoundary"),
            })
    shutil.rmtree(data_dir, ignore_errors=True)
    manifest.sort(key=lambda m: (m["type"] != "figure", m["number"]))
    return manifest


def _safe_int(v: Any) -> int:
    try:
        return int(re.sub(r"\D", "", str(v)) or 0)
    except (TypeError, ValueError):
        return 0


def _detect_column_layout(texts, page_width):
    """检测两栏布局，返回栏分隔线的 x 位置；单栏返回 None。"""
    if len(texts) < 4:
        return None
    centres = [(r.x0 + r.x1) / 2 for r in texts if r.width > 30]
    if len(centres) < 3:
        return None
    cmin, cmax = min(centres), max(centres)
    mid = (cmin + cmax) / 2
    left = [c for c in centres if c < mid]
    right = [c for c in centres if c > mid]
    if left and right and max(left) + 40 < min(right):
        return int((max(left) + min(right)) // 2)
    return None


def _cluster_rects(rects, gap=35):
    """将空间上接近的矩形聚类合并（用于多 panel figure/table）。"""
    import fitz as _fitz
    if not rects:
        return []
    sorted_rects = sorted(rects, key=lambda r: (r.y0, r.x0))
    clusters = [_fitz.Rect(sorted_rects[0])]
    for r in sorted_rects[1:]:
        last = clusters[-1]
        if r.x0 - last.x1 <= gap and abs(r.y0 - last.y0) <= gap * 2:
            clusters[-1] = last | r
        else:
            clusters.append(_fitz.Rect(r))
    return clusters


# ---------------------------------------------------------------------------
# 后端 2：pymupdf caption 锚定裁剪
# ---------------------------------------------------------------------------

def _graphic_rects(page: "fitz.Page") -> list["fitz.Rect"]:
    """页面上的图形元素（内嵌位图 + 矢量绘制）包围盒。"""
    rects: list[fitz.Rect] = []
    max_h = page.rect.height * 0.35  # 排除超过页面高度 35% 的大背景图
    for img in page.get_images(full=True):
        try:
            for r in page.get_image_rects(img[0]):
                rr = fitz.Rect(r)
                if rr.y1 - rr.y0 < max_h:
                    rects.append(rr)
        except Exception:
            pass
    for dr in page.get_drawings():
        r = fitz.Rect(dr["rect"])
        if r.width > 4 and r.height > 4:  # 忽略细小描边
            if r.y1 - r.y0 < max_h:
                rects.append(r)
    return rects


def _find_captions(page: "fitz.Page") -> list[dict[str, Any]]:
    caps = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" not in b:
            continue
        text = " ".join(
            span["text"] for line in b["lines"] for span in line["spans"]
        ).strip()
        m = CAPTION_RE.match(text)
        if m:
            kind = "table" if m.group(1).lower().startswith("table") else "figure"
            caps.append({
                "type": kind,
                "number": int(m.group(2)),
                "caption": text[:400],
                "rect": fitz.Rect(b["bbox"]),
            })
    return caps


def _union_in_band(rects: list["fitz.Rect"], band: "fitz.Rect", c: "fitz.Rect", horiz_constraint: bool = True) -> "fitz.Rect | None":
    """并集：落在 band 内，且（可选）与 caption 水平重叠的矩形。"""
    hit = fitz.Rect()
    empty = True
    for g in rects:
        vertical_ok = g.y0 >= band.y0 - 2 and g.y1 <= band.y1 + 2
        if vertical_ok:
            if horiz_constraint and not (g.x1 > c.x0 - 40 and g.x0 < c.x1 + 40):
                continue
            hit = g if empty else (hit | g)
            empty = False
    return None if empty else hit


def _column_of(rect, col_divider):
    """返回 rect 所在的栏：'left', 'right', 或 None（跨栏或无法判断）。"""
    if col_divider is None:
        return None
    margin = 10  # 分隔线周围的容差
    spans_both = (rect.x0 < col_divider - margin) and (rect.x1 > col_divider + margin)
    if spans_both:
        return None
    # 按中点位置判定
    mid = (rect.x0 + rect.x1) / 2
    return 'left' if mid < col_divider else 'right'

def _crop_region(cap: dict[str, Any], graphics: list["fitz.Rect"], texts: list["fitz.Rect"],
                 page_rect: "fitz.Rect", other_caps: list["fitz.Rect"]) -> "fitz.Rect | None":
    """按排版惯例确定图区：Figure 标题在图下方 → 取上方内容；
    Table 标题通常在表上方，但也可能在表下方 → 同时检查上下两个 band。
    figure 优先用图形元素；table（及无图形命中的 figure）回退用文本块并集——覆盖纯文本渲染的表格。
    """
    c = cap["rect"]
    above = cap["type"] == "figure"  # figure 图在标题上方
    band = fitz.Rect(page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1)
    if above:
        band.y1 = c.y0
        nearest = page_rect.y0
        col_divider = _detect_column_layout(texts, page_rect.width)
        c_col = _column_of(c, col_divider) if col_divider else None
        for oc in other_caps:
            if col_divider:
                oc_col = _column_of(oc, col_divider)
                if c_col and oc_col and c_col != oc_col:
                    continue
            if oc.y1 <= c.y0 and oc.y1 > nearest:
                nearest = oc.y1
        band.y0 = nearest
    else:
        band.y0 = c.y1
        nearest = page_rect.y1
        col_divider = _detect_column_layout(texts, page_rect.width)
        c_col = _column_of(c, col_divider) if col_divider else None
        for oc in other_caps:
            if col_divider:
                oc_col = _column_of(oc, col_divider)
                if c_col and oc_col and c_col != oc_col:
                    continue
            if oc.y0 >= c.y1 and oc.y0 < nearest:
                nearest = oc.y0
        band.y1 = nearest

    hit = None
    # figure 优先用图形元素
    if cap["type"] == "figure":
        candidates = graphics if graphics else (graphics + texts)
        hit = _union_in_band(candidates, band, c, horiz_constraint=True)
        # 多 panel 场景：用聚类合并邻近图形/文本
        if hit is None and graphics:
            all_in_band = [g for g in graphics if g.y0 >= band.y0 - 2 and g.y1 <= band.y1 + 2]
            if len(all_in_band) >= 2:
                clusters = _cluster_rects(all_in_band)
                for cl in clusters:
                    if cl.x1 > c.x0 - 40 and cl.x0 < c.x1 + 40:
                        hit = cl if hit is None else (hit | cl)
    else:
        # table：同时检查上方和下方的 band（caption 可能在上方也可能在下方）
        for look_above in [True, False]:
            if hit is not None:
                break
            if look_above:
                last_cap_above = max([oc.y1 for oc in other_caps if oc.y1 <= c.y0] + [page_rect.y0])
                tbl_band = fitz.Rect(page_rect.x0, last_cap_above, page_rect.x1, c.y0)
            else:
                next_cap_below = min([oc.y0 for oc in other_caps if oc.y0 >= c.y1] + [page_rect.y1])
                tbl_band = fitz.Rect(page_rect.x0, c.y1, page_rect.x1, next_cap_below)
            # 对 table 放宽水平约束（caption 常跨栏）
            hit = _union_in_band(graphics + texts, tbl_band, c, horiz_constraint=False)
    if hit is None:
        return None
    # 把 caption 一并纳入，方便读者，并留白边
    hit = hit | c
    pad = 6
    hit.x0 = max(page_rect.x0, hit.x0 - pad)
    hit.y0 = max(page_rect.y0, hit.y0 - pad)
    hit.x1 = min(page_rect.x1, hit.x1 + pad)
    hit.y1 = min(page_rect.y1, hit.y1 + pad)
    if hit.width < 30 or hit.height < 30:
        return None
    return hit


def extract_with_pymupdf(pdf: Path, output: Path) -> list[dict[str, Any]]:
    figures_dir = output / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf))
    manifest: list[dict[str, Any]] = []
    matrix = fitz.Matrix(ZOOM, ZOOM)

    for pageno, page in enumerate(doc, start=1):
        caps = _find_captions(page)
        if not caps:
            continue
        graphics = _graphic_rects(page)
        cap_rects = [c["rect"] for c in caps]
        # 文本块（排除 caption 自身），供表格/矢量图裁剪回退使用
        texts = []
        for b in page.get_text("dict")["blocks"]:
            if "lines" not in b:
                continue
            r = fitz.Rect(b["bbox"])
            if not any(r.intersects(cr) for cr in cap_rects) and r.width > 8 and r.height > 4:
                texts.append(r)
        for cap in caps:
            others = [r for r in cap_rects if r != cap["rect"]]
            region = _crop_region(cap, graphics, texts, page.rect, others)
            image_path = ""
            bbox = None
            if region is not None:
                pix = page.get_pixmap(matrix=matrix, clip=region)
                name = f"{cap['type']}-{cap['number']:03d}.png"
                pix.save(str(figures_dir / name))
                image_path = f"figures/{name}"
                bbox = [region.x0, region.y0, region.x1, region.y1]
            manifest.append({
                "type": cap["type"],
                "number": cap["number"],
                "caption": cap["caption"],
                "page": pageno,
                "image_path": image_path,
                "bbox": bbox,
            })
    doc.close()

    # 去重：同一 type+number 保留有裁图的那条
    dedup: dict[tuple, dict[str, Any]] = {}
    for m in manifest:
        key = (m["type"], m["number"])
        if key not in dedup or (not dedup[key]["image_path"] and m["image_path"]):
            dedup[key] = m
    result = list(dedup.values())
    result.sort(key=lambda m: (m["type"] != "figure", m["number"]))
    return result


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract & crop figures/tables from a PDF.")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Output dir (figures/ + figure_manifest.json).")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--method", choices=["auto", "pdffigures2", "pymupdf"], default="auto")
    parser.add_argument("--jar", type=Path, default=None, help="Path to pdffigures2 jar (overrides config).")
    args = parser.parse_args()

    config = load_config(args.config)
    jar = args.jar or config.get("figure", {}).get("pdffigures2_jar")
    jar_path = Path(jar) if jar else None

    args.output.mkdir(parents=True, exist_ok=True)

    method = args.method
    if method == "auto":
        method = "pdffigures2" if (jar_path and jar_path.exists() and shutil.which("java")) else "pymupdf"

    if method == "pdffigures2":
        if not (jar_path and jar_path.exists()):
            print("ERROR: pdffigures2 jar not found. Set [figure].pdffigures2_jar or --jar.", file=sys.stderr)
            sys.exit(1)
        print("Using pdffigures2 backend (precise crop).", file=sys.stderr)
        manifest = extract_with_pdffigures2(args.pdf, args.output, jar_path)
    else:
        print("Using PyMuPDF backend (caption-anchored crop fallback).", file=sys.stderr)
        manifest = extract_with_pymupdf(args.pdf, args.output)

    out = args.output / "figure_manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    cropped = sum(1 for m in manifest if m["image_path"])
    print(f"Wrote {len(manifest)} figure/table entries ({cropped} cropped) to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
