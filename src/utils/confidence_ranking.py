"""Cheap proxy for the logit-based "energy scoring" approach from the
hypothesis-ranking paper (alphaxiv 2608.17270): given a paper's real
hypothesis and a flawed alternative, score which one the model finds more
plausible using its own intrinsic confidence, rather than an explicit
reasoning-based LLM-as-judge verdict.

True replication would score each candidate's teacher-forced token log-
probabilities directly -- but the public Gemini API has logprobs disabled
for every current model (`gemini-2.5-pro`, `-flash`, `-flash-lite` all
reject `response_logprobs=True` with "Logprobs is not enabled for models/...").
Getting real logits would need Vertex AI (a separate GCP project + billing,
not just an API key) -- that part is a genuine "you'd have to set this up"
gap, flagged rather than worked around silently.

Proxy used instead: force a single-letter multiple-choice answer (no
reasoning allowed) at temperature > 0, repeated N times, and tally how often
the model picks the original vs the altered hypothesis. This is a Monte-Carlo
approximation of confidence (higher win-rate for the original = the model is
more consistently "confident" in it, even without seeing exact logits) --
the same methodological contrast the paper draws (confidence signal vs.
explicit judge reasoning), just estimated by sampling instead of exact logits.
"""

from __future__ import annotations

import os
import random
import re

from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash"  # gemini-2.5-pro can't disable thinking (forces budget>0); flash can

_PROMPT_TEMPLATE = """You are given the context of a research plan and two candidate hypotheses, labeled A and B. Exactly one of them is the hypothesis actually used in this research; the other is a flawed alternative that would not hold up.

Do NOT explain your reasoning. Answer with ONLY the single letter "A" or "B" and nothing else.

Research context:
## Problem
{problem}

## Method
{method}

## Experiment Design
{experiment_design}

Hypothesis A:
{hyp_a}

Hypothesis B:
{hyp_b}

Which hypothesis (A or B) is the one actually used in this research?"""

_ED_PROMPT_TEMPLATE = """You are given the context of a research plan and two candidate versions of one part of its experiment design, labeled A and B. Exactly one is the version actually used in this research and would validly test the stated hypothesis; the other has a methodological flaw (e.g. a confound, a missing control, a wrong metric) that would undermine the test.

Do NOT explain your reasoning. Answer with ONLY the single letter "A" or "B" and nothing else.

Research context:
## Problem
{problem}

## Hypothesis
{hypothesis}

## Method
{method}

Experiment design excerpt A:
{ed_a}

Experiment design excerpt B:
{ed_b}

Which excerpt (A or B) is the one that would actually let the researchers validly test the stated hypothesis?"""


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


def _call_once(prompt: str, temperature: float) -> str:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    try:
        # gemini-2.5-pro is a "thinking" model by default -- it burns tokens
        # on internal reasoning before ever emitting the answer. Disabling
        # thinking outright is also more faithful to the paper's spirit here:
        # an immediate forced-choice confidence read, not a reasoned verdict
        # (that's what the LLM-as-judge pipeline is for).
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=20,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return (response.text or "").strip()
    except Exception as e:
        print(f"[confidence_ranking] sample failed: {e}")
        return ""


def _vote_loop(prompt_fn, n_samples: int, temperature: float) -> dict:
    """
    Shared voting loop: `prompt_fn(original_is_a: bool) -> str` builds one
    forced-choice prompt with the original/altered text randomly assigned to
    A/B (to cancel out position bias); this calls it `n_samples` times and
    tallies how often the model picked the original.

    A LOW win-rate (close to 0.5, or below) means the model can't reliably
    tell the original from the altered version by intrinsic confidence alone
    -- i.e. a genuinely hard-to-detect error by this signal, complementing
    (not replacing) the explicit LLM-judge filters already in the pipeline.
    """
    votes_for_original = 0
    valid_samples = 0
    raw_answers = []

    for _ in range(n_samples):
        original_is_a = random.random() < 0.5
        prompt = prompt_fn(original_is_a)
        answer = _call_once(prompt, temperature=temperature)
        raw_answers.append(answer)

        # take the LAST standalone A/B in the response, not the first -- with
        # more token headroom the model may mention both letters while
        # reasoning before giving its final answer at the end
        matches = re.findall(r"\b([AB])\b", answer.upper())
        if not matches:
            continue
        picked = matches[-1]
        valid_samples += 1
        if (picked == "A") == original_is_a:
            votes_for_original += 1

    win_rate = votes_for_original / valid_samples if valid_samples else None
    return {
        "n_samples": n_samples,
        "valid_samples": valid_samples,
        "votes_for_original": votes_for_original,
        "win_rate_for_original": win_rate,
        "raw_answers": raw_answers,
    }


def confidence_win_rate(
    problem: str,
    method: str,
    experiment_design: str,
    original_hypothesis: str,
    altered_hypothesis: str,
    n_samples: int = 10,
    temperature: float = 0.7,
) -> dict:
    """Hypothesis-track version: forced choice between the true hypothesis
    and the altered one, given the rest of the (unaltered) plan as context."""

    def prompt_fn(original_is_a: bool) -> str:
        hyp_a = original_hypothesis if original_is_a else altered_hypothesis
        hyp_b = altered_hypothesis if original_is_a else original_hypothesis
        return _PROMPT_TEMPLATE.format(
            problem=problem, method=method, experiment_design=experiment_design, hyp_a=hyp_a, hyp_b=hyp_b
        )

    return _vote_loop(prompt_fn, n_samples, temperature)


def confidence_win_rate_ed(
    problem: str,
    hypothesis: str,
    method: str,
    original_ed_excerpt: str,
    altered_ed_excerpt: str,
    n_samples: int = 10,
    temperature: float = 0.7,
) -> dict:
    """ED-track version: forced choice between the true experiment-design
    excerpt and the altered one, given problem/hypothesis/method as context
    (not the full experiment_design, so the model can't just pattern-match
    against surrounding unaltered steps -- it has to judge the excerpt on
    its own methodological merits)."""

    def prompt_fn(original_is_a: bool) -> str:
        ed_a = original_ed_excerpt if original_is_a else altered_ed_excerpt
        ed_b = altered_ed_excerpt if original_is_a else original_ed_excerpt
        return _ED_PROMPT_TEMPLATE.format(problem=problem, hypothesis=hypothesis, method=method, ed_a=ed_a, ed_b=ed_b)

    return _vote_loop(prompt_fn, n_samples, temperature)


if __name__ == "__main__":
    import json
    import sys

    _load_dotenv()
    path = sys.argv[1]
    with open(path) as f:
        d = json.load(f)
    meta = d["_error_metadata"]
    if meta["track"] not in ("hypothesis",) and not meta["track"].startswith("hypothesis"):
        print("This check only applies to hypothesis-track altered plans.")
        sys.exit(1)

    original = meta["original_text"][0]
    altered_full = d["hypothesis"]
    # reconstruct the pre-alteration hypothesis by undoing the one splice
    modified = meta["modified_text"][0]
    original_hypothesis = altered_full.replace(modified, original)

    result = confidence_win_rate(
        d["problem"], d["method"], d["experiment_design"], original_hypothesis, altered_full
    )
    print(json.dumps(result, indent=2))
