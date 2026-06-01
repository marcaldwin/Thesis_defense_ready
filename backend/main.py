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
from backend.sage_review.services.analysis_service import (
    AnalysisService,
    AnalysisServiceError,
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


analysis_service = AnalysisService()
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
    try:
        return analysis_service.analyze_api_section(
            text,
            section_name,
            source_filename=source_filename,
        )
    except AnalysisServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


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
    try:
        return analysis_service.analyze_api_full_manuscript(
            text,
            source_filename=source_filename,
        )
    except AnalysisServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


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
