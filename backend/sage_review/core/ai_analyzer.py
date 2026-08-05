"""AI/NLP analysis utilities for SAGE-Review.

This module uses pretrained NLP models for section classification and semantic
evidence coverage detection. It avoids keyword-only rules and keeps analysis
model-driven.
"""

import re
from threading import Lock
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import pipeline

from backend.sage_review.core.evidence_analyzer import (
    classify_coverage_level,
    get_section_specific_criteria,
    interpretation_for_criterion,
    summarize_coverage,
)


SECTION_LABELS = [
    "Abstract",
    "Introduction",
    "Objectives of the Study",
    "Literature Review",
    "Methodology",
    "Results and Discussion",
    "Limitations",
    "Conclusion",
    "Unknown / Mixed Section",
]

MODEL_NAME = "valhalla/distilbart-mnli-12-1"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
UNKNOWN_SECTION = "Unknown / Mixed Section"
CONFIDENCE_THRESHOLD = 0.35
STRONG_COVERAGE_THRESHOLD = 0.65
MODERATE_COVERAGE_THRESHOLD = 0.45
MAX_CLASSIFICATION_CHARS = 5000

EVIDENCE_CRITERIA = {
    "Dataset Description": (
        "The manuscript explains the dataset, number of samples, classes, "
        "participants, data split, and data distribution."
    ),
    "Participant / Sample Description": (
        "The manuscript describes the participants, respondents, sample size, "
        "sampling method, eligibility criteria, or study population."
    ),
    "Data Collection Procedure": (
        "The manuscript explains how data was gathered, collected, recorded, "
        "surveyed, observed, or obtained during the study."
    ),
    "Preprocessing Description": (
        "The manuscript describes data cleaning, normalization, resizing, "
        "augmentation, feature extraction, encoding, or preprocessing steps."
    ),
    "Model Training Description": (
        "The manuscript explains model training, algorithm configuration, "
        "hyperparameters, training process, validation, or learning procedure."
    ),
    "Model Evaluation Metrics": (
        "The manuscript reports accuracy, precision, recall, F1-score, "
        "classification results, and testing performance."
    ),
    "Confusion Matrix / Error Analysis": (
        "The manuscript discusses a confusion matrix, misclassifications, "
        "prediction errors, false positives, false negatives, or error analysis."
    ),
    "Mobile Prototype Testing": (
        "The manuscript evaluates a mobile application prototype, interface, "
        "mobile features, user interaction, or app functionality testing."
    ),
    "Latency / Response Time Testing": (
        "The manuscript measures processing time, response time, inference "
        "time, or delay of the prototype or mobile application."
    ),
    "Usability Evaluation": (
        "The manuscript evaluates usability, user experience, ease of use, "
        "satisfaction, learnability, accessibility, or user feedback."
    ),
    "Limitations / Scope": (
        "The manuscript explains the study limitations, boundaries, scope, "
        "constraints, assumptions, exclusions, or areas not covered."
    ),
    "Conclusion Support": (
        "The manuscript connects the findings, evaluation results, and evidence "
        "to the conclusion or final claims of the study."
    ),
}

EVIDENCE_INTERPRETATIONS = {
    "Dataset Description": {
        "Strong": "Dataset details are clearly explained, including the source, sample, or structure of the data.",
        "Moderate": "Dataset details are present but may need clearer sample size, source, split, or distribution information.",
        "Weak": "Dataset details are not clearly explained in this section. Add sample size, data source, or data distribution if this section is expected to contain methodology details.",
    },
    "Participant / Sample Description": {
        "Strong": "The participant or sample setup is clearly described.",
        "Moderate": "The participant or sample setup is partly described but may need clearer selection criteria or sample size.",
        "Weak": "Participant or sample details are unclear. Add who or what was included, how many were used, and how they were selected.",
    },
    "Data Collection Procedure": {
        "Strong": "The data collection process is explained clearly enough to support defense questions.",
        "Moderate": "The data collection process is partly explained but needs a clearer sequence of steps.",
        "Weak": "The data collection process is not clear. Add how the data was gathered, recorded, and prepared for the study.",
    },
    "Preprocessing Description": {
        "Strong": "Preprocessing or preparation steps are clearly described.",
        "Moderate": "Preprocessing is mentioned but needs more detail about what was changed or prepared.",
        "Weak": "Preprocessing is not clearly explained. Add cleaning, normalization, encoding, augmentation, or preparation steps if applicable.",
    },
    "Model Training Description": {
        "Strong": "The model or system training process is clearly explained.",
        "Moderate": "The model or system training process is partly explained but needs clearer setup or configuration.",
        "Weak": "The model or training process is unclear. Add the technique used, training setup, testing approach, or development procedure.",
    },
    "Model Evaluation Metrics": {
        "Strong": "Evaluation metrics are clearly reported and can support performance claims.",
        "Moderate": "Evaluation metrics are present but need clearer explanation or connection to the study objectives.",
        "Weak": "Evaluation metrics are weak or missing. Add accuracy, precision, recall, F1-score, testing results, or other relevant measures.",
    },
    "Confusion Matrix / Error Analysis": {
        "Strong": "The section explains errors, misclassifications, or performance weaknesses clearly.",
        "Moderate": "Error discussion is present but needs clearer explanation of causes or patterns.",
        "Weak": "Error analysis is weak or missing. Add misclassification patterns, weak cases, or reasons for incorrect results if this section reports model performance.",
    },
    "Mobile Prototype Testing": {
        "Strong": "Prototype testing is clearly described with actual use or system behavior.",
        "Moderate": "Prototype testing is mentioned but needs clearer tasks, device context, or user interaction details.",
        "Weak": "Prototype testing is not clearly explained. Add how the system was tested on the actual prototype if this section discusses implementation or results.",
    },
    "Latency / Response Time Testing": {
        "Strong": "Processing time or response time evidence is clearly reported.",
        "Moderate": "Response time is partly discussed but needs clearer measured values or testing conditions.",
        "Weak": "Processing time is not clearly supported. Add response time, inference time, or delay measurements if speed is part of the system claim.",
    },
    "Usability Evaluation": {
        "Strong": "Usability or user experience evidence is clearly described.",
        "Moderate": "Usability evidence is present but needs clearer participant feedback, task results, or ratings.",
        "Weak": "Usability evidence is weak or missing. Add user feedback, usability testing results, or observed interface issues if this section evaluates the prototype.",
    },
    "Limitations / Scope": {
        "Strong": "The study scope and limitations are clearly stated.",
        "Moderate": "Limitations are partly stated but need clearer boundaries or constraints.",
        "Weak": "Scope and limitations are unclear. Add dataset limits, system constraints, assumptions, and conditions where the system may not work well.",
    },
    "Conclusion Support": {
        "Strong": "The conclusions are clearly connected to evidence or findings.",
        "Moderate": "The conclusions are partly supported but need clearer links to results.",
        "Weak": "The conclusion support is weak. Connect final claims directly to findings, metrics, or observed results.",
    },
}


_section_classifier: Any = None
_embedding_model: SentenceTransformer | None = None
_section_classifier_lock = Lock()
_embedding_model_lock = Lock()


def load_section_classifier() -> Any:
    """Load and cache the zero-shot classification pipeline (module singleton)."""
    global _section_classifier
    if _section_classifier is None:
        with _section_classifier_lock:
            if _section_classifier is None:
                _section_classifier = pipeline(
                    task="zero-shot-classification",
                    model=MODEL_NAME,
                )
    return _section_classifier


def load_embedding_model() -> SentenceTransformer:
    """Load and cache the sentence-transformers embedding model (module singleton)."""
    global _embedding_model
    if _embedding_model is None:
        with _embedding_model_lock:
            if _embedding_model is None:
                _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def _clean_model_text(value: object) -> str:
    """Convert extracted document content into safe plain text for NLP models."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                value = value.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

    text = str(value)
    text = text.replace("\x00", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def classify_section_zero_shot(text: str) -> dict[str, object]:
    """Classify thesis text into a manuscript section using zero-shot NLP.

    Args:
        text: Thesis manuscript text pasted by the user.

    Returns:
        A dictionary containing the predicted section, top confidence, and all
        label scores sorted by the model.
    """
    clean_text = _clean_model_text(text)
    if not clean_text:
        return {
            "predicted_section": UNKNOWN_SECTION,
            "confidence": 0.0,
            "all_scores": [],
        }

    classifier = load_section_classifier()
    result = classifier(
        clean_text[:MAX_CLASSIFICATION_CHARS],
        candidate_labels=SECTION_LABELS,
        hypothesis_template="This thesis manuscript section is about {}.",
        multi_label=False,
    )

    labels = result.get("labels", [])
    scores = result.get("scores", [])
    all_scores = [
        {"label": label, "score": round(float(score), 4)}
        for label, score in zip(labels, scores)
    ]

    top_label = all_scores[0]["label"] if all_scores else UNKNOWN_SECTION
    top_score = float(all_scores[0]["score"]) if all_scores else 0.0
    predicted_section = (
        str(top_label) if top_score >= CONFIDENCE_THRESHOLD else UNKNOWN_SECTION
    )

    return {
        "predicted_section": predicted_section,
        "confidence": round(top_score, 4),
        "all_scores": all_scores,
    }


def compute_semantic_similarity(text: str, criteria_text: str) -> float:
    """Compute cosine similarity between thesis text and one criterion."""
    clean_text = _clean_model_text(text)
    clean_criteria = _clean_model_text(criteria_text)
    if not clean_text or not clean_criteria:
        return 0.0

    model = load_embedding_model()
    embeddings = model.encode(
        [clean_text, clean_criteria],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    similarity = float(np.dot(embeddings[0], embeddings[1]))
    return round(float(similarity), 4)


def _coverage_level(similarity_score: float) -> str:
    """Convert a similarity score into an evidence coverage level."""
    if similarity_score >= STRONG_COVERAGE_THRESHOLD:
        return "Strong"
    if similarity_score >= MODERATE_COVERAGE_THRESHOLD:
        return "Moderate"
    return "Weak"


def _coverage_interpretation(evidence_area: str, coverage_level: str) -> str:
    """Return a plain-language interpretation for one evidence area."""
    area_interpretations = EVIDENCE_INTERPRETATIONS.get(evidence_area, {})
    return area_interpretations.get(
        coverage_level,
        f"{evidence_area} needs clearer explanation if this section is expected to discuss it.",
    )


def analyze_evidence_coverage(
    section_name: str | None,
    section_text: str,
    embedding_model=None
) -> list[dict[str, object]] | dict[str, object]:
    """Evaluate semantic coverage using section-specific evidence criteria.

    Backward compatibility: if section_name is omitted, returns only the list
    of coverage rows. If section_name is provided, returns a structured dict
    containing criteria_used, evidence_coverage, and grouped area lists.
    """
    clean_text = _clean_model_text(section_text)
    if not clean_text:
        empty = []
        if section_name:
            return {
                "criteria_used": [],
                "evidence_coverage": empty,
                "strong_areas": [],
                "moderate_areas": [],
                "weak_areas": [],
            }
        return empty

    model = load_embedding_model()
    if section_name:
        criteria = get_section_specific_criteria(section_name)
    else:
        criteria = EVIDENCE_CRITERIA
    evidence_areas = list(criteria.keys())
    criteria_texts = [criteria[area] for area in evidence_areas]
    embeddings = model.encode(
        [clean_text, *criteria_texts],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    text_embedding = embeddings[0]
    criteria_embeddings = embeddings[1:]
    similarity_scores = np.matmul(criteria_embeddings, text_embedding)

    coverage_results = []
    for evidence_area, similarity_score_value in zip(
        evidence_areas,
        similarity_scores,
    ):
        similarity_score = round(float(similarity_score_value), 4)
        coverage_level = classify_coverage_level(similarity_score)
        if section_name:
            interpretation = interpretation_for_criterion(
                evidence_area,
                coverage_level,
                section_name,
            )
        else:
            interpretation = _coverage_interpretation(evidence_area, coverage_level)

        coverage_results.append(
            {
                "Evidence Area": evidence_area,
                "Criteria": evidence_area,
                "Similarity Score": similarity_score,
                "Coverage Level": coverage_level,
                "Interpretation": interpretation,
            }
        )

    if section_name:
        grouped = summarize_coverage(coverage_results)
        return {
            "criteria_used": evidence_areas,
            "evidence_coverage": coverage_results,
            **grouped,
        }

    return coverage_results
