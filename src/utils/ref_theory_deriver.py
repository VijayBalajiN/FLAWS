"""Port of AIScientist's `aiscientist/core/ref_theory_deriver.py`.

Derives `ref_theory` from a plan's `problem` text -- the underlying
theoretical claim/mechanism the plan's approach depends on, stated as a
general claim (not "we hypothesize...") with anything describing a
result/finding stripped out. This becomes our "Hypothesis" for the error-
insertion pipeline: a single falsifiable statement, so no separate claim-
extraction step is needed for the hypothesis-error track.

System prompt copied verbatim from the source; only the LLM client is
swapped for Gemini (via `google-generativeai`), matching
`research_plan_extraction.py` and FLAWS's own `llm_calls.py` convention.
"""

from __future__ import annotations

import os

import google.generativeai as genai

SYSTEM_PROMPT = """\
You extract the reference theory a research plan's problem statement leans on.

Given a "Problem" section from a research plan, identify the underlying theoretical \
claim, mechanism, or framework the plan's approach depends on, and state it as a \
general theoretical claim -- not phrased as "this plan proposes..." or "we hypothesize \
that...", just the claim itself, the way a textbook would state it.

Strip out anything that describes or implies a result, finding, or measured outcome: \
the plan hasn't been run yet, and the reference theory is what's being tested, not \
what was found. Also drop motivation/framing about why the problem matters or what \
gap it fills -- keep only the theoretical claim itself, stated precisely enough that \
someone could derive predictions from it in a new scenario.

Respond with ONLY the reference theory statement itself -- no preamble, no headers, \
no quotation marks around it."""


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


def derive_ref_theory(problem: str, model: str = "gemini-2.5-pro") -> str:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    gen_model = genai.GenerativeModel(model_name=model, system_instruction=SYSTEM_PROMPT)
    response = gen_model.generate_content(
        f"Problem:\n{problem}", generation_config=genai.GenerationConfig(temperature=0.0)
    )
    return response.text.strip()


if __name__ == "__main__":
    import sys

    _load_dotenv()
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        problem_text = f.read()
    print(derive_ref_theory(problem_text))
