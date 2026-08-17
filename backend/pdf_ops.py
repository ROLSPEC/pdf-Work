"""Server-side PDF operations using pypdf and pikepdf."""
import io
from typing import Optional
from pypdf import PdfReader, PdfWriter
import pikepdf


def extract_text(data: bytes) -> str:
    """Extract all text from a PDF."""
    reader = PdfReader(io.BytesIO(data))
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        parts.append(f"[page {i+1}]\n{t}")
    return "\n\n".join(parts)


def extract_text_by_page(data: bytes) -> list[dict]:
    reader = PdfReader(io.BytesIO(data))
    out = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        out.append({"page": i + 1, "text": t})
    return out


def page_count(data: bytes) -> int:
    return len(PdfReader(io.BytesIO(data)).pages)


def protect(data: bytes, password: str) -> bytes:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        buf = io.BytesIO()
        pdf.save(buf, encryption=pikepdf.Encryption(owner=password, user=password, R=6))
        return buf.getvalue()


def unlock(data: bytes, password: str) -> bytes:
    with pikepdf.open(io.BytesIO(data), password=password) as pdf:
        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()


def flatten(data: bytes) -> bytes:
    """Flatten forms and annotations."""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            if "/Annots" in page:
                del page["/Annots"]
        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()


def repair(data: bytes) -> bytes:
    """Try to repair a PDF by re-saving."""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        buf = io.BytesIO()
        pdf.save(buf, fix_metadata_version=True, linearize=True)
        return buf.getvalue()


def strip_metadata(data: bytes) -> bytes:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        with pdf.open_metadata() as meta:
            meta.clear()
        if pdf.docinfo:
            for k in list(pdf.docinfo.keys()):
                del pdf.docinfo[k]
        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()


def to_text_file(data: bytes) -> bytes:
    return extract_text(data).encode("utf-8")


def bates_stamp(data: bytes, prefix: str = "BATES", start: int = 1) -> bytes:
    """Add Bates numbering using reportlab overlay."""
    from reportlab.pdfgen import canvas
    from pypdf import PdfWriter as _Writer  # local alias

    src = PdfReader(io.BytesIO(data))
    writer = _Writer()
    for i, page in enumerate(src.pages):
        box = page.mediabox
        w = float(box.width)
        h = float(box.height)
        stamp_buf = io.BytesIO()
        c = canvas.Canvas(stamp_buf, pagesize=(w, h))
        c.setFont("Helvetica-Bold", 10)
        c.setFillGray(0.2)
        c.drawRightString(w - 24, 18, f"{prefix}-{start + i:06d}")
        c.save()
        stamp_buf.seek(0)
        stamp_page = PdfReader(stamp_buf).pages[0]
        page.merge_page(stamp_page)
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
