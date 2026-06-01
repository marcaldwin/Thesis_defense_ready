"""Before-and-after revision comparison utilities for SAGE-Review."""

import re

from backend.sage_review.core.ai_analyzer import (
    analyze_evidence_coverage,
    classify_section_zero_shot,
)
from backend.sage_review.core.ai_scoring import compute_defense_readiness_score
from backend.sage_review.services.feedback_generator import (
    generate_defense_notes,
    generate_defense_questions,
    generate_priority_fixes,
    generate_revision_suggestions,
    generate_safer_wording_suggestions,
)


def _clean_text(value: object) -> str:
    """Convert pasted revision text into safe plain text."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\x00", " ").replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _basic_stats(text: str) -> dict[str, int]:
    """Return basic counts for revision text."""
    return {
        "word_count": len(text.split()) if text else 0,
        "character_count": len(text),
    }


def _expected_area_groups(
    evidence_coverage: list[dict[str, object]],
    expected_areas: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Return strong, moderate, and weak expected evidence areas."""
    strong_areas = []
    moderate_areas = []
    weak_areas = []

    for item in evidence_coverage:
        area = str(item["Evidence Area"])
        if area not in expected_areas:
            continue
        level = str(item["Coverage Level"])
        if level == "Strong":
            strong_areas.append(area)
        elif level == "Moderate":
            moderate_areas.append(area)
        else:
            weak_areas.append(area)

    return strong_areas, moderate_areas, weak_areas


def _compare_evidence_areas(
    original_coverage: list[dict[str, object]],
    revised_coverage: list[dict[str, object]],
    expected_areas: list[str],
) -> list[dict[str, object]]:
    """Build per-area semantic comparison between original and revised."""
    orig_by_area = {str(item["Evidence Area"]): item for item in original_coverage}
    rev_by_area = {str(item["Evidence Area"]): item for item in revised_coverage}

    # All areas from both, preserving insertion order
    all_areas: list[str] = list(
        dict.fromkeys(list(orig_by_area.keys()) + list(rev_by_area.keys()))
    )

    rows = []
    for area in all_areas:
        orig = orig_by_area.get(area, {})
        rev = rev_by_area.get(area, {})
        orig_score = float(orig.get("Similarity Score", 0.0))
        rev_score = float(rev.get("Similarity Score", 0.0))
        delta = round(rev_score - orig_score, 4)
        orig_level = str(orig.get("Coverage Level", "Weak"))
        rev_level = str(rev.get("Coverage Level", "Weak"))
        improved = delta >= 0.05
        resolved = orig_level == "Weak" and rev_level in ("Moderate", "Strong")
        if resolved:
            status = "Resolved"
        elif improved:
            status = "Improved"
        elif delta <= -0.05:
            status = "Worsened"
        else:
            status = "Unchanged"
        rows.append(
            {
                "evidence_area": area,
                "Evidence Area": area,
                "original_score": round(orig_score, 4),
                "Original Similarity": round(orig_score, 4),
                "revised_score": round(rev_score, 4),
                "Revised Similarity": round(rev_score, 4),
                "score_change": delta,
                "Change": delta,
                "original_level": orig_level,
                "Original Level": orig_level,
                "revised_level": rev_level,
                "Revised Level": rev_level,
                "Status": status,
                "is_expected": area in expected_areas,
                "improved": improved,
                "resolved": resolved,
            }
        )
    return rows


def analyze_revision_text(text: str) -> dict[str, object]:
    """Analyze one revision text using the existing SAGE-Review pipeline."""
    clean_text = _clean_text(text)
    if not clean_text:
        raise ValueError("Revision text is empty.")

    stats = _basic_stats(clean_text)
    classification = classify_section_zero_shot(clean_text)
    predicted_section = str(classification["predicted_section"])
    evidence_result = analyze_evidence_coverage(predicted_section, clean_text)
    evidence_coverage = list(evidence_result["evidence_coverage"])
    score_result = compute_defense_readiness_score(
        evidence_coverage,
        predicted_section,
        classification_confidence=float(classification["confidence"]),
    )
    expected_areas = list(score_result["criteria_used"])
    strong_areas = list(evidence_result["strong_areas"])
    moderate_areas = list(evidence_result["moderate_areas"])
    weak_areas = list(evidence_result["weak_areas"])

    return {
        "input_text": clean_text,
        "text_preview": clean_text[:1000],
        "word_count": stats["word_count"],
        "character_count": stats["character_count"],
        "predicted_section": predicted_section,
        "section_confidence": round(float(classification["confidence"]) * 100, 2),
        "section_scores": classification["all_scores"],
        "evidence_coverage": evidence_coverage,
        "defense_score": round(float(score_result["defense_score"]), 2),
        "risk_level": score_result["risk_level"],
        "avg_expected_similarity": score_result.get("avg_expected_similarity", 0.0),
        "criteria_used": list(evidence_result["criteria_used"]),
        "score_breakdown": score_result["score_breakdown"],
        "expected_areas": expected_areas,
        "strong_areas": strong_areas,
        "moderate_areas": moderate_areas,
        "weak_areas": weak_areas,
        "strengths": score_result["strengths"],
        "deductions": score_result["deductions"],
        "priority_fixes": generate_priority_fixes(
            score_result,
            evidence_coverage,
            predicted_section,
        ),
        "revision_suggestions": generate_revision_suggestions(
            predicted_section,
            evidence_coverage,
            score_result,
        ),
        "safer_wording_suggestions": generate_safer_wording_suggestions(clean_text),
        "defense_questions": generate_defense_questions(
            predicted_section,
            evidence_coverage,
            score_result,
        ),
        "defense_notes": generate_defense_notes(score_result),
    }


def compare_revision_results(
    original_result: dict[str, object],
    revised_result: dict[str, object],
) -> dict[str, object]:
    """Compare original and revised section analysis results."""
    original_score = round(float(original_result["defense_score"]), 2)
    revised_score = round(float(revised_result["defense_score"]), 2)
    score_improvement = round(revised_score - original_score, 2)

    # Union of expected areas from both analyses
    expected_areas: list[str] = list(
        dict.fromkeys(
            list(original_result.get("expected_areas", []))
            + list(revised_result.get("expected_areas", []))
        )
    )

    original_coverage = list(original_result.get("evidence_coverage", []))
    revised_coverage = list(revised_result.get("evidence_coverage", []))

    evidence_comparison = _compare_evidence_areas(
        original_coverage, revised_coverage, expected_areas
    )

    orig_sim = {str(item["Evidence Area"]): float(item.get("Similarity Score", 0.0))
                for item in original_coverage}
    rev_sim = {str(item["Evidence Area"]): float(item.get("Similarity Score", 0.0))
               for item in revised_coverage}

    if expected_areas:
        avg_orig = sum(orig_sim.get(a, 0.0) for a in expected_areas) / len(expected_areas)
        avg_rev = sum(rev_sim.get(a, 0.0) for a in expected_areas) / len(expected_areas)
    else:
        avg_orig = 0.0
        avg_rev = 0.0

    semantic_improvement = round(avg_rev - avg_orig, 4)

    improved_areas = [r["evidence_area"] for r in evidence_comparison if r["improved"]]
    resolved_areas = [r["evidence_area"] for r in evidence_comparison if r["resolved"]]
    remaining_weak_areas = [
        r["evidence_area"]
        for r in evidence_comparison
        if r["is_expected"] and r["revised_level"] == "Weak" and not r["improved"]
    ]

    original_risk = str(original_result["risk_level"])
    revised_risk = str(revised_result["risk_level"])

    if score_improvement > 0:
        summary = (
            f"The revised version improved by {score_improvement:.2f} points, "
            f"from {original_score:.2f}/100 to {revised_score:.2f}/100. "
            f"The risk level changed from {original_risk} to {revised_risk}."
        )
    elif score_improvement < 0:
        summary = (
            f"The revised version decreased by {abs(score_improvement):.2f} "
            f"points, from {original_score:.2f}/100 to "
            f"{revised_score:.2f}/100. Review whether important evidence was "
            "removed or weakened."
        )
    elif semantic_improvement > 0.02:
        summary = (
            "The final readiness score did not change because the revised "
            "evidence did not cross the scoring threshold, but several "
            "evidence areas improved semantically."
        )
    else:
        summary = (
            f"The revised version kept the same score of {revised_score:.2f}/100. "
            "The revision added clearer methodological details, but more "
            "measurable values may be needed to raise the readiness level."
        )

    if resolved_areas:
        summary += " Newly supported areas: " + ", ".join(resolved_areas[:3]) + "."
    elif improved_areas and score_improvement == 0:
        summary += " Semantically improved areas: " + ", ".join(improved_areas[:3]) + "."

    return {
        "original_score": original_score,
        "revised_score": revised_score,
        "score_improvement": score_improvement,
        "original_risk": original_risk,
        "revised_risk": revised_risk,
        "semantic_improvement": semantic_improvement,
        "avg_original_similarity": round(avg_orig, 4),
        "avg_revised_similarity": round(avg_rev, 4),
        "improved_areas": improved_areas,
        "semantic_improvement_score": semantic_improvement,
        "improved_evidence_areas": improved_areas,
        "resolved_weak_areas": resolved_areas,
        "resolved_areas": resolved_areas,
        "remaining_weak_areas": remaining_weak_areas,
        "evidence_comparison_table": evidence_comparison,
        "evidence_comparison": evidence_comparison,
        "summary": summary,
    }
