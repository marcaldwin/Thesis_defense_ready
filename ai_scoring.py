"""Explainable defense readiness scoring for SAGE-Review."""

from evidence_analyzer import get_section_specific_criteria, normalize_section_name


_SUFFICIENT_WORD_COUNTS: dict[str, int] = {
    "Abstract": 100,
    "Introduction": 300,
    "Objectives of the Study": 100,
    "Literature Review": 400,
    "Methodology": 300,
    "Results and Discussion": 300,
    "Conclusion": 150,
    "Limitations": 100,
}


def _risk_level(score: float) -> str:
    if score >= 85:
        return "Low"
    if score >= 70:
        return "Moderate"
    return "High"


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def compute_defense_readiness_score(
    evidence_coverage: list[dict[str, object]],
    predicted_section: str,
    classification_confidence: float | None = None,
    alignment_score: float | None = None,
    risk_deductions: float = 0.0,
    missing_section_deductions: float = 0.0,
    word_count: int = 0,
) -> dict[str, object]:
    """Compute a calibrated, section-specific defense readiness score.

    Formula:
        base_score        = 35
        evidence_points   = average_expected_similarity * 50   (max 50)
        coverage_bonus    = +10 if ≥50% criteria are Moderate/Strong
                          + +5 if section word count meets threshold
        risk_deduction    = 5–15 only for severely low evidence (aggregate)
        final_score       = clamp(base + evidence_points + coverage_bonus - risk_deduction, 0, 100)
    """
    section = normalize_section_name(predicted_section)
    criteria = get_section_specific_criteria(section)
    expected_areas = list(criteria.keys())
    expected_items = list(criteria.keys())

    similarity_by_area = {
        str(item["Evidence Area"]): float(item.get("Similarity Score", 0.0))
        for item in evidence_coverage
    }
    coverage_by_area = {
        str(item["Evidence Area"]): str(item.get("Coverage Level", "Weak"))
        for item in evidence_coverage
    }

    expected_scores = [similarity_by_area.get(area, 0.0) for area in expected_areas]
    average_similarity = (
        sum(expected_scores) / len(expected_scores) if expected_scores else 0.0
    )

    # ── Scoring components ──────────────────────────────────────────
    base_score = 35.0
    evidence_points = average_similarity * 50.0

    coverage_bonus = 0.0
    if expected_areas:
        moderate_or_strong = sum(
            1
            for area in expected_areas
            if coverage_by_area.get(area, "Weak") in ("Moderate", "Strong")
        )
        if moderate_or_strong / len(expected_areas) >= 0.5:
            coverage_bonus += 10.0

    threshold = _SUFFICIENT_WORD_COUNTS.get(section, 150)
    if word_count >= threshold:
        coverage_bonus += 5.0

    # Single aggregate risk deduction — only for severely sparse evidence.
    # Avoids the old pattern of subtracting 6–12 per area which forced every
    # section to High risk regardless of content.
    risk_deduction = 0.0
    if average_similarity < 0.30:
        risk_deduction = 15.0
    elif average_similarity < 0.38:
        risk_deduction = 10.0
    elif average_similarity < 0.44 and expected_areas:
        weak_count = sum(
            1
            for area in expected_areas
            if coverage_by_area.get(area, "Weak") == "Weak"
        )
        if weak_count / len(expected_areas) > 0.70:
            risk_deduction = 5.0

    score = _clamp_score(base_score + evidence_points + coverage_bonus - risk_deduction)

    # ── Deductions list (display only, not subtracted individually) ──
    deductions: list[dict[str, object]] = []
    strengths: list[str] = []
    for area in expected_areas:
        level = coverage_by_area.get(area, "Weak")
        sim = similarity_by_area.get(area, 0.0)
        if level == "Strong":
            strengths.append(f"{area} is strongly supported for this section.")
        elif level == "Moderate":
            deductions.append(
                {
                    "Evidence Area": area,
                    "Deduction": 0,
                    "Reason": f"{area} is partially supported but should be clearer.",
                    "Similarity Score": round(sim, 4),
                }
            )
        else:
            deductions.append(
                {
                    "Evidence Area": area,
                    "Deduction": 0,
                    "Reason": f"{area} is weak for the expected content of this section.",
                    "Similarity Score": round(sim, 4),
                }
            )

    score_breakdown = {
        "base_score": round(base_score, 2),
        "average_similarity": round(average_similarity, 4),
        "evidence_points": round(evidence_points, 2),
        "coverage_bonus": round(coverage_bonus, 2),
        "risk_deduction": round(risk_deduction, 2),
        "final_score": score,
    }

    return {
        "defense_score": score,
        "score": score,
        "risk_level": _risk_level(score),
        "predicted_section": section,
        "criteria_used": expected_areas,
        "expected_areas": expected_areas,
        "expected_items": expected_items,
        "avg_expected_similarity": round(average_similarity, 4),
        "score_breakdown": score_breakdown,
        "strengths": strengths,
        "deductions": deductions,
    }
