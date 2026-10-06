"""Render docs/submission.md into the submission PDF.

Kept in-repo so the 作品说明 PDF can be regenerated whenever the Markdown
changes — the PDF is a build artifact, the Markdown stays the source of truth.

Usage
-----
    pip install reportlab
    python tools/render_submission_pdf.py
    python tools/render_submission_pdf.py docs/submission.md output/pdf/OpenGuide-作品说明.pdf

Fonts: Windows built-ins (Microsoft YaHei body, Consolas code) plus ReportLab's
STSong-Light CID font for CJK inside ASCII-art diagrams (Consolas has no CJK
glyphs, so those runs must switch face or the diagram grid collapses).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)

FONT_DIR = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("Body", FONT_DIR / "msyh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("BodyBold", FONT_DIR / "msyhbd.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("Mono", FONT_DIR / "consola.ttf"))
pdfmetrics.registerFont(TTFont("MonoBold", FONT_DIR / "consolab.ttf"))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyBold",
                              italic="Body", boldItalic="BodyBold")
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

INK = colors.HexColor("#14233b")
MUTED = colors.HexColor("#5b6b7a")
ACCENT = colors.HexColor("#168b78")
ACCENT_WARM = colors.HexColor("#df623f")
RULE = colors.HexColor("#d7e0e6")
CODE_BG = colors.HexColor("#f5f7f9")
CODE_BORDER = colors.HexColor("#dfe6ec")
TBL_HEAD = colors.HexColor("#eef4f2")
CALLOUT_BG = colors.HexColor("#fff7f2")

PAGE_W, PAGE_H = A4
MARGIN_X = 20 * mm
MARGIN_TOP = 22 * mm
MARGIN_BOTTOM = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X


def make_styles():
    S = {}
    S["h1"] = ParagraphStyle("h1", fontName="BodyBold", fontSize=17, leading=24,
                             textColor=INK, spaceBefore=16, spaceAfter=8)
    S["h2"] = ParagraphStyle("h2", fontName="BodyBold", fontSize=13.5, leading=20,
                             textColor=ACCENT, spaceBefore=13, spaceAfter=6)
    S["h3"] = ParagraphStyle("h3", fontName="BodyBold", fontSize=11.5, leading=17,
                             textColor=INK, spaceBefore=10, spaceAfter=4)
    S["body"] = ParagraphStyle("body", fontName="Body", fontSize=9.6, leading=16.4,
                               textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6,
                               wordWrap="CJK")
    S["bullet"] = ParagraphStyle("bullet", parent=S["body"], leftIndent=13, bulletIndent=3,
                                 spaceAfter=3.5)
    S["table"] = ParagraphStyle("table", fontName="Body", fontSize=8.6, leading=13,
                                textColor=INK, wordWrap="CJK")
    S["table_head"] = ParagraphStyle("table_head", fontName="BodyBold", fontSize=8.6,
                                     leading=13, textColor=INK, wordWrap="CJK")
    S["code"] = ParagraphStyle("code", fontName="Mono", fontSize=8.2, leading=12.6,
                               textColor=colors.HexColor("#1f2d3d"))
    S["callout"] = ParagraphStyle("callout", fontName="Body", fontSize=9.6, leading=16.4,
                                  textColor=INK, wordWrap="CJK")
    S["toc"] = ParagraphStyle("toc", fontName="Body", fontSize=9.4, leading=16,
                              textColor=INK, wordWrap="CJK")
    S["toc2"] = ParagraphStyle("toc2", parent=S["toc"], leftIndent=16, fontSize=8.8,
                               textColor=MUTED, leading=14.5)
    return S


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str, mono_color: str = "#b23a1f") -> str:
    t = esc(text)
    t = re.sub(r"`([^`]+)`",
               lambda m: f'<font name="Mono" size="8.8" color="{mono_color}">{m.group(1)}</font>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)
    return t


def strip_inline(text: str) -> str:
    t = re.sub(r"`([^`]+)`", r"\1", text)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)
    return t


_CJK_RUN = re.compile(r"([\u3000-\u303f\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef]+)")


def _mono_markup(line: str) -> str:
    parts = _CJK_RUN.split(line)
    out = []
    for i, part in enumerate(parts):
        if not part:
            continue
        cell = esc(part).replace(" ", "&nbsp;")
        out.append(f'<font name="STSong-Light">{cell}</font>' if i % 2 == 1 else cell)
    return "".join(out)


def code_block(lines, S) -> Table:
    body = "<br/>".join(_mono_markup(l) for l in lines) or "&nbsp;"
    t = Table([[Paragraph(body, S["code"])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.6, CODE_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def callout_block(text: str, S) -> Table:
    t = Table([[Paragraph(inline(text), S["callout"])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CALLOUT_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, ACCENT_WARM),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def table_block(rows, S) -> Table:
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    data = [[Paragraph(inline(c, mono_color="#1f6f5f"), S["table_head"]) for c in rows[0]]]
    for r in rows[1:]:
        data.append([Paragraph(inline(c, mono_color="#1f6f5f"), S["table"]) for c in r])
    weights = []
    for i in range(ncol):
        longest = max((len(strip_inline(r[i])) for r in rows), default=4)
        weights.append(min(max(longest, 6), 46))
    total = sum(weights)
    widths = [CONTENT_W * w / total for w in weights]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), TBL_HEAD),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fafcfc")))
    t.setStyle(TableStyle(style))
    return t


class Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(path, pagesize=A4, title="OpenGuide 作品说明",
                         author="OpenGuide 团队",
                         subject="开源项目新手贡献智能向导 · 作品说明",
                         leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                         topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM)
        frame = Frame(MARGIN_X, MARGIN_BOTTOM, CONTENT_W,
                      PAGE_H - MARGIN_TOP - MARGIN_BOTTOM, id="main")
        self.addPageTemplates([PageTemplate(id="cover", frames=[frame]),
                               PageTemplate(id="body", frames=[frame],
                                            onPage=self._decorate)])

    def _decorate(self, canvas, doc):
        canvas.saveState()
        y = PAGE_H - MARGIN_TOP + 7 * mm
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_X, y - 3, PAGE_W - MARGIN_X, y - 3)
        canvas.setFont("Body", 7.4)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN_X, y + 1.5, "OpenGuide · 作品说明")
        canvas.drawRightString(PAGE_W - MARGIN_X, y + 1.5, "AI + 开源赛道")
        canvas.setFont("Body", 8)
        canvas.drawCentredString(PAGE_W / 2, MARGIN_BOTTOM - 9 * mm, f"- {doc.page - 1} -")
        canvas.restoreState()


def parse_markdown(md: str):
    lines, out, i = md.splitlines(), [], 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(("code", buf))
            continue
        if re.match(r"^#{1,4}\s", s):
            out.append((f"h{min(len(s) - len(s.lstrip('#')), 3)}", s.lstrip('#').strip()))
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = lines[i].strip().strip("|")
                if not re.match(r"^[\s:|-]+$", raw):
                    rows.append([c.strip() for c in raw.split("|")])
                i += 1
            out.append(("table", rows))
            continue
        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(("quote", " ".join(x for x in buf if x)))
            continue
        if re.match(r"^[-*]\s", s):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s", lines[i].strip()):
                items.append(lines[i].strip()[2:].strip())
                i += 1
            out.append(("ul", items))
            continue
        if re.match(r"^\d+\.\s", s):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s", "", lines[i].strip()))
                i += 1
            out.append(("ol", items))
            continue
        if not s:
            i += 1
            continue
        buf = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|```|\||>|[-*]\s|\d+\.\s)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        out.append(("p", " ".join(buf)))
    return out


def build(md_path: Path, out_path: Path) -> Path:
    S = make_styles()
    blocks = parse_markdown(md_path.read_text(encoding="utf-8"))
    toc = [(k, strip_inline(t)) for k, t in blocks
           if k in ("h2", "h3") and strip_inline(t)]

    doc = Doc(str(out_path))
    story = [Spacer(1, 6 * mm)]
    story.append(Paragraph("OpenGuide", ParagraphStyle(
        "cov1", fontName="BodyBold", fontSize=38, leading=46, textColor=ACCENT)))
    story.append(Paragraph("开源项目新手贡献智能向导", ParagraphStyle(
        "cov2", fontName="BodyBold", fontSize=20, leading=30, textColor=INK)))
    story.append(Spacer(1, 3 * mm))
    story.append(Table([[""]], colWidths=[CONTENT_W], rowHeights=[1.6],
                       style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_WARM)])))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "输入一个 GitHub 仓库 URL，输出一份<b>带证据、可执行、会陪你走完每一步</b>的新手贡献路线图。",
        ParagraphStyle("cov3", fontName="Body", fontSize=11.5, leading=21,
                       textColor=MUTED, wordWrap="CJK", alignment=TA_LEFT)))
    story.append(Spacer(1, 10 * mm))
    meta = [
        ("申报方向", "方向一（开源赋能的 AI 应用创新）为主；方向三（真实开源贡献闭环）作佐证"),
        ("作品名称", "OpenGuide —— 开源项目新手贡献智能向导"),
        ("团队", "3 人（全栈，代号 A / B / C）"),
        ("许可", "MIT"),
        ("文档版本", "2026-10-06"),
    ]
    mt = Table([[Paragraph(f"<b>{k}</b>", S["table"]), Paragraph(v, S["table"])] for k, v in meta],
               colWidths=[26 * mm, CONTENT_W - 26 * mm], hAlign="LEFT")
    mt.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(mt)

    story.append(PageBreak())
    story.append(Paragraph("目录", ParagraphStyle(
        "toc_title", fontName="BodyBold", fontSize=13.5, leading=20,
        textColor=ACCENT, spaceAfter=6)))
    for k, t in toc:
        story.append(Paragraph(inline(t), S["toc"] if k == "h2" else S["toc2"]))
    story.append(PageBreak())

    for kind, payload in blocks:
        if kind == "h1":
            if strip_inline(payload) == "OpenGuide 作品说明":
                continue
            story.append(Paragraph(inline(payload), S["h1"]))
        elif kind in ("h2", "h3"):
            story.append(Paragraph(inline(payload), S[kind]))
        elif kind == "p":
            story.append(Paragraph(inline(payload), S["body"]))
        elif kind == "quote":
            story.extend([Spacer(1, 2), callout_block(payload, S), Spacer(1, 6)])
        elif kind == "ul":
            for it in payload:
                story.append(Paragraph(inline(it), S["bullet"], bulletText="\u2022"))
            story.append(Spacer(1, 2))
        elif kind == "ol":
            for n, it in enumerate(payload, 1):
                story.append(Paragraph(inline(it), S["bullet"], bulletText=f"{n}."))
            story.append(Spacer(1, 2))
        elif kind == "code":
            story.extend([Spacer(1, 2), code_block(payload, S), Spacer(1, 7)])
        elif kind == "table":
            t = table_block(payload, S)
            story.extend([Spacer(1, 2),
                          KeepTogether([t]) if len(payload) >= 3 else t,
                          Spacer(1, 7)])

    doc.build(story)
    return out_path


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/submission.md")
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/pdf/OpenGuide-作品说明.pdf")
    dst.parent.mkdir(parents=True, exist_ok=True)
    build(src, dst)
    print(f"built {dst} ({dst.stat().st_size} bytes)")
