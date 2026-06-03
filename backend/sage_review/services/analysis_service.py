"""Shared analysis orchestration for Streamlit and FastAPI entry points."""

from __future__ import annotations

from datetime import datetime
import hashlib
import re
import time
from typing import Any

from backend.sage_review.core.ai_analyzer import (
    analyze_evidence_coverage,
    classify_section_zero_shot,
)
from backend.sage_review.core.ai_scoring import compute_defense_readiness_score
from backend.sage_review.core.alignment_analyzer import generate_alignment_matrix
from backend.sage_review.core.evidence_analyzer import normalize_section_name
from backend.sage_review.core.highlight_analyzer import analyze_contextual_highlights
from backend.sage_review.core.responsible_ai_guardrail import (
    filter_unsafe_recommendations,
    generate_responsible_ai_warnings,
)
from backend.sage_review.core.section_extractor import (
    MAJOR_REQUIRED_SECTIONS,
    extract_sections_with_metadata,
)
from backend.sage_review.services.feedback_generator import (
    generate_defense_notes,
    generate_defense_questions,
    generate_next_best_action,
    generate_panel_risk,
    generate_plain_language_diagnosis,
    generate_priority_fixes,
    generate_revision_suggestions,
    generate_section_recommendation,
    generate_safer_wording_suggestions,
    generate_suggested_revision_wording,
)

try:
    from backend.sage_review.services.gemini_feedback_generator import (
        generate_gemini_feedback,
    )
except (ImportError, ModuleNotFoundError):

    def generate_gemini_feedback(**kwargs):  # type: ignore[misc]
        return {"feedback_mode": "Template fallback"}


class AnalysisServiceError(Exception):
    """Application-level analysis error that API callers can map to HTTP errors."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class AnalysisService:
    """Coordinate document normalization, analysis, scoring, feedback, and results."""

    def resolve_section_label(
        self,
        section_name: str | None = None,
        scoring_section: str | None = None,
        semantic_prediction: str | None = None,
    ) -> dict[str, str]:
        """Resolve the user-facing section label from reliable sources first."""
        candidates = [
            ("heading", section_name),
            ("scoring_section", scoring_section),
            ("semantic_classifier", semantic_prediction),
        ]
        for source, value in candidates:
            normalized = normalize_section_name(value or "")
            if normalized != "Unknown":
                confidence = "High" if source in {"heading", "scoring_section"} else "Medium"
                return {
                    "display_section": normalized,
                    "resolved_section_label": normalized,
                    "section_label_source": source,
                    "section_label_confidence": confidence,
                }
        return {
            "display_section": "Unknown / Mixed Section",
            "resolved_section_label": "Unknown / Mixed Section",
            "section_label_source": "semantic_classifier",
            "section_label_confidence": "Low",
        }

    def normalize_analysis_text(self, value: object) -> str:
        """Convert pasted or extracted content into safe plain text for analysis."""
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
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def normalize_text(self, value: object) -> str:
        """Clean text for single-section API analysis."""
        if value is None:
            return ""
        text = str(value)
        text = text.replace("\x00", " ").replace("\xa0", " ")
        return " ".join(text.split())

    def normalize_manuscript_text(self, value: object) -> str:
        """Clean full-manuscript text while preserving line breaks."""
        if value is None:
            return ""
        text = str(value)
        text = text.replace("\x00", " ").replace("\xa0", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    def count_evidence_levels(
        self,
        evidence_coverage: list[dict[str, object]],
    ) -> tuple[int, int, int, list[str]]:
        """Count strong/moderate/weak evidence areas."""
        strong_count = 0
        moderate_count = 0
        weak_count = 0
        weak_items = []

        for item in evidence_coverage:
            level = str(item.get("Coverage Level", "Weak"))
            if level == "Strong":
                strong_count += 1
            elif level == "Moderate":
                moderate_count += 1
            else:
                weak_count += 1
                weak_items.append(item)

        weak_items = sorted(
            weak_items,
            key=lambda item: float(item.get("Similarity Score", 0.0)),
        )
        top_weak_areas = [str(item["Evidence Area"]) for item in weak_items[:5]]
        return strong_count, moderate_count, weak_count, top_weak_areas

    def build_manuscript_evidence_summary(
        self,
        section_details: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Summarize section-specific evidence without listing every criterion."""
        summary: list[dict[str, Any]] = []
        for section in section_details:
            section_name = str(
                section.get("section_name")
                or section.get("scoring_section")
                or section.get("predicted_section")
                or "Unknown"
            )
            coverage_rows = [
                item
                for item in section.get("evidence_coverage", [])
                if str(item.get("Evidence Area", "")) in set(section.get("expected_areas", []))
            ]
            weak_rows = sorted(
                (
                    row
                    for row in coverage_rows
                    if row.get("Coverage Level") == "Weak"
                ),
                key=lambda row: float(row.get("Similarity Score", 0.0)),
            )
            strong_rows = sorted(
                (
                    row
                    for row in coverage_rows
                    if row.get("Coverage Level") == "Strong"
                ),
                key=lambda row: float(row.get("Similarity Score", 0.0)),
                reverse=True,
            )
            critical_missing_rows = [
                row
                for row in weak_rows
                if float(row.get("Similarity Score", 0.0)) < 0.30
            ][:3]

            for row in weak_rows[:3]:
                summary.append(
                    self._build_manuscript_summary_row(
                        section_name,
                        row,
                        "Top Weak Criterion",
                    )
                )
            for row in strong_rows[:3]:
                summary.append(
                    self._build_manuscript_summary_row(
                        section_name,
                        row,
                        "Strongest Criterion",
                    )
                )
            for row in critical_missing_rows:
                summary.append(
                    self._build_manuscript_summary_row(
                        section_name,
                        row,
                        "Critical Missing Criterion",
                    )
                )

        return summary

    def _display_similarity(self, value: Any) -> float:
        """Clamp raw similarity for user-facing evidence display."""
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0.0
        return round(max(0.0, min(1.0, score)), 4)

    def _evidence_next_action(self, criterion: str, section_name: str) -> str:
        """Return a concrete action for weak evidence criteria."""
        actions = {
            "Research Purpose": "State the study purpose in one direct sentence and connect it to the problem.",
            "Method Summary": "Briefly name the method, model, or development process used.",
            "Key Results Summary": "Add the main measured result or finding from the results section.",
            "Problem Context": "Explain the real-world problem before introducing the proposed system.",
            "Research Gap": "State what existing studies or systems still fail to address.",
            "Study Purpose": "Add a clear sentence explaining what the study aims to accomplish.",
            "Objectives Mention": "List or reference the specific objectives clearly.",
            "Related Studies Coverage": "Add relevant studies and explain how each relates to the current work.",
            "Comparison of Existing Systems": "Compare existing systems by features, methods, performance, and limitations.",
            "Research Gap Synthesis": "Synthesize the common gap across studies instead of listing sources only.",
            "Dataset Description": "State dataset source, size, classes, split, and distribution.",
            "Participant or Sample Description": "State sample size, selection criteria, and sampling method.",
            "Data Collection Procedure": "Describe how data was gathered, recorded, labeled, and validated.",
            "Preprocessing Description": "Explain cleaning, normalization, augmentation, encoding, or preparation steps.",
            "Model or Algorithm Description": "Describe the model, algorithm, architecture, or system logic clearly enough to reproduce.",
            "Evaluation Metrics": "Reference the accuracy, confusion matrix, usability result, or table number that supports this claim.",
            "Model Evaluation Metrics": "Report accuracy, precision, recall, F1-score, or another metric tied to the objective.",
            "Confusion Matrix or Error Analysis": "Add a confusion matrix, error table, or paragraph explaining misclassified cases.",
            "Latency or Response Time Results": "Report measured response time, device conditions, and number of test runs.",
            "Usability Evaluation Results": "Summarize user tasks, ratings, respondents, or usability table results.",
            "Objective-to-Result Connection": "Add a table or paragraph showing which result supports each objective.",
            "Summary of Main Findings": "Summarize the main findings using specific results from the study.",
            "Objective Support": "Connect each conclusion to a specific objective and finding.",
            "Limitations": "State scope boundaries and explain how they affect interpretation of the findings.",
            "Avoidance of Overclaims": "Revise broad claims so they match the actual measured results and study scope.",
            "Recommendations": "Add practical recommendations based on the findings and limitations.",
            "Future Work": "Identify concrete next work, such as more data, more users, or broader testing.",
        }
        return actions.get(
            criterion,
            f"Add section-specific evidence for {criterion.lower()} in the {section_name} section.",
        )

    def _build_evidence_display_item(
        self,
        row: dict[str, Any],
        section_name: str,
    ) -> dict[str, Any]:
        """Build a simplified evidence item while preserving legacy keys."""
        criterion = str(row.get("Evidence Area") or row.get("criterion") or "")
        raw_score = row.get("Similarity Score", row.get("similarity_score", 0.0))
        display_score = self._display_similarity(raw_score)
        level = str(row.get("Coverage Level") or row.get("coverage_level") or "Weak")
        next_action = self._evidence_next_action(criterion, section_name)
        return {
            "section": section_name,
            "criterion": criterion,
            "coverage_level": level,
            "display_score": display_score,
            "display_percent": round(display_score * 100, 1),
            "display_score_label": f"{round(display_score * 100)}%",
            "raw_similarity_score": raw_score,
            "next_action": next_action,
            "Evidence Area": criterion,
            "Similarity Score": display_score,
            "Coverage Level": level,
            "Interpretation": row.get("Interpretation", ""),
        }

    def build_section_evidence_summary(
        self,
        section_name: str,
        evidence_coverage: list[dict[str, Any]],
        expected_areas: list[str],
    ) -> dict[str, Any]:
        """Build concise evidence lists for default display."""
        expected = set(expected_areas)
        relevant_rows = [
            row
            for row in evidence_coverage
            if str(row.get("Evidence Area", "")) in expected
        ]
        display_rows = [
            self._build_evidence_display_item(row, section_name)
            for row in relevant_rows
        ]
        weak_rows = sorted(
            (
                row
                for row in display_rows
                if row["coverage_level"] == "Weak"
            ),
            key=lambda row: row["display_score"],
        )
        strongest_rows = sorted(
            (
                row
                for row in display_rows
                if row["coverage_level"] == "Strong"
            ),
            key=lambda row: row["display_score"],
            reverse=True,
        )
        critical_rows = [
            row
            for row in weak_rows
            if row["display_score"] < 0.30
        ]

        default_rows = []
        seen = set()
        for row in critical_rows[:3] + weak_rows[:5] + strongest_rows[:3]:
            key = (row["section"], row["criterion"])
            if key not in seen:
                default_rows.append(row)
                seen.add(key)

        summary = {
            "critical_missing_evidence": critical_rows[:3],
            "top_weak_evidence": weak_rows[:5],
            "strongest_evidence": strongest_rows[:3],
        }
        return {
            "evidence_summary_simple": summary,
            "critical_missing_evidence": summary["critical_missing_evidence"],
            "top_weak_evidence": summary["top_weak_evidence"],
            "strongest_evidence": summary["strongest_evidence"],
            "evidence_display_rows": default_rows,
        }

    def build_manuscript_evidence_summary_simple(
        self,
        section_details: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a manuscript-level evidence summary grouped by section."""
        critical = []
        weak = []
        strong = []
        for section in section_details:
            section_name = str(
                section.get("section_name")
                or section.get("scoring_section")
                or section.get("predicted_section")
                or "Unknown"
            )
            section_summary = section.get("evidence_summary_simple") or {}
            critical.extend(section_summary.get("critical_missing_evidence", []))
            weak.extend(section_summary.get("top_weak_evidence", []))
            strong.extend(section_summary.get("strongest_evidence", []))

        critical = sorted(critical, key=lambda row: row.get("display_score", 0.0))[:5]
        weak = sorted(weak, key=lambda row: row.get("display_score", 0.0))[:8]
        strong = sorted(
            strong,
            key=lambda row: row.get("display_score", 0.0),
            reverse=True,
        )[:5]

        display_rows = []
        seen = set()
        for row in critical + weak + strong:
            key = (row.get("section"), row.get("criterion"))
            if key not in seen:
                display_rows.append(row)
                seen.add(key)

        summary = {
            "critical_missing_evidence": critical,
            "top_weak_evidence": weak,
            "strongest_evidence": strong,
        }
        return {
            "evidence_summary_simple": summary,
            "critical_missing_evidence": critical,
            "top_weak_evidence": weak,
            "strongest_evidence": strong,
            "evidence_display_rows": display_rows,
        }

    def _build_manuscript_summary_row(
        self,
        section_name: str,
        row: dict[str, Any],
        summary_type: str,
    ) -> dict[str, Any]:
        """Build a backward-compatible evidence summary row with section context."""
        evidence_area = str(row.get("Evidence Area", ""))
        return {
            "Section Name": section_name,
            "Evidence Area": f"{section_name}: {evidence_area}",
            "Criterion": evidence_area,
            "Similarity Score": row.get("Similarity Score", 0.0),
            "Coverage Level": row.get("Coverage Level", "Weak"),
            "Summary Type": summary_type,
            "Interpretation": (
                f"{summary_type} for {section_name}: "
                f"{row.get('Interpretation', '')}"
            ),
        }

    def build_section_score_explainability(
        self,
        section_name: str,
        evidence_coverage: list[dict[str, Any]],
        score_result: dict[str, Any],
        classification_confidence: float,
        word_count: int,
        priority_fixes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Expose score inputs and practical reasons without changing scoring."""
        raw_breakdown = dict(score_result.get("score_breakdown", {}))
        final_score = float(score_result.get("defense_score", 0.0))
        average_similarity = float(raw_breakdown.get("average_similarity", 0.0))
        weak_items = sorted(
            (
                item
                for item in evidence_coverage
                if item.get("Coverage Level") == "Weak"
            ),
            key=lambda item: float(item.get("Similarity Score", 0.0)),
        )
        weak_count = len(weak_items)
        total_count = max(len(evidence_coverage), 1)

        threshold_by_section = {
            "Abstract": 100,
            "Introduction": 300,
            "Objectives of the Study": 100,
            "Literature Review": 400,
            "Methodology": 300,
            "Results and Discussion": 300,
            "Conclusion": 150,
            "Limitations": 100,
        }
        word_threshold = threshold_by_section.get(section_name, 150)
        completeness_score = min((word_count / word_threshold) * 100, 100.0)
        evidence_score = round(average_similarity * 100, 2)

        score_breakdown = {
            **raw_breakdown,
            "evidence_coverage_score": evidence_score,
            "alignment_score": None,
            "section_completeness_score": round(completeness_score, 2),
            "weak_evidence_penalty": raw_breakdown.get("risk_deduction", 0.0),
            "extraction_confidence": round(classification_confidence * 100, 2),
            "final_score": final_score,
        }

        score_reasons = []
        for item in weak_items[:3]:
            area = str(item.get("Evidence Area", "Unknown criterion"))
            metric = round(float(item.get("Similarity Score", 0.0)), 4)
            score_reasons.append(
                {
                    "affected_section": section_name,
                    "issue": f"Weak evidence coverage for {area}.",
                    "metric": f"similarity_score={metric}",
                    "evidence": item.get("Interpretation", ""),
                    "next_action": (
                        f"Add clearer section-specific evidence for {area.lower()}."
                    ),
                }
            )

        if completeness_score < 100:
            score_reasons.append(
                {
                    "affected_section": section_name,
                    "issue": "The section appears short for this thesis section type.",
                    "metric": f"word_count={word_count}, expected_minimum={word_threshold}",
                    "evidence": "Short sections may not contain enough detail for defense readiness.",
                    "next_action": "Expand the section with concrete methods, findings, or support.",
                }
            )

        priority_actions = [
            str(fix.get("Suggested Fix") or fix.get("Issue") or fix)
            for fix in priority_fixes
        ][:3]
        while len(priority_actions) < 3 and len(score_reasons) > len(priority_actions):
            priority_actions.append(str(score_reasons[len(priority_actions)]["next_action"]))

        score_explanation = (
            f"The final score is {final_score:.2f}/100. It uses the existing "
            f"section formula: base score plus evidence points and available "
            f"coverage bonuses, minus the existing weak-evidence penalty. "
            f"For {section_name}, evidence coverage is {evidence_score:.2f}/100 "
            f"with {weak_count} weak criteria out of {total_count} checked criteria."
        )

        return {
            "score_breakdown": score_breakdown,
            "score_explanation": score_explanation,
            "score_reasons": score_reasons[:5],
            "priority_actions": priority_actions[:3],
        }

    def build_manuscript_score_explainability(
        self,
        section_details: list[dict[str, Any]],
        section_results: list[dict[str, Any]],
        score_breakdown: dict[str, Any],
        overall_score: float,
        analysis_confidence: str,
        missing_major_sections: list[str],
        top_weak_alignment_pairs: list[str],
    ) -> dict[str, Any]:
        """Explain the existing full-manuscript weighted score."""
        weak_sections = sorted(
            section_results,
            key=lambda item: float(item.get("Defense Score", 0.0)),
        )
        weakest_sections = weak_sections[:3]
        weak_evidence_penalty = sum(
            float(
                section.get("score_breakdown", {}).get(
                    "weak_evidence_penalty",
                    section.get("score_breakdown", {}).get("risk_deduction", 0.0),
                )
            )
            for section in section_details
        )

        expanded_breakdown = {
            **score_breakdown,
            "evidence_coverage_score": score_breakdown.get("evidence_coverage_score"),
            "alignment_score": score_breakdown.get("semantic_alignment_score"),
            "section_completeness_score": score_breakdown.get("completeness_score"),
            "weak_evidence_penalty": round(weak_evidence_penalty, 2),
            "extraction_confidence": score_breakdown.get("classification_score"),
            "final_score": overall_score,
        }

        score_reasons: list[dict[str, Any]] = []
        for section in weakest_sections:
            section_name = str(section.get("Section Name", "Unknown"))
            score_reasons.append(
                {
                    "affected_section": section_name,
                    "issue": "This is one of the lowest-scoring extracted sections.",
                    "metric": f"defense_score={section.get('Defense Score')}",
                    "evidence": f"Top weak areas: {section.get('Top Weak Areas', '')}",
                    "next_action": (
                        "Revise the weakest section-specific criteria in this section first."
                    ),
                }
            )

        for section_name in missing_major_sections[:3]:
            score_reasons.append(
                {
                    "affected_section": section_name,
                    "issue": "Required thesis section was not confidently extracted.",
                    "metric": "section_extraction=missing",
                    "evidence": "Missing or unclear headings reduce manuscript-level confidence.",
                    "next_action": "Add or clarify the section heading and required content.",
                }
            )

        for pair in top_weak_alignment_pairs[:2]:
            score_reasons.append(
                {
                    "affected_section": pair,
                    "issue": "Weak semantic alignment between thesis sections.",
                    "metric": "alignment_level=weak",
                    "evidence": pair,
                    "next_action": (
                        "Add linking statements that connect objectives, methods, results, and conclusions."
                    ),
                }
            )

        priority_actions = [
            str(reason["next_action"])
            for reason in score_reasons
        ][:3]

        score_explanation = (
            f"The final manuscript score is {overall_score:.2f}/100. It uses the "
            "existing weighted formula: section extraction, section classification "
            "confidence, evidence coverage, semantic alignment, and completeness. "
            f"The current analysis confidence is {analysis_confidence}."
        )

        return {
            "score_breakdown": expanded_breakdown,
            "score_explanation": score_explanation,
            "score_reasons": score_reasons[:6],
            "priority_actions": priority_actions,
        }

    def analyze_api_section(
        self,
        text: str,
        section_name: str | None = None,
        source_filename: str | None = None,
    ) -> dict[str, Any]:
        """Run the FastAPI single-section analysis pipeline."""
        clean_text = self.normalize_text(text)
        if not clean_text:
            raise AnalysisServiceError("No readable text was provided.", 400)

        start_time = time.perf_counter()
        analysis_text = clean_text[:10000]
        classification = classify_section_zero_shot(analysis_text)
        semantic_predicted_section = str(classification["predicted_section"])
        canonical_section = normalize_section_name(
            section_name or semantic_predicted_section
        )
        section_label = self.resolve_section_label(
            section_name=section_name,
            scoring_section=canonical_section,
            semantic_prediction=semantic_predicted_section,
        )
        predicted_section = section_label["resolved_section_label"]

        print("--------------------------------------------------")
        print("SECTION DEBUG")
        print(f"raw section_name:    {section_name}")
        print(f"canonical/scoring section: {canonical_section}")
        print(f"semantic prediction: {semantic_predicted_section}")
        print(f"resolved label:      {predicted_section}")

        evidence_result = analyze_evidence_coverage(canonical_section, analysis_text)
        evidence_coverage = list(evidence_result["evidence_coverage"])
        score_result = compute_defense_readiness_score(
            evidence_coverage,
            canonical_section,
            classification_confidence=float(classification["confidence"]),
            word_count=len(analysis_text.split()),
        )
        expected_areas = list(score_result["criteria_used"])

        print(f"criteria_used:       {expected_areas}")
        print(f"top_weak_areas:      {evidence_result['weak_areas']}")
        print("--------------------------------------------------")

        strong_areas = list(evidence_result["strong_areas"])
        needs_improvement_areas = list(evidence_result["weak_areas"]) + list(
            evidence_result["moderate_areas"]
        )
        priority_fixes = generate_priority_fixes(
            score_result,
            evidence_coverage,
            canonical_section,
        )
        revision_suggestions = generate_revision_suggestions(
            canonical_section,
            evidence_coverage,
            score_result,
        )
        safer_wording = generate_safer_wording_suggestions(analysis_text)
        defense_questions = generate_defense_questions(
            canonical_section,
            evidence_coverage,
            score_result,
        )
        defense_notes = generate_defense_notes(score_result)
        section_recommendations = generate_section_recommendation(
            canonical_section,
            needs_improvement_areas,
        )
        top_weak_areas_only = [
            str(item["Evidence Area"])
            for item in evidence_coverage
            if item.get("Coverage Level") == "Weak"
        ]

        contextual_highlights = analyze_contextual_highlights(
            section_name=canonical_section,
            section_text=analysis_text,
            weak_areas=top_weak_areas_only,
        )

        print("--------------------------------------------------")
        print("SECTION HIGHLIGHTS DEBUG")
        print(f"section_name:        {canonical_section}")
        print(f"highlight_count:     {len(contextual_highlights['highlights'])}")
        print(
            "first_highlight_type: "
            f"{contextual_highlights['highlights'][0]['highlight_type'] if contextual_highlights['highlights'] else 'None'}"
        )
        print("--------------------------------------------------")

        next_best_action = generate_next_best_action(
            canonical_section,
            top_weak_areas_only,
        )
        generate_panel_risk(canonical_section, top_weak_areas_only)
        suggested_revision_wording = generate_suggested_revision_wording(
            top_weak_areas_only
        )

        section_score = float(score_result["defense_score"])
        section_risk = str(score_result["risk_level"])
        score_explainability = self.build_section_score_explainability(
            canonical_section,
            evidence_coverage,
            score_result,
            float(classification["confidence"]),
            len(clean_text.split()),
            priority_fixes,
        )
        section_evidence_summary = self.build_section_evidence_summary(
            canonical_section,
            evidence_coverage,
            expected_areas,
        )
        gemini_feedback = generate_gemini_feedback(
            section_name=canonical_section,
            section_text=analysis_text,
            top_weak_areas=top_weak_areas_only,
            defense_score=section_score,
            risk_level=section_risk,
            evidence_coverage=evidence_coverage,
        )

        generated_feedback = [
            priority_fixes,
            revision_suggestions,
            section_recommendations,
            safer_wording,
            defense_questions,
            defense_notes,
        ]
        responsible_ai_warnings = generate_responsible_ai_warnings(
            clean_text,
            generated_feedback,
        )
        priority_fixes = filter_unsafe_recommendations(priority_fixes)
        revision_suggestions = filter_unsafe_recommendations(revision_suggestions)
        section_recommendations = filter_unsafe_recommendations(section_recommendations)
        defense_notes = filter_unsafe_recommendations(defense_notes)
        strong_count, moderate_count, weak_count, top_weak_areas = (
            self.count_evidence_levels(evidence_coverage)
        )
        processing_time = round(time.perf_counter() - start_time, 2)

        doc_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:8]
        avg_similarity = sum(
            [float(e.get("Similarity Score", 0)) for e in evidence_coverage]
        ) / max(len(evidence_coverage), 1)
        first_3_scores = [
            f"{e.get('Evidence Area', '')}: {e.get('Similarity Score', 0)}"
            for e in evidence_coverage[:3]
        ]

        print("--- Backend Debug Log: Analyze Section ---")
        print(f"Source filename: {source_filename}")
        print(f"Document hash: {doc_hash}")
        print(f"Extracted text length: {len(clean_text)}")
        print("Sections found: 1")
        print(f"Section name: {section_name or predicted_section}")
        print(f"Average similarity: {avg_similarity:.3f}")
        print(f"First 3 evidence scores: {', '.join(first_3_scores)}")
        print("------------------------------------------")

        section_dict = {
            "analysis_mode": "Single Section Mode",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "document_hash": doc_hash,
            "source_filename": source_filename,
            "section_name": section_label["display_section"],
            "display_section": section_label["display_section"],
            "resolved_section_label": section_label["resolved_section_label"],
            "section_label_source": section_label["section_label_source"],
            "section_label_confidence": section_label["section_label_confidence"],
            "scoring_section": canonical_section,
            "predicted_section": predicted_section,
            "semantic_predicted_section": semantic_predicted_section,
            "section_confidence": round(float(classification["confidence"]) * 100, 2),
            "section_scores": classification["all_scores"],
            "word_count": len(clean_text.split()),
            "character_count": len(clean_text),
            "text_preview": clean_text[:1000],
            "evidence_coverage": evidence_coverage,
            "evidence_summary_simple": section_evidence_summary[
                "evidence_summary_simple"
            ],
            "critical_missing_evidence": section_evidence_summary[
                "critical_missing_evidence"
            ],
            "top_weak_evidence": section_evidence_summary["top_weak_evidence"],
            "strongest_evidence": section_evidence_summary["strongest_evidence"],
            "evidence_display_rows": section_evidence_summary["evidence_display_rows"],
            "criteria_used": list(evidence_result["criteria_used"]),
            "defense_score": round(section_score, 2),
            "risk_level": section_risk,
            "score_summary": (
                f"The analyzed section received a defense readiness score of "
                f"{section_score:.2f}/100 with a {section_risk} risk level."
            ),
            "expected_areas": expected_areas,
            "expected_items": score_result["expected_items"],
            "avg_expected_similarity": score_result["avg_expected_similarity"],
            "strong_areas": strong_areas,
            "needs_improvement_areas": needs_improvement_areas,
            "plain_language_diagnosis": generate_plain_language_diagnosis(
                canonical_section,
                section_score,
                section_risk,
                strong_areas,
                needs_improvement_areas,
            ),
            "section_recommendations": section_recommendations,
            "strengths": score_result["strengths"],
            "deductions": score_result["deductions"],
            "score_breakdown": score_explainability["score_breakdown"],
            "score_explanation": score_explainability["score_explanation"],
            "score_reasons": score_explainability["score_reasons"],
            "priority_actions": score_explainability["priority_actions"],
            "priority_fixes": priority_fixes,
            "revision_suggestions": revision_suggestions,
            "safer_wording_suggestions": safer_wording,
            "defense_questions": defense_questions,
            "defense_notes": defense_notes,
            "responsible_ai_warnings": responsible_ai_warnings,
            "strong_evidence_count": strong_count,
            "moderate_evidence_count": moderate_count,
            "weak_evidence_count": weak_count,
            "top_weak_areas": top_weak_areas,
            "processing_time_seconds": processing_time,
            "next_best_action": next_best_action,
            "suggested_revision_wording": suggested_revision_wording,
            "contextual_highlights": contextual_highlights["highlights"],
        }
        section_dict.update(gemini_feedback)
        return section_dict

    def analyze_api_full_manuscript(
        self,
        text: str,
        source_filename: str | None = None,
    ) -> dict[str, Any]:
        """Run the FastAPI full-manuscript analysis pipeline."""
        clean_text = self.normalize_manuscript_text(text)
        if not clean_text:
            raise AnalysisServiceError("No readable manuscript text was provided.", 400)

        doc_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:8]
        start_time = time.perf_counter()
        extraction_result = extract_sections_with_metadata(clean_text)
        extracted_sections = dict(extraction_result["sections"])
        extraction_status = dict(extraction_result["extraction_status"])
        missing_major_sections = list(extraction_result["missing_major_sections"])
        sections_needing_review = list(extraction_result["sections_needing_review"])
        detected_headings = list(extraction_result.get("detected_headings", []))
        major_detected_headings = list(
            extraction_result.get("major_detected_headings", detected_headings)
        )
        all_detected_headings = list(
            extraction_result.get("all_detected_headings", detected_headings)
        )

        word_count_total = len(clean_text.split())
        major_present = [s for s in MAJOR_REQUIRED_SECTIONS if s in extracted_sections]
        extraction_warnings: list[str] = []
        if len(extracted_sections) <= 1 and word_count_total >= 5000:
            extraction_warnings.append(
                "Section extraction may have failed. Please check document headings "
                "or use DOCX upload with clear headings."
            )
        if len(major_present) <= 1:
            extraction_warnings.append(
                "Fewer than two major thesis sections were detected. The defense "
                "readiness score below is unreliable until extraction is fixed."
            )

        if not extracted_sections:
            raise AnalysisServiceError(
                "No recognizable thesis sections were extracted. "
                "Please ensure the document has clear chapter or section headings "
                "(e.g., 'CHAPTER 3', '3 Methodology', '4 Results and Discussion').",
                422,
            )

        objectives_confident = (
            extraction_status.get("Objectives of the Study") == "confidently extracted"
        )
        raw_alignment_results = generate_alignment_matrix(extracted_sections)
        alignment_results = [
            item
            for item in raw_alignment_results
            if item["Similarity Score"] is not None
            and (
                objectives_confident
                or "Objectives of the Study" not in str(item["Section Pair"])
            )
        ]

        section_details = []
        section_results = []
        for section_name, section_text in extracted_sections.items():
            if section_name == "References":
                continue

            section_result = self.analyze_api_section(
                section_text,
                section_name,
                source_filename=source_filename,
            )
            section_result["analysis_mode"] = "Full Manuscript Section"
            section_details.append(section_result)
            section_results.append(
                {
                    "Section Name": section_result["resolved_section_label"],
                    "Display Section": section_result["display_section"],
                    "Resolved Section Label": section_result[
                        "resolved_section_label"
                    ],
                    "Section Label Source": section_result["section_label_source"],
                    "Section Label Confidence": section_result[
                        "section_label_confidence"
                    ],
                    "Scoring Section": section_result["scoring_section"],
                    "Predicted Section": section_result["predicted_section"],
                    "Semantic Predicted Section": section_result[
                        "semantic_predicted_section"
                    ],
                    "Word Count": section_result["word_count"],
                    "Defense Score": section_result["defense_score"],
                    "Risk Level": section_result["risk_level"],
                    "Weak Evidence Count": section_result["weak_evidence_count"],
                    "Top Weak Areas": ", ".join(section_result["top_weak_areas"]),
                    "Criteria Used": section_result["criteria_used"],
                }
            )

        section_extraction_score = (
            (len(major_present) / len(MAJOR_REQUIRED_SECTIONS)) * 100
            if MAJOR_REQUIRED_SECTIONS
            else 100.0
        )
        classification_score = (
            sum(item.get("section_confidence", 0) for item in section_details)
            / len(section_details)
            if section_details
            else 0.0
        )
        avg_sim = (
            sum(item.get("avg_expected_similarity", 0) for item in section_details)
            / len(section_details)
            if section_details
            else 0.0
        )
        evidence_coverage_score = min(avg_sim * 100, 100.0)
        alignment_scores = [
            float(item.get("Similarity Score", 0))
            for item in alignment_results
            if item.get("Similarity Score") is not None
        ]
        semantic_alignment_score = (
            (sum(alignment_scores) / len(alignment_scores)) * 100
            if alignment_scores
            else 0.0
        )
        word_count = sum(item.get("word_count", 0) for item in section_details)
        completeness_score = min((word_count / 8000) * 100, 100.0)

        final_score = (
            section_extraction_score * 0.20
            + classification_score * 0.15
            + evidence_coverage_score * 0.30
            + semantic_alignment_score * 0.25
            + completeness_score * 0.10
        )
        overall_score = round(final_score, 2)

        if final_score >= 85:
            risk_level_str = "Low"
        elif final_score >= 70:
            risk_level_str = "Moderate"
        else:
            risk_level_str = "High"

        if section_extraction_score >= 80 and classification_score >= 80:
            analysis_confidence = "High"
        elif section_extraction_score >= 60 and classification_score >= 60:
            analysis_confidence = "Moderate"
        else:
            analysis_confidence = "Partial"

        if analysis_confidence == "Low":
            result_type = "Extraction Incomplete"
            recommendation = (
                "Fix headings or analyze sections individually. The extractor could "
                "not confidently locate the major thesis sections."
            )
        else:
            result_type = "Full Manuscript Analysis"
            recommendation = ""

        main_issues = []
        if "Objectives of the Study" in missing_major_sections:
            main_issues.append("Objectives section not confidently extracted")
        if not objectives_confident:
            main_issues.append("Alignment analysis incomplete")
        if any(item["Weak Evidence Count"] > 0 for item in section_results):
            main_issues.append("Some sections have weak evidence coverage")

        responsible_ai_warnings = []
        for section in section_details:
            responsible_ai_warnings.extend(section.get("responsible_ai_warnings", []))
        responsible_ai_warnings = list(dict.fromkeys(responsible_ai_warnings))
        top_weak_sections = [
            str(item["Section Name"])
            for item in sorted(
                section_results,
                key=lambda row: float(row["Defense Score"]),
            )[:3]
        ]
        top_weak_alignment_pairs = [
            str(item["Section Pair"])
            for item in alignment_results
            if item["Alignment Level"] in {"Weak Alignment", "Missing Section"}
        ][:5]
        processing_time = round(time.perf_counter() - start_time, 2)

        manuscript_score_breakdown = {
            "section_extraction_score": round(section_extraction_score, 2),
            "classification_score": round(classification_score, 2),
            "evidence_coverage_score": round(evidence_coverage_score, 2),
            "semantic_alignment_score": round(semantic_alignment_score, 2),
            "completeness_score": round(completeness_score, 2),
        }
        manuscript_score_explainability = self.build_manuscript_score_explainability(
            section_details,
            section_results,
            manuscript_score_breakdown,
            overall_score,
            analysis_confidence,
            missing_major_sections,
            top_weak_alignment_pairs,
        )

        avg_sim_total = 0.0
        scores_to_print = []
        if len(section_details) > 0:
            first_section_ev = section_details[0].get("evidence_coverage", [])
            total_evidences = sum(
                len(s.get("evidence_coverage", [])) for s in section_details
            )
            avg_sim_total = sum(
                float(e.get("Similarity Score", 0))
                for s in section_details
                for e in s.get("evidence_coverage", [])
            ) / max(total_evidences, 1)
            scores_to_print = [
                f"{e.get('Evidence Area', '')}: {e.get('Similarity Score', 0)}"
                for e in first_section_ev[:3]
            ]

        print("--- Backend Debug Log: Analyze Full Manuscript ---")
        print(f"Source filename: {source_filename}")
        print(f"Document hash: {doc_hash}")
        print(f"Extracted text length: {len(clean_text)}")
        print(f"Sections found: {len(extracted_sections)}")
        print(f"Section names: {list(extracted_sections.keys())}")
        print(f"Average similarity: {avg_sim_total:.3f}")
        print(f"First 3 evidence scores (1st section): {', '.join(scores_to_print)}")
        print("--------------------------------------------------")

        manuscript_evidence_summary_simple = (
            self.build_manuscript_evidence_summary_simple(section_details)
        )

        return {
            "analysis_mode": "Full Manuscript Mode",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "document_hash": doc_hash,
            "source_filename": source_filename,
            "predicted_section": "Full Manuscript",
            "section_confidence": "",
            "section_scores": [],
            "word_count": word_count,
            "character_count": len(clean_text),
            "text_preview": clean_text[:1000],
            "defense_score": overall_score,
            "risk_level": risk_level_str,
            "overall_score": overall_score,
            "overall_risk_level": risk_level_str,
            "overall_summary": (
                "Preliminary full manuscript review generated from extracted thesis sections."
            ),
            "analysis_confidence": analysis_confidence,
            "result_type": result_type,
            "recommendation": recommendation,
            "extraction_warnings": extraction_warnings,
            "detected_headings": detected_headings,
            "major_detected_headings": major_detected_headings,
            "all_detected_headings": all_detected_headings,
            "main_issues": main_issues,
            "alignment_results": alignment_results,
            "raw_alignment_results": raw_alignment_results,
            "alignment_deduction": 0,
            "weak_alignment_count": sum(
                1
                for item in alignment_results
                if item.get("Alignment Level") == "Weak Alignment"
            ),
            "missing_alignment_count": 0,
            "objectives_confident": objectives_confident,
            "manuscript_evidence_summary": self.build_manuscript_evidence_summary(
                section_details
            ),
            "evidence_summary_simple": manuscript_evidence_summary_simple[
                "evidence_summary_simple"
            ],
            "critical_missing_evidence": manuscript_evidence_summary_simple[
                "critical_missing_evidence"
            ],
            "top_weak_evidence": manuscript_evidence_summary_simple[
                "top_weak_evidence"
            ],
            "strongest_evidence": manuscript_evidence_summary_simple[
                "strongest_evidence"
            ],
            "evidence_display_rows": manuscript_evidence_summary_simple[
                "evidence_display_rows"
            ],
            "top_weak_sections": top_weak_sections,
            "top_weak_alignment_pairs": top_weak_alignment_pairs,
            "overall_defense_notes": [
                "Prepare clear explanations that connect objectives, methodology, results, and conclusion.",
                "Review weak alignment pairs before defense and add linking statements where needed.",
                "Use section-specific evidence tables to support answers to panel questions.",
            ],
            "section_results": section_results,
            "section_details": section_details,
            "extracted_sections": extracted_sections,
            "extraction_status": extraction_status,
            "sections_needing_review": sections_needing_review,
            "missing_major_sections": missing_major_sections,
            "responsible_ai_warnings": responsible_ai_warnings,
            "strong_evidence_count": sum(
                item["strong_evidence_count"] for item in section_details
            ),
            "moderate_evidence_count": sum(
                item["moderate_evidence_count"] for item in section_details
            ),
            "weak_evidence_count": sum(
                item["weak_evidence_count"] for item in section_details
            ),
            "top_weak_areas": list(
                dict.fromkeys(
                    area
                    for section in section_details
                    for area in section.get("top_weak_areas", [])
                )
            )[:5],
            "processing_time_seconds": processing_time,
            "readiness_score": overall_score,
            "total_word_count": word_count,
            "processing_time": processing_time,
            "score_breakdown": manuscript_score_explainability["score_breakdown"],
            "score_explanation": manuscript_score_explainability["score_explanation"],
            "score_reasons": manuscript_score_explainability["score_reasons"],
            "priority_actions": manuscript_score_explainability["priority_actions"],
            "extracted_section_stats": {
                k: {
                    "found": True,
                    "word_count": len(v.split()),
                }
                for k, v in extracted_sections.items()
            },
            "weakest_areas": list(
                dict.fromkeys(
                    area
                    for section in section_details
                    for area in section.get("top_weak_areas", [])
                )
            )[:5],
            "recommendations": recommendation,
            "defense_questions": [],
        }
