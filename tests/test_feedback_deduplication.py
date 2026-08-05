import pytest

from backend.sage_review.services.feedback_generator import (
    generate_priority_fixes,
    generate_revision_suggestions,
)
from backend.sage_review.services.gemini_feedback_generator import _validate_feedback


def test_priority_fixes_do_not_repeat_the_primary_fix():
    evidence = [
        {
            "Evidence Area": "Dataset Description",
            "Coverage Level": "Weak",
            "Similarity Score": 0.1,
        },
        {
            "Evidence Area": "Data Collection Procedure",
            "Coverage Level": "Weak",
            "Similarity Score": 0.2,
        },
    ]
    score = {
        "risk_level": "High",
        "criteria_used": ["Dataset Description", "Data Collection Procedure"],
    }

    fixes = generate_priority_fixes(score, evidence, "Methodology")
    wording = [fix["Suggested Fix"] for fix in fixes]

    assert len(wording) == len(set(wording))


def test_revision_suggestions_are_unique():
    suggestions = generate_revision_suggestions(
        "Methodology",
        [],
        {"risk_level": "High", "criteria_used": []},
    )

    assert len(suggestions) == len(set(suggestions))


def test_gemini_feedback_removes_repeated_action_and_list_items():
    result = _validate_feedback(
        {
            "feedback_mode": "Gemini-grounded",
            "dynamic_diagnosis": "The dataset description needs more detail.",
            "dynamic_next_best_action": "State the dataset source and size.",
            "dynamic_panel_risk": "The panel may question dataset reliability.",
            "dynamic_suggested_revision_wording": [
                "State the dataset source and size.",
                "The dataset contains [number] samples from [source].",
                "The dataset contains [number] samples from [source]!",
            ],
            "dynamic_defense_questions": [
                "How was the dataset selected?",
                "How was the dataset selected?",
            ],
        }
    )

    assert result["dynamic_suggested_revision_wording"] == [
        "The dataset contains [number] samples from [source]."
    ]
    assert result["dynamic_defense_questions"] == [
        "How was the dataset selected?"
    ]


def test_gemini_feedback_rejects_wrong_list_types():
    with pytest.raises(ValueError):
        _validate_feedback(
            {
                "dynamic_diagnosis": "Diagnosis",
                "dynamic_next_best_action": "Action",
                "dynamic_panel_risk": "Risk",
                "dynamic_suggested_revision_wording": "not a list",
                "dynamic_defense_questions": [],
            }
        )
