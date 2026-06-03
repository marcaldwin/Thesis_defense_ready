from backend.sage_review.services.analysis_service import AnalysisService
from backend.sage_review.services.feedback_generator import (
    generate_plain_language_diagnosis,
    generate_priority_fixes,
)


def test_weak_conclusion_feedback_mentions_objective_support_and_action():
    evidence = [
        {
            "Evidence Area": "Objective Support",
            "Similarity Score": 0.1,
            "Coverage Level": "Weak",
        },
        {
            "Evidence Area": "Summary of Main Findings",
            "Similarity Score": 0.2,
            "Coverage Level": "Weak",
        },
    ]
    score_result = {
        "risk_level": "High",
        "criteria_used": ["Objective Support", "Summary of Main Findings"],
    }

    diagnosis = generate_plain_language_diagnosis(
        "Conclusion",
        26.65,
        "High",
        [],
        ["Objective Support", "Summary of Main Findings"],
    )
    fixes = generate_priority_fixes(score_result, evidence, "Conclusion")
    combined = " ".join([diagnosis] + [fix["Suggested Fix"] for fix in fixes])

    assert "Objective Support" in combined
    assert "study objective" in combined or "each study objective" in combined
    assert "result" in combined or "table" in combined or "finding" in combined


def test_weak_results_feedback_mentions_metrics_or_objective_connection():
    evidence = [
        {
            "Evidence Area": "Model Evaluation Metrics",
            "Similarity Score": 0.1,
            "Coverage Level": "Weak",
        },
        {
            "Evidence Area": "Confusion Matrix or Error Analysis",
            "Similarity Score": 0.2,
            "Coverage Level": "Weak",
        },
        {
            "Evidence Area": "Objective-to-Result Connection",
            "Similarity Score": 0.2,
            "Coverage Level": "Weak",
        },
    ]
    score_result = {
        "risk_level": "High",
        "criteria_used": [
            "Model Evaluation Metrics",
            "Confusion Matrix or Error Analysis",
            "Objective-to-Result Connection",
        ],
    }

    fixes = generate_priority_fixes(
        score_result,
        evidence,
        "Results and Discussion",
    )
    combined = " ".join(fix["Suggested Fix"] for fix in fixes)

    assert "accuracy" in combined or "precision" in combined or "F1-score" in combined
    assert "confusion matrix" in combined
    assert "objective-to-result" in combined


def test_alignment_feedback_includes_pair_and_next_action():
    service = AnalysisService()
    explained = service.explain_alignment_weaknesses(
        [
            {
                "Section Pair": "Methodology <-> Results and Discussion",
                "Similarity Score": 0.258,
                "Alignment Level": "Weak Alignment",
                "Risk": "High",
                "Interpretation": "These sections appear weakly connected.",
            }
        ]
    )

    assert explained[0]["section_pair"] == "Methodology <-> Results and Discussion"
    assert "methodology" in explained[0]["reason"].lower()
    assert explained[0]["next_action"]


def test_add_clearer_evidence_does_not_appear_alone():
    evidence = [
        {
            "Evidence Area": "Objective Support",
            "Similarity Score": 0.1,
            "Coverage Level": "Weak",
        }
    ]
    score_result = {
        "risk_level": "High",
        "criteria_used": ["Objective Support"],
    }

    fixes = generate_priority_fixes(score_result, evidence, "Conclusion")
    combined = " ".join(fix["Suggested Fix"] for fix in fixes)

    assert "Add clearer evidence for objective support." not in combined
    assert "Conclusion" in " ".join(fix["Issue"] for fix in fixes)
    assert "Objective Support" in " ".join(fix["Issue"] for fix in fixes)
