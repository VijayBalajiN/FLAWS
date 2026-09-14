"""Post-hoc classification of every "general"-track candidate (survivors and
rejects alike) into the A/B/C/D taxonomy from `plan_prompts.py`'s module
docstring -- decoupled from generation, per the "classify after generating"
plan item. Uses gemini-2.5-flash (a lightweight tagging task, no need for
gemini-2.5-pro's heavier reasoning -- same precedent as confidence_ranking.py).

Survivors' classification is merged into their existing `_altered.json`
metadata; rejects (no altered-plan JSON exists for them) get a sidecar
`{paper}_{label}_classification.json` file.
"""

from __future__ import annotations

import glob
import json
import os
import re

from google import genai
from google.genai import types

from src.utils.formatting import format_generated_error
from src.utils.plan_prompts import generate_classify_error_prompt

MODEL = "gemini-2.5-flash"


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _call(prompt: str) -> str:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=200,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return (response.text or "").strip()


def classify_one(original_text: str, modified_text: str, explanation: str) -> dict:
    prompt = generate_classify_error_prompt(original_text, modified_text, explanation)
    completion = _call(prompt)
    category_match = re.search(r":category:\s*([ABCD])", completion, re.IGNORECASE)
    reasoning_match = re.search(r":reasoning:\s*(.*?)(?=\n:\w+:|$)", completion, re.DOTALL)
    return {
        "category": category_match.group(1).upper() if category_match else None,
        "reasoning": reasoning_match.group(1).strip() if reasoning_match else None,
        "raw": completion,
    }


CATEGORY_NAMES = {
    "A": "Internal Contradiction",
    "B": "Conflict with Established Beliefs",
    "C": "Undermining a Premise",
    "D": "Others",
}


def classify_all(out_dir: str) -> None:
    generated_files = sorted(glob.glob(os.path.join(out_dir, "*_general_c*_v*_generated.txt")))
    print(f"Found {len(generated_files)} general-track candidates to classify")

    for path in generated_files:
        base = path[: -len("_generated.txt")]
        label = os.path.basename(base)  # e.g. BERT_general_c2_v1

        modified_text, original_text, explanation_list, _ = format_generated_error(path)
        if not modified_text or not modified_text[0]:
            print(f"[{label}] no parseable generation, skipping")
            continue

        result = classify_one(original_text[0], modified_text[0], explanation_list[0])
        category_name = CATEGORY_NAMES.get(result["category"], "UNPARSED")
        print(f"[{label}] -> {result['category']} ({category_name}): {result['reasoning']}")

        altered_path = f"{base}_altered.json"
        if os.path.exists(altered_path):
            with open(altered_path) as f:
                altered = json.load(f)
            altered["_error_metadata"]["classification"] = {
                "category": result["category"],
                "category_name": category_name,
                "reasoning": result["reasoning"],
            }
            with open(altered_path, "w") as f:
                json.dump(altered, f, indent=2)
        else:
            sidecar_path = f"{base}_classification.json"
            with open(sidecar_path, "w") as f:
                json.dump(
                    {
                        "label": label,
                        "original_text": original_text[0],
                        "modified_text": modified_text[0],
                        "explanation": explanation_list[0],
                        "category": result["category"],
                        "category_name": category_name,
                        "reasoning": result["reasoning"],
                    },
                    f,
                    indent=2,
                )


if __name__ == "__main__":
    import sys

    _load_dotenv()
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "data/altered_plans"
    classify_all(out_dir)
