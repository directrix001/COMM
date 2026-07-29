"""
Diff engine.

Pipeline for comparing two SOP text bodies:

  1. normalize_lines()   -- split into clean, comparable lines
  2. SequenceMatcher      -- find which lines were kept / added / removed / replaced
  3. classify_change()    -- tag each change block: numeric_threshold / routing_ownership
                             / process / wording
  4. score_severity()     -- critical / moderate / minor, based on the change type
  5. explain_change()     -- plain-language explanation (rule-based by default;
                             swaps to gpt-4o-mini automatically if OPENAI_API_KEY is set)

This is intentionally rule-based end to end so it runs with zero external
dependencies. `ai_explain.py` is the single seam where the AI/RAG layer
(embeddings + gpt-4o-mini) plugs in — see that file's docstring.
"""
import difflib
import re
from dataclasses import dataclass
from typing import List, Optional

from .models import ChangeType, Severity
from .ai_explain import generate_explanation

HEADING_PATTERN = re.compile(r"^\s*(STEP\s*\d+|SECTION\s*\d+|\d+[\.\)])", re.IGNORECASE)

NUMERIC_PATTERN = re.compile(r"\$\s?\d[\d,]*(\.\d+)?|\d+(\.\d+)?\s?%|\b\d+(\.\d+)?\b")

ROUTING_KEYWORDS = [
    "approve", "approval", "route", "routed", "routing", "notify", "notified",
    "cc ", "cc:", "escalate", "escalation", "sign-off", "sign off", "reviewer",
    "owner", "lead", "manager", "mailbox", "stakeholder", "send to", "forward to",
]


@dataclass
class RawChangeBlock:
    tag: str                 # 'replace' | 'insert' | 'delete'
    old_text: Optional[str]
    new_text: Optional[str]
    section_label: Optional[str]


def normalize_lines(text: str) -> List[str]:
    lines = [ln.strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln]


def _nearest_heading(lines: List[str], index: int) -> Optional[str]:
    for i in range(index, -1, -1):
        if HEADING_PATTERN.match(lines[i]):
            return lines[i][:120]
    return None


def _extract_numbers(text: str) -> List[str]:
    return [m.group(0) for m in NUMERIC_PATTERN.finditer(text)]


def _strip_numbers(text: str) -> str:
    return NUMERIC_PATTERN.sub("#", text)


def classify_change(old_text: str, new_text: str, tag: str) -> ChangeType:
    old_text = old_text or ""
    new_text = new_text or ""
    combined = f"{old_text} {new_text}".lower()

    # 1. Numbers changed but the surrounding words are basically the same
    #    -> a threshold/amount/date was tuned, not a rewrite.
    if old_text and new_text:
        old_numbers = _extract_numbers(old_text)
        new_numbers = _extract_numbers(new_text)
        if old_numbers != new_numbers:
            skeleton_ratio = difflib.SequenceMatcher(
                None, _strip_numbers(old_text), _strip_numbers(new_text)
            ).ratio()
            if skeleton_ratio > 0.75:
                return ChangeType.numeric_threshold

    # 2. Approval / notification / ownership language touched
    if any(kw in combined for kw in ROUTING_KEYWORDS):
        return ChangeType.routing_ownership

    # 3. A whole step was added or removed, or heavily rewritten
    if tag in ("insert", "delete"):
        return ChangeType.process
    if old_text and new_text:
        ratio = difflib.SequenceMatcher(None, old_text.lower(), new_text.lower()).ratio()
        if ratio < 0.55:
            return ChangeType.process

    # 4. Otherwise it's phrasing/formatting only
    return ChangeType.wording


def score_severity(change_type: ChangeType, tag: str) -> Severity:
    if change_type == ChangeType.numeric_threshold:
        return Severity.critical
    if change_type == ChangeType.routing_ownership:
        return Severity.moderate
    if change_type == ChangeType.process:
        return Severity.critical if tag == "delete" else Severity.moderate
    return Severity.minor


def diff_texts(old_text: str, new_text: str) -> List[dict]:
    """
    Compare two SOP bodies and return a list of change dicts, each with:
    section_label, change_type, severity, old_text, new_text, explanation.
    Lines that are unchanged between versions are not returned.
    """
    old_lines = normalize_lines(old_text)
    new_lines = normalize_lines(new_text)

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    results = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        old_chunk = "\n".join(old_lines[i1:i2]) or None
        new_chunk = "\n".join(new_lines[j1:j2]) or None

        anchor_index = j1 if j1 < len(new_lines) else max(0, len(new_lines) - 1)
        section_label = _nearest_heading(new_lines, anchor_index) if new_lines else None
        if section_label is None and old_lines:
            section_label = _nearest_heading(old_lines, min(i1, len(old_lines) - 1))

        change_type = classify_change(old_chunk or "", new_chunk or "", tag)
        severity = score_severity(change_type, tag)
        explanation = generate_explanation(old_chunk, new_chunk, change_type, section_label)

        results.append({
            "section_label": section_label,
            "change_type": change_type,
            "severity": severity,
            "old_text": old_chunk,
            "new_text": new_chunk,
            "explanation": explanation,
        })

    return results
