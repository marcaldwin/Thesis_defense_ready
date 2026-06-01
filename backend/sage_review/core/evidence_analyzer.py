"""Section-specific semantic evidence criteria for SAGE-Review."""

STRONG_THRESHOLD = 0.65
MODERATE_THRESHOLD = 0.45


SECTION_CRITERIA = {
    "Abstract": {
        "Research Purpose": "The abstract clearly states the main purpose or problem addressed by the study.",
        "Method Summary": "The abstract briefly summarizes the method, research approach, or development process used.",
        "Dataset or Input Summary": "The abstract summarizes the dataset, participants, samples, input data, or materials used.",
        "Model or System Summary": "The abstract briefly describes the proposed model, algorithm, prototype, or system.",
        "Key Results Summary": "The abstract reports the most important results, performance, evaluation, or findings.",
        "Conclusion or Contribution Summary": "The abstract states the main conclusion, contribution, or implication supported by the findings.",
        "Scope or Limitation Statement": "The abstract briefly acknowledges the scope, context, or limitation of the study.",
    },
    "Introduction": {
        "Problem Context": "The introduction explains the background, real-world problem, and context of the study.",
        "Research Gap": "The introduction identifies a gap, limitation, or unresolved issue in prior work or current practice.",
        "Study Purpose": "The introduction clearly states the purpose or aim of the study.",
        "Objectives Mention": "The introduction mentions the general objective, specific objectives, research questions, or study aims.",
        "Significance of the Study": "The introduction explains why the study matters and who may benefit from it.",
        "Scope or Boundary": "The introduction defines the study scope, boundaries, context, or limits.",
        "Motivation for Proposed System": "The introduction explains why the proposed system, model, or solution is needed.",
    },
    "Objectives of the Study": {
        "General Objective": "The section states the broad overall objective of the study.",
        "Specific Objectives": "The section lists specific objectives or research tasks that support the general objective.",
        "Measurable Outputs": "The objectives describe measurable outputs, deliverables, results, or performance targets.",
        "Method Connection": "The objectives can be connected to a method, procedure, prototype, model, or implementation step.",
        "Evaluation Connection": "The objectives can be evaluated using metrics, testing, validation, user feedback, or results.",
        "Scope Boundary": "The objectives make clear the scope, context, users, dataset, or system boundary.",
    },
    "Literature Review": {
        "Related Studies Coverage": "The literature review discusses relevant prior studies, systems, methods, or findings.",
        "Comparison of Existing Systems": "The literature review compares existing systems, approaches, technologies, strengths, and weaknesses.",
        "Method or Technology Support": "The literature review supports the selected method, model, framework, or technology.",
        "Research Gap Synthesis": "The literature review synthesizes limitations or gaps from prior work.",
        "Link to Proposed Study": "The literature review explains how reviewed works justify or connect to the current study.",
        "Citation Support": "The literature review uses citations or source-based discussion to support claims.",
    },
    "Methodology": {
        "Research Design": "The methodology explains the research design, development approach, or study workflow.",
        "Dataset Description": "The methodology describes the dataset, inputs, samples, classes, data split, or data distribution.",
        "Participant or Sample Description": "The methodology describes participants, respondents, samples, selection criteria, or sample size.",
        "Data Collection Procedure": "The methodology explains how data was collected, recorded, gathered, or obtained.",
        "Preprocessing Description": "The methodology describes cleaning, normalization, augmentation, encoding, or preparation steps.",
        "Model or Algorithm Description": "The methodology explains the model, algorithm, architecture, training setup, or system logic.",
        "System Development Procedure": "The methodology describes how the prototype, application, or system was designed and developed.",
        "Evaluation Metrics": "The methodology states the metrics, validation method, testing approach, or evaluation criteria.",
        "Prototype Testing Procedure": "The methodology explains how the prototype or application was tested with users, devices, or scenarios.",
    },
    "Results and Discussion": {
        "Dataset or Experiment Summary": "The results summarize the experiment, test setup, dataset, samples, or evaluation context.",
        "Model Evaluation Metrics": "The results report accuracy, precision, recall, F1-score, performance, or classification metrics.",
        "Confusion Matrix or Error Analysis": "The results discuss confusion matrix values, errors, misclassifications, or weak cases.",
        "Prototype Testing Results": "The results report prototype tests, system output, mobile testing, or functional testing outcomes.",
        "Latency or Response Time Results": "The results report response time, inference time, processing delay, or speed measurements.",
        "Usability Evaluation Results": "The results report usability testing, user feedback, satisfaction, ease of use, or acceptability.",
        "Interpretation of Findings": "The discussion interprets what the findings mean and why the results occurred.",
        "Objective-to-Result Connection": "The discussion connects results back to the research objectives or questions.",
    },
    "Conclusion": {
        "Summary of Main Findings": "The conclusion summarizes the main findings and study outcomes.",
        "Objective Support": "The conclusion explains how the objectives were achieved or supported by findings.",
        "Results-Based Claims": "The conclusion makes claims that are directly supported by results and evidence.",
        "Limitations": "The conclusion acknowledges study limitations, constraints, scope, or boundaries.",
        "Recommendations": "The conclusion provides recommendations based on the study findings.",
        "Future Work": "The conclusion describes possible future improvements, extensions, or further research.",
        "Avoidance of Overclaims": "The conclusion avoids exaggerated claims and stays within the evidence and scope of the study.",
    },
    "Unknown": {
        "Purpose": "The text explains the main purpose or objective.",
        "Method": "The text describes the method, approach, or procedure used.",
        "Evidence": "The text provides data, citations, or support for its claims.",
        "Result": "The text states clear outcomes, findings, or results.",
        "Limitation": "The text acknowledges scope, boundaries, or limitations."
    }
}


SECTION_ALIASES = {
    "Unknown / Mixed Section": "Methodology",
    "Results": "Results and Discussion",
    "Discussion": "Results and Discussion",
    "Results and Discussions": "Results and Discussion",
    "Literature": "Literature Review",
}


def normalize_section_name(section_name: str) -> str:
    """Normalize a section name for criteria lookup."""
    text = str(section_name or "").lower().strip()
    if "abstract" in text:
        return "Abstract"
    if "objective" in text:
        return "Objectives of the Study"
    if "introduction" in text:
        return "Introduction"
    if "literature" in text or "related" in text or "rrl" in text:
        return "Literature Review"
    if "method" in text:
        return "Methodology"
    if "result" in text or "discussion" in text:
        return "Results and Discussion"
    if "conclusion" in text or "recommendation" in text or "summary" in text:
        return "Conclusion"
    if "limitation" in text:
        return "Limitations"
    return "Unknown"


def get_section_specific_criteria(section_name: str) -> dict[str, str]:
    """Return natural-language criteria for the given thesis section."""
    normalized = normalize_section_name(section_name)
    return SECTION_CRITERIA.get(normalized, SECTION_CRITERIA["Unknown"])


def classify_coverage_level(similarity_score: float) -> str:
    """Convert a semantic similarity score into a coverage level."""
    if similarity_score >= STRONG_THRESHOLD:
        return "Strong"
    if similarity_score >= MODERATE_THRESHOLD:
        return "Moderate"
    return "Weak"


def summarize_coverage(evidence_coverage: list[dict[str, object]]) -> dict[str, list[str]]:
    """Group evidence criteria by coverage level."""
    grouped = {"strong_areas": [], "moderate_areas": [], "weak_areas": []}
    for item in evidence_coverage:
        area = str(item.get("Evidence Area", ""))
        level = str(item.get("Coverage Level", "Weak"))
        if level == "Strong":
            grouped["strong_areas"].append(area)
        elif level == "Moderate":
            grouped["moderate_areas"].append(area)
        else:
            grouped["weak_areas"].append(area)
    return grouped


def interpretation_for_criterion(
    criterion: str,
    coverage_level: str,
    section_name: str,
) -> str:
    """Create a plain-language interpretation for one section-specific criterion."""
    section = normalize_section_name(section_name)
    if coverage_level == "Strong":
        return f"{criterion} is clearly supported in the {section.lower()} section."
    if coverage_level == "Moderate":
        return f"{criterion} is partly present, but the {section.lower()} section would benefit from clearer evidence."
    return f"{criterion} is weak or unclear for the expected content of the {section.lower()} section."
