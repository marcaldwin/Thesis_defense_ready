import hashlib

from backend.sage_review.core.document_loader import (
    normalize_extracted_text,
    sanitize_unicode_text,
)
from backend.sage_review.services.analysis_service import AnalysisService


def test_pdf_surrogates_are_replaced_before_utf8_encoding():
    extracted = "Results before \udce2\udce2 malformed text after"

    sanitized = normalize_extracted_text(extracted)

    assert "\udce2" not in sanitized
    assert "\ufffd\ufffd" in sanitized
    hashlib.sha256(sanitized.encode("utf-8")).hexdigest()


def test_analysis_normalizers_sanitize_pasted_and_uploaded_text():
    service = AnalysisService()
    malformed = "CHAPTER 1\nIntroduction \ud800 content"

    single_section = service.normalize_text(malformed)
    full_manuscript = service.normalize_manuscript_text(malformed)

    assert single_section == "CHAPTER 1 Introduction \ufffd content"
    assert full_manuscript == "CHAPTER 1\nIntroduction \ufffd content"
    single_section.encode("utf-8")
    full_manuscript.encode("utf-8")


def test_unicode_sanitizer_preserves_valid_unicode():
    valid_text = "Filipino thesis — café ✓"

    assert sanitize_unicode_text(valid_text) == valid_text
