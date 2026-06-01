import os
import json
from google import genai
from google.genai import types

def generate_gemini_feedback(
    section_name: str,
    section_text: str,
    top_weak_areas: list[str],
    defense_score: int,
    risk_level: str,
    evidence_coverage: list[dict]
) -> dict:
    """
    Generate dynamic feedback using the Gemini API.
    Returns a dictionary matching the schema. If it fails or is disabled,
    returns {"feedback_mode": "Template fallback"}.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    llm_enabled = os.getenv("LLM_FEEDBACK_ENABLED", "false").lower() == "true"
    
    if not llm_enabled or not api_key:
        return {"feedback_mode": "Template fallback"}

    try:
        client = genai.Client(api_key=api_key)
        
        # Prepare evidence context
        evidence_summary = []
        for e in evidence_coverage:
            area = e.get("Evidence Area", "Unknown Area")
            level = e.get("Coverage Level", "Weak")
            score = e.get("Similarity Score", 0.0)
            evidence_summary.append(f"- {area}: {level} ({score:.3f})")
        evidence_str = "\n".join(evidence_summary)
        
        # Limit text preview to avoid exceeding prompt size limits
        text_preview = section_text[:3000] + ("..." if len(section_text) > 3000 else "")
        
        prompt = f"""
You are an expert academic thesis defense coach. Review the following thesis section and provide dynamic feedback.
Your goal is to help the student improve their defense readiness.

SECTION NAME: {section_name}
CURRENT SCORE: {defense_score}/100
RISK LEVEL: {risk_level}

WEAK AREAS TO ADDRESS:
{', '.join(top_weak_areas) if top_weak_areas else 'None'}

EVIDENCE COVERAGE SCORES:
{evidence_str}

SECTION EXCERPT:
{text_preview}

Based on the above, provide your analysis in JSON format with exactly the following keys:
- "feedback_mode": strictly the string "Gemini-grounded"
- "dynamic_diagnosis": A clear, plain-language paragraph explaining what is good and what needs improvement based on the evidence.
- "dynamic_next_best_action": One actionable sentence instructing the student what to fix first.
- "dynamic_panel_risk": One sentence explaining what a defense panel is likely to criticize based on the weak areas.
- "dynamic_suggested_revision_wording": A list of up to 3 specific sentences the student could add or revise to fix the weak areas.
- "dynamic_defense_questions": A list of up to 3 challenging questions a panelist might ask regarding this section.

CRITICAL INSTRUCTIONS:
1. DO NOT invent data, citations, participant counts, accuracy values, adviser approval, or expert validation.
2. If evidence or metrics are missing, you MUST use placeholders like [number], [metric], [result], [table number].
3. Ensure the output is strictly valid JSON without markdown wrapping.
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4,
            ),
        )
        
        try:
            result = json.loads(response.text)
            # Validate required keys
            required_keys = ["feedback_mode", "dynamic_diagnosis", "dynamic_next_best_action", "dynamic_panel_risk", "dynamic_suggested_revision_wording", "dynamic_defense_questions"]
            for key in required_keys:
                if key not in result:
                    raise ValueError(f"Missing key {key}")
            
            result["feedback_mode"] = "Gemini-grounded"
            return result
        except json.JSONDecodeError:
            print("Gemini API Error: Invalid JSON response")
            return {"feedback_mode": "Template fallback"}
        except ValueError as e:
            print(f"Gemini API Error: {e}")
            return {"feedback_mode": "Template fallback"}

    except Exception as e:
        print(f"Gemini API Error: {str(e)}")
        return {"feedback_mode": "Template fallback"}
