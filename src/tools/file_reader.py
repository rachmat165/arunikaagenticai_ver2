"""
Membaca dan mengekstrak teks dari berbagai format file attachment Telegram.
Mendukung: PDF, DOCX, DOC, TXT, MD, dan gambar (via AI vision jika tersedia).
"""

import asyncio
import os
from pathlib import Path


SUPPORTED_TEXT = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".py"}
SUPPORTED_PDF  = {".pdf"}
SUPPORTED_DOCX = {".docx", ".doc"}
SUPPORTED_IMG  = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_CHARS      = 12_000   # batas karakter yang dikirim ke AI


async def extract_text(file_path: str, file_name: str) -> dict:
    """
    Ekstrak teks dari file. Returns:
      {'text': str, 'pages': int, 'file_name': str, 'file_type': str}
    atau {'error': str}
    """
    ext = Path(file_name).suffix.lower()

    def _read():
        if ext in SUPPORTED_TEXT:
            return _read_text(file_path)
        elif ext in SUPPORTED_PDF:
            return _read_pdf(file_path)
        elif ext in SUPPORTED_DOCX:
            return _read_docx(file_path)
        else:
            return {
                "error": (
                    f"Format *{ext}* belum didukung.\n"
                    f"Format yang didukung: PDF, DOCX, TXT, MD, CSV"
                )
            }

    try:
        result = await asyncio.to_thread(_read)
        if "error" not in result:
            result["file_name"] = file_name
            result["file_type"] = ext.lstrip(".")
        return result
    except Exception as e:
        return {"error": f"Gagal membaca file: {e}"}


def _read_text(path: str) -> dict:
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = Path(path).read_text(encoding=enc)
            return {"text": text[:MAX_CHARS], "pages": 1}
        except UnicodeDecodeError:
            continue
    return {"error": "Tidak bisa decode file teks"}


def _read_pdf(path: str) -> dict:
    try:
        import pdfplumber
        parts = []
        pages = 0
        with pdfplumber.open(path) as pdf:
            pages = len(pdf.pages)
            for page in pdf.pages[:30]:
                t = page.extract_text()
                if t:
                    parts.append(t.strip())
        text = "\n\n".join(parts)
        if not text.strip():
            return {"error": "PDF tidak mengandung teks yang bisa diekstrak (mungkin scan/gambar)"}
        return {"text": text[:MAX_CHARS], "pages": pages}
    except ImportError:
        return {"error": "Library pdfplumber tidak tersedia"}


def _read_docx(path: str) -> dict:
    try:
        from docx import Document
        doc = Document(path)
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paras)
        if not text.strip():
            return {"error": "Dokumen DOCX kosong atau tidak mengandung teks"}
        return {"text": text[:MAX_CHARS], "pages": 1}
    except ImportError:
        return {"error": "Library python-docx tidak tersedia"}


def is_image(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in SUPPORTED_IMG


def is_supported(file_name: str) -> bool:
    ext = Path(file_name).suffix.lower()
    return ext in (SUPPORTED_TEXT | SUPPORTED_PDF | SUPPORTED_DOCX)
