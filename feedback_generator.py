"""Structured thesis defense feedback generation for SAGE-Review.

The functions in this module convert scoring and semantic coverage outputs into
practical defense preparation guidance. This is not a generic chatbot.
"""

import re

from defense_question_generator import generate_section_defense_questions
from evidence_analyzer import get_section_specific_criteria


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
        return (
            f"This {section_name.lower()} section is {readiness}. It contains "
            f"some relevant content, but the system detected weak support for "
            f"{weak_text}. Revise this section by adding clearer evidence before "
            f"defense."
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
    "Research Purpose": "State the study purpose in one direct sentence.",
    "Method Summary": "Briefly summarize the method or development process used.",
    "Key Results Summary": "Add the most important measured result or finding.",
    "Problem Context": "Explain the problem context before introducing the solution.",
    "Research Gap": "State what previous studies or current systems do not address.",
    "Study Purpose": "Add a clear statement of what the study aims to accomplish.",
    "Objectives Mention": "Make the objectives or study aims explicit.",
    "Related Studies Coverage": "Add more relevant studies and explain their findings.",
    "Comparison of Existing Systems": "Compare systems by method, features, performance, and limitations.",
    "Research Gap Synthesis": "Synthesize the gap across studies instead of listing sources only.",
    "Dataset Description": "State dataset source, size, classes, split, and distribution.",
    "Participant or Sample Description": "State sample size, selection criteria, and sampling method.",
    "Data Collection Procedure": "Describe how data was gathered, recorded, and validated.",
    "Preprocessing Description": "Explain cleaning, normalization, augmentation, encoding, or preparation steps.",
    "Model or Algorithm Description": "Describe the model, algorithm, architecture, or system logic.",
    "Evaluation Metrics": "State the metrics and why they match the objectives.",
    "Confusion Matrix or Error Analysis": "Explain errors, misclassifications, and weak cases.",
    "Latency or Response Time Results": "Report measured response time or processing delay.",
    "Usability Evaluation Results": "Summarize usability testing, ratings, tasks, or user feedback.",
    "Objective-to-Result Connection": "Link each result back to a specific objective.",
    "Limitations": "State the study limits, constraints, and conditions where results may not apply.",
    "Avoidance of Overclaims": "Revise claims so they stay within the actual evidence.",
}


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
    if score_result.get("risk_level") == "High":
        fixes.append(
            {
                "Priority": "High",
                "Issue": "Section needs targeted revision before defense.",
                "Why It Matters": "Weak expected criteria may lead to adviser or panel questions.",
                "Suggested Fix": "Address the weakest section-specific criteria first.",
            }
        )

    for item in _weak_and_moderate_items(evidence_coverage):
        area = str(item["Evidence Area"])
        if area not in expected:
            continue
        level = str(item["Coverage Level"])
        fixes.append(
            {
                "Priority": "High" if level == "Weak" else "Medium",
                "Issue": f"{level} support for {area}",
                "Why It Matters": f"{area} is expected in the {predicted_section} section.",
                "Suggested Fix": CRITERION_FIX_GUIDANCE.get(
                    area,
                    f"Add clearer evidence for {area.lower()}.",
                ),
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
    weak = [
        str(item["Evidence Area"])
        for item in evidence_coverage
        if item.get("Coverage Level") == "Weak"
    ][:3]
    if weak:
        suggestions.append("Prioritize weak criteria: " + ", ".join(weak) + ".")
    return suggestions[:4]


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
        recommendations.append("Focus first on: " + ", ".join(weak_areas[:3]) + ".")
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
    return actions.get(section_name, "Review the weak areas and add clear evidence to support your claims.")


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
            suggestions.append(f"Add clear evidence or measurable data for {area.lower()}.")
            
    return suggestions[:3]
