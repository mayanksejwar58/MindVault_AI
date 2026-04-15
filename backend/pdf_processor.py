import io
import logging

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

ocr = None
_ocr_init_attempted = False


def get_ocr():
    """Lazily initialize PaddleOCR if available.

    If paddle/paddleocr runtime dependencies are missing, return None.
    """
    global ocr
    global _ocr_init_attempted

    if ocr is None and not _ocr_init_attempted:
        _ocr_init_attempted = True
        try:
            from paddleocr import PaddleOCR

            ocr = PaddleOCR(use_angle_cls=True, lang="en")
            logger.info("PaddleOCR initialized successfully")
        except Exception as exc:
            logger.warning("PaddleOCR unavailable; OCR will be skipped on image-only pages: %s", exc)
            ocr = None

    return ocr


def extract_text_from_pdf(file_path):
    doc = fitz.open(file_path)
    pages_data = []

    for i, page in enumerate(doc):
        text = page.get_text()

        if not text.strip():
            images = page.get_images(full=True)
            text = ""
            ocr_engine = get_ocr()

            for img in images:
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

                if ocr_engine is not None:
                    result = ocr_engine.ocr(image)
                    if result:
                        for block in result:
                            if isinstance(block, list):
                                for line in block:
                                    if (
                                        isinstance(line, (list, tuple))
                                        and len(line) >= 2
                                        and isinstance(line[1], (list, tuple))
                                        and line[1]
                                    ):
                                        text += f"{line[1][0]} "
                else:
                    logger.warning(
                        "Skipping OCR on page %s because PaddleOCR is unavailable",
                        i + 1,
                    )

        pages_data.append({
            "page": i + 1,
            "text": text,
        })

    return pages_data


def split_text(text, chunk_size=500, overlap=100):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    return chunks
