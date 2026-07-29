"""
Plain-language explanations for a detected change.

Default: a rule-based template, so the app runs with zero API cost/keys.

To switch a deployment on to gpt-4o-mini, set OPENAI_API_KEY (and optionally
OPENAI_MODEL) in the environment — generate_explanation() will use it
automatically, with the rule-based version as a fallback if the call fails.

This is also the natural place to add the RAG layer described earlier:
embed each SOP's sections with an embedding model (e.g. text-embedding-3-small),
store the vectors alongside SOPVersion, and use similarity search to match
sections between versions before diffing — instead of (or in addition to)
the line-position matching difflib does today. See `embed_sections()` below
for the stub to fill in.
"""
import os
from typing import Optional, List

from .models import ChangeType

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

_TEMPLATES = {
    ChangeType.numeric_threshold: (
        "A number changed from \"{old}\" to \"{new}\"{section}. Because this "
        "looks like a threshold, amount, or timing value, it can change what "
        "gets flagged or escalated even though the wording around it barely moved."
    ),
    ChangeType.routing_ownership: (
        "The approval/notification path changed{section}: "
        "{old_part}{new_part} A different person or team is now involved in this step."
    ),
    ChangeType.process: (
        "{action}{section}: \"{shown}\". This changes what someone actually "
        "has to do, not just how it's worded."
    ),
    ChangeType.wording: (
        "Phrasing or formatting changed{section}, with no apparent change to "
        "what the procedure requires."
    ),
}


def _section_suffix(section_label: Optional[str]) -> str:
    return f" (near \"{section_label}\")" if section_label else ""


def _rule_based_explanation(
    old_text: Optional[str], new_text: Optional[str],
    change_type: ChangeType, section_label: Optional[str]
) -> str:
    section = _section_suffix(section_label)

    if change_type == ChangeType.numeric_threshold:
        return _TEMPLATES[change_type].format(
            old=old_text or "(nothing)", new=new_text or "(removed)", section=section
        )

    if change_type == ChangeType.routing_ownership:
        old_part = f"it used to say \"{old_text}\". " if old_text else ""
        new_part = f"it now says \"{new_text}\"." if new_text else "that line was removed."
        return _TEMPLATES[change_type].format(section=section, old_part=old_part, new_part=new_part)

    if change_type == ChangeType.process:
        if old_text and new_text:
            action, shown = "A step was rewritten", new_text
        elif new_text:
            action, shown = "A new step was added", new_text
        else:
            action, shown = "A step was removed", old_text
        return _TEMPLATES[change_type].format(action=action, section=section, shown=shown)

    return _TEMPLATES[ChangeType.wording].format(section=section)


def _openai_explanation(
    old_text: Optional[str], new_text: Optional[str],
    change_type: ChangeType, section_label: Optional[str]
) -> Optional[str]:
    """Best-effort call to gpt-4o-mini. Returns None on any failure so the
    caller falls back to the rule-based explanation."""
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        prompt = (
            "You are summarizing one change between two versions of a company "
            "Standard Operating Procedure for an auditor. Be concise (2-3 sentences), "
            "state what changed in plain language, and note the operational or risk "
            "impact if any. Do not restate the raw text verbatim; explain it.\n\n"
            f"Section: {section_label or 'unknown'}\n"
            f"Change type (pre-classified): {change_type.value}\n"
            f"Old text: {old_text or '(none — this is new content)'}\n"
            f"New text: {new_text or '(none — this text was removed)'}\n"
        )
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=180,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None


def generate_explanation(
    old_text: Optional[str], new_text: Optional[str],
    change_type: ChangeType, section_label: Optional[str]
) -> str:
    ai_result = _openai_explanation(old_text, new_text, change_type, section_label)
    if ai_result:
        return ai_result
    return _rule_based_explanation(old_text, new_text, change_type, section_label)


# ---------------------------------------------------------------------------
# RAG stub: section-level matching via embeddings.
# Not called yet — diff_engine.py currently matches sections positionally
# with difflib, which works well when SOPs keep a stable structure. Wire this
# in when SOPs get reordered or renamed between versions and positional
# matching starts misaligning sections.
# ---------------------------------------------------------------------------
def embed_sections(sections: List[str]) -> List[List[float]]:
    """Return one embedding vector per section string. Requires OPENAI_API_KEY."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set — embeddings are not available.")
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=sections)
    return [item.embedding for item in response.data]
