"""Document text extraction helpers for SAGE-Review uploads."""

from io import BytesIO
from pathlib import Path
import re

from docx import Document
from PyPDF2 import PdfReader


def normalize_extracted_text(text: object) -> str:
    """Clean text extracted from uploaded documents while preserving paragraphs."""
    if text is None:
        return ""

    clean_text = str(text)
    clean_text = clean_text.replace("\x00", " ").replace("\xa0", " ")
    clean_text = clean_text.replace("\r\n", "\n").replace("\r", "\n")

    # PDF extraction often joins words at lowercase-to-uppercase or digit
    # boundaries. This repair improves model input without using scoring rules.
    clean_text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", clean_text)
    clean_text = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", clean_text)
    clean_text = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", clean_text)

    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in clean_text.split("\n")
    ]
    paragraphs = [line for line in lines if line]
    return "\n\n".join(paragraphs)


def extract_text_from_txt(uploaded_file) -> str:
    """Read text from an uploaded TXT file."""
    raw_bytes = uploaded_file.getvalue()
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return normalize_extracted_text(raw_bytes.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise ValueError("The TXT file could not be decoded as readable text.")


def extract_text_from_docx(uploaded_file) -> str:
    """Extract paragraph text from an uploaded DOCX file."""
    document = Document(BytesIO(uploaded_file.getvalue()))
    paragraphs = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]
    return normalize_extracted_text("\n\n".join(paragraphs))


def extract_text_from_pdf(uploaded_file) -> str:
    """Extract text from all pages of an uploaded PDF file."""
    reader = PdfReader(BytesIO(uploaded_file.getvalue()))
    page_texts = []
    for page in reader.pages:
        try:
            page_text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            page_text = page.extract_text() or ""
        if page_text.strip():
            page_texts.append(page_text.strip())
    return normalize_extracted_text("\n\n".join(page_texts))


def extract_text_from_uploaded_file(uploaded_file) -> str:
    """Extract text from a supported uploaded document."""
    if uploaded_file is None:
        return ""

    extension = Path(uploaded_file.name).suffix.lower()
    if extension == ".txt":
        return extract_text_from_txt(uploaded_file)
    if extension == ".docx":
        return extract_text_from_docx(uploaded_file)
    if extension == ".pdf":
        return extract_text_from_pdf(uploaded_file)

    raise ValueError(
        "Unsupported file type. Please upload a .txt, .docx, or .pdf document."
    )
