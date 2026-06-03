from backend.sage_review.core.evidence_analyzer import get_section_specific_criteria


def test_methodology_does_not_use_conclusion_criteria():
    methodology = get_section_specific_criteria("Methodology")

    assert "Summary of Main Findings" not in methodology
    assert "Future Work" not in methodology
    assert "Dataset Description" in methodology


def test_conclusion_does_not_use_methodology_criteria():
    conclusion = get_section_specific_criteria("Conclusion")

    assert "Dataset Description" not in conclusion
    assert "Model or Algorithm Description" not in conclusion
    assert "Summary of Main Findings" in conclusion


def test_results_does_not_use_introduction_criteria():
    results = get_section_specific_criteria("Results and Discussion")

    assert "Problem Context" not in results
    assert "Research Gap" not in results
    assert "Model Evaluation Metrics" in results
