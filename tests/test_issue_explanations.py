from backend.sage_review.services.analysis_service import AnalysisService


def test_top_weak_sections_explained_has_required_fields():
    service = AnalysisService()
    section_summary = service.build_section_evidence_summary(
        "Conclusion",
        [
            {
                "Evidence Area": "Objective Support",
                "Similarity Score": 0.1,
                "Coverage Level": "Weak",
                "Interpretation": "Objective support is unclear.",
            },
            {
                "Evidence Area": "Summary of Main Findings",
                "Similarity Score": 0.2,
                "Coverage Level": "Weak",
                "Interpretation": "Findings summary is unclear.",
            },
        ],
        ["Objective Support", "Summary of Main Findings"],
    )

    explained = service.build_top_weak_sections_explained(
        [
            {
                "resolved_section_label": "Conclusion",
                "defense_score": 26.65,
                "risk_level": "High",
                **section_summary,
            }
        ]
    )

    assert explained
    assert explained[0]["section"] == "Conclusion"
    assert explained[0]["reason"]
    assert explained[0]["weak_criteria"]
    assert explained[0]["next_action"]


def test_main_issues_explained_and_fix_order_exist():
    service = AnalysisService()
    weak_sections = [
        {
            "section": "Conclusion",
            "score": 26.65,
            "risk_level": "High",
            "weak_criteria": ["Objective Support"],
            "reason": "Objective Support was weak.",
            "evidence_metric": "1 critical criterion was weak",
            "next_action": "Connect each conclusion to a specific result.",
        }
    ]
    alignment = [
        {
            "section_pair": "Methodology <-> Results and Discussion",
            "similarity": 0.258,
            "risk": "High",
            "reason": "The methodology and results are weakly connected.",
            "next_action": "Add a table mapping methodology steps to reported results.",
        }
    ]

    issues = service.build_main_issues_explained(
        weak_sections,
        alignment,
        [],
        True,
    )
    fix_order = service.build_recommended_fix_order(issues)

    assert issues
    assert issues[0]["issue_type"] == "Weak Evidence Coverage"
    assert issues[0]["next_action"]
    assert fix_order
    assert fix_order[0]["priority"] == 1


def test_alignment_weak_pairs_include_reason_and_next_action():
    service = AnalysisService()
    explained = service.explain_alignment_weaknesses(
        [
            {
                "Section Pair": "Methodology <-> Results and Discussion",
                "Similarity Score": 0.258,
                "Alignment Level": "Weak Alignment",
                "Risk": "High",
                "Interpretation": "These sections appear weakly connected.",
            }
        ]
    )

    assert explained
    assert explained[0]["reason"]
    assert explained[0]["next_action"]
