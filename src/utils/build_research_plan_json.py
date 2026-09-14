"""Combines `plan_txt_parser` + `ref_theory_deriver` (Phase 2) to turn one
`data/research_plans/<paper>.txt` into a structured
`data/research_plans_structured/<paper>.json`:

    {paper_id, problem, method, experiment_design, hypothesis}

`hypothesis` is `ref_theory` under AIScientist's naming -- the single
falsifiable claim the error-insertion pipeline's hypothesis-error track will
target directly, no separate claim-extraction needed.
"""

from __future__ import annotations

import json
import os
import sys

from src.utils.plan_txt_parser import parse_sections
from src.utils.ref_theory_deriver import _load_dotenv, derive_ref_theory


def build(paper_id: str, plan_txt_path: str, output_path: str) -> dict:
    with open(plan_txt_path, "r", encoding="utf-8") as f:
        text = f.read()

    sections = parse_sections(text)
    hypothesis = derive_ref_theory(sections["problem"])

    result = {
        "paper_id": paper_id,
        "problem": sections["problem"],
        "method": sections["method"],
        "experiment_design": sections["experiment_design"],
        "hypothesis": hypothesis,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    _load_dotenv()
    paper_id = sys.argv[1]
    plan_txt_path = sys.argv[2]
    output_path = sys.argv[3]
    build(paper_id, plan_txt_path, output_path)
    print(f"Saved structured plan to {output_path}")
