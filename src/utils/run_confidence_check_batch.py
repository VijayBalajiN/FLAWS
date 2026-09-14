"""Batch-runs `confidence_ranking.confidence_win_rate` across every
hypothesis-type altered plan (all tracks except "ed", which alters
experiment_design, not hypothesis), and writes results + updates each
plan's `_error_metadata` in place with a `confidence_check` block.

Skips combos already checked (idempotent -- safe to re-run / resume).
"""

from __future__ import annotations

import glob
import json
import os

from src.utils.confidence_ranking import _load_dotenv, confidence_win_rate

PLANS_DIR = "data/final_altered_plans"
MIRROR_DIR = "data/altered_plans"
AISCIENTIST_DIR = "/Users/vijaybalajinarasimmabharathi/Desktop/7th-sem/project/AIScientist/data/flaws_altered_plans"


def process_one(path: str) -> dict | None:
    with open(path) as f:
        d = json.load(f)
    meta = d["_error_metadata"]
    if meta["track"] == "ed":
        return None
    if "confidence_check" in meta:
        print(f"[{os.path.basename(path)}] already checked, skipping")
        return meta["confidence_check"]

    original = meta["original_text"][0]
    modified = meta["modified_text"][0]
    altered_full = d["hypothesis"]
    original_hypothesis = altered_full.replace(modified, original)
    if original_hypothesis == altered_full:
        print(f"[{os.path.basename(path)}] could not reconstruct original (splice not found verbatim), skipping")
        return None

    result = confidence_win_rate(d["problem"], d["method"], d["experiment_design"], original_hypothesis, altered_full)
    win_rate = result["win_rate_for_original"]
    print(f"[{os.path.basename(path)}] win_rate_for_original={win_rate}")

    check_block = {
        "method": (
            "sampling-based forced-choice (gemini-2.5-flash, thinking disabled, n=10, temp=0.7), "
            "proxy for logit-based energy scoring (alphaxiv 2608.17270) since Gemini API has logprobs "
            "disabled for all current models"
        ),
        **result,
        "interpretation": (
            "win_rate_for_original is the fraction of forced A/B choices where the model picked the TRUE "
            "original hypothesis over the inserted error; low win-rate means the model could not reliably "
            "distinguish the error from the truth even without being allowed to reason."
        ),
    }

    for base_dir in (PLANS_DIR, MIRROR_DIR, AISCIENTIST_DIR):
        target = os.path.join(base_dir, os.path.basename(path))
        if not os.path.exists(target):
            continue
        with open(target) as f:
            dd = json.load(f)
        dd["_error_metadata"]["confidence_check"] = check_block
        if win_rate is not None and win_rate <= 0.3 and dd["_error_metadata"]["status"] != "accepted":
            dd["_error_metadata"]["status"] = "accepted_via_confidence_check"
        with open(target, "w") as f:
            json.dump(dd, f, indent=2)

    return check_block


if __name__ == "__main__":
    _load_dotenv()
    paths = sorted(glob.glob(os.path.join(PLANS_DIR, "*.json")))
    for path in paths:
        try:
            process_one(path)
        except Exception as e:
            print(f"[{os.path.basename(path)}] FAILED: {e}")
