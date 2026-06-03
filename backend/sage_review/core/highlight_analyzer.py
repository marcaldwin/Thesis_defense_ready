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

DATA_HANDLING_WORDS = {
    "confidentiality", "confidential", "rename", "renamed", "coded",
    "participant code", "without using real names", "identity", "anonymized",
    "anonymous", "privacy"
}

CONFIDENTIALITY_GUARANTEE_WORDS = {
    "guarantees anonymity", "fully protects identity", "completely secure",
    "impossible to identify", "100% confidential"
}

CITATION_PATTERNS = [
    r"\([A-Z][A-Za-z-]+(?:\s+et\s+al\.)?,\s*\d{4}\)",
    r"\bet al\.\b",
    r"\baccording to\b",
    r"\bas stated by\b",
    r"\bcited by\b",
    r"\bbased on\b.{0,60}\b(study|studies|source|literature)\b",
]

SOFTENING_WORDS = {
    "may", "can", "might", "within the scope", "based on the results",
    "observed", "suggests", "suggest", "indicates", "indicate", "appears",
    "was observed", "were observed"
}

RESULT_CLAIM_WORDS = {
    "recognized", "recognised", "confused", "classified", "detected",
    "performed", "consistent", "consistently", "results showed",
    "results indicate", "findings show"
}

STRONG_UNSUPPORTED_WORDS = {
    "proves", "guarantees", "guaranteed", "always", "completely solves",
    "fully eliminates", "highly accurate", "reliable for all users",
    "works in all real-world conditions", "100% accurate", "no errors",
    "fully solves", "universal", "perfectly"
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


def _has_citation_evidence(text: str) -> bool:
    """Detect common citation signals in academic claims."""
    return any(re.search(pattern, text, flags=re.I) for pattern in CITATION_PATTERNS)


def _build_highlight(
    claim_category: str,
    severity: str,
    sentence: str,
    reason: str,
    suggested_revision: str,
) -> dict[str, str]:
    """Build a frontend-compatible highlight with an explicit category."""
    highlight_type = (
        "Overclaim Risk"
        if claim_category == "Strong Unsupported Overclaim"
        else claim_category
    )
    return {
        "highlight_type": highlight_type,
        "claim_category": claim_category,
        "category": claim_category,
        "severity": severity,
        "risk_level": severity,
        "text": sentence,
        "quoted_sentence": sentence,
        "reason": reason,
        "why_flagged": reason,
        "suggested_revision": suggested_revision,
        "suggested_action": suggested_revision,
    }


def classify_claim(sentence: str) -> dict[str, str] | None:
    """Classify a highlighted sentence before assigning overclaim risk."""
    lower_sentence = sentence.lower()
    has_metric = _contains_measurable_evidence(sentence)
    has_citation = _has_citation_evidence(sentence)
    has_softening = _contains_words(sentence, SOFTENING_WORDS)
    has_strong_overclaim = _contains_words(sentence, STRONG_UNSUPPORTED_WORDS)
    has_data_handling = _contains_words(sentence, DATA_HANDLING_WORDS)

    if has_data_handling:
        if _contains_words(sentence, CONFIDENTIALITY_GUARANTEE_WORDS):
            return _build_highlight(
                "Strong Unsupported Overclaim",
                "High",
                sentence,
                "This data-handling statement uses absolute privacy or anonymity language that needs strong proof.",
                "Describe the actual confidentiality procedure without guaranteeing anonymity or perfect security.",
            )
        return _build_highlight(
            "Data Handling Statement",
            "Low",
            sentence,
            "This describes a data handling or confidentiality procedure, not a strong empirical overclaim.",
            "Keep the procedure factual and avoid absolute privacy guarantees.",
        )

    if has_citation:
        return _build_highlight(
            "Citation-Supported Claim",
            "Low",
            sentence,
            "This claim includes citation evidence, so it should not be treated as a high unsupported overclaim.",
            "Keep the citation and make sure the reference actually supports the statement.",
        )

    if has_softening and not has_strong_overclaim:
        return _build_highlight(
            "Limitation Statement",
            "Low",
            sentence,
            "This statement uses cautious wording that limits the claim scope.",
            "Keep the cautious wording and connect it to the relevant result or limitation.",
        )

    if has_strong_overclaim:
        return _build_highlight(
            "Strong Unsupported Overclaim",
            "High",
            sentence,
            "This statement makes a strong unsupported empirical, performance, generalization, reliability, or guarantee claim.",
            "Use scoped wording and add measurable evidence, such as a metric, table, sample size, or test condition.",
        )

    if _contains_words(sentence, RESULT_CLAIM_WORDS) and not has_metric:
        return _build_highlight(
            "Result Claim Needing Metric",
            "Medium",
            sentence,
            "This result interpretation needs measurable support before it can be defended confidently.",
            "Add measurable support, such as accuracy, confusion matrix reference, table number, or number of test cases.",
        )

    if _contains_words(sentence, NEEDS_SUPPORT_WORDS) and not has_metric:
        return _build_highlight(
            "Vague Evidence",
            "Medium",
            sentence,
            "The claim needs a clearer connection to specific findings or evidence.",
            "Connect this claim to a specific result, table, metric, or observed finding.",
        )

    if _contains_words(sentence, VAGUE_EVIDENCE_WORDS) and not has_metric:
        return _build_highlight(
            "Vague Evidence",
            "Medium",
            sentence,
            "This statement is related to performance or quality but does not provide measurable evidence.",
            "Add a measurable value or reference to a result table, such as a metric, score, number of trials, or table number.",
        )

    if "real-time" in lower_sentence and not has_metric:
        return _build_highlight(
            "Methodology Statement",
            "Medium",
            sentence,
            "Real-time behavior should be supported with timing or deployment evidence.",
            "Add measured latency, response time, device conditions, or a table reference.",
        )

    return None


def analyze_contextual_highlights(section_name: str, section_text: str, weak_areas: list[str] = None) -> dict:
    """Detect overclaims, vague evidence, and unsupported claims in a section."""
    sentences = _split_into_sentences(section_text)
    highlights = []
    
    for sentence in sentences:
        highlight = classify_claim(sentence)
        if highlight is not None:
            highlights.append(highlight)
                
    # Sort highlights by severity (High first)
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    highlights.sort(key=lambda h: severity_order.get(h["severity"], 3))
    
    # Return top 5 highlights per section
    return {
        "section_name": section_name,
        "highlights": highlights[:5]
    }
