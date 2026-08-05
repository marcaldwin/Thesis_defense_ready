from backend.sage_review.core.document_loader import (
    extract_best_page_text,
    has_suspicious_word_spacing,
    repair_joined_words,
)


class FakePdfPage:
    def extract_text(self, **options):
        if options.get("extraction_mode") == "layout":
            return "Thischapterpresentsthesummaryofthestudyandtheconclusions."
        return "This chapter presents the summary of the study and the conclusions."


def test_pdf_extractor_selects_candidate_with_normal_word_spacing():
    assert extract_best_page_text(FakePdfPage()) == (
        "This chapter presents the summary of the study and the conclusions."
    )


def test_joined_word_repair_only_runs_for_suspicious_text():
    joined = (
        "Thischapterpresentsthesummaryofthestudy,"
        "includingthedatasetcollectionandkeypointextraction."
    )

    assert has_suspicious_word_spacing(joined)
    repaired = repair_joined_words(joined)

    assert "This chapter presents the summary of the study" in repaired
    assert "including the dataset collection and keypoint extraction" in repaired


def test_normal_manuscript_spacing_is_not_modified():
    normal = (
        "This chapter presents the internationalization methodology and "
        "recommendations for future improvement."
    )

    assert not has_suspicious_word_spacing(normal)
    assert repair_joined_words(normal) == normal
