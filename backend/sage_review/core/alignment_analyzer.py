"""Semantic alignment analysis for major thesis manuscript sections."""

import numpy as np

from backend.sage_review.core.ai_analyzer import load_embedding_model


ALIGNMENT_PAIRS = [
    ("Objectives of the Study", "Methodology"),
    ("Objectives of the Study", "Results and Discussion"),
    ("Objectives of the Study", "Conclusion"),
    ("Methodology", "Results and Discussion"),
    ("Results and Discussion", "Conclusion"),
]


def compute_section_similarity(section_a_text: str, section_b_text: str) -> float:
    """Compute cosine similarity between two thesis sections using embeddings."""
    clean_a = str(section_a_text or "").strip()
    clean_b = str(section_b_text or "").strip()
    if not clean_a or not clean_b:
        return 0.0

    model = load_embedding_model()
    embeddings = model.encode(
        [clean_a, clean_b],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    score = float(np.dot(embeddings[0], embeddings[1]))
    return round(max(0.0, min(1.0, score)), 4)


def classify_alignment_level(score: float) -> dict[str, object]:
    """Classify a section similarity score into alignment level and risk."""
    rounded_score = round(float(score), 4)
    if rounded_score >= 0.65:
        return {
            "score": rounded_score,
            "level": "Strong Alignment",
            "risk": "Low",
        }
    if rounded_score >= 0.45:
        return {
            "score": rounded_score,
            "level": "Moderate Alignment",
            "risk": "Moderate",
        }
    return {
        "score": rounded_score,
        "level": "Weak Alignment",
        "risk": "High",
    }


def generate_alignment_interpretation(
    pair_name: str,
    score: float | None,
    level: str,
) -> str:
    """Generate a readable interpretation for an alignment result."""
    if level == "Missing Section" or score is None:
        return "Alignment cannot be computed because one or both sections are missing."
    if level == "Strong Alignment":
        return (
            "These sections appear strongly connected. The later section likely "
            "supports the earlier section."
        )
    if level == "Moderate Alignment":
        return (
            "These sections are partially connected, but the manuscript may need "
            "clearer explanation linking them."
        )
    return (
        "These sections appear weakly connected. This may cause defense questions "
        "about consistency."
    )


def generate_alignment_matrix(
    extracted_sections: dict[str, str],
) -> list[dict[str, object]]:
    """Generate semantic alignment results for required thesis section pairs."""
    alignment_results = []

    for section_a, section_b in ALIGNMENT_PAIRS:
        pair_name = f"{section_a} <-> {section_b}"
        if section_a not in extracted_sections or section_b not in extracted_sections:
            alignment_results.append(
                {
                    "Section Pair": pair_name,
                    "Similarity Score": None,
                    "Alignment Level": "Missing Section",
                    "Risk": "High",
                    "Interpretation": generate_alignment_interpretation(
                        pair_name,
                        None,
                        "Missing Section",
                    ),
                }
            )
            continue

        score = compute_section_similarity(
            extracted_sections[section_a],
            extracted_sections[section_b],
        )
        alignment = classify_alignment_level(score)
        level = str(alignment["level"])
        alignment_results.append(
            {
                "Section Pair": pair_name,
                "Similarity Score": alignment["score"],
                "Alignment Level": level,
                "Risk": alignment["risk"],
                "Interpretation": generate_alignment_interpretation(
                    pair_name,
                    score,
                    level,
                ),
            }
        )

    return alignment_results
