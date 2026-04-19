import io
import logging

import fitz  # PyMuPDF
from PIL import Image
import pytesseract

import platform
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# On Linux (Render), tesseract is found automatically via PATH

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path):
    doc = fitz.open(file_path)
    pages_data = []

    for i, page in enumerate(doc):
        # Try direct text extraction first
        text = page.get_text()

        if not text.strip():
            try:
                # Render page as high-res image and run OCR on it
                mat = fitz.Matrix(2, 2)  # 2x zoom = ~144 DPI
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                text = pytesseract.image_to_string(pil_image, lang="eng")
                if text.strip():
                    logger.info("OCR extracted text from page %s", i + 1)
                else:
                    logger.warning("OCR returned empty text for page %s", i + 1)
            except Exception as exc:
                logger.warning("OCR failed on page %s: %s", i + 1, exc)
                text = ""

        pages_data.append({"page": i + 1, "text": text})

    return pages_data


def split_text(text, chunk_size=500, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks