"""Streamlit interface for SAGE-Review."""

from datetime import datetime
import json
from pathlib import Path
import re
import time

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from backend.sage_review.core.alignment_analyzer import generate_alignment_matrix
from backend.sage_review.core.ai_analyzer import (
    analyze_evidence_coverage,
    classify_section_zero_shot,
)
from backend.sage_review.core.ai_scoring import compute_defense_readiness_score
from backend.sage_review.core.document_loader import extract_text_from_uploaded_file
from backend.sage_review.services.evaluation_engine import (
    ensure_evaluation_dataset_template,
    generate_evaluation_summary,
    load_evaluation_dataset,
    run_evaluation_on_dataset,
    save_evaluation_results,
)
from backend.sage_review.services.expert_validation import (
    compute_validation_summary,
    load_validation_results,
    save_validation_response,
)
from backend.sage_review.services.feedback_generator import (
    generate_defense_notes,
    generate_defense_questions,
    generate_plain_language_diagnosis,
    generate_priority_fixes,
    generate_revision_suggestions,
    generate_section_recommendation,
    generate_safer_wording_suggestions,
)
from backend.sage_review.services.report_generator import (
    generate_pdf_report,
    save_review_history,
)
from backend.sage_review.services.revision_comparison import (
    analyze_revision_text,
    compare_revision_results,
)
from backend.sage_review.core.responsible_ai_guardrail import (
    filter_unsafe_recommendations,
    generate_responsible_ai_warnings,
)
from backend.sage_review.core.section_extractor import (
    MAJOR_REQUIRED_SECTIONS,
    extract_sections_with_metadata,
)
from backend.sage_review.utils.visualizer import (
    plot_alignment_matrix_chart,
    plot_evidence_coverage_chart,
    plot_section_scores_chart,
)


def normalize_analysis_text(value: object) -> str:
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


def get_basic_text_stats(text: str) -> dict[str, int | str]:
    """Return basic manuscript text statistics for display."""
    clean_text = normalize_analysis_text(text)
    return {
        "word_count": len(clean_text.split()) if clean_text else 0,
        "character_count": len(clean_text),
        "preview": clean_text[:500],
    }


def style_coverage_table(row: pd.Series) -> list[str]:
    """Apply readable row colors based on semantic coverage level."""
    if row["Coverage Level"] == "Strong":
        return ["background-color: #d1e7dd; color: #0f5132"] * len(row)
    if row["Coverage Level"] == "Moderate":
        return ["background-color: #fff3cd; color: #664d03"] * len(row)
    return ["background-color: #f8d7da; color: #842029"] * len(row)


def count_evidence_levels(
    evidence_coverage: list[dict[str, object]],
) -> tuple[int, int, int, list[str]]:
    """Count evidence coverage levels and return the weakest evidence areas."""
    strong_count = 0
    moderate_count = 0
    weak_count = 0
    weak_items = []

    for item in evidence_coverage:
        coverage_level = str(item["Coverage Level"])
        if coverage_level == "Strong":
            strong_count += 1
        elif coverage_level == "Moderate":
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


def build_score_summary(score_result: dict[str, object]) -> str:
    """Create a short readable summary of the readiness score."""
    return (
        f"The analyzed section received a defense readiness score of "
        f"{float(score_result['score']):.2f}/100 with a "
        f"{score_result['risk_level']} risk level. The score is based on "
        "semantic evidence coverage for the expected thesis defense areas."
    )


def overall_risk_level(score: float) -> str:
    """Convert an overall manuscript score into a risk level."""
    if score >= 85:
        return "Low"
    if score >= 70:
        return "Moderate"
    return "High"


def format_risk_label(risk_level: str) -> str:
    """Return a user-friendly risk label."""
    if risk_level == "Low":
        return "Low Risk - mostly defense-ready."
    if risk_level == "Moderate":
        return "Moderate Risk - usable, but needs targeted improvement."
    return "High Risk - revision recommended before defense."


def get_section_area_groups(
    evidence_coverage: list[dict[str, object]],
    expected_areas: list[str],
) -> tuple[list[str], list[str]]:
    """Return strong and needs-improvement evidence areas for expected areas."""
    relevant_items = [
        item
        for item in evidence_coverage
        if str(item["Evidence Area"]) in expected_areas
    ]
    strong_areas = [
        str(item["Evidence Area"])
        for item in relevant_items
        if item["Coverage Level"] == "Strong"
    ]
    needs_improvement = [
        str(item["Evidence Area"])
        for item in sorted(
            relevant_items,
            key=lambda item: (
                0 if item["Coverage Level"] == "Weak" else 1,
                float(item["Similarity Score"]),
            ),
        )
        if item["Coverage Level"] != "Strong"
    ]
    return strong_areas, needs_improvement


def build_manuscript_evidence_summary(
    section_details: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Average expected evidence area scores across analyzed sections."""
    grouped_scores: dict[str, list[float]] = {}
    for section in section_details:
        expected_areas = set(section["expected_areas"])
        for item in section["evidence_coverage"]:
            area = str(item["Evidence Area"])
            if area in expected_areas:
                grouped_scores.setdefault(area, []).append(float(item["Similarity Score"]))

    summary = []
    for area, scores in grouped_scores.items():
        average_score = round(sum(scores) / len(scores), 4)
        if average_score >= 0.65:
            level = "Strong"
        elif average_score >= 0.45:
            level = "Moderate"
        else:
            level = "Weak"
        summary.append(
            {
                "Evidence Area": area,
                "Similarity Score": average_score,
                "Coverage Level": level,
                "Interpretation": "Average expected evidence coverage across extracted sections.",
            }
        )

    return sorted(summary, key=lambda item: float(item["Similarity Score"]), reverse=True)


def analyze_text_section(text: str, section_name: str | None = None) -> dict[str, object]:
    """Run the existing AI/NLP pipeline for one text section."""
    clean_text = normalize_analysis_text(text)
    if not clean_text:
        raise ValueError("The selected section has no readable text to analyze.")

    stats = get_basic_text_stats(clean_text)
    classification = classify_section_zero_shot(clean_text)
    predicted_section = str(classification["predicted_section"])
    evidence_result = analyze_evidence_coverage(clean_text, predicted_section)
    evidence_coverage = list(evidence_result["evidence_coverage"])
    score_result = compute_defense_readiness_score(
        evidence_coverage,
        predicted_section,
        classification_confidence=float(classification["confidence"]),
    )
    expected_areas = score_result["criteria_used"]
    strong_areas = list(evidence_result["strong_areas"])
    needs_improvement_areas = list(evidence_result["weak_areas"]) + list(
        evidence_result["moderate_areas"]
    )
    priority_fixes = generate_priority_fixes(
        score_result,
        evidence_coverage,
        predicted_section,
    )
    revision_suggestions = generate_revision_suggestions(
        predicted_section,
        evidence_coverage,
        score_result,
    )
    wording_suggestions = generate_safer_wording_suggestions(clean_text)
    defense_questions = generate_defense_questions(
        predicted_section,
        evidence_coverage,
        score_result,
    )
    defense_notes = generate_defense_notes(score_result)
    diagnosis = generate_plain_language_diagnosis(
        section_name or predicted_section,
        float(score_result["score"]),
        str(score_result["risk_level"]),
        strong_areas,
        needs_improvement_areas,
    )
    section_recommendations = generate_section_recommendation(
        section_name or predicted_section,
        needs_improvement_areas,
    )
    generated_feedback = [
        priority_fixes,
        revision_suggestions,
        section_recommendations,
        wording_suggestions,
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
    strong_count, moderate_count, weak_count, top_weak_areas = count_evidence_levels(
        evidence_coverage
    )

    return {
        "section_name": section_name or predicted_section,
        "input_text": clean_text,
        "text_preview": clean_text[:1000],
        "predicted_section": predicted_section,
        "section_confidence": round(float(classification["confidence"]) * 100, 2),
        "section_scores": classification["all_scores"],
        "word_count": stats["word_count"],
        "character_count": stats["character_count"],
        "evidence_coverage": evidence_coverage,
        "defense_score": score_result["defense_score"],
        "risk_level": score_result["risk_level"],
        "score_summary": build_score_summary(score_result),
        "expected_areas": expected_areas,
        "criteria_used": list(evidence_result["criteria_used"]),
        "expected_items": score_result["expected_items"],
        "strong_areas": strong_areas,
        "needs_improvement_areas": needs_improvement_areas,
        "plain_language_diagnosis": diagnosis,
        "section_recommendations": section_recommendations,
        "strengths": score_result["strengths"],
        "deductions": score_result["deductions"],
        "score_breakdown": score_result["score_breakdown"],
        "priority_fixes": priority_fixes,
        "revision_suggestions": revision_suggestions,
        "safer_wording_suggestions": wording_suggestions,
        "defense_questions": defense_questions,
        "defense_notes": defense_notes,
        "responsible_ai_warnings": responsible_ai_warnings,
        "strong_evidence_count": strong_count,
        "moderate_evidence_count": moderate_count,
        "weak_evidence_count": weak_count,
        "top_weak_areas": top_weak_areas,
    }


def analyze_full_manuscript(text: str) -> dict[str, object]:
    """Extract and analyze thesis sections, then compute overall readiness."""
    clean_text = normalize_analysis_text(text)
    extraction_result = extract_sections_with_metadata(clean_text)
    extracted_sections = dict(extraction_result["sections"])
    extraction_status = dict(extraction_result["extraction_status"])
    sections_needing_review = list(extraction_result["sections_needing_review"])
    missing_major_sections = list(extraction_result["missing_major_sections"])
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
    section_summary_rows = []

    for section_name, section_text in extracted_sections.items():
        clean_section_text = normalize_analysis_text(section_text)
        if not clean_section_text:
            continue

        section_result = analyze_text_section(clean_section_text, section_name)
        section_details.append(section_result)
        section_summary_rows.append(
            {
                "Section Name": section_name,
                "Predicted Section": section_result["predicted_section"],
                "Word Count": section_result["word_count"],
                "Defense Score": section_result["defense_score"],
                "Risk Level": section_result["risk_level"],
                "Weak Evidence Count": section_result["weak_evidence_count"],
                "Top Weak Areas": ", ".join(section_result["top_weak_areas"]),
            }
        )

    average_score = (
        sum(float(item["defense_score"]) for item in section_details)
        / len(section_details)
        if section_details
        else 0.0
    )
    weak_alignment_count = sum(
        1
        for item in alignment_results
        if item["Alignment Level"] == "Weak Alignment"
    )
    missing_alignment_count = 0
    alignment_deduction = min(20, 5 * weak_alignment_count)
    overall_score = max(
        40.0 if section_details else 0.0,
        min(
            100.0,
            average_score
            - (5 * len(missing_major_sections))
            - alignment_deduction,
        ),
    )
    analysis_confidence = (
        "Complete"
        if not missing_major_sections and not sections_needing_review
        else "Partial"
    )
    main_issues = []
    if "Objectives of the Study" in missing_major_sections:
        main_issues.append("Objectives section not confidently extracted")
    if not objectives_confident:
        main_issues.append("Alignment analysis incomplete")
    if any(int(item["Weak Evidence Count"]) > 0 for item in section_summary_rows):
        main_issues.append("Some sections have weak evidence coverage")
    manuscript_evidence_summary = build_manuscript_evidence_summary(section_details)

    return {
        "overall_score": round(overall_score, 2),
        "overall_risk_level": overall_risk_level(overall_score),
        "alignment_results": alignment_results,
        "raw_alignment_results": raw_alignment_results,
        "alignment_deduction": alignment_deduction,
        "weak_alignment_count": weak_alignment_count,
        "missing_alignment_count": missing_alignment_count,
        "objectives_confident": objectives_confident,
        "analysis_confidence": analysis_confidence,
        "main_issues": main_issues,
        "manuscript_evidence_summary": manuscript_evidence_summary,
        "section_results": section_summary_rows,
        "section_details": section_details,
        "extracted_sections": extracted_sections,
        "extraction_status": extraction_status,
        "sections_needing_review": sections_needing_review,
        "missing_major_sections": missing_major_sections,
    }


def show_evidence_summary(coverage_table: pd.DataFrame) -> None:
    """Show grouped evidence coverage summaries with Streamlit status styles."""
    strong_areas = coverage_table.loc[
        coverage_table["Coverage Level"] == "Strong", "Evidence Area"
    ].tolist()
    moderate_areas = coverage_table.loc[
        coverage_table["Coverage Level"] == "Moderate", "Evidence Area"
    ].tolist()
    weak_areas = coverage_table.loc[
        coverage_table["Coverage Level"] == "Weak", "Evidence Area"
    ].tolist()

    summary_left, summary_right = st.columns(2)
    with summary_left:
        st.markdown("#### Strong Evidence Areas")
        if strong_areas:
            for area in strong_areas:
                st.success(area)
        else:
            st.info("No strong evidence areas detected yet.")

    with summary_right:
        st.markdown("#### Weak or Missing Evidence Areas")
        if weak_areas:
            for area in weak_areas:
                st.warning(area)
        else:
            st.success("No weak evidence areas detected.")

    if moderate_areas:
        st.markdown("#### Moderate Evidence Areas")
        for area in moderate_areas:
            st.warning(area)


def show_responsible_ai_warnings(result: dict[str, object]) -> None:
    """Display responsible AI warnings when integrity risks are detected."""
    warnings = list(result.get("responsible_ai_warnings", []))
    if not warnings:
        return

    st.markdown("### Responsible AI Warnings")
    for warning in warnings:
        st.warning(str(warning))
    st.info(
        "SAGE-Review is a decision-support tool. It does not replace adviser "
        "or panel judgment."
    )


def show_defense_readiness_score(result: dict[str, object]) -> None:
    """Display the defense readiness scoring output."""
    st.markdown("### AI Defense Readiness Score")
    score_col, risk_col = st.columns(2)
    score_col.metric("Readiness Score", f"{float(result['defense_score']):.2f}/100")
    risk_col.metric("Risk Level", str(result["risk_level"]))

    strengths = list(result.get("strengths", []))
    deductions = list(result.get("deductions", []))
    detail_left, detail_right = st.columns(2)
    with detail_left:
        st.markdown("#### Strengths")
        if strengths:
            for strength in strengths:
                st.success(str(strength))
        else:
            st.warning("No strong expected evidence areas detected yet.")
    with detail_right:
        st.markdown("#### Deductions")
        if deductions:
            st.dataframe(pd.DataFrame(deductions), use_container_width=True, hide_index=True)
        else:
            st.success("No deductions from expected evidence areas.")


def show_feedback_section(result: dict[str, object]) -> None:
    """Display structured feedback and defense preparation output."""
    st.markdown("### Intelligent Feedback and Defense Preparation")

    st.markdown("#### Priority Fixes")
    if result["priority_fixes"]:
        st.dataframe(
            pd.DataFrame(result["priority_fixes"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No priority fixes detected from the current evidence profile.")

    feedback_left, feedback_right = st.columns(2)
    with feedback_left:
        st.markdown("#### Revision Suggestions")
        for suggestion in result["revision_suggestions"]:
            st.write(f"- {suggestion}")
        st.markdown("#### Defense Preparation Notes")
        for note in result["defense_notes"]:
            st.write(f"- {note}")

    with feedback_right:
        st.markdown("#### Recommended Defense Questions")
        if result["defense_questions"]:
            for question in result["defense_questions"]:
                st.write(f"- {question}")
        else:
            st.success("No additional defense questions were generated.")

    st.markdown("#### Safer Academic Wording Suggestions")
    if result["safer_wording_suggestions"]:
        st.dataframe(
            pd.DataFrame(result["safer_wording_suggestions"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No risky academic wording was detected.")


def show_export_buttons(pdf_path: str, csv_path: str) -> None:
    """Display PDF and CSV download buttons."""
    st.markdown("### Export Results")
    pdf_file = Path(pdf_path)
    csv_file = Path(csv_path)
    export_left, export_right = st.columns(2)

    with export_left:
        st.download_button(
            "Download PDF Report",
            data=pdf_file.read_bytes(),
            file_name=pdf_file.name,
            mime="application/pdf",
            use_container_width=True,
        )
    with export_right:
        st.download_button(
            "Download CSV Review History",
            data=csv_file.read_bytes(),
            file_name=csv_file.name,
            mime="text/csv",
            use_container_width=True,
        )


def show_expert_validation_form(
    result: dict[str, object],
    form_key: str,
) -> None:
    """Display an adviser validation form for a completed analysis."""
    with st.expander("Expert / Adviser Validation Form", expanded=False):
        st.info(
            "Use this form when an adviser or evaluator wants to rate the "
            "system output for this analysis."
        )
        with st.form(f"expert_validation_{form_key}"):
            evaluator_name = st.text_input(
                "Evaluator name or evaluator code",
                key=f"{form_key}_evaluator_name",
            )
            sample_id = st.text_input(
                "Sample ID or document name",
                value=str(result.get("sample_id", "")),
                key=f"{form_key}_sample_id",
            )
            detected_section_correct = st.radio(
                "Detected section correct?",
                ["Yes", "No"],
                horizontal=True,
                key=f"{form_key}_detected_correct",
            )

            rating_col_one, rating_col_two = st.columns(2)
            with rating_col_one:
                score_reasonable = st.slider(
                    "Score reasonable rating",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"{form_key}_score_reasonable",
                )
                feedback_useful = st.slider(
                    "Feedback useful rating",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"{form_key}_feedback_useful",
                )
            with rating_col_two:
                questions_relevant = st.slider(
                    "Defense questions relevant rating",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"{form_key}_questions_relevant",
                )
                recommendations_acceptable = st.slider(
                    "Recommendations acceptable rating",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"{form_key}_recommendations_acceptable",
                )

            comments = st.text_area(
                "Comments",
                key=f"{form_key}_comments",
            )
            submitted = st.form_submit_button("Save Validation Response")

        if submitted:
            response = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analysis_mode": result.get("analysis_mode", ""),
                "system_detected_section": result.get("predicted_section", ""),
                "system_score": result.get("defense_score", ""),
                "system_risk_level": result.get("risk_level", ""),
                "evaluator_name_or_code": evaluator_name,
                "sample_id_or_document_name": sample_id,
                "detected_section_correct": detected_section_correct,
                "score_reasonable_rating": score_reasonable,
                "feedback_useful_rating": feedback_useful,
                "defense_questions_relevant_rating": questions_relevant,
                "recommendations_acceptable_rating": recommendations_acceptable,
                "comments": comments,
            }
            save_validation_response(response)
            st.success("Expert validation response saved successfully.")


def handle_validation_results_summary_mode() -> None:
    """Display aggregate adviser validation results."""
    st.markdown("### Validation Results Summary")
    validation_df = load_validation_results()

    if validation_df.empty:
        st.info("No expert validation responses have been saved yet.")
        return

    summary = compute_validation_summary(validation_df)
    metric_one, metric_two, metric_three = st.columns(3)
    metric_one.metric(
        "Total Validation Responses",
        summary["total_validation_responses"],
    )
    metric_two.metric(
        "Mean Score Reasonableness",
        f"{summary['mean_score_reasonableness']:.2f}/5",
    )
    metric_three.metric(
        "Correct Section Detection",
        f"{summary['correct_section_detection_percentage']:.2f}%",
    )

    metric_four, metric_five, metric_six = st.columns(3)
    metric_four.metric(
        "Mean Feedback Usefulness",
        f"{summary['mean_feedback_usefulness']:.2f}/5",
    )
    metric_five.metric(
        "Mean Question Relevance",
        f"{summary['mean_question_relevance']:.2f}/5",
    )
    metric_six.metric(
        "Mean Recommendation Acceptability",
        f"{summary['mean_recommendation_acceptability']:.2f}/5",
    )

    st.markdown("### Saved Validation Responses")
    st.dataframe(validation_df, use_container_width=True, hide_index=True)

    validation_path = Path("data/expert_validation_results.csv")
    if validation_path.exists():
        st.download_button(
            "Download Expert Validation Results CSV",
            data=validation_path.read_bytes(),
            file_name=validation_path.name,
            mime="text/csv",
            use_container_width=True,
        )


def plot_manual_vs_system_score(results_df: pd.DataFrame):
    """Create a compact manual score vs system score chart."""
    chart_df = results_df.dropna(subset=["manual_score", "system_score"])
    if chart_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 3.5))
    x_positions = range(len(chart_df))
    ax.plot(
        x_positions,
        chart_df["manual_score"],
        marker="o",
        label="Manual Score",
    )
    ax.plot(
        x_positions,
        chart_df["system_score"],
        marker="o",
        label="System Score",
    )
    ax.set_title("Manual Score vs System Score")
    ax.set_xlabel("Sample")
    ax.set_ylabel("Score")
    ax.set_ylim(0, 100)
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(chart_df["sample_id"].astype(str), rotation=35, ha="right")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_processing_time_per_sample(results_df: pd.DataFrame):
    """Create a compact processing time chart."""
    if results_df.empty or "processing_time_seconds" not in results_df.columns:
        return None

    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.bar(
        results_df["sample_id"].astype(str),
        results_df["processing_time_seconds"],
        color="#4f81bd",
    )
    ax.set_title("Processing Time per Sample")
    ax.set_xlabel("Sample")
    ax.set_ylabel("Seconds")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    return fig


def plot_classification_correctness(results_df: pd.DataFrame):
    """Create a correct vs incorrect classification chart."""
    if results_df.empty or "section_correct" not in results_df.columns:
        return None

    correct_count = int(results_df["section_correct"].sum())
    incorrect_count = int(len(results_df) - correct_count)
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.bar(
        ["Correct", "Incorrect"],
        [correct_count, incorrect_count],
        color=["#198754", "#dc3545"],
    )
    ax.set_title("Correct vs Incorrect Classification")
    ax.set_ylabel("Sample Count")
    ax.set_ylim(0, max(1, len(results_df)))
    fig.tight_layout()
    return fig


def show_evaluation_charts(results_df: pd.DataFrame) -> None:
    """Display evaluation charts with empty-state handling."""
    chart_one, chart_two = st.columns(2)

    with chart_one:
        manual_score_chart = plot_manual_vs_system_score(results_df)
        if manual_score_chart:
            st.pyplot(manual_score_chart)
        else:
            st.info("Not enough score data to display this chart yet.")

    with chart_two:
        classification_chart = plot_classification_correctness(results_df)
        if classification_chart:
            st.pyplot(classification_chart)
        else:
            st.info("Not enough classification data to display this chart yet.")

    processing_chart = plot_processing_time_per_sample(results_df)
    if processing_chart:
        st.pyplot(processing_chart)
    else:
        st.info("Not enough processing time data to display this chart yet.")


def build_revision_evidence_comparison_table(
    original_result: dict[str, object],
    revised_result: dict[str, object],
) -> pd.DataFrame:
    """Build a side-by-side evidence coverage comparison table."""
    original_by_area = {
        str(item["Evidence Area"]): item
        for item in original_result.get("evidence_coverage", [])
    }
    revised_by_area = {
        str(item["Evidence Area"]): item
        for item in revised_result.get("evidence_coverage", [])
    }
    evidence_areas = sorted(set(original_by_area) | set(revised_by_area))

    rows = []
    for area in evidence_areas:
        original_item = original_by_area.get(area, {})
        revised_item = revised_by_area.get(area, {})
        original_score = original_item.get("Similarity Score")
        revised_score = revised_item.get("Similarity Score")
        score_change = None
        if original_score is not None and revised_score is not None:
            score_change = round(float(revised_score) - float(original_score), 4)

        rows.append(
            {
                "Evidence Area": area,
                "Original Score": original_score,
                "Original Level": original_item.get("Coverage Level", ""),
                "Revised Score": revised_score,
                "Revised Level": revised_item.get("Coverage Level", ""),
                "Score Change": score_change,
            }
        )

    return pd.DataFrame(rows)


def plot_revision_score_comparison(comparison: dict[str, object]):
    """Create a bar chart comparing original and revised readiness scores."""
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    scores = [
        float(comparison["original_score"]),
        float(comparison["revised_score"]),
    ]
    ax.bar(
        ["Original", "Revised"],
        scores,
        color=["#6c757d", "#198754" if scores[1] >= scores[0] else "#dc3545"],
    )
    ax.set_title("Original vs Revised Readiness Score")
    ax.set_ylabel("Readiness Score")
    ax.set_ylim(0, 100)
    for index, score in enumerate(scores):
        ax.text(index, min(score + 2, 98), f"{score:.2f}", ha="center")
    fig.tight_layout()
    return fig


def _comparison_export_payload(
    original_result: dict[str, object],
    revised_result: dict[str, object],
    comparison: dict[str, object],
) -> dict[str, object]:
    """Build a compact JSON-safe comparison export object."""
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "comparison": comparison,
        "original": {
            "predicted_section": original_result["predicted_section"],
            "section_confidence": original_result["section_confidence"],
            "word_count": original_result["word_count"],
            "defense_score": original_result["defense_score"],
            "risk_level": original_result["risk_level"],
            "weak_areas": original_result["weak_areas"],
            "priority_fixes": original_result["priority_fixes"],
        },
        "revised": {
            "predicted_section": revised_result["predicted_section"],
            "section_confidence": revised_result["section_confidence"],
            "word_count": revised_result["word_count"],
            "defense_score": revised_result["defense_score"],
            "risk_level": revised_result["risk_level"],
            "weak_areas": revised_result["weak_areas"],
            "priority_fixes": revised_result["priority_fixes"],
        },
    }


def handle_revision_comparison_mode() -> None:
    """Render Before-and-After Revision Comparison Mode."""
    st.markdown("### Before-and-After Revision Comparison Mode")
    st.info(
        "Paste the original and revised versions of the same thesis section. "
        "SAGE-Review will compare semantic evidence coverage, readiness score, "
        "risk level, and remaining weak areas."
    )

    original_col, revised_col = st.columns(2)
    with original_col:
        original_text = st.text_area(
            "Original Thesis Section",
            height=340,
            placeholder="Paste the original version here...",
        )
    with revised_col:
        revised_text = st.text_area(
            "Revised Thesis Section",
            height=340,
            placeholder="Paste the revised version here...",
        )

    compare_clicked = st.button(
        "Compare Revisions",
        type="primary",
        use_container_width=True,
    )

    if not compare_clicked:
        return

    original_text = normalize_analysis_text(original_text)
    revised_text = normalize_analysis_text(revised_text)
    if not original_text or not revised_text:
        st.warning("Please paste both the original and revised thesis sections.")
        return

    try:
        with st.spinner("Analyzing and comparing thesis revisions using pretrained NLP models..."):
            original_result = analyze_revision_text(original_text)
            revised_result = analyze_revision_text(revised_text)
            for revision_result in (original_result, revised_result):
                generated_feedback = [
                    revision_result.get("priority_fixes", []),
                    revision_result.get("revision_suggestions", []),
                    revision_result.get("defense_questions", []),
                    revision_result.get("defense_notes", []),
                ]
                revision_result["responsible_ai_warnings"] = (
                    generate_responsible_ai_warnings(
                        revision_result.get("input_text", ""),
                        generated_feedback,
                    )
                )
                revision_result["priority_fixes"] = filter_unsafe_recommendations(
                    revision_result.get("priority_fixes", [])
                )
                revision_result["revision_suggestions"] = filter_unsafe_recommendations(
                    revision_result.get("revision_suggestions", [])
                )
                revision_result["defense_notes"] = filter_unsafe_recommendations(
                    revision_result.get("defense_notes", [])
                )
            comparison = compare_revision_results(original_result, revised_result)
            evidence_table = build_revision_evidence_comparison_table(
                original_result,
                revised_result,
            )
    except Exception as exc:
        st.error(
            "The revision comparison could not be completed. Check that the "
            "required models are available and that both text areas contain "
            "readable thesis text."
        )
        st.exception(exc)
        return

    st.markdown("### Revision Comparison Summary")
    metric_one, metric_two, metric_three, metric_four = st.columns(4)
    metric_one.metric("Original Score", f"{comparison['original_score']:.2f}/100")
    metric_two.metric("Revised Score", f"{comparison['revised_score']:.2f}/100")
    metric_three.metric(
        "Improvement",
        f"{comparison['score_improvement']:+.2f}",
    )
    metric_four.metric(
        "Risk Level Change",
        f"{comparison['original_risk']} -> {comparison['revised_risk']}",
    )

    if float(comparison["score_improvement"]) > 0:
        st.success(comparison["summary"])
    elif float(comparison["score_improvement"]) < 0:
        st.warning(comparison["summary"])
    else:
        st.info(comparison["summary"])

    revision_warnings = list(
        dict.fromkeys(
            list(original_result.get("responsible_ai_warnings", []))
            + list(revised_result.get("responsible_ai_warnings", []))
        )
    )
    if revision_warnings:
        st.markdown("### Responsible AI Warnings")
        for warning in revision_warnings:
            st.warning(str(warning))
        st.info(
            "SAGE-Review is a decision-support tool. It does not replace adviser "
            "or panel judgment."
        )

    area_left, area_right = st.columns(2)
    with area_left:
        st.markdown("#### Resolved Weak Areas")
        resolved = list(comparison["resolved_weak_areas"])
        if resolved:
            for area in resolved:
                st.success(area)
        else:
            st.info("No weak evidence areas were fully resolved yet.")

    with area_right:
        st.markdown("#### Remaining Weak Areas")
        remaining = list(comparison["remaining_weak_areas"])
        if remaining:
            for area in remaining:
                st.warning(area)
        else:
            st.success("No original weak evidence areas remain weak.")

    st.markdown("### Score Comparison")
    st.pyplot(plot_revision_score_comparison(comparison))

    st.markdown("### Side-by-Side Evidence Coverage")
    if not evidence_table.empty:
        st.dataframe(
            evidence_table.style.format(
                {
                    "Original Score": "{:.2f}",
                    "Revised Score": "{:.2f}",
                    "Score Change": "{:+.2f}",
                },
                na_rep="",
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Not enough evidence coverage data to display this table yet.")

    with st.expander("View Detailed Revision Feedback", expanded=False):
        detail_left, detail_right = st.columns(2)
        with detail_left:
            st.markdown("#### Original")
            st.write(f"Detected section: {original_result['predicted_section']}")
            st.write(f"Confidence: {original_result['section_confidence']:.2f}%")
            st.write("Priority fixes:")
            for fix in original_result["priority_fixes"][:3]:
                st.warning(str(fix.get("Issue", fix)))
        with detail_right:
            st.markdown("#### Revised")
            st.write(f"Detected section: {revised_result['predicted_section']}")
            st.write(f"Confidence: {revised_result['section_confidence']:.2f}%")
            st.write("Priority fixes:")
            for fix in revised_result["priority_fixes"][:3]:
                st.warning(str(fix.get("Issue", fix)))

    export_payload = _comparison_export_payload(
        original_result,
        revised_result,
        comparison,
    )
    export_csv = pd.DataFrame(
        [
            {
                "original_score": comparison["original_score"],
                "revised_score": comparison["revised_score"],
                "score_improvement": comparison["score_improvement"],
                "original_risk": comparison["original_risk"],
                "revised_risk": comparison["revised_risk"],
                "resolved_weak_areas": "; ".join(comparison["resolved_weak_areas"]),
                "remaining_weak_areas": "; ".join(comparison["remaining_weak_areas"]),
                "summary": comparison["summary"],
            }
        ]
    ).to_csv(index=False)

    st.markdown("### Export Comparison")
    export_left, export_right = st.columns(2)
    with export_left:
        st.download_button(
            "Download Comparison JSON",
            data=json.dumps(export_payload, indent=2, default=str),
            file_name="revision_comparison.json",
            mime="application/json",
            use_container_width=True,
        )
    with export_right:
        st.download_button(
            "Download Comparison CSV",
            data=export_csv,
            file_name="revision_comparison.csv",
            mime="text/csv",
            use_container_width=True,
        )


def handle_evaluation_dataset_mode() -> None:
    """Render Evaluation Dataset Mode for batch validation."""
    template_path = ensure_evaluation_dataset_template()

    st.markdown("### Evaluation Dataset Mode")
    st.info(
        "Upload a labeled CSV to compare SAGE-Review predictions with manual "
        "section labels, manual scores, and manually identified issues."
    )

    with st.container(border=True):
        st.markdown("#### Required CSV Columns")
        st.code(
            "sample_id, section_text, true_section, manual_score, manual_issues",
            language="text",
        )
        template_file = Path(template_path)
        st.download_button(
            "Download Evaluation Dataset Template",
            data=template_file.read_bytes(),
            file_name=template_file.name,
            mime="text/csv",
            use_container_width=True,
        )

    uploaded_csv = st.file_uploader(
        "Upload evaluation dataset CSV",
        type=["csv"],
    )

    if uploaded_csv is None:
        st.info("Upload a CSV file to begin evaluation.")
        return

    try:
        dataset_df = load_evaluation_dataset(uploaded_csv)
    except Exception as exc:
        st.error(f"Evaluation dataset could not be loaded: {exc}")
        return

    st.markdown("### Dataset Preview")
    st.dataframe(dataset_df.head(20), use_container_width=True, hide_index=True)
    st.caption(f"Loaded {len(dataset_df)} evaluation samples.")

    run_clicked = st.button(
        "Run Evaluation",
        type="primary",
        use_container_width=True,
    )

    if not run_clicked:
        return

    try:
        with st.spinner("Running evaluation using pretrained NLP models..."):
            results_df = run_evaluation_on_dataset(dataset_df)
            summary = generate_evaluation_summary(results_df)
            results_path = save_evaluation_results(results_df)
    except Exception as exc:
        st.error(
            "The evaluation could not be completed. Check the CSV content and "
            "confirm that the required NLP models are available."
        )
        st.exception(exc)
        return

    st.markdown("### Evaluation Metrics")
    metric_one, metric_two, metric_three, metric_four = st.columns(4)
    metric_one.metric(
        "Section Classification Accuracy",
        f"{summary['section_classification_accuracy']:.2f}%",
    )
    metric_two.metric(
        "Average Absolute Score Difference",
        f"{summary['average_absolute_score_difference']:.2f}",
    )
    metric_three.metric(
        "Issue Detection Agreement",
        f"{summary['issue_detection_agreement']:.2f}%",
    )
    metric_four.metric(
        "Average Processing Time",
        f"{summary['average_processing_time']:.2f}s",
    )

    st.markdown("### Evaluation Results")
    st.dataframe(results_df, use_container_width=True, hide_index=True)

    st.markdown("### Evaluation Charts")
    show_evaluation_charts(results_df)

    results_file = Path(results_path)
    st.download_button(
        "Download Evaluation Results CSV",
        data=results_file.read_bytes(),
        file_name=results_file.name,
        mime="text/csv",
        use_container_width=True,
    )
    st.success("Evaluation results saved successfully.")


def show_single_section_result(result: dict[str, object]) -> None:
    """Render the existing single-section analysis outputs."""
    st.markdown("### Initial Text Summary")
    col_word_count, col_character_count = st.columns(2)
    col_word_count.metric("Word Count", result["word_count"])
    col_character_count.metric("Character Count", result["character_count"])

    st.markdown("### AI/NLP Section Classification")
    col_section, col_confidence = st.columns(2)
    col_section.metric("Detected Section", result["predicted_section"])
    col_confidence.metric("Confidence", f"{float(result['section_confidence']):.2f}%")

    score_table = pd.DataFrame(result["section_scores"])
    if not score_table.empty:
        score_table["score"] = score_table["score"].map(lambda score: f"{score * 100:.2f}%")
        score_table = score_table.rename(
            columns={"label": "Section Label", "score": "Confidence Score"}
        )
        st.dataframe(score_table, use_container_width=True, hide_index=True)

    st.markdown("### Semantic Evidence Coverage")
    coverage_table = pd.DataFrame(result["evidence_coverage"])
    if not coverage_table.empty:
        show_evidence_summary(coverage_table)
        styled_coverage_table = coverage_table.style.apply(
            style_coverage_table,
            axis=1,
        ).format({"Similarity Score": "{:.2f}"})
        st.dataframe(styled_coverage_table, use_container_width=True, hide_index=True)
        st.pyplot(plot_evidence_coverage_chart(result["evidence_coverage"]))
    else:
        st.info("Not enough data to display this chart yet.")

    show_defense_readiness_score(result)
    show_responsible_ai_warnings(result)
    show_feedback_section(result)

    with st.container(border=True):
        st.markdown("#### Preview")
        st.write(str(result["text_preview"])[:500])


def show_full_manuscript_result(
    result: dict[str, object],
    pdf_path: str | None = None,
    csv_path: str | None = None,
) -> None:
    """Render full manuscript output using a cleaner tabbed dashboard."""
    extracted_names = list(result["extracted_sections"].keys())
    sections_needing_review = list(
        dict.fromkeys(
            list(result["sections_needing_review"])
            + list(result["missing_major_sections"])
        )
    )

    tab_summary, tab_sections, tab_alignment, tab_charts, tab_export = st.tabs(
        [
            "Executive Summary",
            "Section Review",
            "Semantic Alignment",
            "Charts",
            "Export Results",
        ]
    )

    with tab_summary:
        st.markdown("### Executive Summary")
        score_col, risk_col, confidence_col = st.columns(3)
        score_label = (
            "Preliminary Score"
            if result["analysis_confidence"] == "Partial"
            else "Overall Score"
        )
        score_col.metric(score_label, f"{result['overall_score']:.2f}/100")
        risk_col.metric("Risk Level", format_risk_label(result["overall_risk_level"]))
        confidence_col.metric("Analysis Confidence", result["analysis_confidence"])

        strong_sections = [
            str(section["Section Name"])
            for section in result["section_results"]
            if float(section["Defense Score"]) >= 80
        ][:3]
        weak_sections = [
            str(section["Section Name"])
            for section in sorted(
                result["section_results"],
                key=lambda section: float(section["Defense Score"]),
            )
            if float(section["Defense Score"]) < 70
        ][:3]

        if result["analysis_confidence"] == "Partial":
            summary_text = (
                "Your manuscript was analyzed, but some results need manual "
                "checking because one or more major sections were not confidently "
                "extracted."
            )
        else:
            summary_text = (
                "Your manuscript was successfully analyzed across the extracted "
                "major sections."
            )
        st.info(summary_text)

        st.markdown("#### Main Strengths")
        if strong_sections:
            for section in strong_sections:
                st.success(section)
        else:
            st.info("No clearly strong section was detected yet.")

        st.markdown("#### Main Concerns")
        concerns = list(result["main_issues"])
        if weak_sections:
            concerns.append("Sections needing targeted revision: " + ", ".join(weak_sections))
        if concerns:
            for concern in concerns[:4]:
                st.warning(concern)
        else:
            st.success("No major concern was detected in the extracted sections.")

        st.markdown("#### Recommended Next Action")
        if "Objectives of the Study" in sections_needing_review:
            st.warning(
                "Fix or clearly label the Objectives of the Study heading, then "
                "run the analysis again."
            )
        elif weak_sections:
            st.warning(
                "Revise the lowest-scoring sections first, then rerun the full "
                "manuscript analysis."
            )
        else:
            st.success(
                "Review the generated defense questions and prepare concise "
                "evidence-based answers."
            )

        show_responsible_ai_warnings(result)

        st.markdown("### Full Manuscript Extraction Summary")
        with st.container(border=True):
            st.write(f"Extracted sections: {len(extracted_names)}")
            st.write("Detected sections: " + (", ".join(extracted_names) or "None"))
            if sections_needing_review:
                st.warning("Sections needing review: " + ", ".join(sections_needing_review))
            else:
                st.success("Sections needing review: None")

        if "Objectives of the Study" in sections_needing_review:
            st.info(
                "The system did not confidently extract the Objectives of the Study "
                "section. This may mean the section is missing, merged with another "
                "section, or written under a different heading such as Statement of "
                "the Problem, Specific Objectives, or Research Questions."
            )

        st.info(
            "Note: Full manuscript analysis depends on correct section extraction. "
            "If a section is not detected, check whether the heading is written "
            "clearly. You may also use Single Section Mode to analyze that section "
            "separately."
        )

    with tab_sections:
        st.markdown("### Section Review")
        if result["section_results"]:
            st.dataframe(
                pd.DataFrame(result["section_results"]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.error("No analyzable thesis sections were extracted.")

        for section_result in result["section_details"]:
            with st.expander(str(section_result["section_name"]), expanded=False):
                st.markdown(f"#### {section_result['section_name']}")
                metric_left, metric_mid, metric_right = st.columns(3)
                metric_left.metric("Word Count", section_result["word_count"])
                metric_mid.metric(
                    "Readiness Score",
                    f"{float(section_result['defense_score']):.2f}/100",
                )
                metric_right.metric("Risk Level", format_risk_label(section_result["risk_level"]))

                st.metric(
                    "Classification Confidence",
                    f"{float(section_result['section_confidence']):.2f}%",
                )

                st.markdown("#### What This Means")
                score_value = float(section_result["defense_score"])
                if score_value >= 80:
                    st.success(section_result["plain_language_diagnosis"])
                elif score_value >= 60:
                    st.warning(section_result["plain_language_diagnosis"])
                else:
                    st.error(section_result["plain_language_diagnosis"])

                section_warnings = list(section_result.get("responsible_ai_warnings", []))
                if section_warnings:
                    st.markdown("#### Responsible AI Notes")
                    for warning in section_warnings:
                        st.warning(str(warning))

                strong_areas = section_result["strong_areas"][:3]
                weak_areas = section_result["needs_improvement_areas"][:3]

                area_left, area_right = st.columns(2)
                with area_left:
                    st.markdown("#### Strong Areas")
                    if strong_areas:
                        for area in strong_areas:
                            st.success(area)
                    else:
                        st.info("No strong area detected yet.")

                with area_right:
                    st.markdown("#### Needs Improvement")
                    if weak_areas:
                        for area in weak_areas:
                            st.warning(area)
                    else:
                        st.success("No major expected evidence gap detected.")

                st.markdown("#### What To Fix Next")
                for recommendation in section_result["section_recommendations"][:2]:
                    st.write(f"- {recommendation}")

                st.markdown("#### Defense Questions To Prepare")
                for question in section_result["defense_questions"][:3]:
                    st.write(f"- {question}")

                with st.expander("View technical evidence scores", expanded=False):
                    coverage_table = pd.DataFrame(section_result["evidence_coverage"])
                    if not coverage_table.empty:
                        relevant_coverage = coverage_table[
                            coverage_table["Evidence Area"].isin(section_result["expected_areas"])
                        ]
                        st.dataframe(
                            relevant_coverage if not relevant_coverage.empty else coverage_table,
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("Not enough data to display this table yet.")

    with tab_alignment:
        st.markdown("### Semantic Alignment")
        st.markdown(
            "This view checks whether the objectives, methodology, results, and "
            "conclusion appear connected in meaning."
        )
        if not result["objectives_confident"]:
            st.info(
                "Semantic alignment could not be fully computed because Objectives "
                "of the Study was not confidently extracted."
            )

        alignment_table = pd.DataFrame(result["alignment_results"])
        if not alignment_table.empty:
            st.dataframe(alignment_table, use_container_width=True, hide_index=True)
        else:
            st.info("Not enough data to display this table yet.")

    with tab_charts:
        st.markdown("### Dashboard Charts")
        if result["section_results"]:
            st.pyplot(plot_section_scores_chart(result["section_results"]))
        else:
            st.info("Not enough data to display this chart yet.")

        if result["alignment_results"]:
            st.pyplot(plot_alignment_matrix_chart(result["alignment_results"]))
        else:
            st.info("Not enough data to display this chart yet.")

        evidence_summary = list(result.get("manuscript_evidence_summary", []))
        if evidence_summary:
            st.pyplot(plot_evidence_coverage_chart(evidence_summary))
            if all(item["Coverage Level"] == "Weak" for item in evidence_summary):
                st.info(
                    "Low semantic scores may mean the selected section does not "
                    "normally contain these evidence types, or the section "
                    "extraction may be incorrect."
                )
        else:
            st.info("Not enough data to display this chart yet.")

    with tab_export:
        st.markdown("### Export Results")
        if pdf_path and csv_path:
            show_export_buttons(pdf_path, csv_path)
        else:
            st.info(
                "Export files will be available after report generation finishes."
            )


def handle_single_section_mode(thesis_text: str) -> None:
    """Run and display Single Section Mode."""
    clean_text = normalize_analysis_text(thesis_text)
    analysis_start = time.perf_counter()
    with st.spinner("Analyzing thesis section using pretrained NLP model..."):
        result = analyze_text_section(clean_text)
        result.update(
            {
                "analysis_mode": "Single Section Mode",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processing_time_seconds": round(
                    time.perf_counter() - analysis_start,
                    2,
                ),
            }
        )

    show_single_section_result(result)
    csv_path = save_review_history(result)
    pdf_path = generate_pdf_report(result)
    show_expert_validation_form(result, "single_section")
    st.info(f"Processing Time: {result['processing_time_seconds']:.2f} seconds")
    st.success("Review report generated successfully.")
    show_export_buttons(pdf_path, csv_path)


def handle_full_manuscript_mode(thesis_text: str) -> None:
    """Run and display Full Manuscript Mode."""
    clean_text = normalize_analysis_text(thesis_text)
    analysis_start = time.perf_counter()
    total_stats = get_basic_text_stats(clean_text)

    with st.spinner("Extracting and analyzing manuscript sections using pretrained NLP models..."):
        full_result = analyze_full_manuscript(clean_text)
        processing_time_seconds = round(time.perf_counter() - analysis_start, 2)

    if not full_result["section_details"]:
        st.error(
            "No major thesis sections were extracted. Check that the manuscript "
            "uses recognizable headings such as Methodology or Results and Discussion."
        )
        return

    all_top_weak = []
    responsible_ai_warnings = []
    for section_result in full_result["section_details"]:
        all_top_weak.extend(section_result["top_weak_areas"])
        responsible_ai_warnings.extend(
            list(section_result.get("responsible_ai_warnings", []))
        )
    top_weak_areas = list(dict.fromkeys(all_top_weak))[:5]
    responsible_ai_warnings = list(dict.fromkeys(responsible_ai_warnings))
    top_weak_sections = [
        str(item["Section Name"])
        for item in sorted(
            full_result["section_results"],
            key=lambda row: float(row["Defense Score"]),
        )[:3]
    ]
    top_weak_alignment_pairs = [
        str(item["Section Pair"])
        for item in full_result["alignment_results"]
        if item["Alignment Level"] in {"Weak Alignment", "Missing Section"}
    ][:5]
    if full_result["analysis_confidence"] == "Partial":
        overall_summary = (
            "The system analyzed the extracted sections and generated a "
            "preliminary defense readiness score. Some results may need manual "
            "checking because one or more major sections were not confidently "
            "extracted."
        )
    else:
        overall_summary = (
            "The system analyzed the extracted sections and generated an "
            "overall defense readiness score based on section-level evidence "
            "coverage and semantic alignment."
        )

    result = {
        "analysis_mode": "Full Manuscript Mode",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input_text": clean_text,
        "text_preview": clean_text[:1000],
        "predicted_section": "Full Manuscript",
        "section_confidence": "",
        "section_scores": [],
        "word_count": total_stats["word_count"],
        "character_count": total_stats["character_count"],
        "defense_score": full_result["overall_score"],
        "risk_level": full_result["overall_risk_level"],
        "strong_evidence_count": sum(
            int(section["strong_evidence_count"])
            for section in full_result["section_details"]
        ),
        "moderate_evidence_count": sum(
            int(section["moderate_evidence_count"])
            for section in full_result["section_details"]
        ),
        "weak_evidence_count": sum(
            int(section["weak_evidence_count"])
            for section in full_result["section_details"]
        ),
        "top_weak_areas": top_weak_areas,
        "processing_time_seconds": processing_time_seconds,
        "overall_score": full_result["overall_score"],
        "overall_risk_level": full_result["overall_risk_level"],
        "overall_summary": overall_summary,
        "analysis_confidence": full_result["analysis_confidence"],
        "main_issues": full_result["main_issues"],
        "responsible_ai_warnings": responsible_ai_warnings,
        "alignment_results": full_result["alignment_results"],
        "raw_alignment_results": full_result["raw_alignment_results"],
        "alignment_deduction": full_result["alignment_deduction"],
        "weak_alignment_count": full_result["weak_alignment_count"],
        "missing_alignment_count": full_result["missing_alignment_count"],
        "objectives_confident": full_result["objectives_confident"],
        "manuscript_evidence_summary": full_result["manuscript_evidence_summary"],
        "top_weak_sections": top_weak_sections,
        "top_weak_alignment_pairs": top_weak_alignment_pairs,
        "overall_defense_notes": [
            "Prepare clear explanations that connect objectives, methodology, results, and conclusion.",
            "Review weak alignment pairs before defense and add linking statements where needed.",
            "Use section-specific evidence tables to support answers to panel questions.",
        ],
        "section_results": full_result["section_results"],
        "section_details": full_result["section_details"],
        "extracted_sections": full_result["extracted_sections"],
        "extraction_status": full_result["extraction_status"],
        "sections_needing_review": full_result["sections_needing_review"],
        "missing_major_sections": full_result["missing_major_sections"],
    }

    csv_path = save_review_history(result)
    pdf_path = generate_pdf_report(result)
    show_full_manuscript_result(result, pdf_path, csv_path)
    show_expert_validation_form(result, "full_manuscript")
    st.info(f"Processing Time: {processing_time_seconds:.2f} seconds")
    st.success("Full manuscript review report generated successfully.")


def main() -> None:
    """Render the SAGE-Review Streamlit application."""
    st.set_page_config(page_title="SAGE-Review", layout="wide")

    st.title("SAGE-Review")
    st.subheader(
        "Intelligent Thesis Defense Readiness and Manuscript Evaluation System"
    )
    st.markdown(
        """
        SAGE-Review analyzes thesis manuscript sections using AI/NLP semantic
        analysis, explainable scoring, structured feedback, and report export.
        """
    )
    st.caption(
        "SAGE-Review is a decision-support tool. It does not replace adviser "
        "or panel judgment."
    )

    analysis_mode = st.radio(
        "Analysis Mode:",
        [
            "Single Section Mode",
            "Full Manuscript Mode",
            "Evaluation Dataset Mode",
            "Before-and-After Revision Mode",
            "Validation Results Summary",
        ],
        horizontal=True,
    )

    if analysis_mode == "Validation Results Summary":
        handle_validation_results_summary_mode()
        return

    if analysis_mode == "Evaluation Dataset Mode":
        handle_evaluation_dataset_mode()
        return

    if analysis_mode == "Before-and-After Revision Mode":
        handle_revision_comparison_mode()
        return

    text_area_label = (
        "Paste a thesis manuscript section below:"
        if analysis_mode == "Single Section Mode"
        else "Paste full thesis manuscript or large chapter text here:"
    )

    with st.container(border=True):
        st.markdown("### Thesis Input")
        uploaded_file = st.file_uploader(
            "Upload thesis document (.txt, .docx, .pdf)",
            type=["txt", "docx", "pdf"],
        )
        uploaded_text = ""

        if uploaded_file is not None:
            try:
                uploaded_text = normalize_analysis_text(
                    extract_text_from_uploaded_file(uploaded_file)
                )
            except Exception as exc:
                st.error(f"File text extraction failed: {exc}")
                uploaded_text = ""

            if uploaded_text.strip():
                uploaded_stats = get_basic_text_stats(uploaded_text)
                st.success(f"Uploaded file: {uploaded_file.name}")
                upload_col_words, upload_col_chars = st.columns(2)
                upload_col_words.metric(
                    "Extracted Word Count",
                    uploaded_stats["word_count"],
                )
                upload_col_chars.metric(
                    "Extracted Character Count",
                    uploaded_stats["character_count"],
                )
                if int(uploaded_stats["word_count"]) > 3000:
                    st.warning(
                        "This uploaded document appears to be a full manuscript. "
                        "Full Manuscript Mode is recommended."
                    )
                with st.expander("Uploaded Text Preview", expanded=False):
                    st.write(uploaded_text[:1000])
                thesis_text = uploaded_text
            else:
                thesis_text = ""
                st.warning("No readable text was extracted from the uploaded file.")
        else:
            thesis_text = st.text_area(
                text_area_label,
                height=320,
                placeholder=(
                    "Paste an abstract, chapter, or full manuscript text here..."
                ),
            )

        analyze_clicked = st.button(
            "Analyze Thesis Section"
            if analysis_mode == "Single Section Mode"
            else "Analyze Full Manuscript",
            type="primary",
            use_container_width=True,
        )

    thesis_text = normalize_analysis_text(thesis_text)

    if analysis_mode == "Single Section Mode" and len(thesis_text.split()) > 3000:
        st.warning(
            "This text is very long and may contain multiple sections. Use Full "
            "Manuscript Mode for better results."
        )

    if analyze_clicked:
        if not thesis_text:
            st.warning("Please paste thesis text before running the analysis.")
            return

        try:
            if analysis_mode == "Single Section Mode":
                handle_single_section_mode(thesis_text)
            else:
                handle_full_manuscript_mode(thesis_text)
        except Exception as exc:
            st.error(
                "The analysis could not be completed. Please check that the "
                "required packages are installed and that the Hugging Face "
                "models can be downloaded."
            )
            st.exception(exc)


if __name__ == "__main__":
    main()
