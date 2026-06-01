"""FastAPI backend for SAGE-Review.

The backend reuses the existing SAGE-Review Python analysis modules and exposes
them through HTTP endpoints for a React frontend.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
import re
import time
from typing import Any
import hashlib

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]

from backend.sage_review.core.ai_analyzer import (
    analyze_evidence_coverage,
    classify_section_zero_shot,
)
from backend.sage_review.core.ai_scoring import compute_defense_readiness_score
from backend.sage_review.core.alignment_analyzer import generate_alignment_matrix
from backend.sage_review.core.document_loader import extract_text_from_uploaded_file
from backend.sage_review.core.evidence_analyzer import normalize_section_name
from backend.sage_review.services.evaluation_engine import (
    generate_evaluation_summary,
    load_evaluation_dataset,
    run_evaluation_on_dataset,
    save_evaluation_results,
)
from backend.sage_review.core.highlight_analyzer import analyze_contextual_highlights
try:
    from backend.sage_review.services.gemini_feedback_generator import (
        generate_gemini_feedback,
    )
except (ImportError, ModuleNotFoundError):
    def generate_gemini_feedback(**kwargs):  # type: ignore[misc]
        return {"feedback_mode": "Template fallback"}
from backend.sage_review.services.feedback_generator import (
    generate_defense_notes,
    generate_defense_questions,
    generate_plain_language_diagnosis,
    generate_priority_fixes,
    generate_revision_suggestions,
    generate_section_recommendation,
    generate_safer_wording_suggestions,
    generate_next_best_action,
    generate_panel_risk,
    generate_suggested_revision_wording,
)
from backend.sage_review.services.report_generator import (
    generate_pdf_report,
    save_review_history,
)
from backend.sage_review.core.responsible_ai_guardrail import (
    filter_unsafe_recommendations,
    generate_responsible_ai_warnings,
)
from backend.sage_review.services.revision_comparison import (
    analyze_revision_text,
    compare_revision_results,
)
from backend.sage_review.core.section_extractor import (
    MAJOR_REQUIRED_SECTIONS,
    extract_sections_with_metadata,
)


app = FastAPI(title="SAGE-Review API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextRequest(BaseModel):
    """JSON body for text-only analysis requests."""

    text: str


class CompareRevisionsRequest(BaseModel):
    """JSON body for before-and-after comparison."""

    original_text: str
    revised_text: str


class UploadedFileAdapter:
    """Adapter matching the Streamlit uploaded file interface used by document_loader."""

    def __init__(self, filename: str, content: bytes) -> None:
        self.name = filename
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def normalize_text(value: object) -> str:
    """Clean text for single-section analysis (collapses all whitespace)."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\x00", " ").replace("\xa0", " ")
    return " ".join(text.split())


def normalize_manuscript_text(value: object) -> str:
    """Clean a full-manuscript text while preserving line breaks.

    Heading-based section extraction depends on intact line breaks, so we only
    collapse runs of spaces/tabs within each line. Carriage returns are
    converted to plain newlines.
    """
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\x00", " ").replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def dataframe_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame into JSON-safe records."""
    clean_df = df.where(pd.notna(df), None)
    return clean_df.to_dict(orient="records")


def count_evidence_levels(
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


def get_section_area_groups(
    evidence_coverage: list[dict[str, object]],
    expected_areas: list[str],
) -> tuple[list[str], list[str]]:
    """Return strong and needs-improvement expected evidence areas."""
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


def risk_level(score: float) -> str:
    """Convert manuscript score into a readable risk level."""
    if score >= 85:
        return "Low"
    if score >= 70:
        return "Moderate"
    return "High"


def analyze_section_pipeline(
    text: str,
    section_name: str | None = None,
    source_filename: str | None = None,
) -> dict[str, Any]:
    """Run the SAGE-Review analysis pipeline for one section."""
    clean_text = normalize_text(text)
    if not clean_text:
        raise HTTPException(status_code=400, detail="No readable text was provided.")

    start_time = time.perf_counter()
    
    # Chunk text to avoid massive tokenization delays for huge sections
    analysis_text = clean_text[:10000]
    
    classification = classify_section_zero_shot(analysis_text)
    predicted_section = str(classification["predicted_section"])
    
    canonical_section = normalize_section_name(section_name or predicted_section)
    
    print("--------------------------------------------------")
    print("SECTION DEBUG")
    print(f"raw section_name:    {section_name}")
    print(f"canonical/scoring section: {canonical_section}")
    print(f"predicted_section:   {predicted_section}")

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
        weak_areas=top_weak_areas_only
    )
    
    print("--------------------------------------------------")
    print("SECTION HIGHLIGHTS DEBUG")
    print(f"section_name:        {canonical_section}")
    print(f"highlight_count:     {len(contextual_highlights['highlights'])}")
    print(f"first_highlight_type: {contextual_highlights['highlights'][0]['highlight_type'] if contextual_highlights['highlights'] else 'None'}")
    print("--------------------------------------------------")
    
    next_best_action = generate_next_best_action(
        canonical_section,
        top_weak_areas_only
    )
    panel_risk = generate_panel_risk(
        canonical_section,
        top_weak_areas_only
    )
    suggested_revision_wording = generate_suggested_revision_wording(
        top_weak_areas_only
    )

    section_score = float(score_result["defense_score"])
    section_risk = str(score_result["risk_level"])
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
    strong_count, moderate_count, weak_count, top_weak_areas = count_evidence_levels(
        evidence_coverage
    )
    processing_time = round(time.perf_counter() - start_time, 2)
    
    doc_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:8]
    avg_similarity = sum([float(e.get("Similarity Score", 0)) for e in evidence_coverage]) / max(len(evidence_coverage), 1)
    first_3_scores = [f"{e.get('Evidence Area', '')}: {e.get('Similarity Score', 0)}" for e in evidence_coverage[:3]]
    
    print(f"--- Backend Debug Log: Analyze Section ---")
    print(f"Source filename: {source_filename}")
    print(f"Document hash: {doc_hash}")
    print(f"Extracted text length: {len(clean_text)}")
    print(f"Sections found: 1")
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
        "section_name": section_name or predicted_section,
        "scoring_section": canonical_section,
        "predicted_section": predicted_section,
        "section_confidence": round(float(classification["confidence"]) * 100, 2),
        "section_scores": classification["all_scores"],
        "word_count": len(clean_text.split()),
        "character_count": len(clean_text),
        "text_preview": clean_text[:1000],
        "evidence_coverage": evidence_coverage,
        "criteria_used": list(evidence_result["criteria_used"]),
        "defense_score": round(section_score, 2),
        "risk_level": section_risk,
        "score_summary": (
            f"The analyzed section received a defense readiness score of "
            f"{section_score:.2f}/100 with a {section_risk} risk level."
        ),
        "expected_areas": expected_areas,
        "expected_items": score_result["expected_items"],
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
        "score_breakdown": score_result["score_breakdown"],
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


def build_manuscript_evidence_summary(
    section_details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Average expected evidence scores across analyzed sections."""
    grouped_scores: dict[str, list[float]] = {}
    for section in section_details:
        expected_areas = set(section.get("expected_areas", []))
        for item in section.get("evidence_coverage", []):
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


def analyze_full_manuscript_pipeline(text: str, source_filename: str | None = None) -> dict[str, Any]:
    """Analyze a full manuscript by extracting and scoring sections."""
    clean_text = normalize_manuscript_text(text)
    if not clean_text:
        raise HTTPException(status_code=400, detail="No readable manuscript text was provided.")

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
        raise HTTPException(
            status_code=422,
            detail=(
                "No recognizable thesis sections were extracted. "
                "Please ensure the document has clear chapter or section headings "
                "(e.g., 'CHAPTER 3', '3 Methodology', '4 Results and Discussion')."
            ),
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
        
        section_result = analyze_section_pipeline(section_text, section_name, source_filename=source_filename)
        section_result["analysis_mode"] = "Full Manuscript Section"
        section_details.append(section_result)
        section_results.append(
            {
                "Section Name": section_name,
                "Scoring Section": section_result["scoring_section"],
                "Predicted Section": section_result["predicted_section"],
                "Word Count": section_result["word_count"],
                "Defense Score": section_result["defense_score"],
                "Risk Level": section_result["risk_level"],
                "Weak Evidence Count": section_result["weak_evidence_count"],
                "Top Weak Areas": ", ".join(section_result["top_weak_areas"]),
                "Criteria Used": section_result["criteria_used"],
            }
        )

    # Calculate new 5-part explainable score
    section_extraction_score = (len(major_present) / len(MAJOR_REQUIRED_SECTIONS)) * 100 if MAJOR_REQUIRED_SECTIONS else 100.0
    
    classification_score = (sum(item.get("section_confidence", 0) for item in section_details) / len(section_details)) if section_details else 0.0

    avg_sim = sum(item.get("avg_expected_similarity", 0) for item in section_details) / len(section_details) if section_details else 0.0
    evidence_coverage_score = min(avg_sim * 100, 100.0)

    alignment_scores = [float(item.get("Similarity Score", 0)) for item in alignment_results if item.get("Similarity Score") is not None]
    semantic_alignment_score = (sum(alignment_scores) / len(alignment_scores)) * 100 if alignment_scores else 0.0

    word_count = sum(item.get("word_count", 0) for item in section_details)
    completeness_score = min((word_count / 8000) * 100, 100.0)

    final_score = (
        section_extraction_score * 0.20 +
        classification_score * 0.15 +
        evidence_coverage_score * 0.30 +
        semantic_alignment_score * 0.25 +
        completeness_score * 0.10
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
        for item in sorted(section_results, key=lambda row: float(row["Defense Score"]))[:3]
    ]
    top_weak_alignment_pairs = [
        str(item["Section Pair"])
        for item in alignment_results
        if item["Alignment Level"] in {"Weak Alignment", "Missing Section"}
    ][:5]
    processing_time = round(time.perf_counter() - start_time, 2)

    avg_sim_total = 0.0
    scores_to_print = []
    if len(section_details) > 0:
        first_section_ev = section_details[0].get("evidence_coverage", [])
        total_evidences = sum(len(s.get("evidence_coverage", [])) for s in section_details)
        avg_sim_total = sum(float(e.get("Similarity Score", 0)) for s in section_details for e in s.get("evidence_coverage", [])) / max(total_evidences, 1)
        scores_to_print = [f"{e.get('Evidence Area', '')}: {e.get('Similarity Score', 0)}" for e in first_section_ev[:3]]

    print(f"--- Backend Debug Log: Analyze Full Manuscript ---")
    print(f"Source filename: {source_filename}")
    print(f"Document hash: {doc_hash}")
    print(f"Extracted text length: {len(clean_text)}")
    print(f"Sections found: {len(extracted_sections)}")
    print(f"Section names: {list(extracted_sections.keys())}")
    print(f"Average similarity: {avg_sim_total:.3f}")
    print(f"First 3 evidence scores (1st section): {', '.join(scores_to_print)}")
    print("--------------------------------------------------")

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
        
        # Original keys for frontend
        "defense_score": overall_score,
        "risk_level": risk_level_str,
        "overall_score": overall_score,
        "overall_risk_level": risk_level_str,
        "overall_summary": "Preliminary full manuscript review generated from extracted thesis sections.",
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
        "weak_alignment_count": sum(1 for item in alignment_results if item.get("Alignment Level") == "Weak Alignment"),
        "missing_alignment_count": 0,
        "objectives_confident": objectives_confident,
        "manuscript_evidence_summary": build_manuscript_evidence_summary(section_details),
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
        "strong_evidence_count": sum(item["strong_evidence_count"] for item in section_details),
        "moderate_evidence_count": sum(item["moderate_evidence_count"] for item in section_details),
        "weak_evidence_count": sum(item["weak_evidence_count"] for item in section_details),
        "top_weak_areas": list(
            dict.fromkeys(
                area
                for section in section_details
                for area in section.get("top_weak_areas", [])
            )
        )[:5],
        "processing_time_seconds": processing_time,

        # New requested keys
        "readiness_score": overall_score,
        "total_word_count": word_count,
        "processing_time": processing_time,
        "score_breakdown": {
            "section_extraction_score": round(section_extraction_score, 2),
            "classification_score": round(classification_score, 2),
            "evidence_coverage_score": round(evidence_coverage_score, 2),
            "semantic_alignment_score": round(semantic_alignment_score, 2),
            "completeness_score": round(completeness_score, 2)
        },
        "extracted_section_stats": {
            k: {
                "found": True,
                "word_count": len(v.split())
            } for k, v in extracted_sections.items()
        },
        "weakest_areas": list(
            dict.fromkeys(
                area
                for section in section_details
                for area in section.get("top_weak_areas", [])
            )
        )[:5],
        "recommendations": recommendation,
        "defense_questions": []
    }


async def extract_text_from_request(request: Request) -> tuple[str, str | None]:
    """Read pasted text or uploaded document text without destroying line breaks.

    Each downstream pipeline applies its own normalization
    (``normalize_text`` for single sections, ``normalize_manuscript_text`` for
    full manuscripts, which keeps newlines so headings can be detected).
    """
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        text = str(form.get("text", "") or "")
        upload = form.get("file")
        if upload is not None and getattr(upload, "filename", ""):
            content = await upload.read()
            adapter = UploadedFileAdapter(upload.filename, content)
            uploaded_text = str(extract_text_from_uploaded_file(adapter) or "")
            return uploaded_text or text, upload.filename
        return text, None

    payload = await request.json()
    return str(payload.get("text", "") or ""), None


def attach_report(result: dict[str, Any]) -> dict[str, Any]:
    """Save history, generate a PDF report, and attach the download filename."""
    save_review_history(result)
    pdf_path = Path(generate_pdf_report(result))
    result["report_filename"] = pdf_path.name
    return result


def apply_revision_guardrails(result: dict[str, Any]) -> dict[str, Any]:
    """Attach responsible AI warnings and filter unsafe revision feedback."""
    generated_feedback = [
        result.get("priority_fixes", []),
        result.get("revision_suggestions", []),
        result.get("defense_questions", []),
        result.get("defense_notes", []),
    ]
    result["responsible_ai_warnings"] = generate_responsible_ai_warnings(
        result.get("input_text", ""),
        generated_feedback,
    )
    result["priority_fixes"] = filter_unsafe_recommendations(
        result.get("priority_fixes", [])
    )
    result["revision_suggestions"] = filter_unsafe_recommendations(
        result.get("revision_suggestions", [])
    )
    result["defense_notes"] = filter_unsafe_recommendations(
        result.get("defense_notes", [])
    )
    return result


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/analyze-section")
async def analyze_section(request: Request) -> dict[str, Any]:
    """Analyze one pasted or uploaded thesis section."""
    text, filename = await extract_text_from_request(request)
    result = analyze_section_pipeline(text, source_filename=filename)
    return attach_report(result)


@app.post("/analyze-full-manuscript")
async def analyze_full_manuscript(request: Request) -> dict[str, Any]:
    """Analyze a full manuscript or large chapter."""
    text, filename = await extract_text_from_request(request)
    result = analyze_full_manuscript_pipeline(text, source_filename=filename)
    return attach_report(result)


@app.post("/compare-revisions")
async def compare_revisions(payload: CompareRevisionsRequest) -> dict[str, Any]:
    """Compare original and revised thesis section versions."""
    original_result = apply_revision_guardrails(
        analyze_revision_text(payload.original_text)
    )
    revised_result = apply_revision_guardrails(
        analyze_revision_text(payload.revised_text)
    )
    comparison = compare_revision_results(original_result, revised_result)
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "comparison": comparison,
        "original": original_result,
        "revised": revised_result,
    }


@app.post("/evaluate-dataset")
async def evaluate_dataset(file: UploadFile = File(...)) -> dict[str, Any]:
    """Run SAGE-Review on a labeled evaluation dataset CSV."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    content = await file.read()
    df = load_evaluation_dataset(BytesIO(content))
    results_df = run_evaluation_on_dataset(df)
    summary = generate_evaluation_summary(results_df)
    results_path = Path(save_evaluation_results(results_df))
    return {
        "summary": summary,
        "results": dataframe_records(results_df),
        "results_filename": results_path.name,
    }


@app.get("/download-report/{filename}")
def download_report(filename: str) -> FileResponse:
    """Download a generated PDF report or evaluation CSV by filename."""
    safe_name = Path(filename).name
    candidate_paths = [
        PROJECT_ROOT / "reports" / safe_name,
        PROJECT_ROOT / "data" / safe_name,
    ]
    for path in candidate_paths:
        if path.exists() and path.is_file():
            return FileResponse(path, filename=safe_name)
    raise HTTPException(status_code=404, detail="File not found.")
