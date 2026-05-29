"""
Generator PDF Umum — laporan, riset, dokumen dari teks/markdown.
Berbeda dari surat_generator.py yang khusus surat resmi ATG.
"""

import re
import asyncio
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether,
)

PRIMARY   = HexColor("#FFB317")
DARK_GRAY = HexColor("#5E5E5E")
TEXT_COL  = HexColor("#2B2B2B")
ACCENT    = HexColor("#1A73E8")

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "dokumen"

BULAN_ID = ["","Januari","Februari","Maret","April","Mei","Juni",
            "Juli","Agustus","September","Oktober","November","Desember"]


def _escape(text: str) -> str:
    """Escape XML special chars, lalu konversi markdown dasar ke ReportLab tags."""
    # Escape dulu
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic _text_ atau *text*
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
    # Inline code `text`
    text = re.sub(r'`(.+?)`', r'<font name="Courier" size="9">\1</font>', text)
    return text


def generate_document_pdf(
    title: str,
    content: str,
    subtitle: str = "",
    author: str = "Reflective Koala AI Agent",
) -> str:
    """
    Konversi judul + konten markdown → PDF.
    Return: path file PDF.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in title[:40]).strip()
    safe = safe.replace(" ", "_") or "dokumen"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = OUTPUT_DIR / f"{ts}_{safe}.pdf"

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        rightMargin=2.2 * cm,
        leftMargin=2.2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title,
        author=author,
    )

    # ── Styles ──────────────────────────────────────────────────────────────
    s_company = ParagraphStyle("company", fontName="Helvetica-Bold",
                               fontSize=9, textColor=DARK_GRAY,
                               alignment=TA_CENTER, spaceAfter=2)
    s_title = ParagraphStyle("doctitle", fontName="Helvetica-Bold",
                             fontSize=20, textColor=PRIMARY,
                             alignment=TA_CENTER, spaceAfter=4)
    s_subtitle = ParagraphStyle("subtitle", fontName="Helvetica",
                                fontSize=11, textColor=DARK_GRAY,
                                alignment=TA_CENTER, spaceAfter=4)
    s_meta = ParagraphStyle("meta", fontName="Helvetica",
                            fontSize=8, textColor=DARK_GRAY,
                            alignment=TA_CENTER, spaceAfter=8)
    s_h1 = ParagraphStyle("h1", fontName="Helvetica-Bold",
                          fontSize=14, textColor=PRIMARY,
                          spaceBefore=14, spaceAfter=4)
    s_h2 = ParagraphStyle("h2", fontName="Helvetica-Bold",
                          fontSize=12, textColor=DARK_GRAY,
                          spaceBefore=10, spaceAfter=3)
    s_h3 = ParagraphStyle("h3", fontName="Helvetica-BoldOblique",
                          fontSize=10, textColor=TEXT_COL,
                          spaceBefore=6, spaceAfter=2)
    s_body = ParagraphStyle("body", fontName="Helvetica",
                            fontSize=10, textColor=TEXT_COL,
                            spaceBefore=2, spaceAfter=2,
                            leading=15, alignment=TA_JUSTIFY)
    s_bullet = ParagraphStyle("bullet", fontName="Helvetica",
                              fontSize=10, textColor=TEXT_COL,
                              spaceBefore=1, spaceAfter=1,
                              leftIndent=14, leading=14)
    s_code = ParagraphStyle("code", fontName="Courier",
                            fontSize=8.5, textColor=TEXT_COL,
                            spaceBefore=2, spaceAfter=2,
                            leftIndent=12, leading=13,
                            backColor=HexColor("#F5F5F5"))
    s_footer = ParagraphStyle("footer", fontName="Helvetica",
                              fontSize=8, textColor=DARK_GRAY,
                              alignment=TA_CENTER)

    # ── Build story ──────────────────────────────────────────────────────────
    now = datetime.now()
    tgl = f"{now.day} {BULAN_ID[now.month]} {now.year}, {now.strftime('%H:%M')}"

    story = []

    # Header
    story.append(Paragraph("PT. ARUNIKA TEKNOLOGI GLOBAL", s_company))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 8))
    story.append(Paragraph(_escape(title), s_title))
    if subtitle:
        story.append(Paragraph(_escape(subtitle), s_subtitle))
    story.append(Paragraph(f"Dibuat: {tgl} | Oleh: {_escape(author)}", s_meta))
    story.append(HRFlowable(width="100%", thickness=0.8, color=DARK_GRAY))
    story.append(Spacer(1, 14))

    # Parse content line by line
    lines = content.split("\n")
    in_code_block = False
    code_lines = []

    for line in lines:
        stripped = line.rstrip()

        # Code block fence ```
        if stripped.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lines = []
            else:
                # Flush code block
                if code_lines:
                    block_text = "<br/>".join(
                        _escape(cl) for cl in code_lines
                    )
                    story.append(Paragraph(block_text, s_code))
                in_code_block = False
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(stripped)
            continue

        if not stripped:
            story.append(Spacer(1, 4))
            continue

        # Headings
        if stripped.startswith("#### "):
            story.append(Paragraph(_escape(stripped[5:]), s_h3))
        elif stripped.startswith("### "):
            story.append(Paragraph(_escape(stripped[4:]), s_h3))
        elif stripped.startswith("## "):
            story.append(Paragraph(_escape(stripped[3:]), s_h2))
        elif stripped.startswith("# "):
            story.append(Paragraph(_escape(stripped[2:]), s_h1))
        # Horizontal rule
        elif re.match(r'^[-=*]{3,}$', stripped):
            story.append(HRFlowable(width="100%", thickness=0.5, color=DARK_GRAY))
        # Bullet / list
        elif re.match(r'^[-•*]\s', stripped):
            story.append(Paragraph("• " + _escape(stripped[2:]), s_bullet))
        elif re.match(r'^\d+[.)]\s', stripped):
            m = re.match(r'^(\d+)[.)]\s+(.*)', stripped)
            if m:
                story.append(Paragraph(f"{m.group(1)}. {_escape(m.group(2))}", s_bullet))
        # Table row (simpel — abaikan formatting tabel, render sebagai teks)
        elif stripped.startswith("|") and stripped.endswith("|"):
            cols = [c.strip() for c in stripped.strip("|").split("|")]
            story.append(Paragraph("  |  ".join(_escape(c) for c in cols), s_body))
        # Normal paragraph
        else:
            story.append(Paragraph(_escape(stripped), s_body))

    # Footer
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY))
    story.append(Paragraph(
        "PT. Arunika Teknologi Global  |  www.arunika2045.com  |  corsec@arunika2045.com",
        s_footer,
    ))

    doc.build(story)
    return str(filepath)


async def generate_document_pdf_async(
    title: str, content: str, subtitle: str = "", author: str = "Reflective Koala AI Agent"
) -> str:
    return await asyncio.to_thread(generate_document_pdf, title, content, subtitle, author)
