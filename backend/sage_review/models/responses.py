"""Pydantic response models for the SAGE-Review FastAPI surface."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str


class ReportInfo(BaseModel):
    """Normalized generated report metadata."""

    filename: str | None = None
    download_url: str | None = None


class FeedbackResponse(BaseModel):
    """Normalized feedback block shared by section and manuscript responses."""

    diagnosis: str | None = None
    next_best_action: str | None = None
    priority_fixes: list[Any] = Field(default_factory=list)
    revision_suggestions: list[Any] = Field(default_factory=list)
    suggested_revision_wording: list[Any] = Field(default_factory=list)
    defense_questions: list[Any] = Field(default_factory=list)
    defense_notes: list[Any] = Field(default_factory=list)
    recommendations: list[Any] | str | None = None
    responsible_ai_warnings: list[Any] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    """Normalized analysis response.

    Extra fields are intentionally allowed so legacy response keys remain
    available to the current React frontend during the transition.
    """

    model_config = ConfigDict(extra="allow")

    analysis_mode: str | None = None
    timestamp: str | None = None
    score: float | None = None
    readiness_score: float | None = None
    risk: str | None = None
    risk_level: str | None = None
    confidence: str | float | None = None
    word_count: int | None = None
    processing_time_seconds: float | None = None
    feedback: FeedbackResponse | None = None
    evidence: list[Any] = Field(default_factory=list)
    evidence_coverage: list[Any] = Field(default_factory=list)
    alignment_matrix: list[Any] = Field(default_factory=list)
    sections: list[Any] = Field(default_factory=list)
    report: ReportInfo | None = None
    report_filename: str | None = None


class RevisionComparisonResponse(BaseModel):
    """Before-and-after revision comparison response."""

    model_config = ConfigDict(extra="allow")

    timestamp: str
    comparison: dict[str, Any]
    original: dict[str, Any]
    revised: dict[str, Any]
    revision_summary: str | None = None
    score_change: float | int | None = None
    semantic_improvement: float | None = None
    evidence_changes: dict[str, Any] = Field(default_factory=dict)


class EvaluationResponse(BaseModel):
    """Evaluation dataset response."""

    model_config = ConfigDict(extra="allow")

    summary: dict[str, Any]
    results: list[dict[str, Any]]
    results_filename: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    report: ReportInfo | None = None
