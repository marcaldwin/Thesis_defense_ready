"""Responsible AI guardrails for SAGE-Review.

These checks are intentionally conservative. They do not judge thesis quality;
they flag integrity risks in user-provided text or generated recommendations
that could encourage fabrication, concealment, or overclaiming.
"""

import re
from typing import Any


RISK_PATTERNS = [
    (
        r"\b(fabricat(?:e|ed|ing)|make up|invent)\b.{0,80}\b(data|results?|dataset|samples?)\b",
        "Do not fabricate data. Only report actual measured results.",
    ),
    (
        r"\b(fake|invent|make up)\b.{0,80}\b(respondents?|participants?|samples?)\b",
        "Do not create fake respondents or participants. Report only real collected data.",
    ),
    (
        r"\b(fake|invent|make up|inflate)\b.{0,80}\b(accuracy|precision|recall|f1|score|performance)\b",
        "Do not report fake accuracy or performance values. Use only measured evaluation results.",
    ),
    (
        r"\b(fake|invent|make up|add)\b.{0,80}\b(citations?|references?|sources?)\b",
        "Do not add fake citations. Cite only sources that were actually reviewed and used.",
    ),
    (
        r"\b(adviser|advisor|expert|panel)\b.{0,80}\b(approved|validated|reviewed|endorsed)\b",
        "Do not claim expert validation or adviser approval unless an expert actually reviewed the system.",
    ),
    (
        r"\b(guarantee|guaranteed|ensure|assure)\b.{0,80}\b(defense approval|approval|passing|pass|accepted)\b",
        "Do not guarantee defense approval. Adviser and panel judgment cannot be replaced by the system.",
    ),
    (
        r"\b(hide|remove|omit|delete|exclude)\b.{0,80}\b(limitations?|scope|constraints?|weakness(?:es)?)\b",
        "Do not remove limitations. Limitations improve defensibility when stated honestly.",
    ),
    (
        r"\b(hide|remove|omit|delete|exclude)\b.{0,80}\b(negative results?|failed cases?|errors?|misclassifications?)\b",
        "Do not hide negative results. Explain errors and weak cases transparently.",
    ),
]

UNSAFE_RECOMMENDATION_PATTERNS = [
    r"\b(fabricat(?:e|ed|ing)|make up|invent)\b",
    r"\bfake\b",
    r"\binflate\b.{0,40}\b(accuracy|score|performance)\b",
    r"\bguarantee\b.{0,80}\b(defense|approval|pass|passing)\b",
    r"\b(hide|remove|omit|delete|exclude)\b.{0,80}\b(limitations?|negative results?|errors?|weakness(?:es)?)\b",
    r"\bclaim\b.{0,80}\b(adviser|advisor|expert|panel)\b.{0,80}\b(approved|validated|reviewed|endorsed)\b",
]


def _to_text(value: Any) -> str:
    """Convert nested feedback structures into searchable text."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_to_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_to_text(item) for item in value)
    return str(value)


def _unique_warnings(warnings: list[str]) -> list[str]:
    """Deduplicate warnings while preserving order."""
    return list(dict.fromkeys(warnings))


def detect_academic_integrity_risks(text: str) -> list[str]:
    """Detect academic integrity risks in user-provided thesis text."""
    searchable_text = _to_text(text).lower()
    warnings = []
    for pattern, warning in RISK_PATTERNS:
        if re.search(pattern, searchable_text, flags=re.I | re.S):
            warnings.append(warning)
    return _unique_warnings(warnings)


def generate_responsible_ai_warnings(
    text: str,
    generated_feedback,
) -> list[str]:
    """Generate warnings from user text and generated feedback content."""
    warnings = detect_academic_integrity_risks(text)
    feedback_text = _to_text(generated_feedback).lower()
    for pattern, warning in RISK_PATTERNS:
        if re.search(pattern, feedback_text, flags=re.I | re.S):
            warnings.append(warning)
    return _unique_warnings(warnings)


def _is_unsafe_recommendation(recommendation: Any) -> bool:
    """Return True when a recommendation encourages unsafe academic behavior."""
    text = _to_text(recommendation).lower()
    return any(
        re.search(pattern, text, flags=re.I | re.S)
        for pattern in UNSAFE_RECOMMENDATION_PATTERNS
    )


def filter_unsafe_recommendations(recommendations):
    """Remove recommendations that suggest fabrication, concealment, or overclaiming."""
    if recommendations is None:
        return []
    if isinstance(recommendations, str):
        return [] if _is_unsafe_recommendation(recommendations) else [recommendations]
    if not isinstance(recommendations, list):
        return recommendations

    return [
        recommendation
        for recommendation in recommendations
        if not _is_unsafe_recommendation(recommendation)
    ]
