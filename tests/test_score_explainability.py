from backend.sage_review.services.analysis_service import AnalysisService


def test_section_score_breakdown_exists_in_explainability_output():
    service = AnalysisService()
    result = service.build_section_score_explainability(
        section_name="Methodology",
        evidence_coverage=[
            {
                "Evidence Area": "Dataset Description",
                "Similarity Score": 0.2,
                "Coverage Level": "Weak",
                "Interpretation": "Dataset details are unclear.",
            }
        ],
        score_result={
            "defense_score": 45.0,
            "score_breakdown": {
                "average_similarity": 0.2,
                "risk_deduction": 15.0,
                "final_score": 45.0,
            },
        },
        classification_confidence=0.8,
        word_count=120,
        priority_fixes=[
            {
                "Suggested Fix": "State dataset source, size, classes, split, and distribution."
            }
        ],
    )

    assert "score_breakdown" in result
    assert result["score_breakdown"]["evidence_coverage_score"] == 20.0
    assert result["score_breakdown"]["final_score"] == 45.0
    assert result["score_reasons"]
    assert result["priority_actions"]
