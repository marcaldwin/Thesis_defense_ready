"""Evaluation dataset utilities for SAGE-Review.

This module runs the existing AI/NLP analysis pipeline against a labeled CSV
dataset so the system can be compared with manual section labels and scores.
"""

from pathlib import Path
import re
import time

import pandas as pd

from backend.sage_review.core.ai_analyzer import (
    analyze_evidence_coverage,
    classify_section_zero_shot,
)
from backend.sage_review.core.ai_scoring import compute_defense_readiness_score


REQUIRED_COLUMNS = [
    "sample_id",
    "section_text",
    "true_section",
    "manual_score",
    "manual_issues",
]

TEMPLATE_ROWS = [
    {
        "sample_id": "sample_001",
        "section_text": "Paste one thesis section here.",
        "true_section": "Methodology",
        "manual_score": 75,
        "manual_issues": "Dataset Description; Model Evaluation Metrics",
    },
    {
        "sample_id": "sample_002",
        "section_text": "Paste another thesis section here.",
        "true_section": "Results and Discussion",
        "manual_score": 68,
        "manual_issues": "Confusion Matrix / Error Analysis; Usability Evaluation",
    },
]


def _clean_text(value: object) -> str:
    """Convert CSV values into safe plain text."""
    if pd.isna(value):
        return ""
    text = str(value)
    text = text.replace("\x00", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_issue_list(value: object) -> list[str]:
    """Parse a manual or system issue list into normalized issue strings."""
    text = _clean_text(value)
    if not text:
        return []
    parts = re.split(r"[;,|]\s*|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def _normalize_issue_text(value: str) -> set[str]:
    """Return meaningful lowercase tokens for issue comparison."""
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "for",
        "in",
        "is",
        "of",
        "or",
        "the",
        "to",
        "with",
    }
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    return {token for token in tokens if token not in stopwords and len(token) > 2}


def _issues_overlap(manual_issue: str, system_issue: str) -> bool:
    """Check whether two issue descriptions refer to a similar concern."""
    manual_tokens = _normalize_issue_text(manual_issue)
    system_tokens = _normalize_issue_text(system_issue)
    if not manual_tokens or not system_tokens:
        return False

    overlap = manual_tokens.intersection(system_tokens)
    required_overlap = 1 if min(len(manual_tokens), len(system_tokens)) <= 2 else 2
    return len(overlap) >= required_overlap


def _sample_issue_agreement(manual_issues: object, system_weak_areas: object) -> float:
    """Compute a per-sample weak issue agreement score from 0.00 to 1.00."""
    manual_items = _parse_issue_list(manual_issues)
    system_items = _parse_issue_list(system_weak_areas)

    if not manual_items and not system_items:
        return 1.0
    if not manual_items or not system_items:
        return 0.0

    matched_manual_count = 0
    for manual_issue in manual_items:
        if any(_issues_overlap(manual_issue, system_issue) for system_issue in system_items):
            matched_manual_count += 1

    return round(matched_manual_count / len(manual_items), 4)


def ensure_evaluation_dataset_template(
    output_path: str = "data/evaluation_dataset_template.csv",
) -> str:
    """Create the evaluation dataset template if it does not already exist."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(TEMPLATE_ROWS, columns=REQUIRED_COLUMNS).to_csv(path, index=False)
    return str(path)


def load_evaluation_dataset(csv_file_or_path) -> pd.DataFrame:
    """Load and validate an evaluation CSV from an upload object or file path."""
    if csv_file_or_path is None:
        raise ValueError("Please upload a CSV evaluation dataset.")

    df = pd.read_csv(csv_file_or_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(
            "The evaluation CSV is missing required columns: "
            + ", ".join(missing_columns)
        )

    df = df[REQUIRED_COLUMNS].copy()
    df["sample_id"] = df["sample_id"].map(_clean_text)
    df["section_text"] = df["section_text"].map(_clean_text)
    df["true_section"] = df["true_section"].map(_clean_text)
    df["manual_issues"] = df["manual_issues"].map(_clean_text)
    df["manual_score"] = pd.to_numeric(df["manual_score"], errors="coerce")
    df = df[df["section_text"] != ""].reset_index(drop=True)

    if df.empty:
        raise ValueError("The evaluation CSV does not contain readable section_text values.")

    return df


def run_evaluation_on_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Run section classification, evidence coverage, and scoring for each sample."""
    result_rows = []

    for _, row in df.iterrows():
        sample_start = time.perf_counter()
        sample_id = _clean_text(row.get("sample_id", ""))
        section_text = _clean_text(row.get("section_text", ""))
        true_section = _clean_text(row.get("true_section", ""))
        manual_score = row.get("manual_score")
        manual_issues = _clean_text(row.get("manual_issues", ""))

        classification = classify_section_zero_shot(section_text)
        predicted_section = str(classification["predicted_section"])
        confidence = round(float(classification["confidence"]) * 100, 2)

        evidence_result = analyze_evidence_coverage(predicted_section, section_text)
        evidence_coverage = list(evidence_result["evidence_coverage"])
        score_result = compute_defense_readiness_score(
            evidence_coverage,
            predicted_section,
            classification_confidence=float(classification["confidence"]),
        )

        weak_areas = [
            str(item["Evidence Area"])
            for item in evidence_coverage
            if str(item["Coverage Level"]) == "Weak"
        ]
        expected_weak_areas = [
            str(item["Evidence Area"])
            for item in evidence_coverage
            if str(item["Coverage Level"]) == "Weak"
            and str(item["Evidence Area"]) in set(score_result["expected_areas"])
        ]

        processing_time = round(time.perf_counter() - sample_start, 2)
        system_score = round(float(score_result["defense_score"]), 2)
        manual_score_value = (
            round(float(manual_score), 2) if pd.notna(manual_score) else None
        )
        absolute_difference = (
            round(abs(system_score - manual_score_value), 2)
            if manual_score_value is not None
            else None
        )
        issue_agreement = _sample_issue_agreement(
            manual_issues,
            "; ".join(weak_areas),
        )

        result_rows.append(
            {
                "sample_id": sample_id,
                "true_section": true_section,
                "predicted_section": predicted_section,
                "section_correct": predicted_section.lower() == true_section.lower(),
                "confidence": confidence,
                "manual_score": manual_score_value,
                "system_score": system_score,
                "absolute_score_difference": absolute_difference,
                "risk_level": score_result["risk_level"],
                "manual_issues": manual_issues,
                "weak_areas": "; ".join(weak_areas),
                "expected_weak_areas": "; ".join(expected_weak_areas),
                "issue_detection_agreement": issue_agreement,
                "processing_time_seconds": processing_time,
            }
        )

    return pd.DataFrame(result_rows)


def compute_section_classification_accuracy(results_df: pd.DataFrame) -> float:
    """Compute exact-match section classification accuracy."""
    if results_df.empty or "section_correct" not in results_df.columns:
        return 0.0
    return round(float(results_df["section_correct"].mean()) * 100, 2)


def compute_score_difference(results_df: pd.DataFrame) -> float:
    """Compute average absolute difference between manual and system scores."""
    if results_df.empty or "absolute_score_difference" not in results_df.columns:
        return 0.0
    differences = pd.to_numeric(
        results_df["absolute_score_difference"],
        errors="coerce",
    ).dropna()
    if differences.empty:
        return 0.0
    return round(float(differences.mean()), 2)


def compute_issue_detection_agreement(results_df: pd.DataFrame) -> float:
    """Compute average agreement between manual issues and system weak areas."""
    if results_df.empty or "issue_detection_agreement" not in results_df.columns:
        return 0.0
    agreements = pd.to_numeric(
        results_df["issue_detection_agreement"],
        errors="coerce",
    ).dropna()
    if agreements.empty:
        return 0.0
    return round(float(agreements.mean()) * 100, 2)


def compute_average_processing_time(results_df: pd.DataFrame) -> float:
    """Compute average processing time per evaluation sample."""
    if results_df.empty or "processing_time_seconds" not in results_df.columns:
        return 0.0
    times = pd.to_numeric(
        results_df["processing_time_seconds"],
        errors="coerce",
    ).dropna()
    if times.empty:
        return 0.0
    return round(float(times.mean()), 2)


def generate_evaluation_summary(results_df: pd.DataFrame) -> dict[str, object]:
    """Generate a compact evaluation metric summary."""
    accuracy = compute_section_classification_accuracy(results_df)
    score_difference = compute_score_difference(results_df)
    issue_agreement = compute_issue_detection_agreement(results_df)
    average_time = compute_average_processing_time(results_df)
    total_samples = len(results_df)
    correct_count = (
        int(results_df["section_correct"].sum())
        if not results_df.empty and "section_correct" in results_df.columns
        else 0
    )

    return {
        "total_samples": total_samples,
        "correct_classifications": correct_count,
        "incorrect_classifications": total_samples - correct_count,
        "section_classification_accuracy": accuracy,
        "average_absolute_score_difference": score_difference,
        "issue_detection_agreement": issue_agreement,
        "average_processing_time": average_time,
    }


def save_evaluation_results(
    results_df: pd.DataFrame,
    output_path: str = "data/evaluation_results.csv",
) -> str:
    """Save evaluation results to CSV and return the output path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(path, index=False)
    return str(path)
