"""Expert/adviser validation storage and summary utilities for SAGE-Review."""

from datetime import datetime
from pathlib import Path

import pandas as pd


VALIDATION_COLUMNS = [
    "timestamp",
    "analysis_mode",
    "system_detected_section",
    "system_score",
    "system_risk_level",
    "evaluator_name_or_code",
    "sample_id_or_document_name",
    "detected_section_correct",
    "score_reasonable_rating",
    "feedback_useful_rating",
    "defense_questions_relevant_rating",
    "recommendations_acceptable_rating",
    "comments",
]


def save_validation_response(
    response: dict[str, object],
    output_path: str = "data/expert_validation_results.csv",
) -> str:
    """Append one expert/adviser validation response to CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    row = {column: response.get(column, "") for column in VALIDATION_COLUMNS}
    if not row["timestamp"]:
        row["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    file_exists = path.exists()
    pd.DataFrame([row], columns=VALIDATION_COLUMNS).to_csv(
        path,
        mode="a",
        header=not file_exists,
        index=False,
    )
    return str(path)


def load_validation_results(
    output_path: str = "data/expert_validation_results.csv",
) -> pd.DataFrame:
    """Load saved expert/adviser validation responses."""
    path = Path(output_path)
    if not path.exists():
        return pd.DataFrame(columns=VALIDATION_COLUMNS)
    return pd.read_csv(path)


def compute_validation_summary(df: pd.DataFrame) -> dict[str, object]:
    """Compute aggregate validation metrics from saved responses."""
    if df.empty:
        return {
            "total_validation_responses": 0,
            "mean_score_reasonableness": 0.0,
            "mean_feedback_usefulness": 0.0,
            "mean_question_relevance": 0.0,
            "mean_recommendation_acceptability": 0.0,
            "correct_section_detection_percentage": 0.0,
        }

    score_reasonable = pd.to_numeric(
        df.get("score_reasonable_rating"),
        errors="coerce",
    )
    feedback_useful = pd.to_numeric(
        df.get("feedback_useful_rating"),
        errors="coerce",
    )
    question_relevant = pd.to_numeric(
        df.get("defense_questions_relevant_rating"),
        errors="coerce",
    )
    recommendation_acceptable = pd.to_numeric(
        df.get("recommendations_acceptable_rating"),
        errors="coerce",
    )

    section_correct = (
        df.get("detected_section_correct", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )
    answered_correctness = section_correct[section_correct.isin(["yes", "no"])]
    correct_percentage = (
        round(float((answered_correctness == "yes").mean()) * 100, 2)
        if not answered_correctness.empty
        else 0.0
    )

    return {
        "total_validation_responses": int(len(df)),
        "mean_score_reasonableness": round(float(score_reasonable.mean()), 2)
        if not score_reasonable.dropna().empty
        else 0.0,
        "mean_feedback_usefulness": round(float(feedback_useful.mean()), 2)
        if not feedback_useful.dropna().empty
        else 0.0,
        "mean_question_relevance": round(float(question_relevant.mean()), 2)
        if not question_relevant.dropna().empty
        else 0.0,
        "mean_recommendation_acceptability": round(
            float(recommendation_acceptable.mean()),
            2,
        )
        if not recommendation_acceptable.dropna().empty
        else 0.0,
        "correct_section_detection_percentage": correct_percentage,
    }
