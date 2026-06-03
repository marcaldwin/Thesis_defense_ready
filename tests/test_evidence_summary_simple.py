from backend.sage_review.services.analysis_service import AnalysisService


def test_section_evidence_summary_keeps_only_section_relevant_criteria():
    service = AnalysisService()
    summary = service.build_section_evidence_summary(
        "Methodology",
        [
            {
                "Evidence Area": "Dataset Description",
                "Similarity Score": 0.2,
                "Coverage Level": "Weak",
                "Interpretation": "Dataset details are unclear.",
            },
            {
                "Evidence Area": "Summary of Main Findings",
                "Similarity Score": 0.9,
                "Coverage Level": "Strong",
                "Interpretation": "Conclusion-only criterion.",
            },
        ],
        ["Dataset Description"],
    )

    criteria = {row["criterion"] for row in summary["evidence_display_rows"]}
    assert criteria == {"Dataset Description"}


def test_negative_similarity_displays_as_zero_and_weak():
    service = AnalysisService()
    summary = service.build_section_evidence_summary(
        "Conclusion",
        [
            {
                "Evidence Area": "Objective Support",
                "Similarity Score": -0.038,
                "Coverage Level": "Weak",
                "Interpretation": "Objective support is missing.",
            }
        ],
        ["Objective Support"],
    )

    row = summary["evidence_display_rows"][0]
    assert row["Similarity Score"] == 0.0
    assert row["display_score_label"] == "0%"
    assert row["Coverage Level"] == "Weak"


def test_default_evidence_display_does_not_return_every_criterion():
    service = AnalysisService()
    rows = [
        {
            "Evidence Area": f"Criterion {i}",
            "Similarity Score": i / 20,
            "Coverage Level": "Weak" if i < 8 else "Strong",
            "Interpretation": "Sample row.",
        }
        for i in range(12)
    ]
    expected = [row["Evidence Area"] for row in rows]

    summary = service.build_section_evidence_summary("Introduction", rows, expected)

    assert len(summary["evidence_display_rows"]) < len(rows)


def test_manuscript_evidence_summary_simple_fields_exist():
    service = AnalysisService()
    section_summary = service.build_section_evidence_summary(
        "Results and Discussion",
        [
            {
                "Evidence Area": "Objective-to-Result Connection",
                "Similarity Score": 0.1,
                "Coverage Level": "Weak",
                "Interpretation": "Objective mapping is missing.",
            },
            {
                "Evidence Area": "Model Evaluation Metrics",
                "Similarity Score": 0.8,
                "Coverage Level": "Strong",
                "Interpretation": "Metrics are reported.",
            },
        ],
        ["Objective-to-Result Connection", "Model Evaluation Metrics"],
    )
    manuscript_summary = service.build_manuscript_evidence_summary_simple(
        [
            {
                "section_name": "Results and Discussion",
                **section_summary,
            }
        ]
    )

    assert "critical_missing_evidence" in manuscript_summary
    assert "top_weak_evidence" in manuscript_summary
    assert "strongest_evidence" in manuscript_summary
    assert manuscript_summary["critical_missing_evidence"]
