"""Automatic thesis section extraction for SAGE-Review.

The extractor separates *major* thesis section headings from numbered
subsections, figure/table captions, and front matter pages. It also:

* Merges split multi-line major headings
  (e.g., ``RESULTS AND\\nDISCUSSION`` → ``RESULTS AND DISCUSSION``).
* Uses a lookahead window so a bare ``CHAPTER N`` line inherits its
  following titled major heading.
* Falls back to extracting an Objectives passage from the Introduction
  when no Objectives heading exists.

Each detected heading carries a ``status`` field so the UI can show only
major headings by default and put noise (captions, minor subsections,
front matter) inside a collapsed debug panel.
"""

from __future__ import annotations

import re


SECTION_ORDER = [
    "Abstract",
    "Introduction",
    "Objectives of the Study",
    "Literature Review",
    "Methodology",
    "Results and Discussion",
    "Limitations",
    "Conclusion",
]

MAJOR_REQUIRED_SECTIONS = [
    "Objectives of the Study",
    "Methodology",
    "Results and Discussion",
    "Conclusion",
]

CHAPTER_TO_SECTION: dict[int, str] = {
    1: "Introduction",
    2: "Literature Review",
    3: "Methodology",
    4: "Results and Discussion",
    5: "Conclusion",
}


# ---------------------------------------------------------------------
# Strict major-heading patterns (must match the whole normalized line)
# ---------------------------------------------------------------------

_MAJOR_HEADING_PATTERNS: list[tuple[str, list[str]]] = [
    ("Abstract", [r"^abstract$"]),
    ("Introduction", [
        r"^introduction$",
        r"^background of the study$",
        r"^problem statement$",
        r"^introduction and problem formulation$"
    ]),
    ("Objectives of the Study", [
        r"^objectives$",
        r"^objectives of the study$",
        r"^project objectives$",
        r"^specific objectives$"
    ]),
    ("Literature Review", [
        r"^review of related literature$",
        r"^review of related studies$",
        r"^related literature$",
        r"^related studies$",
        r"^literature review$",
        r"^rrl$"
    ]),
    ("Methodology", [
        r"^methodology$",
        r"^research methodology$",
        r"^materials and methods$",
        r"^methods$",
        r"^implementation$"
    ]),
    ("Results and Discussion", [
        r"^results and discussion$",
        r"^results and discussions$",
        r"^result and discussion$",
        r"^result and discussions$",
        r"^results$",
        r"^result$",
        r"^discussion$",
        r"^discussions$",
        r"^findings$",
        r"^implementation, evaluation, and results$",
        r"^evaluation and results$"
    ]),
    ("Conclusion", [
        r"^summary,?\s*conclusions?,?\s*and\s*recommendations?$",
        r"^summary,?\s*conclusion\s*and\s*recommendation$",
        r"^summary,?\s*conclusion,?\s*and\s*recommendation$",
        r"^summary,?\s*conclusions?\s*and\s*recommendations?$",
        r"^conclusions?\s*and\s*recommendations?$",
        r"^summary and conclusions?$",
        r"^summary and conclusion$",
        r"^conclusions?$",
        r"^conclusion$",
        r"^conclusion and recommendation$",
        r"^conclusion and recommendations$",
        r"^conclusion and recomendation$",
        r"^conclusion and recomendations$",
        r"^recommendations?$",
        r"^recommendation$"
    ]),
    ("Ethics", [
        r"^ethics$",
        r"^responsible ai$",
        r"^ethics and responsible ai$"
    ]),
    ("References", [
        r"^references$",
        r"^reference$",
        r"^bibliography$"
    ]),
]

# Headings used by the merge / inject helpers to recover structure from
# manuscripts pasted as a single paragraph.
_CAPS_HEADINGS_FOR_BREAK = [
    "ABSTRACT",
    "INTRODUCTION",
    "REVIEW OF RELATED LITERATURE",
    "REVIEW OF RELATED STUDIES",
    "RELATED LITERATURE",
    "RELATED STUDIES",
    "LITERATURE REVIEW",
    "METHODOLOGY",
    "RESULTS AND DISCUSSION",
    "RESULTS AND DISCUSSIONS",
    "RESULT AND DISCUSSION",
    "RESULT AND DISCUSSIONS",
    "RESULTS",
    "RESULT",
    "FINDINGS",
    "SUMMARY, CONCLUSION, AND RECOMMENDATION",
    "SUMMARY, CONCLUSIONS, AND RECOMMENDATIONS",
    "SUMMARY, CONCLUSION AND RECOMMENDATION",
    "SUMMARY, CONCLUSIONS AND RECOMMENDATIONS",
    "SUMMARY AND CONCLUSIONS",
    "SUMMARY AND CONCLUSION",
]


# Chapter marker — supports arabic 1-5 and Roman I-V, optional inline title.
_CHAPTER_LINE = re.compile(
    r"^\s*chapter\s+([1-5]|iv|v|i{1,3})\b[\s:.\-]*(.*?)\s*$",
    re.I,
)

_ROMAN_TO_INT = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}


# Captions / figure references — never major headings.
_CAPTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*figure\s+\d+\b", re.I),
    re.compile(r"^\s*table\s+\d+\b", re.I),
    re.compile(r"^\s*fig\.\s*\d+\b", re.I),
    re.compile(r"\bscreen\s+displaying\b", re.I),
    re.compile(r"^\s*\d+\.?\s+results?\s+screen\b", re.I),
]


# Front matter / end matter — break sections but produce no section.
_FRONT_MATTER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^title\s+page$", re.I),
    re.compile(r"^approval\s+(?:sheet|page|of\s+manuscript)$", re.I),
    re.compile(r"^academic\s+integrity\b", re.I),
    re.compile(r"^biographical\s+(?:data|sketch)$", re.I),
    re.compile(r"^acknowledg(?:e)?ments?$", re.I),
    re.compile(r"^dedication$", re.I),
    re.compile(r"^table\s+of\s+contents$", re.I),
    re.compile(r"^list\s+of\s+(?:tables|figures|appendices|appendixes|symbols|abbreviations)$", re.I),
    re.compile(r"^literature\s+cited$", re.I),
    re.compile(r"^bibliography$", re.I),
    re.compile(r"^references$", re.I),
    re.compile(r"^works\s+cited$", re.I),
    re.compile(r"^appendi(?:x|ces|xes)\b", re.I),
    re.compile(r"^examining\s+committee\b", re.I),
    re.compile(r"^author(?:'?s)?\s+name$", re.I),
    re.compile(r"^degree\s+name$", re.I),
    re.compile(r"^vita$", re.I),
    re.compile(r"^curriculum\s+vitae$", re.I),
]


# Any "N." or "N.M." numbered line counts as a minor subsection unless it
# *also* matches a major pattern via stripped text.
_NUMBERED_LINE_RE = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+\S")


# Objectives fallback phrases — used inside the Introduction body.
OBJECTIVES_FALLBACK_PATTERNS = [
    r"\bthe\s+general\s+objective\b",
    r"\bgeneral\s+objective\s+of\s+this\s+study\b",
    r"\bspecifically,?\s+(?:this|the)\s+study\s+aims\b",
    r"\bthe\s+objectives?\s+of\s+this\s+study\b",
    r"\bspecific\s+objectives?\b",
    r"\bresearch\s+objectives?\b",
    r"\bresearch\s+questions?\b",
    r"\bstatement\s+of\s+the\s+problem\b",
    r"\bproblems?\s+of\s+the\s+study\b",
    r"\bthis\s+study\s+aims\b",
]


# Status constants
_STATUS_MAJOR = "Detected Major Heading"
_STATUS_CHAPTER = "Detected Chapter Marker"
_STATUS_MERGED = "Merged Split Heading"
_STATUS_CAPTION = "Ignored Caption"
_STATUS_FRONT = "Ignored Front Matter"
_STATUS_MINOR = "Ignored Minor Heading"
_STATUS_TOC = "Ignored Table of Contents Entry"
_STATUS_UNKNOWN = "Unknown"
_STATUS_FALLBACK = "Derived Subsection from Introduction"

_MAJOR_STATUSES = {_STATUS_MAJOR, _STATUS_CHAPTER, _STATUS_MERGED}
_SECTION_BREAK_STATUSES = _MAJOR_STATUSES | {_STATUS_FRONT}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _normalize_for_match(line: str) -> str:
    s = str(line or "").strip()
    s = re.sub(r"[.…·•‥⋯]+", " ", s)
    s = re.sub(r"[^A-Za-z, ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _match_major_section(line: str) -> str | None:
    """Return the major section name if ``line`` matches strictly."""
    clean = _normalize_for_match(line)
    if not clean:
        return None
    for section, patterns in _MAJOR_HEADING_PATTERNS:
        for pattern in patterns:
            if re.match(pattern, clean):
                return section
    return None


def _is_caption(line: str) -> bool:
    s = str(line or "").strip()
    return any(p.search(s) for p in _CAPTION_PATTERNS)


def _is_front_matter(line: str) -> bool:
    clean = _normalize_for_match(line)
    if not clean:
        return False
    return any(p.match(clean) for p in _FRONT_MATTER_PATTERNS)


def _is_numbered_minor(line: str) -> bool:
    return _NUMBERED_LINE_RE.match(str(line or "")) is not None


def _is_toc_entry(line: str) -> bool:
    """Return True for table-of-contents leader/page-number entries."""
    s = str(line or "").strip()
    if not s:
        return False

    leader_chars = sum(1 for char in s if char in ".…·•‥⋯")
    has_dot_leader = re.search(r"\.{5,}", s) is not None
    has_many_leaders = leader_chars >= 5
    ends_with_page_number = re.search(r"(?:[.…·•‥⋯\s])+\d+\s*$", s) is not None
    return has_dot_leader or has_many_leaders or (ends_with_page_number and leader_chars >= 2)


def _chapter_number(token: str) -> int | None:
    t = (token or "").strip().lower()
    if t.isdigit():
        n = int(t)
        return n if 1 <= n <= 5 else None
    return _ROMAN_TO_INT.get(t)


# ---------------------------------------------------------------------
# Pre-processing
# ---------------------------------------------------------------------

def clean_manuscript_text(text: str) -> str:
    """Clean the manuscript text by removing noise before section extraction."""
    lines = text.splitlines()
    cleaned = []

    skip_exact = {
        "table of contents",
        "list of figures",
        "list of tables",
        "page"
    }

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if not stripped:
            cleaned.append("")
            continue

        if lower in skip_exact:
            continue

        if stripped.isdigit():
            continue

        cleaned.append(stripped)

    return "\n".join(cleaned)

def _merge_split_headings(text: str) -> str:
    """Join multi-line variants of compound major headings into one line."""
    if not text:
        return text

    # 3-line: SUMMARY, / CONCLUSIONS, AND / RECOMMENDATIONS
    text = re.sub(
        r"^[ \t]*(SUMMARY,?)[ \t]*\n[ \t]*(CONCLUSIONS?,?[ \t]*AND)[ \t]*\n[ \t]*(RECOMMENDATIONS?)[ \t]*$",
        r"\1 \2 \3",
        text,
        flags=re.M | re.I,
    )
    # 2-line: SUMMARY, / CONCLUSION, AND RECOMMENDATION
    text = re.sub(
        r"^[ \t]*(SUMMARY,?)[ \t]*\n[ \t]*(CONCLUSIONS?,?[ \t]*AND[ \t]*RECOMMENDATIONS?)[ \t]*$",
        r"\1 \2",
        text,
        flags=re.M | re.I,
    )
    # 2-line: SUMMARY, CONCLUSIONS, AND / RECOMMENDATIONS
    text = re.sub(
        r"^[ \t]*(SUMMARY,?[ \t]*CONCLUSIONS?,?[ \t]*AND)[ \t]*\n[ \t]*(RECOMMENDATIONS?)[ \t]*$",
        r"\1 \2",
        text,
        flags=re.M | re.I,
    )
    # 2-line: RESULTS AND / DISCUSSION
    text = re.sub(
        r"^[ \t]*(RESULTS[ \t]+AND)[ \t]*\n[ \t]*(DISCUSSIONS?)[ \t]*$",
        r"\1 \2",
        text,
        flags=re.M | re.I,
    )
    # 2-line: SUMMARY AND / CONCLUSION(S)
    text = re.sub(
        r"^[ \t]*(SUMMARY[ \t]+AND)[ \t]*\n[ \t]*(CONCLUSIONS?)[ \t]*$",
        r"\1 \2",
        text,
        flags=re.M | re.I,
    )
    # 2-line: CONCLUSION(S) AND / RECOMMENDATION(S)
    text = re.sub(
        r"^[ \t]*(CONCLUSIONS?[ \t]+AND)[ \t]*\n[ \t]*(RECOMMENDATIONS?)[ \t]*$",
        r"\1 \2",
        text,
        flags=re.M | re.I,
    )
    # 2-line: REVIEW OF RELATED / LITERATURE
    text = re.sub(
        r"^[ \t]*(REVIEW[ \t]+OF[ \t]+RELATED)[ \t]*\n[ \t]*(LITERATURE|STUDIES)[ \t]*$",
        r"\1 \2",
        text,
        flags=re.M | re.I,
    )
    return text


def _inject_heading_breaks(text: str) -> str:
    """Insert newlines before known caps headings and CHAPTER N markers.

    Helps when a manuscript was pasted as one long paragraph. Idempotent.
    """
    if not text:
        return text

    text = re.sub(
        r"(?<!\n)\s+(?=CHAPTER\s+(?:[1-5]|IV|V|I{1,3})\b)",
        "\n",
        text,
        flags=re.I,
    )
    for heading in _CAPS_HEADINGS_FOR_BREAK:
        escaped = re.escape(heading)
        text = re.sub(
            rf"(?<!\n)\s+(?={escaped}(?=\s|$|[.,:]))",
            "\n",
            text,
        )
    return text


# ---------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------

def _looks_like_heading(stripped: str) -> bool:
    s = stripped.strip()
    if not s:
        return False
    if len(s) > 220:
        return False
    heading_part = re.split(r"[.…·•‥⋯]{2,}", s, maxsplit=1)[0].strip()
    word_count = len(heading_part.split())
    if word_count == 0 or word_count > 14:
        return False
    if s[-1] in "?!":
        return False
    return True


def _classify_heading(stripped: str) -> tuple[str | None, str, int | None]:
    """Classify one non-empty, heading-shaped line.

    Returns ``(normalized_section_or_None, status, chapter_number_or_None)``.
    """
    if _is_toc_entry(stripped):
        toc_label = re.split(r"[.…·•‥⋯]{2,}", stripped, maxsplit=1)[0]
        toc_label = re.sub(r"\s+\d+\s*$", "", toc_label).strip()
        return _match_major_section(toc_label), _STATUS_TOC, None

    if _is_caption(stripped):
        return None, _STATUS_CAPTION, None

    if _is_front_matter(stripped):
        return None, _STATUS_FRONT, None

    chap_match = _CHAPTER_LINE.match(stripped)
    if chap_match:
        chap_num = _chapter_number(chap_match.group(1))
        inline_title = chap_match.group(2).strip()
        if inline_title:
            inline_section = _match_major_section(inline_title)
            if inline_section:
                return inline_section, _STATUS_CHAPTER, chap_num
            if len(inline_title.split()) > 4:
                return None, _STATUS_UNKNOWN, None
        return None, _STATUS_CHAPTER, chap_num

    major = _match_major_section(stripped)
    if major:
        if major == "Conclusion" and _normalize_for_match(stripped).startswith("summary"):
            return major, _STATUS_MERGED, None
        return major, _STATUS_MAJOR, None

    if _is_numbered_minor(stripped):
        return None, _STATUS_MINOR, None

    return None, _STATUS_UNKNOWN, None


def _detect_headings(text: str) -> list[dict[str, object]]:
    detected: list[dict[str, object]] = []
    offset = 0
    in_toc_region = False
    for line_num, line in enumerate(text.splitlines(keepends=True), start=1):
        line_start = offset
        line_end = offset + len(line)
        offset = line_end
        stripped = line.strip()
        if not stripped:
            continue
        if not _looks_like_heading(stripped):
            continue
        normalized, status, chap_num = _classify_heading(stripped)
        clean_line = _normalize_for_match(stripped)

        if status == _STATUS_FRONT and clean_line == "table of contents":
            in_toc_region = True
        elif in_toc_region and status == _STATUS_FRONT and re.match(
            r"^list of (figures|tables|appendices|appendixes|symbols|abbreviations)$",
            clean_line,
        ):
            in_toc_region = False
        elif (
            in_toc_region
            and status in _MAJOR_STATUSES
            and normalized == "Abstract"
        ):
            in_toc_region = False
        elif in_toc_region and status in _MAJOR_STATUSES | {_STATUS_UNKNOWN, _STATUS_MINOR}:
            status = _STATUS_TOC
            if normalized is None:
                normalized = _match_major_section(stripped)

        detected.append(
            {
                "raw_heading": stripped,
                "normalized_section": normalized or "Unknown",
                "line_number": line_num,
                "status": status,
                "chapter": chap_num,
                "heading_start": line_start,
                "content_start": line_end,
            }
        )
    return detected


def _attach_chapters_to_titles(detected: list[dict[str, object]]) -> None:
    """Bare ``CHAPTER N`` entries inherit the next titled major heading.

    Falls back to ``CHAPTER_TO_SECTION`` if no titled heading follows the
    chapter marker within 10 lines.
    """
    LINE_WINDOW = 10
    for index, entry in enumerate(detected):
        if entry["status"] != _STATUS_CHAPTER:
            continue
        if entry["normalized_section"] != "Unknown":
            continue  # Inline title already supplied the section
        chap_line = int(entry["line_number"])
        title_section: str | None = None
        for next_entry in detected[index + 1:]:
            if int(next_entry["line_number"]) - chap_line > LINE_WINDOW:
                break
            if next_entry["status"] == _STATUS_CHAPTER:
                break
            if next_entry["status"] == _STATUS_MAJOR:
                title_section = str(next_entry["normalized_section"])
                next_entry["status"] = _STATUS_MERGED
                break
        if title_section is None:
            chap_num = entry.get("chapter")
            if isinstance(chap_num, int):
                title_section = CHAPTER_TO_SECTION.get(chap_num)
        if title_section:
            entry["normalized_section"] = title_section


def _ignore_pre_body_major_headings(detected: list[dict[str, object]]) -> None:
    """Ignore major heading candidates that appear before the real body ABSTRACT.

    Front matter and table-of-contents pages often list INTRODUCTION,
    METHODOLOGY, RESULTS, and CONCLUSION before the manuscript body starts.
    When a real ABSTRACT heading is present, major candidates before that
    point are treated as debug-only TOC/front-matter entries.
    """
    abstract_indices = [
        index
        for index, entry in enumerate(detected)
        if entry["normalized_section"] == "Abstract"
        and entry["status"] in _MAJOR_STATUSES
    ]
    if not abstract_indices:
        return

    body_abstract_index = abstract_indices[-1]
    for entry in detected[:body_abstract_index]:
        if entry["status"] in _MAJOR_STATUSES:
            entry["status"] = _STATUS_TOC


# ---------------------------------------------------------------------
# Section building
# ---------------------------------------------------------------------

def _extract_sections(
    text: str,
    all_detected: list[dict[str, object]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Walk *all* detected headings; only major statuses produce sections.

    Captions and minor numbered subsections do not break a section so that
    paragraphs in between are still attributed to the parent major section.
    Front matter / references DO break the current section.
    """
    sections: dict[str, list[str]] = {}
    source_per_section: dict[str, str] = {}

    current_major: str | None = None
    current_start: int = 0
    current_source: str | None = None

    def close(end_pos: int) -> None:
        nonlocal current_major, current_source
        if current_major is None:
            return
        body = text[current_start:end_pos].strip()
        if body:
            sections.setdefault(current_major, []).append(body)
            if current_source == "heading":
                source_per_section[current_major] = "heading"
            elif source_per_section.get(current_major) != "heading":
                source_per_section[current_major] = "chapter"
        current_major = None
        current_source = None

    for head in all_detected:
        status = str(head["status"])
        if status not in _SECTION_BREAK_STATUSES:
            continue
        close(int(head["heading_start"]))
        if status in _MAJOR_STATUSES:
            normalized = str(head["normalized_section"])
            if normalized in {"Unknown", "References"}:
                continue
            current_major = normalized
            current_start = int(head["content_start"])
            current_source = (
                "heading"
                if status in {_STATUS_MAJOR, _STATUS_MERGED}
                else "chapter"
            )
        # Front matter: section already closed; no new section starts.

    close(len(text))

    merged = {name: "\n\n".join(parts) for name, parts in sections.items()}
    return merged, source_per_section


# ---------------------------------------------------------------------
# Objectives fallback
# ---------------------------------------------------------------------

def extract_objectives_fallback(text: str, window_words: int = 400) -> str:
    """Extract a likely objectives passage when no Objectives heading exists.

    Looks for objective-related phrases and returns a window of roughly
    ``window_words`` words around the first hit.
    """
    clean_text = str(text or "").strip()
    if not clean_text:
        return ""
    for pattern in OBJECTIVES_FALLBACK_PATTERNS:
        match = re.search(pattern, clean_text, flags=re.I)
        if not match:
            continue
        words_before = clean_text[: match.start()].split()
        words_after = clean_text[match.start():].split()
        before = words_before[-60:]
        after = words_after[:window_words]
        return " ".join(before + after).strip()
    return ""


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def normalize_heading(heading: str) -> str:
    """Backwards-compatible: map a single heading line to a known section."""
    return _match_major_section(heading) or "Unknown"


def _build_status_map(
    sections: dict[str, str],
    source_map: dict[str, str],
) -> dict[str, str]:
    status: dict[str, str] = {}
    for name in sections:
        src = source_map.get(name, "heading")
        if src == "heading":
            status[name] = "confidently extracted"
        elif src == "chapter":
            status[name] = "chapter fallback"
        elif src == "fallback":
            status[name] = "derived subsection from introduction"
        else:
            status[name] = "confidently extracted"
    return status


def _to_output(entry: dict[str, object]) -> dict[str, object]:
    """Convert an internal heading entry to the API-facing shape."""
    raw = str(entry["raw_heading"])
    normalized = str(entry["normalized_section"])
    return {
        "raw_heading": raw,
        "raw": raw,
        "normalized_section": normalized,
        "normalized": normalized,
        "line_number": int(entry["line_number"]),
        "status": str(entry["status"]),
        "chapter": entry.get("chapter"),
        "is_chapter_marker": str(entry["status"])
        in {_STATUS_CHAPTER, _STATUS_MERGED}
        and entry.get("chapter") is not None,
    }


def extract_sections_with_metadata(text: str) -> dict[str, object]:
    """Extract sections and return rich metadata for UI and debugging."""
    text = str(text or "")
    text = clean_manuscript_text(text)
    text = _merge_split_headings(text)
    text = _inject_heading_breaks(text)

    detected = _detect_headings(text)
    _attach_chapters_to_titles(detected)
    _ignore_pre_body_major_headings(detected)

    raw_sections, source_map = _extract_sections(text, detected)

    # Objectives fallback (prefer the Introduction body)
    fallback_used = False
    if "Objectives of the Study" not in raw_sections:
        intro_text = raw_sections.get("Introduction", "")
        fallback_text = extract_objectives_fallback(intro_text) if intro_text else ""
        if not fallback_text:
            fallback_text = extract_objectives_fallback(text)
        if fallback_text:
            raw_sections["Objectives of the Study"] = fallback_text
            source_map["Objectives of the Study"] = "fallback"
            fallback_used = True

    pruned_sections = {
        name: body
        for name, body in raw_sections.items()
        if len(body.split()) >= 10 or name == "Objectives of the Study"
    }

    ordered_sections = {
        name: pruned_sections[name]
        for name in SECTION_ORDER
        if name in pruned_sections
    }

    extraction_status = _build_status_map(ordered_sections, source_map)

    all_detected_out = [_to_output(h) for h in detected]
    major_detected_out = [
        _to_output(h) for h in detected if str(h["status"]) in _MAJOR_STATUSES
    ]

    if fallback_used and "Objectives of the Study" in ordered_sections:
        major_detected_out.append(
            {
                "raw_heading": "(extracted from Introduction)",
                "raw": "(extracted from Introduction)",
                "normalized_section": "Objectives of the Study",
                "normalized": "Objectives of the Study",
                "line_number": 0,
                "status": _STATUS_FALLBACK,
                "explanation": (
                    "The Objectives section was not detected as a standalone "
                    "major heading, so it was derived from the Introduction section."
                ),
                "chapter": None,
                "is_chapter_marker": False,
            }
        )

    sections_needing_review = [
        name
        for name, status in extraction_status.items()
        if status != "confidently extracted"
    ]
    missing_major_sections = [
        name for name in MAJOR_REQUIRED_SECTIONS if name not in ordered_sections
    ]

    return {
        "sections": ordered_sections,
        "extraction_status": extraction_status,
        "major_detected_headings": major_detected_out,
        "all_detected_headings": all_detected_out,
        "detected_headings": major_detected_out,  # backward-compat alias
        "sections_needing_review": sections_needing_review,
        "missing_major_sections": missing_major_sections,
    }


def extract_sections_from_manuscript(text: str) -> dict[str, str]:
    """Extract major thesis sections from full manuscript text using headings."""
    return extract_sections_with_metadata(text)["sections"]
