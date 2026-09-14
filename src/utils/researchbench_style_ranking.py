"""Hit@1 ranking evaluation over the 16 ResearchBench-style candidates
(1 gold + 15 negatives) built by `researchbench_style_negatives.py`, mirroring
the alphaxiv 2608.17270 paper's head-to-head comparison:

  - "confidence_style": forced single-number pick, thinking disabled, no
    reasoning allowed -- proxy for their logit-based energy scoring (true
    logprobs aren't available on the public Gemini API, see confidence_ranking.py).
  - "prompted_judge": the model is explicitly told to reason step by step
    before answering -- their "prompted LLM-as-judge" baseline.

With n=1 paper this can't reproduce their percentage, but it does tell us,
for this specific case, which method actually finds the real hypothesis
among 16 plausible-sounding candidates.
"""

from __future__ import annotations

import json
import os
import random
import re

from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash"

_CONFIDENCE_PROMPT = """Below are {n} candidate research hypotheses for a paper. Exactly one is the hypothesis actually used in the paper; the rest are plausible but incorrect.

Do NOT explain your reasoning. Answer with ONLY the number of the one correct hypothesis, nothing else.

{candidates}

Which number is the hypothesis actually used in the paper?"""

_JUDGE_PROMPT = """Below are {n} candidate research hypotheses for a paper. Exactly one is the hypothesis actually used in the paper; the rest are plausible but incorrect.

Think step by step: compare the candidates, identify what distinguishes the real hypothesis from a plausible-but-wrong one (e.g. overclaiming, missing a key qualifier, wrong emphasis), and reason toward your answer.

{candidates}

After your reasoning, on the FINAL line, output only: ANSWER: <number>"""


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


def _load_candidates(path: str) -> tuple[list[str], int]:
    """Returns (shuffled candidate texts, index of the gold one)."""
    with open(path) as f:
        d = json.load(f)
    items = [d["gold"]["hypothesis"]] + [n["hypothesis"] for n in d["wrong_inspiration_negatives"]] + [
        n["hypothesis"] for n in d["incomplete_inspiration_negatives"]
    ]
    order = list(range(len(items)))
    random.shuffle(order)
    shuffled = [items[i] for i in order]
    gold_position = order.index(0)  # where original index 0 (gold) ended up
    return shuffled, gold_position


def _call(prompt: str, thinking_budget: int, max_output_tokens: int) -> str:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        ),
    )
    return (response.text or "").strip()


def run_evaluation(candidates_path: str, seed: int = 0) -> dict:
    random.seed(seed)
    shuffled, gold_position = _load_candidates(candidates_path)
    candidates_block = "\n\n".join(f"{i + 1}. {c}" for i, c in enumerate(shuffled))
    gold_number = gold_position + 1

    confidence_prompt = _CONFIDENCE_PROMPT.format(n=len(shuffled), candidates=candidates_block)
    confidence_answer = _call(confidence_prompt, thinking_budget=0, max_output_tokens=10)
    confidence_pick = _extract_number(confidence_answer)

    judge_prompt = _JUDGE_PROMPT.format(n=len(shuffled), candidates=candidates_block)
    judge_answer = _call(judge_prompt, thinking_budget=-1, max_output_tokens=2000)
    judge_pick = _extract_number(judge_answer, prefer_last=True)

    return {
        "gold_number": gold_number,
        "gold_hypothesis": shuffled[gold_position],
        "confidence_style": {
            "raw_answer": confidence_answer,
            "picked": confidence_pick,
            "correct": confidence_pick == gold_number,
        },
        "prompted_judge": {
            "raw_answer": judge_answer,
            "picked": judge_pick,
            "correct": judge_pick == gold_number,
        },
        "shuffled_candidates": shuffled,
    }


def _extract_number(text: str, prefer_last: bool = False) -> int | None:
    if prefer_last:
        match = re.search(r"ANSWER:\s*(\d+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    numbers = re.findall(r"\b(\d{1,2})\b", text)
    if not numbers:
        return None
    return int(numbers[-1] if prefer_last else numbers[0])


if __name__ == "__main__":
    _load_dotenv()
    result = run_evaluation("data/researchbench_style/AttentionIsAllYouNeed_candidates.json")
    out_path = "data/researchbench_style/AttentionIsAllYouNeed_ranking_result.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"gold_number={result['gold_number']}")
    print(f"confidence_style: picked={result['confidence_style']['picked']} correct={result['confidence_style']['correct']}")
    print(f"prompted_judge:   picked={result['prompted_judge']['picked']} correct={result['prompted_judge']['correct']}")
    print(f"Wrote {out_path}")
