"""Visualization helpers for SAGE-Review dashboards."""

import matplotlib.pyplot as plt


def plot_evidence_coverage_chart(evidence_coverage: list[dict[str, object]]):
    """Plot semantic evidence coverage similarity scores."""
    sorted_items = sorted(
        evidence_coverage,
        key=lambda item: float(item["Similarity Score"]),
        reverse=True,
    )[:8]
    labels = [str(item["Evidence Area"]) for item in sorted_items]
    scores = [float(item["Similarity Score"]) for item in sorted_items]

    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.bar(labels, scores, color="#4C78A8")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Similarity Score")
    ax.set_title("Semantic Evidence Coverage Scores")
    ax.tick_params(axis="x", labelrotation=35, labelsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return fig


def plot_section_scores_chart(section_results: list[dict[str, object]]):
    """Plot defense readiness scores for extracted manuscript sections."""
    labels = [str(item["Section Name"]) for item in section_results]
    scores = [float(item["Defense Score"]) for item in section_results]

    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.bar(labels, scores, color="#59A14F")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Defense Readiness Score")
    ax.set_title("Defense Readiness Score per Section")
    ax.tick_params(axis="x", labelrotation=25, labelsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return fig


def plot_alignment_matrix_chart(alignment_results: list[dict[str, object]]):
    """Plot semantic alignment scores between thesis section pairs."""
    filtered_results = [
        item for item in alignment_results if item["Similarity Score"] is not None
    ]
    labels = [str(item["Section Pair"]) for item in filtered_results]
    scores = [float(item["Similarity Score"]) for item in filtered_results]

    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.bar(labels, scores, color="#F28E2B")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Similarity Score")
    ax.set_title("Semantic Alignment Between Thesis Sections")
    ax.tick_params(axis="x", labelrotation=25, labelsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return fig
