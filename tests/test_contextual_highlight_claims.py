from backend.sage_review.core.highlight_analyzer import classify_claim


def test_file_renaming_confidentiality_is_not_high_overclaim():
    result = classify_claim(
        "Each file is renamed using a simple code ASL_ALWAYS_P01_001 that "
        "represents the participant and the target word, without using real "
        "names to maintain confidentiality."
    )

    assert result is not None
    assert result["claim_category"] == "Data Handling Statement"
    assert result["severity"] != "High"


def test_citation_supported_claim_is_not_high_overclaim():
    result = classify_claim(
        "Mobile sign language recognition studies also note that frame "
        "extraction, sampling rate, and real-time mobile input conditions can "
        "affect recognition performance (Kim et al., 2024)."
    )

    assert result is not None
    assert result["claim_category"] == "Citation-Supported Claim"
    assert result["severity"] != "High"


def test_guarantees_accuracy_is_high_overclaim():
    result = classify_claim("The system guarantees 100% accuracy with no errors.")

    assert result is not None
    assert result["claim_category"] == "Strong Unsupported Overclaim"
    assert result["severity"] == "High"


def test_consistent_recognition_result_needs_metric_not_high_overclaim():
    result = classify_claim(
        "Some signs were recognized consistently, while others were confused "
        "with visually or temporally similar signs."
    )

    assert result is not None
    assert result["claim_category"] in {"Result Claim Needing Metric", "Vague Evidence"}
    assert result["severity"] != "High"
