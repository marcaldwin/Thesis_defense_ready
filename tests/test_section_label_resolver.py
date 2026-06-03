from backend.sage_review.core.section_extractor import (
    extract_sections_with_metadata,
    normalize_heading,
)
from backend.sage_review.services.analysis_service import AnalysisService


def test_methodology_heading_resolves_to_methodology_not_unknown():
    service = AnalysisService()
    resolved = service.resolve_section_label(
        section_name="METHODOLOGY",
        scoring_section="Methodology",
        semantic_prediction="Unknown / Mixed Section",
    )

    assert resolved["resolved_section_label"] == "Methodology"
    assert resolved["resolved_section_label"] != "Unknown / Mixed Section"
    assert resolved["section_label_source"] == "heading"


def test_results_heading_resolves_to_results_and_discussion_not_unknown():
    service = AnalysisService()
    resolved = service.resolve_section_label(
        section_name="RESULTS AND DISCUSSION",
        scoring_section="Results and Discussion",
        semantic_prediction="Unknown / Mixed Section",
    )

    assert resolved["resolved_section_label"] == "Results and Discussion"
    assert resolved["resolved_section_label"] != "Unknown / Mixed Section"


def test_conclusion_heading_resolves_to_conclusion_not_unknown():
    assert normalize_heading("SUMMARY, CONCLUSIONS, AND RECOMMENDATIONS") == "Conclusion"


def test_objectives_derived_from_introduction_uses_clear_status_wording():
    text = """
INTRODUCTION
This study focuses on thesis review support. The general objective of this
study is to develop a system that evaluates thesis defense readiness.
Specifically, this study aims to identify weak evidence coverage and provide
revision guidance for students before defense.

METHODOLOGY
The study used a software development approach with text analysis components.

RESULTS AND DISCUSSION
The results present section analysis, evidence coverage, and score feedback.

SUMMARY, CONCLUSIONS, AND RECOMMENDATIONS
The study concludes that structured review feedback can support revision.
"""

    result = extract_sections_with_metadata(text)
    objective_heading = next(
        heading
        for heading in result["major_detected_headings"]
        if heading["normalized_section"] == "Objectives of the Study"
    )

    assert "Objectives of the Study" in result["sections"]
    assert objective_heading["status"] == "Derived Subsection from Introduction"
    assert "derived from the Introduction section" in objective_heading["explanation"]
