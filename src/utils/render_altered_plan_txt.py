"""Renders the altered-plan JSON files (`data/final_altered_plans/*.json`)
back into the same plain-text Problem/Method/Experiment-Design shape used
elsewhere (e.g. AIScientist's `data/attention_is_all_you_need.txt`), so they
can be dropped in alongside the other plan-text examples and parsed the same
way (`plan_txt_parser.parse_sections`).

Adds a `## Hypothesis` section on top of that shape -- the reference plan
examples don't have one (ref_theory is derived from `problem`, not stored in
the txt), but our JSON schema treats `hypothesis` as a first-class field, and
it's the field the "hypothesis*" tracks actually alter, so it has to be
visible in the rendered text for that alteration to show up at all.
"""

from __future__ import annotations

import glob
import json
import os


def render_plan_txt(plan: dict) -> str:
    return (
        f"## Problem\n\n{plan['problem']}\n\n"
        f"## Hypothesis\n\n{plan['hypothesis']}\n\n"
        f"## Method\n\n{plan['method']}\n\n"
        f"## Experiment Design\n\n{plan['experiment_design']}\n"
    )


def convert_all(input_dir: str, output_dir: str) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    written = []
    for path in sorted(glob.glob(os.path.join(input_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        name = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(output_dir, f"{name}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(render_plan_txt(plan))
        written.append(out_path)
    return written


if __name__ == "__main__":
    import sys

    input_dir = sys.argv[1] if len(sys.argv) > 1 else "data/final_altered_plans"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "data/final_altered_plans/txt"
    files = convert_all(input_dir, output_dir)
    print(f"Wrote {len(files)} files to {output_dir}")
