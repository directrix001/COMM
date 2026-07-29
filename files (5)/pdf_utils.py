"""
PDF -> plain text.

Kept as its own module so the extraction strategy can be swapped later
(e.g. add OCR fallback for scanned SOPs with pytesseract) without touching
anything else in the app.
"""
from pypdf import PdfReader
import io


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    full_text = "\n".join(pages)

    if not full_text.strip():
        raise ValueError(
            "No extractable text found in this PDF. It may be a scanned "
            "image — OCR isn't wired up yet."
        )
    return full_text
