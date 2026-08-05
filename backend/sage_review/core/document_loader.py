"""Document text extraction helpers for SAGE-Review uploads."""

from io import BytesIO
from pathlib import Path
import re

from docx import Document
from pypdf import PdfReader
import wordninja


def sanitize_unicode_text(text: object) -> str:
    """Replace malformed Unicode surrogates with safe replacement characters.

    Some PDFs contain broken character maps that cause PyPDF2 to return lone
    UTF-16 surrogate code points. Python can hold those values in ``str``, but
    they cannot be encoded as UTF-8 for hashing, JSON responses, logs, or LLM
    requests. Replacing only the invalid code points preserves the rest of the
    extracted manuscript.
    """
    if text is None:
        return ""
    return re.sub(r"[\ud800-\udfff]", "\ufffd", str(text))


def _letter_spacing_ratio(text: str) -> float:
    """Return the share of letters followed by a whitespace-separated letter."""
    letter_count = len(re.findall(r"[A-Za-z]", text))
    if not letter_count:
        return 0.0
    word_boundaries = len(re.findall(r"(?<=[A-Za-z])\s+(?=[A-Za-z])", text))
    return word_boundaries / letter_count


def has_suspicious_word_spacing(text: str) -> bool:
    """Detect pages where PDF extraction joined most English words together."""
    clean_text = sanitize_unicode_text(text)
    return (
        _letter_spacing_ratio(clean_text) < 0.075
        and bool(re.search(r"[A-Za-z]{18,}", clean_text))
    )


def repair_joined_words(text: str) -> str:
    """Split long alphabetic runs only when the whole page has broken spacing."""
    clean_text = sanitize_unicode_text(text)
    if not has_suspicious_word_spacing(clean_text):
        return clean_text

    def split_run(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.isupper():
            return token
        pieces = wordninja.split(token)
        return " ".join(pieces) if len(pieces) > 1 else token

    repaired = re.sub(r"[A-Za-z]{12,}", split_run, clean_text)
    repaired = re.sub(r"\bdata\s+set\b", "dataset", repaired, flags=re.I)
    repaired = re.sub(r"\bkey\s+point\b", "keypoint", repaired, flags=re.I)
    repaired = re.sub(r"(?<=[,;:!?])(?=[A-Za-z])", " ", repaired)
    repaired = re.sub(r"(?<=[.])(?=[A-Z])", " ", repaired)
    return repaired


def _pdf_extraction_quality(text: str) -> float:
    """Score an extraction by plausible word spacing and retained text."""
    clean_text = sanitize_unicode_text(text)
    letter_count = len(re.findall(r"[A-Za-z]", clean_text))
    if not letter_count:
        return float("-inf")

    spacing_ratio = _letter_spacing_ratio(clean_text)
    plausible_spacing = 1.0 - min(abs(spacing_ratio - 0.16) / 0.16, 1.0)
    long_run_letters = sum(
        max(0, len(run) - 17)
        for run in re.findall(r"[A-Za-z]{18,}", clean_text)
    )
    long_run_penalty = long_run_letters / letter_count
    retained_text_bonus = min(letter_count / 500.0, 1.0) * 0.1
    return plausible_spacing - (long_run_penalty * 2.0) + retained_text_bonus


def extract_best_page_text(page) -> str:
    """Try layout and plain PDF extraction, then select the more readable text."""
    candidates: list[str] = []
    extraction_options = (
        {
            "extraction_mode": "layout",
            "layout_mode_space_vertically": False,
        },
        {"extraction_mode": "plain"},
    )
    for options in extraction_options:
        try:
            candidate = sanitize_unicode_text(page.extract_text(**options) or "")
        except (TypeError, ValueError, KeyError):
            continue
        if candidate.strip() and candidate not in candidates:
            candidates.append(candidate)

    if not candidates:
        candidate = sanitize_unicode_text(page.extract_text() or "")
        if candidate.strip():
            candidates.append(candidate)
    if not candidates:
        return ""

    best_text = max(candidates, key=_pdf_extraction_quality)
    return repair_joined_words(best_text)


def normalize_extracted_text(text: object) -> str:
    """Clean text extracted from uploaded documents while preserving paragraphs."""
    if text is None:
        return ""

    clean_text = sanitize_unicode_text(text)
    clean_text = clean_text.replace("\x00", " ").replace("\xa0", " ")
    clean_text = clean_text.replace("\r\n", "\n").replace("\r", "\n")
    clean_text = re.sub(r"\b([A-Z]{2,})([a-z]+)\b", r"\1 \2", clean_text)
    clean_text = re.sub(r"(?<=[,;:!?])(?=[A-Za-z])", " ", clean_text)
    clean_text = re.sub(r"(?<=[.])(?=[A-Z])", " ", clean_text)

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
        page_text = extract_best_page_text(page)
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
