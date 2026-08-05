"""Structured thesis defense feedback generation for SAGE-Review.

The functions in this module convert scoring and semantic coverage outputs into
practical defense preparation guidance. This is not a generic chatbot.
"""

import re

from backend.sage_review.services.defense_question_generator import (
    generate_section_defense_questions,
)
from backend.sage_review.core.evidence_analyzer import get_section_specific_criteria


RISKY_WORDING = {
    "perfect": (
        "This implies no errors or limitations.",
        "performed well within the tested conditions",
    ),
    "always": (
        "This suggests the result is guaranteed in every case.",
        "was observed in the evaluated cases",
    ),
    "fully solves": (
        "This overstates the contribution and may be challenged during defense.",
        "addresses the problem within the defined study scope",
    ),
    "completely accurate": (
        "This implies flawless model performance.",
        "achieved the reported accuracy under the test conditions",
    ),
    "works for all": (
        "This generalizes beyond the evaluated users, data, or conditions.",
        "worked for the participants and samples included in the study",
    ),
    "real-time": (
        "This requires latency or response time evidence.",
        "processed inputs within the measured response time",
    ),
    "highly accurate": (
        "This needs strong evaluation metrics and error analysis.",
        "achieved the reported evaluation performance",
    ),
    "universal": (
        "This claims broad applicability beyond the study scope.",
        "applicable within the defined study context",
    ),
    "guarantees": (
        "This implies certainty that research results usually cannot support.",
        "is designed to support",
    ),
}


def _coverage_by_area(evidence_coverage: list[dict[str, object]]) -> dict[str, str]:
    """Map evidence area names to coverage levels."""
    return {
        str(item["Evidence Area"]): str(item["Coverage Level"])
        for item in evidence_coverage
    }


def generate_safer_wording_suggestions(text: str) -> list[dict[str, str]]:
    """Detect risky academic wording and suggest safer alternatives."""
    suggestions = []
    for phrase, (why_risky, safer_alternative) in RISKY_WORDING.items():
        pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
        if pattern.search(text):
            suggestions.append(
                {
                    "Risky Wording": phrase,
                    "Why Risky": why_risky,
                    "Safer Alternative": safer_alternative,
                }
            )

    return suggestions


def generate_defense_notes(score_result: dict[str, object]) -> list[str]:
    """Generate defense preparation notes based on risk level."""
    risk_level = score_result.get("risk_level")
    if risk_level == "Low":
        return ["Prepare short explanations for minor weaknesses."]
    if risk_level == "Moderate":
        return ["Prepare evidence-based answers for weak areas before defense."]
    return [
        "Revise the section before defense and avoid strong claims until "
        "evidence is added."
    ]


def generate_plain_language_diagnosis(
    section_name: str,
    score: float,
    risk_level: str,
    strong_areas: list[str],
    weak_areas: list[str],
) -> str:
    """Explain section readiness in plain adviser-style language."""
    if score >= 80:
        readiness = "mostly ready for defense"
    elif score >= 60:
        readiness = "partially ready for defense"
    else:
        readiness = "not yet defense-ready"

    if weak_areas:
        weak_text = ", ".join(weak_areas[:2])
        section_lower = section_name.lower()
        consequence = (
            "This may make it harder to defend how the section supports the "
            "study objectives, methods, or findings."
        )
        if section_name == "Conclusion":
            consequence = (
                "This means the conclusion may not clearly show how the study "
                "findings answer the research objectives."
            )
        elif section_name == "Results and Discussion":
            consequence = (
                "This means the results may not clearly report the metrics, "
                "error analysis, or objective-to-result links needed for defense."
            )
        elif section_name == "Methodology":
            consequence = (
                "This means the procedure may not be reproducible enough for "
                "panel questions about data, model setup, or evaluation."
            )
        return (
            f"The {section_lower} section is {readiness} because the system "
            f"detected weak support for {weak_text}. {consequence}"
        )

    if strong_areas:
        strong_text = ", ".join(strong_areas[:2])
        return (
            f"This {section_name.lower()} section is {readiness}. The strongest "
            f"support appears in {strong_text}. Review the section for clarity, "
            f"but no major evidence gap was detected."
        )

    return (
        f"This {section_name.lower()} section is {readiness}. The system could "
        f"not identify strong evidence areas, so the section may need clearer "
        f"organization and more explicit support."
    )


SECTION_RECOMMENDATIONS = {
    "Abstract": [
        "Summarize purpose, method, key result, and conclusion in a concise paragraph.",
        "Include scope or limitation briefly without adding detailed technical tables.",
    ],
    "Introduction": [
        "Clarify the problem context, research gap, and motivation for the proposed system.",
        "Make the objectives visible and connect them to the identified gap.",
    ],
    "Objectives of the Study": [
        "Make each objective measurable and connect it to a method, output, or evaluation result.",
        "Separate the general objective from specific objectives if they are currently merged.",
    ],
    "Literature Review": [
        "Compare related studies instead of only describing them one by one.",
        "End with a clear research gap and explain how the reviewed work supports the proposed system.",
    ],
    "Methodology": [
        "Add dataset size, participants, collection procedure, preprocessing, model, and evaluation metrics.",
        "Make the procedure reproducible enough that another researcher can follow it.",
    ],
    "Results and Discussion": [
        "Report performance metrics, error analysis, usability, latency, and interpretation where applicable.",
        "Connect each result to a research objective.",
    ],
    "Conclusion": [
        "Tie conclusions directly to findings and avoid claims not supported by results.",
        "State limitations, recommendations, and future work clearly.",
    ],
    "Limitations": [
        "State scope boundaries, data limits, system constraints, and responsible AI limitations.",
        "Explain how each limitation affects real-world use or interpretation.",
    ],
}


CRITERION_FIX_GUIDANCE = {
    "Research Purpose": "In this section, state the study purpose in one direct sentence and connect it to the problem being evaluated.",
    "Method Summary": "Briefly name the method, model, or development process so the reader can see how the study was carried out.",
    "Key Results Summary": "Add the main measured result or finding; if no value is available, add a metric, table reference, or finding that supports this point.",
    "Problem Context": "Explain the real-world problem before introducing the proposed system or study solution.",
    "Research Gap": "State what previous studies, current systems, or existing practice still do not address.",
    "Study Purpose": "Add a clear sentence explaining what the study aims to accomplish and why that aim follows from the gap.",
    "Objectives Mention": "List or reference the study objectives so the reader can trace them to methods and results.",
    "Related Studies Coverage": "Add relevant studies and explain what each contributes to the current study context.",
    "Comparison of Existing Systems": "Compare existing systems by method, feature, performance, and limitation rather than only listing them.",
    "Research Gap Synthesis": "Summarize the shared gap across reviewed studies and explain how the current study responds to it.",
    "Dataset Description": "State the dataset source, size, classes, split, and distribution used for this section's claims.",
    "Participant or Sample Description": "State sample size, selection criteria, and sampling method so the panel can judge representativeness.",
    "Data Collection Procedure": "Describe how data was gathered, recorded, labeled, and validated.",
    "Preprocessing Description": "Explain cleaning, normalization, augmentation, encoding, or preparation steps before model or system use.",
    "Model or Algorithm Description": "Describe the model, algorithm, architecture, or system logic clearly enough to reproduce the work.",
    "Evaluation Metrics": "State the metric, table reference, or finding that shows how the objective was evaluated.",
    "Model Evaluation Metrics": "Report accuracy, precision, recall, F1-score, or another metric tied to the objective.",
    "Confusion Matrix or Error Analysis": "Add a confusion matrix, error table, or explanation of misclassified cases.",
    "Latency or Response Time Results": "Report measured response time, device conditions, and number of test runs.",
    "Usability Evaluation Results": "Summarize user tasks, ratings, respondents, or usability table results.",
    "Objective-to-Result Connection": "Add an objective-to-result mapping table or paragraph showing which result answers each objective.",
    "Summary of Main Findings": "Summarize the main findings using specific results from the study; if values are unavailable, reference the finding or table that supports the summary.",
    "Objective Support": "Add one sentence for each study objective explaining which result, table, or finding supports the conclusion.",
    "Results-Based Claims": "Tie each claim to a reported result, metric, table, or observed finding.",
    "Limitations": "State the study limits, constraints, and conditions where results may not apply.",
    "Avoidance of Overclaims": "Revise broad claims so they match the measured results and study scope.",
    "Recommendations": "Base recommendations on specific findings, limitations, or observed results.",
    "Future Work": "Name concrete next work, such as more data, more users, broader testing, or improved evaluation.",
}


def criterion_fix_guidance(area: str, section_name: str) -> str:
    """Return specific guidance grounded in section and criterion."""
    guidance = CRITERION_FIX_GUIDANCE.get(
        area,
        (
            f"In the {section_name} section, add a metric, table reference, "
            f"or finding that supports {area.lower()}."
        ),
    )
    if section_name and section_name not in guidance:
        return f"For {section_name}, {guidance[0].lower()}{guidance[1:]}"
    return guidance


def _weak_and_moderate_items(evidence_coverage: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        item
        for item in evidence_coverage
        if str(item.get("Coverage Level", "Weak")) != "Strong"
    ]


def generate_priority_fixes(
    score_result: dict[str, object],
    evidence_coverage: list[dict[str, object]],
    predicted_section: str,
) -> list[dict[str, str]]:
    """Generate section-specific priority fixes from expected criteria."""
    fixes = []
    expected = set(score_result.get("criteria_used", get_section_specific_criteria(predicted_section).keys()))
    weak_items = [
        item
        for item in _weak_and_moderate_items(evidence_coverage)
        if str(item["Evidence Area"]) in expected
    ]
    for item in weak_items:
        area = str(item["Evidence Area"])
        level = str(item["Coverage Level"])
        fixes.append(
            {
                "Priority": "High" if level == "Weak" else "Medium",
                "Issue": f"{predicted_section}: {level} support for {area}",
                "Why It Matters": (
                    f"{area} is expected in {predicted_section}; weak support can "
                    "make the section harder to defend."
                ),
                "Suggested Fix": criterion_fix_guidance(area, predicted_section),
            }
        )
    return fixes[:6]


def generate_revision_suggestions(
    predicted_section: str,
    evidence_coverage: list[dict[str, object]],
    score_result: dict[str, object],
) -> list[str]:
    """Generate section-specific revision suggestions."""
    suggestions = list(
        SECTION_RECOMMENDATIONS.get(
            predicted_section,
            ["Clarify the section purpose and connect claims to evidence."],
        )
    )
    return list(dict.fromkeys(suggestions))[:3]


def generate_defense_questions(
    predicted_section: str,
    evidence_coverage: list[dict[str, object]],
    score_result: dict[str, object],
) -> list[str]:
    """Generate section-specific defense questions."""
    weak = [
        str(item["Evidence Area"])
        for item in evidence_coverage
        if item.get("Coverage Level") == "Weak"
    ]
    return generate_section_defense_questions(
        predicted_section,
        weak,
        str(score_result.get("risk_level", "")),
    )


def generate_section_recommendation(
    section_name: str,
    weak_areas: list[str],
) -> list[str]:
    """Generate one or two practical next fixes for a section."""
    recommendations = list(
        SECTION_RECOMMENDATIONS.get(
            section_name,
            ["Clarify weak criteria and connect claims to evidence."],
        )
    )
    if weak_areas:
        first = weak_areas[0]
        recommendations.append(
            f"Focus first on {first}: {criterion_fix_guidance(first, section_name)}"
        )
    return recommendations[:2]


def generate_next_best_action(section_name: str, weak_areas: list[str]) -> str:
    """Generate one clear action the student should do next for the section."""
    actions = {
        "Abstract": "Add one sentence summarizing the key result and one sentence stating the study scope.",
        "Introduction": "Clarify the research gap and connect it directly to the proposed system.",
        "Objectives of the Study": "Ensure each objective is measurable and directly links to the methodology.",
        "Literature Review": "Compare related studies focusing on their limitations and how your system addresses them.",
        "Methodology": "Add dataset size, participant details, collection procedure, preprocessing, model setup, and evaluation metrics.",
        "Results and Discussion": "Add measurable results and explain how each result answers the objectives.",
        "Limitations": "Clearly state the scope boundaries and under what conditions the system might fail.",
        "Conclusion": "Connect each conclusion to a specific finding and soften unsupported claims.",
    }
    if weak_areas:
        first = weak_areas[0]
        return criterion_fix_guidance(first, section_name)
    return actions.get(section_name, "Review the weak areas and add a metric, table reference, or finding that supports the section's main claim.")


def generate_panel_risk(section_name: str, weak_areas: list[str]) -> str:
    """Explain what defense question may arise from the primary weak area."""
    if not weak_areas:
        return "Low panel risk detected for this section based on current evidence."
    
    primary_weak_area = weak_areas[0]
    
    risks = {
        "Dataset Description": "The panel may question the reliability of the study if the dataset size and split are not clearly defined.",
        "Participant / Sample Description": "The panel may ask how participants were selected and if the sample represents the target users.",
        "Data Collection Procedure": "The panel may question the validity of your data if the collection process is unclear.",
        "Preprocessing Description": "The panel may ask how the data was cleaned or augmented before training.",
        "Model Training Description": "The panel may challenge your results if the model training and setup cannot be reproduced.",
        "Model Evaluation Metrics": "The panel may ask how the system was evaluated because the section does not clearly report metrics.",
        "Confusion Matrix / Error Analysis": "The panel may ask about the system's weaknesses and why certain errors occurred.",
        "Mobile Prototype Testing": "The panel may question the prototype's usefulness without evidence of actual device testing.",
        "Latency / Response Time Testing": "The panel may ask if the system is fast enough for real-world use.",
        "Usability Evaluation": "The panel may ask for evidence that target users find the system usable and helpful.",
        "Limitations / Scope": "The panel may challenge your claims if the boundaries and limitations of the system are not clear.",
        "Conclusion Support": "The panel may ask why the conclusion claims effectiveness if the findings are not clearly connected.",
        "Research Purpose": "The panel may ask what specific problem the study aims to solve.",
        "Method Summary": "The panel may ask for a brief overview of how the system was developed.",
        "Key Results Summary": "The panel may ask what the most significant finding of the study was.",
        "Problem Context": "The panel may ask to explain the real-world context of the problem.",
        "Research Gap": "The panel may ask what exactly is missing in current solutions that your system addresses.",
        "Study Purpose": "The panel may ask for the main goal of the research.",
        "Objectives Mention": "The panel may ask what the specific objectives are.",
        "Related Studies Coverage": "The panel may ask how your work compares to existing studies.",
        "Comparison of Existing Systems": "The panel may ask why your system is better than existing ones.",
        "Research Gap Synthesis": "The panel may ask to clearly identify the gap across all reviewed studies.",
        "Model or Algorithm Description": "The panel may ask for technical details on how the core algorithm works.",
        "Evaluation Metrics": "The panel may ask what metrics prove the system works.",
        "Objective-to-Result Connection": "The panel may ask to show the specific result that satisfies each objective.",
        "Avoidance of Overclaims": "The panel may challenge broad claims that are not supported by the data."
    }
    
    default_risk = f"The panel may ask for more details regarding {primary_weak_area.lower()}."
    return risks.get(primary_weak_area, default_risk)


def generate_suggested_revision_wording(weak_areas: list[str]) -> list[str]:
    """Generate safe academic rewrite templates for weak areas."""
    templates = {
        "Problem Statement": "Add: The main problem addressed by this study is [specific problem].",
        "System Purpose": "Add: The proposed system aims to [main goal] by [method].",
        "Methods Used": "Add: This study utilizes [method name] to [purpose].",
        "Main Results": "Add: The results indicate a [metric] of [value], demonstrating [finding].",
        "Conclusion": "Add: It is concluded that [main conclusion] based on the findings.",
        "Background": "Add: Currently, [context], which faces the challenge of [issue].",
        "Research Gap": "Add: However, existing solutions lack [missing feature/limitation].",
        "Objectives": "Add: Specifically, this study aims to [specific objective].",
        "Significance": "Add: This is significant for [target group] because it [benefit].",
        "Data Source": "Add: Data was collected from [source] consisting of [number] samples.",
        "System Development": "Add: The system was developed using [tool/framework] to handle [process].",
        "Model or Algorithm": "Add: The core algorithm used is [algorithm name], which works by [mechanism].",
        "Testing Procedure": "Add: The system was tested by [testing method] under [conditions].",
        "Evaluation Metrics": "Add: Performance was measured using [metric 1] and [metric 2].",
        "Measurable Results": "Add: The system achieved [metric] of [value], outperforming [baseline].",
        "Tables or Figures": "Add: As shown in Table [X], the results indicate [finding].",
        "Interpretation": "Add: This suggests that [interpretation of the result].",
        "Comparison": "Add: Compared to [prior work], this approach improves [metric] by [value].",
        "Limitations": "Add: One limitation is [limitation], which may affect [condition].",
        "Summary of Findings": "Add: Overall, the study found that [main finding].",
        "Objective Answer": "Add: The objective to [objective] was met by [evidence].",
        "Recommendations": "Add: It is recommended to [recommendation] for better [outcome].",
        "Future Work": "Add: Future research should focus on [future direction]."
    }
    
    suggestions = []
    for area in weak_areas:
        if area in templates:
            suggestions.append(templates[area])
        else:
            suggestions.append(
                f"Add a metric, table reference, or finding that supports {area.lower()}."
            )
            
    return suggestions[:3]
