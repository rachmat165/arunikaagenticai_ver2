from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN

class DocumentGenerator:
    BRAND_COLOR = HexColor("#0066CC")
    COMPANY_NAME = "PT. Arunika Teknologi Global"
    COMPANY_ADDRESS = "Jl. Calung No. 7, Kota Bandung, Jawa Barat 40223"
    COMPANY_PHONE = "+62-274-1234567"
    COMPANY_EMAIL = "corsec@arunika2045.com"

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_letter(self, recipient: str, subject: str, body: str, signature_name: str = "Rachmat A.K.\nDirector") -> str:
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_letter.pdf"
        filepath = self.output_dir / "surat" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        c = canvas.Canvas(str(filepath), pagesize=A4)
        width, height = A4

        c.setFont("Helvetica", 10)
        c.drawString(inch * 0.5, height - inch * 0.5, self.COMPANY_NAME)
        c.drawString(inch * 0.5, height - inch * 0.7, self.COMPANY_ADDRESS)
        c.drawString(inch * 0.5, height - inch * 0.9, self.COMPANY_PHONE)
        c.drawString(inch * 0.5, height - inch * 1.1, self.COMPANY_EMAIL)

        c.setLineWidth(2)
        c.setStrokeColor(self.BRAND_COLOR)
        c.line(inch * 0.5, height - inch * 1.3, width - inch * 0.5, height - inch * 1.3)

        y = height - inch * 2
        c.setFont("Helvetica-Bold", 11)
        c.drawString(inch * 0.5, y, f"Kepada: {recipient}")

        y -= inch * 0.3
        c.setFont("Helvetica", 10)
        c.drawString(inch * 0.5, y, f"Perihal: {subject}")

        y -= inch * 0.5
        c.drawString(inch * 0.5, y, f"Tanggal: {datetime.now().strftime('%d-%m-%Y')}")

        y -= inch * 0.8
        c.setFont("Helvetica", 10)
        body_lines = body.split("\n")
        for line in body_lines:
            c.drawString(inch * 0.5, y, line[:90])
            y -= inch * 0.25
            if y < inch:
                c.showPage()
                y = height - inch

        y -= inch * 0.5
        c.setFont("Helvetica", 9)
        c.drawString(inch * 0.5, y, "Hormat kami,")

        y -= inch * 1
        c.setFont("Helvetica", 9)
        for line in signature_name.split("\n"):
            c.drawString(inch * 0.5, y, line)
            y -= inch * 0.25

        c.save()
        return str(filepath)

    def create_presentation(self, title: str, slides_data: list[dict]) -> str:
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_presentation.pptx"
        filepath = self.output_dir / "presentasi" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)

        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title.text = title
        subtitle.text = f"PT. Arunika Teknologi Global\n{datetime.now().strftime('%d-%m-%Y')}"

        for slide_data in slides_data:
            bullet_slide_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(bullet_slide_layout)
            shapes = slide.shapes

            title_shape = shapes.title
            body_shape = shapes.placeholders[1]

            title_shape.text = slide_data.get("title", "Slide")

            tf = body_shape.text_frame
            tf.clear()

            for point in slide_data.get("points", []):
                p = tf.add_paragraph()
                p.text = point
                p.level = 0

        prs.save(str(filepath))
        return str(filepath)
