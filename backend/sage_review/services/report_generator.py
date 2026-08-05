"""CSV history logging and PDF report generation for SAGE-Review."""

import csv
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


HISTORY_FIELDS = [
    "timestamp",
    "predicted_section",
    "section_confidence",
    "word_count",
    "character_count",
    "defense_score",
    "risk_level",
    "strong_evidence_count",
    "moderate_evidence_count",
    "weak_evidence_count",
    "top_weak_areas",
    "processing_time_seconds",
]


def save_review_history(
    result: dict[str, object],
    csv_path: str | Path | None = None,
) -> str:
    """Append one analysis summary row to the review history CSV."""
    output_path = Path(csv_path) if csv_path else PROJECT_ROOT / "data" / "review_history.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output_path.exists()

    row = {field: result.get(field, "") for field in HISTORY_FIELDS}
    if isinstance(row["top_weak_areas"], list):
        row["top_weak_areas"] = ", ".join(str(area) for area in row["top_weak_areas"])

    with output_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HISTORY_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    return str(output_path)


def _styles() -> dict[str, ParagraphStyle]:
    """Create readable PDF paragraph styles."""
    base_styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "SageTitle",
            parent=base_styles["Title"],
            fontSize=16,
            leading=20,
            spaceAfter=14,
        ),
        "heading": ParagraphStyle(
            "SageHeading",
            parent=base_styles["Heading2"],
            fontSize=12,
            leading=15,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "SageBody",
            parent=base_styles["BodyText"],
            fontSize=9,
            leading=12,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "SageSmall",
            parent=base_styles["BodyText"],
            fontSize=8,
            leading=10,
        ),
    }


def _paragraph(text: object, style: ParagraphStyle) -> Paragraph:
    """Return a wrapped ReportLab paragraph with safe string conversion."""
    safe_text = str(text).encode("latin-1", "replace").decode("latin-1")
    clean_text = escape(safe_text).replace("\n", "<br/>")
    return Paragraph(clean_text, style)


def _add_heading(story: list[object], text: str, styles: dict[str, ParagraphStyle]) -> None:
    """Append a section heading to the PDF story."""
    story.append(_paragraph(text, styles["heading"]))


def _add_key_value_table(
    story: list[object],
    rows: list[tuple[str, object]],
    styles: dict[str, ParagraphStyle],
) -> None:
    """Append a two-column wrapped key/value table."""
    table_data = [
        [_paragraph(label, styles["small"]), _paragraph(value, styles["small"])]
        for label, value in rows
    ]
    table = Table(table_data, colWidths=[1.9 * inch, 4.6 * inch], repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 8))


def _add_table(
    story: list[object],
    headers: list[str],
    rows: list[dict[str, object]],
    styles: dict[str, ParagraphStyle],
    col_widths: list[float],
) -> None:
    """Append a wrapped table if rows exist."""
    if not rows:
        story.append(_paragraph("None recorded.", styles["body"]))
        return

    table_data = [[_paragraph(header, styles["small"]) for header in headers]]
    for row in rows:
        table_data.append(
            [_paragraph(row.get(header, ""), styles["small"]) for header in headers]
        )

    table = Table(table_data, colWidths=col_widths, repeatRows=1, splitByRow=True)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9ECEF")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 8))


def _add_bullet_list(
    story: list[object],
    items: list[object],
    styles: dict[str, ParagraphStyle],
) -> None:
    """Append a simple wrapped bullet list."""
    if not items:
        story.append(_paragraph("None recorded.", styles["body"]))
        return

    for item in items:
        story.append(_paragraph(f"- {item}", styles["body"]))
    story.append(Spacer(1, 6))


def _preferred_feedback(result: dict[str, object], dynamic_key: str, fallback_key: str):
    """Use validated Gemini feedback when active, otherwise template feedback."""
    if result.get("feedback_mode") == "Gemini-grounded" and result.get(dynamic_key):
        return result.get(dynamic_key)
    return result.get(fallback_key)


def generate_pdf_report(
    result: dict[str, object],
    output_dir: str | Path | None = None,
) -> str:
    """Generate a readable PDF report from a complete analysis result."""
    output_path = Path(output_dir) if output_dir else PROJECT_ROOT / "reports"
    output_path.mkdir(parents=True, exist_ok=True)

    filename_timestamp = str(result["timestamp"]).replace("-", "").replace(":", "")
    filename_timestamp = filename_timestamp.replace(" ", "_")
    unique_suffix = uuid4().hex[:8]
    pdf_path = output_path / f"SAGE_Review_Report_{filename_timestamp}_{unique_suffix}.pdf"

    styles = _styles()
    story: list[object] = []
    document = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    story.append(
        _paragraph(
            "SAGE-Review Explainable Thesis Defense Readiness Report",
            styles["title"],
        )
    )

    if result.get("analysis_mode") == "Full Manuscript Mode":
        _add_heading(story, "1. Full Manuscript Summary", styles)
        _add_key_value_table(
            story,
            [
                ("Date/time", result.get("timestamp", "")),
                ("Word count", result.get("word_count", "")),
                ("Character count", result.get("character_count", "")),
                ("Extracted sections", len(result.get("extracted_sections", {}))),
                ("Overall defense readiness score", result.get("overall_score", "")),
                ("Overall risk level", result.get("overall_risk_level", "")),
                ("Missing major sections", ", ".join(result.get("missing_major_sections", []))),
                ("Processing time", f"{result.get('processing_time_seconds', '')} seconds"),
            ],
            styles,
        )
        story.append(_paragraph(result.get("overall_summary", ""), styles["body"]))
        story.append(
            _paragraph(
                "The semantic alignment score measures how closely major thesis "
                "sections are related in meaning based on sentence-transformer "
                "embeddings. It is used to identify possible gaps between "
                "objectives, methodology, results, and conclusion.",
                styles["body"],
            )
        )

        _add_heading(story, "2. Semantic Alignment Analysis", styles)
        _add_key_value_table(
            story,
            [
                ("Alignment deduction", result.get("alignment_deduction", "")),
                ("Weak alignment pairs", result.get("weak_alignment_count", "")),
                ("Missing alignment pairs", result.get("missing_alignment_count", "")),
            ],
            styles,
        )
        _add_table(
            story,
            [
                "Section Pair",
                "Similarity Score",
                "Alignment Level",
                "Risk",
                "Interpretation",
            ],
            list(result.get("alignment_results", [])),
            styles,
            [1.65 * inch, 0.75 * inch, 1.05 * inch, 0.6 * inch, 2.45 * inch],
        )

        _add_heading(story, "3. Weak Areas and Preparation Notes", styles)
        story.append(_paragraph("Top Weak Sections", styles["heading"]))
        explained_weak_sections = list(result.get("top_weak_sections_explained", []))
        if explained_weak_sections:
            _add_table(
                story,
                [
                    "section",
                    "score",
                    "risk_level",
                    "weak_criteria",
                    "reason",
                    "next_action",
                ],
                explained_weak_sections,
                styles,
                [
                    0.9 * inch,
                    0.45 * inch,
                    0.6 * inch,
                    1.25 * inch,
                    1.75 * inch,
                    1.55 * inch,
                ],
            )
        else:
            _add_bullet_list(story, list(result.get("top_weak_sections", [])), styles)
        story.append(_paragraph("Main Issues", styles["heading"]))
        explained_issues = list(result.get("main_issues_explained", []))
        if explained_issues:
            _add_table(
                story,
                [
                    "issue_type",
                    "title",
                    "affected_sections",
                    "severity",
                    "reason",
                    "next_action",
                ],
                explained_issues,
                styles,
                [
                    0.85 * inch,
                    1.05 * inch,
                    1.05 * inch,
                    0.55 * inch,
                    1.65 * inch,
                    1.4 * inch,
                ],
            )
        else:
            _add_bullet_list(story, list(result.get("main_issues", [])), styles)
        story.append(_paragraph("Top Weak Alignment Pairs", styles["heading"]))
        explained_alignments = list(result.get("alignment_weaknesses_explained", []))
        if explained_alignments:
            _add_table(
                story,
                ["section_pair", "similarity", "risk", "reason", "next_action"],
                explained_alignments,
                styles,
                [1.3 * inch, 0.55 * inch, 0.5 * inch, 2.0 * inch, 2.15 * inch],
            )
        else:
            _add_bullet_list(story, list(result.get("top_weak_alignment_pairs", [])), styles)
        story.append(_paragraph("Recommended Fix Order", styles["heading"]))
        _add_table(
            story,
            ["priority", "section", "fix", "why"],
            list(result.get("recommended_fix_order", [])),
            styles,
            [0.5 * inch, 1.0 * inch, 2.3 * inch, 2.7 * inch],
        )
        story.append(_paragraph("Recommended Overall Defense Preparation Notes", styles["heading"]))
        _add_bullet_list(story, list(result.get("overall_defense_notes", [])), styles)

        _add_heading(story, "4. Section-by-Section Score Table", styles)
        _add_table(
            story,
            [
                "Section Name",
                "Predicted Section",
                "Word Count",
                "Defense Score",
                "Risk Level",
                "Weak Evidence Count",
                "Top Weak Areas",
            ],
            list(result.get("section_results", [])),
            styles,
            [
                1.0 * inch,
                1.1 * inch,
                0.65 * inch,
                0.75 * inch,
                0.7 * inch,
                0.75 * inch,
                1.55 * inch,
            ],
        )

        _add_heading(story, "5. Detailed Findings by Section", styles)
        for section_result in result.get("section_details", []):
            story.append(_paragraph(str(section_result.get("section_name", "")), styles["heading"]))
            _add_key_value_table(
                story,
                [
                    ("Predicted section", section_result.get("predicted_section", "")),
                    ("Classification confidence", section_result.get("section_confidence", "")),
                    ("Word count", section_result.get("word_count", "")),
                    ("Defense score", section_result.get("defense_score", "")),
                    ("Risk level", section_result.get("risk_level", "")),
                ],
                styles,
            )
            story.append(_paragraph(section_result.get("score_summary", ""), styles["body"]))

            diagnosis = _preferred_feedback(
                section_result,
                "dynamic_diagnosis",
                "plain_language_diagnosis",
            )
            if diagnosis:
                story.append(_paragraph("Diagnosis", styles["heading"]))
                story.append(_paragraph(diagnosis, styles["body"]))

            next_action = _preferred_feedback(
                section_result,
                "dynamic_next_best_action",
                "next_best_action",
            )
            if next_action:
                story.append(_paragraph("Next Best Action", styles["heading"]))
                story.append(_paragraph(next_action, styles["body"]))

            panel_risk = _preferred_feedback(
                section_result,
                "dynamic_panel_risk",
                "panel_risk",
            )
            if panel_risk:
                story.append(_paragraph("Likely Panel Risk", styles["heading"]))
                story.append(_paragraph(panel_risk, styles["body"]))

            story.append(_paragraph("Evidence Coverage", styles["heading"]))
            _add_table(
                story,
                ["Evidence Area", "Similarity Score", "Coverage Level", "Interpretation"],
                list(section_result.get("evidence_coverage", [])),
                styles,
                [1.55 * inch, 0.8 * inch, 0.9 * inch, 3.25 * inch],
            )

            story.append(_paragraph("Strengths", styles["heading"]))
            _add_bullet_list(story, list(section_result.get("strengths", [])), styles)

            story.append(_paragraph("Deductions", styles["heading"]))
            _add_table(
                story,
                ["Evidence Area", "Deduction", "Reason"],
                list(section_result.get("deductions", [])),
                styles,
                [1.8 * inch, 0.8 * inch, 3.9 * inch],
            )

            story.append(_paragraph("Priority Fixes", styles["heading"]))
            _add_table(
                story,
                ["Priority", "Issue", "Why It Matters", "Suggested Fix"],
                list(section_result.get("priority_fixes", [])),
                styles,
                [0.65 * inch, 1.35 * inch, 2.2 * inch, 2.3 * inch],
            )

            if section_result.get("feedback_mode") == "Gemini-grounded":
                story.append(_paragraph("Suggested Revision Wording", styles["heading"]))
                _add_bullet_list(
                    story,
                    list(section_result.get("dynamic_suggested_revision_wording", [])),
                    styles,
                )
            else:
                story.append(_paragraph("Revision Suggestions", styles["heading"]))
                _add_bullet_list(story, list(section_result.get("revision_suggestions", [])), styles)
                story.append(_paragraph("Suggested Revision Wording", styles["heading"]))
                _add_bullet_list(story, list(section_result.get("suggested_revision_wording", [])), styles)

            story.append(_paragraph("Recommended Defense Questions", styles["heading"]))
            _add_bullet_list(
                story,
                list(
                    _preferred_feedback(
                        section_result,
                        "dynamic_defense_questions",
                        "defense_questions",
                    )
                    or []
                ),
                styles,
            )

            story.append(_paragraph("Text Preview", styles["heading"]))
            story.append(_paragraph(str(section_result.get("text_preview", ""))[:1000], styles["body"]))

        document.build(story)
        return str(pdf_path)

    _add_heading(story, "1. Basic Information", styles)
    _add_key_value_table(
        story,
        [
            ("Date/time", result.get("timestamp", "")),
            ("Word count", result.get("word_count", "")),
            ("Character count", result.get("character_count", "")),
            ("Detected section", result.get("predicted_section", "")),
            ("Section confidence", result.get("section_confidence", "")),
            ("Defense readiness score", result.get("defense_score", "")),
            ("Risk level", result.get("risk_level", "")),
            ("Processing time", f"{result.get('processing_time_seconds', '')} seconds"),
        ],
        styles,
    )

    _add_heading(story, "2. Score Summary", styles)
    story.append(_paragraph(result.get("score_summary", ""), styles["body"]))
    diagnosis = _preferred_feedback(result, "dynamic_diagnosis", "plain_language_diagnosis")
    if diagnosis:
        story.append(_paragraph("Diagnosis", styles["heading"]))
        story.append(_paragraph(diagnosis, styles["body"]))
    next_action = _preferred_feedback(result, "dynamic_next_best_action", "next_best_action")
    if next_action:
        story.append(_paragraph("Next Best Action", styles["heading"]))
        story.append(_paragraph(next_action, styles["body"]))
    panel_risk = _preferred_feedback(result, "dynamic_panel_risk", "panel_risk")
    if panel_risk:
        story.append(_paragraph("Likely Panel Risk", styles["heading"]))
        story.append(_paragraph(panel_risk, styles["body"]))
    story.append(_paragraph("Strengths", styles["heading"]))
    _add_bullet_list(story, list(result.get("strengths", [])), styles)
    story.append(_paragraph("Deductions", styles["heading"]))
    _add_table(
        story,
        ["Evidence Area", "Deduction", "Reason"],
        list(result.get("deductions", [])),
        styles,
        [1.8 * inch, 0.8 * inch, 3.9 * inch],
    )

    _add_heading(story, "3. Semantic Evidence Coverage", styles)
    _add_table(
        story,
        ["Evidence Area", "Similarity Score", "Coverage Level", "Interpretation"],
        list(result.get("evidence_coverage", [])),
        styles,
        [1.55 * inch, 0.8 * inch, 0.9 * inch, 3.25 * inch],
    )

    _add_heading(story, "4. Priority Fixes", styles)
    _add_table(
        story,
        ["Priority", "Issue", "Why It Matters", "Suggested Fix"],
        list(result.get("priority_fixes", [])),
        styles,
        [0.65 * inch, 1.35 * inch, 2.2 * inch, 2.3 * inch],
    )

    if result.get("feedback_mode") == "Gemini-grounded":
        _add_heading(story, "5. Suggested Revision Wording", styles)
        _add_bullet_list(
            story,
            list(result.get("dynamic_suggested_revision_wording", [])),
            styles,
        )
    else:
        _add_heading(story, "5. Revision Suggestions", styles)
        _add_bullet_list(story, list(result.get("revision_suggestions", [])), styles)
        _add_heading(story, "Suggested Revision Wording", styles)
        _add_bullet_list(story, list(result.get("suggested_revision_wording", [])), styles)

    _add_heading(story, "6. Safer Academic Wording Suggestions", styles)
    _add_table(
        story,
        ["Risky Wording", "Why Risky", "Safer Alternative"],
        list(result.get("safer_wording_suggestions", [])),
        styles,
        [1.1 * inch, 2.7 * inch, 2.7 * inch],
    )

    _add_heading(story, "7. Recommended Defense Questions", styles)
    _add_bullet_list(
        story,
        list(
            _preferred_feedback(
                result,
                "dynamic_defense_questions",
                "defense_questions",
            )
            or []
        ),
        styles,
    )

    _add_heading(story, "8. Defense Preparation Notes", styles)
    _add_bullet_list(story, list(result.get("defense_notes", [])), styles)

    _add_heading(story, "9. Text Preview", styles)
    story.append(_paragraph(str(result.get("text_preview", ""))[:1000], styles["body"]))

    document.build(story)
    return str(pdf_path)
