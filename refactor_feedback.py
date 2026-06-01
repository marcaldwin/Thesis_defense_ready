import re

with open("feedback_generator.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Remove SECTION_EXPECTED_AREAS
text = re.sub(r"SECTION_EXPECTED_AREAS = \{.*?\n\}\n+", "", text, flags=re.DOTALL)

# 2. Update generate_priority_fixes to use get_section_specific_criteria
text = text.replace(
    "expected_areas = SECTION_EXPECTED_AREAS.get(predicted_section, set())",
    "expected_areas = set(get_section_specific_criteria(predicted_section).keys())"
)

# 3. Remove hardcoded Abstract check in generate_priority_fixes
text = re.sub(
    r"        if predicted_section == \"Abstract\" and area not in \{.*?        \}:\n            continue\n+",
    "",
    text,
    flags=re.DOTALL
)

text = re.sub(r"AREA_FIX_GUIDANCE = \{.*?\n\}\n+", "AREA_FIX_GUIDANCE = {}\n\n", text, flags=re.DOTALL)
text = re.sub(r"AREA_IMPORTANCE = \{.*?\n\}\n+", "AREA_IMPORTANCE = {}\n\n", text, flags=re.DOTALL)

new_templates = """    templates = {
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
    }"""
text = re.sub(r"    templates = \{.*?    \}\n", new_templates + "\n", text, flags=re.DOTALL)

with open("feedback_generator.py", "w", encoding="utf-8") as f:
    f.write(text)
