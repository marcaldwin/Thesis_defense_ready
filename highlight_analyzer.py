"""Contextual Overclaim and Vague Wording Highlighting for SAGE-Review.

Detects risky, vague, or unsupported claims in manuscript sections
without altering existing semantic scoring or analysis features.
"""

import re

OVERCLAIM_WORDS = {
    "fully solves", "guarantees", "guaranteed", "always", "never",
    "completely", "perfectly", "100%", "all users", "all students",
    "no errors", "eliminates", "proves", "real-time", "universal",
    "highly accurate", "effective without clear metric", "successful without clear metric"
}

VAGUE_EVIDENCE_WORDS = {
    "good results", "effective", "efficient", "successful", "reliable",
    "fast", "accurate", "useful", "better", "improved", "strong performance",
    "acceptable", "high performance"
}

MEASURABLE_EVIDENCE_WORDS = {
    "accuracy", "precision", "recall", "f1-score", "f1", "mean",
    "standard deviation", "p-value", "r =", "respondents", "participants",
    "trials", "seconds", "%", "table", "figure", "confusion matrix",
    "usability score", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"
}

NEEDS_SUPPORT_WORDS = {
    "this indicates", "this shows", "this proves", "this means",
    "therefore", "as a result"
}


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences safely by punctuation and paragraphs."""
    # Split by newlines first to preserve paragraph bounds
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    sentences = []
    
    for p in paragraphs:
        # Split by ., ?, ! followed by space or end of string
        parts = re.split(r'(?<=[.!?])\s+', p)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Ignore very short sentences under 5 words
            word_count = len(part.split())
            if word_count >= 5:
                sentences.append(part)
                
    return sentences


def _contains_words(text: str, word_set: set[str]) -> bool:
    """Check if the text contains any of the words/phrases in the set."""
    lower_text = text.lower()
    for word in word_set:
        if word in lower_text:
            return True
    return False


def _contains_measurable_evidence(text: str) -> bool:
    """Check if text contains numbers, metrics, or evidence keywords."""
    lower_text = text.lower()
    
    # Check for digits
    if any(char.isdigit() for char in lower_text):
        return True
        
    for word in MEASURABLE_EVIDENCE_WORDS:
        if word in lower_text:
            return True
            
    return False


def analyze_contextual_highlights(section_name: str, section_text: str, weak_areas: list[str] = None) -> dict:
    """Detect overclaims, vague evidence, and unsupported claims in a section."""
    sentences = _split_into_sentences(section_text)
    highlights = []
    
    for sentence in sentences:
        # 1. Overclaim Risk
        if _contains_words(sentence, OVERCLAIM_WORDS):
            highlights.append({
                "highlight_type": "Overclaim Risk",
                "severity": "High",
                "text": sentence,
                "reason": "This statement may overclaim because it makes a strong claim without showing measurable evidence or scope limitations.",
                "suggested_revision": "Use safe wording: \"Within the scope of this study, [claim] was observed based on [evidence/metric].\""
            })
            continue # Prioritize highest severity
            
        # 2. Needs Support Detection
        if _contains_words(sentence, NEEDS_SUPPORT_WORDS):
            if not _contains_measurable_evidence(sentence):
                highlights.append({
                    "highlight_type": "Needs Support",
                    "severity": "Medium",
                    "text": sentence,
                    "reason": "The claim may need clearer connection to specific findings or evidence.",
                    "suggested_revision": "Connect this claim to a specific result, table, metric, or observed finding."
                })
                continue
                
        # 3. Vague Evidence Detection
        if _contains_words(sentence, VAGUE_EVIDENCE_WORDS):
            if not _contains_measurable_evidence(sentence):
                highlights.append({
                    "highlight_type": "Vague Evidence",
                    "severity": "Medium",
                    "text": sentence,
                    "reason": "This statement is related to performance or quality but does not provide measurable evidence.",
                    "suggested_revision": "Add a measurable value or reference to a result table, such as [metric], [score], [number of trials], or [table number]."
                })
                
    # Sort highlights by severity (High first)
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    highlights.sort(key=lambda h: severity_order.get(h["severity"], 3))
    
    # Return top 5 highlights per section
    return {
        "section_name": section_name,
        "highlights": highlights[:5]
    }
