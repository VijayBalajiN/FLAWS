"""Port of AIScientist's `aiscientist/core/plan_txt_parser.py`, copied
verbatim (pure regex, no LLM, no dependency on AIScientist's package).

Splits a prose research-plan text into its Problem/Method/Experiment
Design sections by markdown header. Tolerant of heading depth (`##` vs
`###`) and of "Experiment Design" vs "Experimental Design".

Extended with an optional "Hypothesis" section (not in AIScientist's
original 3-section format, where ref_theory is derived rather than
authored) -- our `plan_as_text()` renders one, and re-splitting an edited
whole-plan blob (see the propagation fix in `plan_error_insertion.py`)
needs to recover it. Optional, not required, so parsing the original
Problem/Method/Experiment-Design-only plan texts still works unchanged."""

from __future__ import annotations

import re

_HEADER_RE = re.compile(r"^#{1,6}\s*(.+?)\s*$", re.MULTILINE)

_HEADING_ALIASES = {
    "problem": "problem",
    "method": "method",
    "methods": "method",
    "experiment design": "experiment_design",
    "experimental design": "experiment_design",
    "hypothesis": "hypothesis",
}

_REQUIRED_SECTIONS = ("problem", "method", "experiment_design")


def parse_sections(text: str) -> dict[str, str]:
    """Return ``{"problem": ..., "method": ..., "experiment_design": ...}``,
    plus ``"hypothesis"`` if a ``## Hypothesis`` header is present.

    Raises ``ValueError`` if any of the three required sections isn't found.
    """
    headers = list(_HEADER_RE.finditer(text))
    sections: dict[str, str] = {}

    for i, header in enumerate(headers):
        key = _HEADING_ALIASES.get(_normalize_heading_text(header.group(1)))
        if key is None:
            continue
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        sections[key] = text[start:end].strip()

    missing = [name for name in _REQUIRED_SECTIONS if name not in sections]
    if missing:
        raise ValueError(
            f"Could not find section(s) {missing} in plan text "
            f"(looked for markdown headers named {sorted(_HEADING_ALIASES)})."
        )
    return sections


def _normalize_heading_text(raw_heading: str) -> str:
    # A heading may carry markdown bold markers (`### **Problem**`) or a
    # trailing title -- strip those before matching against the alias table.
    cleaned = raw_heading.strip().strip("*").strip()
    return cleaned.lower()
