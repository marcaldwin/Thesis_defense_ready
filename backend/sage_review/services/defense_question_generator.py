"""Section-specific defense question generation for SAGE-Review."""


SECTION_DEFENSE_QUESTIONS = {
    "Abstract": [
        "What is the main problem addressed by the study?",
        "What method was used to develop and evaluate the system?",
        "What were the key results?",
        "What conclusion is directly supported by the findings?",
    ],
    "Introduction": [
        "What specific research gap does your study address?",
        "Why is this problem important?",
        "Who benefits from the proposed system?",
        "How do your objectives respond to the identified gap?",
    ],
    "Objectives of the Study": [
        "How does each objective connect to a method and result?",
        "Which objective is hardest to validate and why?",
        "What measurable output proves each objective was achieved?",
    ],
    "Literature Review": [
        "Which related study is closest to your work?",
        "What limitation in previous work does your study address?",
        "How did the reviewed studies influence your chosen method?",
    ],
    "Methodology": [
        "How was the dataset collected and prepared?",
        "How did you validate the model?",
        "Why did you choose this model or technique?",
        "How can another researcher reproduce your process?",
    ],
    "Results and Discussion": [
        "What metrics prove your system performance?",
        "What caused the weakest results?",
        "How did prototype testing perform?",
        "How do the results answer each objective?",
    ],
    "Conclusion": [
        "Which results support your conclusion?",
        "What are the limitations of the study?",
        "What should be improved in future work?",
        "What should not be overclaimed based on your findings?",
    ],
    "Limitations": [
        "Which limitation most affects real-world use?",
        "How would you address this limitation in future work?",
        "Which constraints should users know before applying the system?",
    ],
}


CRITERION_QUESTIONS = {
    "Research Gap": "What exact gap in previous work does this study address?",
    "Dataset Description": "What is the source, size, and structure of your dataset?",
    "Participant or Sample Description": "How were participants or samples selected?",
    "Data Collection Procedure": "How did you ensure the data collection process was reliable?",
    "Model or Algorithm Description": "Why is this model or algorithm appropriate for the problem?",
    "Evaluation Metrics": "Why are these evaluation metrics appropriate for your objectives?",
    "Model Evaluation Metrics": "What metrics prove your system performance?",
    "Confusion Matrix or Error Analysis": "What error patterns appeared and how do you explain them?",
    "Latency or Response Time Results": "How did you verify response time or processing speed?",
    "Usability Evaluation Results": "How did usability testing support the usefulness of the prototype?",
    "Limitations": "Which limitation most affects interpretation of the findings?",
    "Avoidance of Overclaims": "Which claims should be limited based on your actual results?",
}


def generate_section_defense_questions(
    section_name: str,
    weak_areas: list[str] | None = None,
    risk_level: str | None = None,
) -> list[str]:
    """Return section-specific and weak-area-specific defense questions."""
    questions = list(SECTION_DEFENSE_QUESTIONS.get(section_name, []))
    for area in weak_areas or []:
        question = CRITERION_QUESTIONS.get(area)
        if question:
            questions.append(question)
    if risk_level == "High":
        questions.append("What evidence should be added first before defense?")
    return list(dict.fromkeys(questions))[:8]
