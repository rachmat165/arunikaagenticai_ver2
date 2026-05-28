"""
Generator Surat Resmi PT. Arunika Teknologi Global
- Letterhead dengan logo ATG (programatik, sesuai brand guidelines)
- Format surat Islami profesional
- Warna brand: Primary #FFB317, Dark #5E5E5E, Light #D5D5D5
"""

import math
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, Image,
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas as pdf_canvas

LOGO_PATH = Path(__file__).parent.parent.parent / "assets" / "logo.png"

# ── Brand Colors ──────────────────────────────────────────────────────────────
PRIMARY    = HexColor("#FFB317")   # Kuning ATG
DARK_GRAY  = HexColor("#5E5E5E")   # Abu gelap
LIGHT_GRAY = HexColor("#D5D5D5")   # Abu terang
TEXT_BLACK = HexColor("#2B2B2B")

# ── Company Info ──────────────────────────────────────────────────────────────
COMPANY = {
    "name":      "PT. ARUNIKA TEKNOLOGI GLOBAL",
    "tagline":   "Teknologi Global",
    "address":   "Jl. Calung No. 7A, Kel. Turangga, Kec. Lengkong, Kota Bandung 40264",
    "email":     "corsec@arunika2045.com",
    "website":   "www.arunika2045.com",
    "phone":     "+62 22 8200 2224",
    "dir_utama": "Adang Ahmad Kunandar",
    "direktur":  "Ir. Rachmat Ari Kusumanto",
    "komisaris": "Dedi Achmad Santika",
}

BULAN_ID = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]
ROMAWI = ["", "I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"]


# ─────────────────────────────────────────────────────────────────────────────
# Logo Flowable — menggambar logo ATG secara programatik
# ─────────────────────────────────────────────────────────────────────────────
class ATGLogoFlowable(Flowable):
    """Gambar logo ATG (diamond + rays + huruf A) menggunakan ReportLab canvas."""

    def __init__(self, size: float = 60):
        super().__init__()
        self.size = size
        self.width = size
        self.height = size

    def draw(self):
        c = self.canv
        s = self.size
        cx, cy = s / 2, s / 2

        # ── Diamond (jajar genjang diputar 45°) ──────────────────────────────
        hw = s * 0.48
        c.setFillColor(PRIMARY)
        c.setStrokeColor(PRIMARY)
        path = c.beginPath()
        path.moveTo(cx,       cy + hw)
        path.lineTo(cx + hw,  cy)
        path.lineTo(cx,       cy - hw)
        path.lineTo(cx - hw,  cy)
        path.close()
        c.drawPath(path, fill=1, stroke=0)

        # ── Rays (sinar) dari tengah atas ────────────────────────────────────
        ray_cx = cx
        ray_cy = cy + s * 0.10
        inner_r = s * 0.085
        outer_r = s * 0.28
        c.setStrokeColor(white)
        c.setLineWidth(1.2)
        for i in range(16):
            angle = (i * 2 * math.pi / 16) - math.pi / 2
            x1 = ray_cx + inner_r * math.cos(angle)
            y1 = ray_cy + inner_r * math.sin(angle)
            x2 = ray_cx + outer_r * math.cos(angle)
            y2 = ray_cy + outer_r * math.sin(angle)
            c.line(x1, y1, x2, y2)

        # ── Huruf "A" (gunung) ───────────────────────────────────────────────
        w = s * 0.22   # lebar kaki
        t = s * 0.055  # tebal dinding
        bx = cx        # puncak x
        by = cy + s * 0.18   # puncak y
        base_y = cy - s * 0.20  # alas

        c.setFillColor(white)
        c.setStrokeColor(white)
        path = c.beginPath()
        path.moveTo(bx - w,       base_y)                        # kiri bawah luar
        path.lineTo(bx - t * 0.5, by)                            # puncak kiri
        path.lineTo(bx,           by + s * 0.01)                 # puncak tengah
        path.lineTo(bx + t * 0.5, by)                            # puncak kanan
        path.lineTo(bx + w,       base_y)                        # kanan bawah luar
        path.lineTo(bx + w - t,   base_y)                        # kanan bawah dalam
        path.lineTo(bx + t * 0.4, by - s * 0.04)                 # puncak dalam kanan
        path.lineTo(bx - t * 0.4, by - s * 0.04)                 # puncak dalam kiri
        path.lineTo(bx - w + t,   base_y)                        # kiri bawah dalam
        path.close()
        c.drawPath(path, fill=1, stroke=0)


# ─────────────────────────────────────────────────────────────────────────────
# Style helpers
# ─────────────────────────────────────────────────────────────────────────────
def _styles() -> dict:
    return {
        "company_name": ParagraphStyle(
            "company_name",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=DARK_GRAY,
            spaceAfter=1,
            leading=16,
        ),
        "company_tagline": ParagraphStyle(
            "company_tagline",
            fontName="Helvetica",
            fontSize=9,
            textColor=PRIMARY,
            spaceAfter=2,
            leading=11,
        ),
        "company_detail": ParagraphStyle(
            "company_detail",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=DARK_GRAY,
            leading=11,
        ),
        "bismillah": ParagraphStyle(
            "bismillah",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=DARK_GRAY,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "bismillah_latin": ParagraphStyle(
            "bismillah_latin",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=DARK_GRAY,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "meta_label": ParagraphStyle(
            "meta_label",
            fontName="Helvetica",
            fontSize=10,
            textColor=TEXT_BLACK,
            leading=14,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=10,
            textColor=TEXT_BLACK,
            leading=16,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "body_bold": ParagraphStyle(
            "body_bold",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=TEXT_BLACK,
            leading=14,
        ),
        "signature": ParagraphStyle(
            "signature",
            fontName="Helvetica",
            fontSize=10,
            textColor=TEXT_BLACK,
            leading=14,
        ),
        "signature_name": ParagraphStyle(
            "signature_name",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=TEXT_BLACK,
            leading=14,
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SuratGenerator
# ─────────────────────────────────────────────────────────────────────────────
class SuratGenerator:
    """Generate surat resmi PT. ATG dalam format PDF berletterhead."""

    COUNTER_FILE = Path(__file__).parent.parent.parent / "data" / "surat_counter.txt"

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir) / "surat"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Nomor surat otomatis ──────────────────────────────────────────────────
    def _next_nomor(self) -> str:
        self.COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        year = now.year
        month = now.month

        try:
            raw = self.COUNTER_FILE.read_text().strip()
            parts = raw.split("/")
            seq = int(parts[0]) + 1 if parts[0].isdigit() else 1
            # Reset seq setiap bulan baru
            stored_month = int(parts[1]) if len(parts) > 1 else 0
            if stored_month != month:
                seq = 1
        except Exception:
            seq = 1

        self.COUNTER_FILE.write_text(f"{seq}/{month}/{year}")
        return f"{seq:03d}/ATG/CORSEC/{ROMAWI[month]}/{year}"

    # ── Helper: format tanggal Indonesia ─────────────────────────────────────
    @staticmethod
    def _tanggal_id(dt: datetime | None = None) -> str:
        d = dt or datetime.now()
        return f"Bandung, {d.day} {BULAN_ID[d.month]} {d.year}"

    # ── Letterhead (header PDF) ───────────────────────────────────────────────
    def _build_header(self, st: dict) -> list:
        if LOGO_PATH.exists():
            logo: Flowable = Image(str(LOGO_PATH), width=62, height=62)
        else:
            logo = ATGLogoFlowable(size=62)

        header_right = [
            Paragraph(COMPANY["name"], st["company_name"]),
            Paragraph(COMPANY["tagline"], st["company_tagline"]),
            Paragraph(COMPANY["address"], st["company_detail"]),
            Paragraph(
                f'✉ {COMPANY["email"]}  |  🌐 {COMPANY["website"]}  |  ☎ {COMPANY["phone"]}',
                st["company_detail"],
            ),
        ]

        header_table = Table(
            [[logo, header_right]],
            colWidths=[2.5 * cm, 14.5 * cm],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (0,  0),  0),
            ("RIGHTPADDING", (0, 0), (0,  0),  6),
            ("LEFTPADDING",  (1, 0), (1,  0),  4),
        ]))

        return [
            header_table,
            Spacer(1, 3 * mm),
            HRFlowable(width="100%", thickness=3, color=PRIMARY, spaceAfter=2),
            HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY, spaceAfter=6),
        ]

    # ── Metadata surat (nomor, perihal, lampiran, kepada) ─────────────────────
    def _build_meta(
        self,
        st: dict,
        nomor: str,
        perihal: str,
        lampiran: str,
        tujuan_nama: str,
        tujuan_jabatan: str,
        tujuan_institusi: str,
        tujuan_kota: str,
    ) -> list:
        rows = []

        # Bismillah
        rows += [
            Paragraph("Bismillahirrahmanirrahim", st["bismillah"]),
            Paragraph(
                "<i>Dengan menyebut nama Allah Yang Maha Pengasih lagi Maha Penyayang</i>",
                st["bismillah_latin"],
            ),
            Spacer(1, 4 * mm),
        ]

        # Tanggal kanan
        rows += [
            Paragraph(self._tanggal_id(), ParagraphStyle(
                "date", fontName="Helvetica", fontSize=10,
                textColor=TEXT_BLACK, alignment=TA_RIGHT,
            )),
            Spacer(1, 3 * mm),
        ]

        # Nomor, Perihal, Lampiran
        meta_data = [
            ["Nomor",    ":", nomor],
            ["Perihal",  ":", perihal],
            ["Lampiran", ":", lampiran or "-"],
        ]
        meta_table = Table(
            [[Paragraph(r[0], st["meta_label"]),
              Paragraph(r[1], st["meta_label"]),
              Paragraph(r[2], st["meta_label"])]
             for r in meta_data],
            colWidths=[2.5 * cm, 0.5 * cm, 14 * cm],
        )
        meta_table.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",  (0, 0), (-1, -1), 1),
        ]))
        rows += [meta_table, Spacer(1, 5 * mm)]

        # Kepada Yth.
        rows += [
            Paragraph("Kepada Yth.", st["body"]),
        ]
        if tujuan_jabatan:
            rows.append(Paragraph(f"Bapak/Ibu {tujuan_jabatan}", st["body"]))
        if tujuan_institusi:
            rows.append(Paragraph(tujuan_institusi, st["body"]))
        rows.append(Paragraph(f"di {tujuan_kota or 'Tempat'}", st["body"]))
        rows.append(Spacer(1, 5 * mm))

        return rows

    # ── Isi surat ─────────────────────────────────────────────────────────────
    def _build_body(self, st: dict, isi: str) -> list:
        rows = [
            Paragraph(
                "Assalamu'alaikum Warahmatullahi Wabarakatuh,",
                st["body_bold"],
            ),
            Spacer(1, 3 * mm),
        ]

        # Split paragraf dan render
        for para in isi.strip().split("\n\n"):
            para = para.strip()
            if not para:
                continue
            rows.append(Paragraph(para.replace("\n", " "), st["body"]))

        rows += [
            Spacer(1, 3 * mm),
            Paragraph(
                "Demikian surat ini kami sampaikan. Atas perhatian dan kerjasamanya, "
                "kami ucapkan terima kasih.",
                st["body"],
            ),
            Spacer(1, 4 * mm),
            Paragraph(
                "Wassalamu'alaikum Warahmatullahi Wabarakatuh.",
                st["body_bold"],
            ),
        ]
        return rows

    # ── Blok tanda tangan ─────────────────────────────────────────────────────
    def _build_signature(
        self,
        st: dict,
        penandatangan_nama: str,
        penandatangan_jabatan: str,
    ) -> list:
        return [
            Spacer(1, 8 * mm),
            Paragraph("Hormat kami,", st["signature"]),
            Paragraph(COMPANY["name"], st["signature_name"]),
            Spacer(1, 18 * mm),   # space untuk tanda tangan
            Paragraph(penandatangan_nama or COMPANY["direktur"], st["signature_name"]),
            Paragraph(penandatangan_jabatan or "Direktur", st["signature"]),
        ]

    # ── Main: generate PDF ────────────────────────────────────────────────────
    def generate_pdf(
        self,
        perihal: str,
        isi: str,
        tujuan_nama: str = "",
        tujuan_jabatan: str = "",
        tujuan_institusi: str = "",
        tujuan_kota: str = "Tempat",
        lampiran: str = "-",
        penandatangan_nama: str = "",
        penandatangan_jabatan: str = "",
        nomor: str | None = None,
    ) -> str:
        """Generate surat PDF. Returns absolute file path."""
        if nomor is None:
            nomor = self._next_nomor()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_perihal = re.sub(r"[^\w\s-]", "", perihal)[:30].strip().replace(" ", "_")
        filename = f"{ts}_{safe_perihal}.pdf"
        filepath = self.output_dir / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=2.0 * cm,
            title=f"Surat ATG — {perihal}",
            author=COMPANY["name"],
        )

        st = _styles()
        story = (
            self._build_header(st)
            + self._build_meta(st, nomor, perihal, lampiran,
                               tujuan_nama, tujuan_jabatan,
                               tujuan_institusi, tujuan_kota)
            + self._build_body(st, isi)
            + self._build_signature(st, penandatangan_nama, penandatangan_jabatan)
        )

        doc.build(story)
        return str(filepath)
