"""Phase 3 orchestrator: retargets FLAWS's error-insertion pipeline
(`single_process/single_error_insertion.py`) from full LaTeX papers onto the
short `(hypothesis, experiment_design)` plan text built in Phase 2.

Five tracks per paper:
  - "general": decompose the plan into 5 distinct falsifiable claims (>=1
    from the hypothesis, the rest from hypothesis or experiment_design),
    then generate 3 candidate falsifications per claim (15 candidates total,
    from just 6 LLM calls) -- diversity comes from genuinely different
    targets and mechanisms, not from resampling one target at a higher
    temperature (see docs/diversity_mechanisms_reference.md for why: neither
    FLAWS nor ResearchBench actually use temperature for this).
  - "hypothesis_internal_contradiction" / "hypothesis_established_belief_conflict"
    / "hypothesis_premise_undermining": typed, per taxonomy_te.txt.
  - "ed": typed (8-category) flaw against `experiment_design`.

Every candidate, regardless of track, goes through the same chain: filter
(invalid, then easy) -> insert -> localize -> internal-identify -> internal-
evaluate -- same stopping conditions as the original FLAWS pipeline. Reuses
`formatting.py` / `insertion_helpers.py` / `evaluation_helpers.py` completely
unchanged (they're string-generic, not LaTeX-specific); only the prompts
(`plan_prompts.py`) are new. No LaTeX combine/compile step -- the final
artifact is the altered plan JSON (one field replaced) plus insertion
metadata, not a PDF.

Every LLM call gets the *whole* plan as context, not just the isolated
altered field -- mirroring `single_error_insertion.py`, where `call_api`
unconditionally appends the full LaTeX source to every prompt (the original
document for generate/filter, the altered document for localize/internal-id).
Skipping this originally caused every hypothesis-track attempt to self-
identify: a one-paragraph hypothesis has nowhere to hide an error when
that's all the model sees.

The three typed hypothesis tracks and "ed" still use `run_track_with_retries`,
which falls back to the "best of the rejects" (see `rank_attempts`) if every
attempt is rejected -- that fallback exists because those tracks only ever
have one target to retry. "general" doesn't need it: with 15 genuinely
distinct candidates per paper, some surviving and some not is expected and
fine, there's no single target whose failure needs rescuing.
"""

from __future__ import annotations

import json
import os
import re
import time

import google.generativeai as genai

from src.utils.evaluation_helpers import levenshtein_identify
from src.utils.formatting import (
    format_generated_error,
    format_identified_error,
    format_localized_error,
    format_tagged_blocks,
)
from src.utils.insertion_helpers import modify_source
from src.utils.plan_txt_parser import parse_sections
from src.utils.plan_prompts import (
    generate_ed_error_prompt,
    generate_filter_easy_prompt,
    generate_filter_invalid_prompt,
    generate_general_decompose_prompt,
    generate_general_error_candidates_prompt,
    generate_hypothesis_error_established_belief_conflict_prompt,
    generate_hypothesis_error_internal_contradiction_prompt,
    generate_hypothesis_error_premise_undermining_prompt,
    generate_internal_identification_prompt,
    generate_localization_prompt,
)

MODEL = "gemini-2.5-pro"

TRACK_FIELD = {
    "hypothesis_internal_contradiction": "hypothesis",
    "hypothesis_established_belief_conflict": "hypothesis",
    "hypothesis_premise_undermining": "hypothesis",
    "ed": "experiment_design",
}
TRACK_GENERATION_PROMPT = {
    "hypothesis_internal_contradiction": generate_hypothesis_error_internal_contradiction_prompt,
    "hypothesis_established_belief_conflict": generate_hypothesis_error_established_belief_conflict_prompt,
    "hypothesis_premise_undermining": generate_hypothesis_error_premise_undermining_prompt,
    "ed": generate_ed_error_prompt,
}

FIELD_LABEL = {"hypothesis": "hypothesis", "experiment_design": "experiment design"}


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


def call_gemini(
    prompt: str, temperature: float = 0.7, max_retries: int = 3, retry_delay: float = 15.0
) -> str:
    """Wraps the Gemini call with retry-with-backoff for transient API errors
    (timeouts, rate limits, etc.) -- without this, one flaky call kills the
    entire multi-hour batch instead of just costing one retry."""
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(model_name=MODEL)
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(
                prompt, generation_config=genai.GenerationConfig(temperature=temperature)
            )
            return response.text
        except Exception as e:
            last_exc = e
            print(f"[call_gemini] attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
    raise RuntimeError(f"call_gemini failed after {max_retries} attempts") from last_exc


def _extract_tag(text: str, tag: str) -> str | None:
    """Pull one `:tag:` block's content out of a raw completion (for fields
    `format_generated_error` doesn't know about, e.g. `:error_type:`)."""
    match = re.search(rf":{tag}:\s*(.*?)(?=\n:\w+:|$)", text, re.DOTALL)
    return match.group(1).strip() if match else None


def plan_as_text(plan: dict) -> str:
    """Render the whole plan as one prose blob -- mirrors AIScientist's
    `ResearchPlan.as_text()`. This is what every LLM call in this pipeline
    gets appended as context, so the model always sees the full plan, not
    just the one field being targeted."""
    return (
        f"## Hypothesis\n{plan['hypothesis']}\n\n"
        f"## Problem\n{plan['problem']}\n\n"
        f"## Method\n{plan['method']}\n\n"
        f"## Experiment Design\n{plan['experiment_design']}\n"
    )


def _editable_plan_context(plan: dict, field_label: str) -> str:
    """Context block for generate/filter calls. Requires the edit stay
    anchored in `field_label` (the track's actual target), while PERMITTING
    (not requiring) additional touches elsewhere -- mirrors FLAWS's original
    `generate_error_generation_prompt`'s "repeat original/modified pairs...
    if the error spans multiple non-contiguous parts", which we'd dropped
    when adapting to plan text. Without the anchor requirement, giving the
    model the whole plan as editable let it drift the entire edit into a
    different section altogether (e.g. a "hypothesis" track's error landing
    in Method instead) instead of propagating a hypothesis-level break
    outward into the ED while still actually breaking the hypothesis."""
    return (
        f"\n\nFor context, here is the full research plan. At least one of your "
        f":original_text:/:modified_text: pairs MUST fall within the {field_label} section "
        f"-- that is your primary target and must actually be modified. If -- and only if -- "
        f"leaving another part of the plan unchanged would create a visible inconsistency with "
        f"the error you introduce there (e.g. the Experiment Design still validly testing a "
        f"Hypothesis you just broke), you MAY additionally modify that other part with further "
        f"pairs. Do this only when truly necessary for the plan to remain internally consistent "
        f"-- most errors do not require touching more than one part of the plan.\n\n"
        + plan_as_text(plan)
    )


def process_candidate(
    paper_id: str,
    plan: dict,
    field: str,
    base: str,
    label: str,
    original_text: list[str],
    modified_text: list[str],
    explanation_list: list[str],
    error_filename: str,
    out_dir: str,
    metadata: dict,
    hallucination_threshold: float = 0.9,
    levenshtein_threshold: float = 0.5,
    generate_k: int = 5,
) -> dict | None:
    """
    Shared chain for one already-generated candidate error, regardless of
    which track/mechanism produced it: filter (invalid, then easy) -> insert
    -> localize -> internal-identify -> internal-evaluate. On success, saves
    `{out_dir}/{paper_id}_{label}_altered.json` and returns the altered plan;
    returns None if filtered/discarded at any stage.

    `metadata` is merged into the saved `_error_metadata` on top of the
    standard fields (status/original_text/modified_text/explanation/
    localized_errors) -- callers pass whatever identifies this candidate
    (track name, or claim/candidate indices for the general track).
    """
    field_label = FIELD_LABEL[field]
    original_plan_context = _editable_plan_context(plan, field_label)

    if not modified_text or not modified_text[0]:
        print(f"[{paper_id}/{label}] generation failed to parse, skipping")
        return None

    # code-level safeguard: the prompt REQUIRES at least one pair to land in
    # the primary target field, but instructions aren't always followed --
    # verify rather than trust, since a drifted edit (e.g. a "hypothesis"
    # track's error landing entirely in Method) defeats the track's purpose
    if not any(o.strip() and o.strip() in plan[field] for o in original_text):
        print(f"[{paper_id}/{label}] rejected: no edit landed in the required {field} section")
        return None

    # filter invalid
    filter_invalid_prompt = generate_filter_invalid_prompt(
        original_text, modified_text, explanation_list, field_label
    )
    filter_invalid_result = call_gemini(filter_invalid_prompt + original_plan_context, temperature=0.0)
    with open(f"{base}_filter_invalid.txt", "w") as f:
        f.write(filter_invalid_result)
    if "No changes required" not in filter_invalid_result:
        print(f"[{paper_id}/{label}] filtered: invalid")
        return None

    # filter easy
    filter_easy_prompt = generate_filter_easy_prompt(
        original_text, modified_text, explanation_list, field_label
    )
    filter_easy_result = call_gemini(filter_easy_prompt + original_plan_context, temperature=0.0)
    with open(f"{base}_filter_easy.txt", "w") as f:
        f.write(filter_easy_result)
    if "No changes required" not in filter_easy_result:
        print(f"[{paper_id}/{label}] filtered: too easy")
        return None

    # insert error into the WHOLE plan text, not just the target field -- a
    # multi-location generation (see _editable_plan_context) may have emitted
    # original/modified pairs spanning more than one section, and modify_source
    # already applies every pair it's given regardless of which section each
    # one falls in, since it's just doing exact/fuzzy text matching
    altered_whole_text = modify_source(
        error_filename=error_filename, latex_source=plan_as_text(plan), threshold=hallucination_threshold
    )
    if altered_whole_text is None:
        print(f"[{paper_id}/{label}] failed to insert (text mismatch)")
        return None

    try:
        altered_sections = parse_sections(altered_whole_text)
    except ValueError as e:
        print(f"[{paper_id}/{label}] failed to insert (splice broke a section header: {e})")
        return None

    altered_plan_for_context = {**plan, **altered_sections}
    altered_plan_context = "\n\n" + plan_as_text(altered_plan_for_context)

    # localize (find any other now-incorrect excerpts elsewhere in the WHOLE plan)
    localize_prompt = generate_localization_prompt(
        original_text, modified_text, explanation_list, field_label, plan_as_text(altered_plan_for_context)
    )
    localize_result = call_gemini(localize_prompt, temperature=0.0)
    localize_filename = f"{base}_localized.txt"
    with open(localize_filename, "w") as f:
        f.write(localize_result)
    localized_errors = format_localized_error(localize_filename) if "error:" in localize_result else []

    # internal identification (self-identification difficulty check, against the WHOLE altered plan)
    word_limit = max([len(t.split()) for t in modified_text + original_text + localized_errors] or [50])
    internal_id_prompt = (
        generate_internal_identification_prompt(field_label, num_chunks=generate_k, word_limit=word_limit)
        + altered_plan_context
    )
    internal_id_result = call_gemini(internal_id_prompt, temperature=0.0)
    internal_id_filename = f"{base}_internal_id.txt"
    with open(internal_id_filename, "w") as f:
        f.write(internal_id_result)

    # internal evaluate (Levenshtein match against ground truth)
    true_error_list = modified_text + localized_errors
    pred_error_list = format_identified_error(internal_id_filename)
    regenerate = levenshtein_identify(
        folder=out_dir,
        paper=paper_id,
        ind=label,
        model=MODEL,
        true_error_list=true_error_list,
        pred_error_list=pred_error_list,
        threshold=levenshtein_threshold,
        top_k=generate_k,
    )
    if regenerate:
        print(f"[{paper_id}/{label}] self-identified (too easy), discarding")
        return None

    touched_fields = [k for k, v in altered_sections.items() if plan.get(k) != v]

    altered_plan = {**plan, **altered_sections}
    altered_plan["_error_metadata"] = {
        "status": "accepted",
        "field": field,
        "touched_fields": touched_fields,
        "original_text": original_text,
        "modified_text": modified_text,
        "explanation": explanation_list,
        "localized_errors": localized_errors,
        **metadata,
    }
    altered_path = f"{out_dir}/{paper_id}_{label}_altered.json"
    with open(altered_path, "w") as f:
        json.dump(altered_plan, f, indent=2)
    print(f"[{paper_id}/{label}] SUCCESS -> {altered_path}")
    return altered_plan


def run_track(
    paper_id: str,
    plan: dict,
    track: str,
    out_dir: str,
    hallucination_threshold: float = 0.9,
    levenshtein_threshold: float = 0.5,
    generate_k: int = 5,
    attempt: int | None = None,
) -> dict | None:
    """
    Run one typed track (a hypothesis_* variant, or "ed") for one paper:
    generate, then hand off to `process_candidate` for the shared chain.

    `attempt`, if given, is folded into intermediate filenames so retries
    (see `run_track_with_retries`) each leave their own paper trail instead
    of overwriting the previous attempt's debug files; the final `_altered`
    output name is unaffected, since only one attempt ever succeeds.
    """
    field = TRACK_FIELD[track]
    target_text = plan[field]

    os.makedirs(out_dir, exist_ok=True)
    suffix = f"_attempt{attempt}" if attempt is not None else ""
    label = f"{track}{suffix}"
    base = f"{out_dir}/{paper_id}_{label}"

    original_plan_context = _editable_plan_context(plan, FIELD_LABEL[field])

    gen_prompt = TRACK_GENERATION_PROMPT[track](target_text)
    completion = call_gemini(gen_prompt + original_plan_context, temperature=0.7)
    error_filename = f"{base}_generated.txt"
    with open(error_filename, "w") as f:
        f.write(completion)

    modified_text, original_text, explanation_list, _ = format_generated_error(error_filename)
    error_type = _extract_tag(completion, "error_type")

    result = process_candidate(
        paper_id=paper_id,
        plan=plan,
        field=field,
        base=base,
        label=label,
        original_text=original_text,
        modified_text=modified_text,
        explanation_list=explanation_list,
        error_filename=error_filename,
        out_dir=out_dir,
        metadata={"track": track, "error_type": error_type},
        hallucination_threshold=hallucination_threshold,
        levenshtein_threshold=levenshtein_threshold,
        generate_k=generate_k,
    )
    # process_candidate saves to `{out_dir}/{paper_id}_{label}_altered.json` --
    # override to the plain track name so run_track's output path is unaffected
    # by the attempt suffix baked into `label` above for scoring purposes.
    if result is not None:
        altered_path = f"{out_dir}/{paper_id}_{track}_altered.json"
        with open(altered_path, "w") as f:
            json.dump(result, f, indent=2)
    return result


def _file_text(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read()


def _parse_max_score(text: str) -> float | None:
    """Extract the raw best-match Levenshtein score from a saved score file
    (same file `evaluation_helpers.calculate_levenshtein` writes), for
    ranking rejected attempts -- not the thresholded pass/fail decision
    `parse_levenshtein` returns."""
    import ast

    scores: list[float] = []
    for pattern in (r"subsets of ground vs pred:\s*(\[[^\]]*\])", r"subsets of pred vs ground:\s*(\[[^\]]*\])"):
        match = re.search(pattern, text)
        if match:
            scores.extend(ast.literal_eval(match.group(1)))
    return max(scores) if scores else None


def rank_attempts(paper_id: str, track: str, out_dir: str, max_attempts: int) -> list[dict]:
    """
    Classify and rank every attempt for a (paper, track) by how close it got
    to surviving, using only signal already on disk (no extra LLM calls):

      Tier 1 -- passed invalid+easy filters, only caught by self-identification.
                Ranked by LOWEST Levenshtein match score (hardest to re-find).
      Tier 2 -- passed invalid filter, failed the "easy" filter (never reached
                insertion/self-identification, so no score to rank by).
      Tier 3 -- failed the invalid filter (broken or self-announcing).
      Tier 4 -- generation itself failed to parse (worst; excluded from ranking).

    Returns attempts sorted best-first (ascending tier, then ascending score
    within tier 1).
    """
    results = []
    for attempt in range(1, max_attempts + 1):
        base = f"{out_dir}/{paper_id}_{track}_attempt{attempt}"
        generated = _file_text(f"{base}_generated.txt")
        if generated is None:
            continue
        modified_text, _, _, _ = format_generated_error(f"{base}_generated.txt")
        if not modified_text or not modified_text[0]:
            continue  # tier 4, excluded

        filter_invalid = _file_text(f"{base}_filter_invalid.txt")
        if filter_invalid is None or "No changes required" not in filter_invalid:
            results.append({"attempt": attempt, "tier": 3, "score": None})
            continue

        filter_easy = _file_text(f"{base}_filter_easy.txt")
        if filter_easy is None or "No changes required" not in filter_easy:
            results.append({"attempt": attempt, "tier": 2, "score": None})
            continue

        score_text = _file_text(f"{out_dir}/{paper_id}_{track}_attempt{attempt}_{MODEL}_score.txt")
        score = _parse_max_score(score_text) if score_text else None
        results.append({"attempt": attempt, "tier": 1, "score": score})

    results.sort(key=lambda r: (r["tier"], r["score"] if r["score"] is not None else 1.0))
    return results


def reconstruct_altered_plan(paper_id: str, plan: dict, track: str, out_dir: str, attempt: int) -> dict:
    """Rebuild the altered-plan JSON for one specific past attempt (used for
    the best-of-rejects fallback): reload its saved generation, reapply the
    same deterministic splice, and pull in whatever localize/internal-id
    artifacts exist for it (may be absent for tier 2/3 attempts, since the
    pipeline stops before reaching those steps)."""
    field = TRACK_FIELD[track]
    base = f"{out_dir}/{paper_id}_{track}_attempt{attempt}"

    modified_text, original_text, explanation_list, _ = format_generated_error(f"{base}_generated.txt")
    completion = _file_text(f"{base}_generated.txt") or ""
    error_type = _extract_tag(completion, "error_type")

    altered_whole_text = modify_source(
        error_filename=f"{base}_generated.txt", latex_source=plan_as_text(plan), threshold=0.9
    )
    try:
        altered_sections = parse_sections(altered_whole_text) if altered_whole_text else {}
    except ValueError:
        altered_sections = {}

    localize_text = _file_text(f"{base}_localized.txt")
    localized_errors = (
        format_localized_error(f"{base}_localized.txt")
        if localize_text and "error:" in localize_text
        else []
    )

    touched_fields = [k for k, v in altered_sections.items() if plan.get(k) != v]
    altered_plan = {**plan, **altered_sections}
    altered_plan["_error_metadata"] = {
        "status": "rejected_best_of_attempts",
        "track": track,
        "field": field,
        "touched_fields": touched_fields,
        "source_attempt": attempt,
        "error_type": error_type,
        "original_text": original_text,
        "modified_text": modified_text,
        "explanation": explanation_list,
        "localized_errors": localized_errors,
    }
    return altered_plan


def run_track_with_retries(
    paper_id: str, plan: dict, track: str, out_dir: str, max_attempts: int = 5
) -> dict | None:
    """
    Retry `run_track` up to `max_attempts` times, stopping at the first
    success. If every attempt is rejected, falls back to saving the
    best-ranked reject (see `rank_attempts`) instead of discarding
    everything. Used for the typed tracks (each has exactly one target, so a
    fallback is needed); "general" doesn't use this, see `run_general_track`.
    """
    for attempt in range(1, max_attempts + 1):
        print(f"[{paper_id}/{track}] attempt {attempt}/{max_attempts}")
        try:
            result = run_track(paper_id, plan, track, out_dir, attempt=attempt)
        except Exception as e:
            print(f"[{paper_id}/{track}] attempt {attempt} crashed: {e}")
            result = None
        if result is not None:
            return result

    print(f"[{paper_id}/{track}] exhausted {max_attempts} attempts, picking best of the rejects")
    ranked = rank_attempts(paper_id, track, out_dir, max_attempts)
    if not ranked:
        print(f"[{paper_id}/{track}] no usable attempts at all (all failed to parse)")
        return None

    best = ranked[0]
    print(f"[{paper_id}/{track}] best reject: attempt {best['attempt']} (tier {best['tier']}, score {best['score']})")
    altered_plan = reconstruct_altered_plan(paper_id, plan, track, out_dir, best["attempt"])
    altered_path = f"{out_dir}/{paper_id}_{track}_altered.json"
    with open(altered_path, "w") as f:
        json.dump(altered_plan, f, indent=2)
    print(f"[{paper_id}/{track}] SAVED BEST REJECT -> {altered_path}")
    return altered_plan


def decompose_general_claims(paper_id: str, plan: dict, out_dir: str) -> list[dict]:
    """Step 1 of the "general" track: identify 5 distinct falsifiable claims
    across the whole plan (>=1 from hypothesis, rest from hypothesis or
    experiment_design). Returns a list of {claim, source_field,
    source_excerpt} dicts, in the order the model produced them."""
    os.makedirs(out_dir, exist_ok=True)
    base = f"{out_dir}/{paper_id}_general_decompose"

    prompt = generate_general_decompose_prompt(plan_as_text(plan))
    completion = call_gemini(prompt, temperature=0.7)
    with open(f"{base}.txt", "w") as f:
        f.write(completion)

    sections = format_tagged_blocks(f"{base}.txt", ["claim", "source_field", "source_excerpt"])
    claims = sections.get("claim", [])
    fields = sections.get("source_field", [])
    excerpts = sections.get("source_excerpt", [])

    n = min(len(claims), len(fields), len(excerpts))
    if n < len(claims) or n < len(fields) or n < len(excerpts):
        print(
            f"[{paper_id}/general] decompose parsing mismatch: "
            f"{len(claims)} claims, {len(fields)} fields, {len(excerpts)} excerpts -- using first {n}"
        )

    result = []
    for i in range(n):
        field = fields[i].strip().lower()
        if field not in ("hypothesis", "experiment_design"):
            print(f"[{paper_id}/general] claim {i + 1}: unrecognized source_field {field!r}, skipping")
            continue
        result.append({"claim": claims[i], "source_field": field, "source_excerpt": excerpts[i]})

    if not any(c["source_field"] == "hypothesis" for c in result):
        print(f"[{paper_id}/general] WARNING: no claim sourced from hypothesis (prompt requires >=1)")

    with open(f"{out_dir}/{paper_id}_general_claims.json", "w") as f:
        json.dump(result, f, indent=2)
    return result


def generate_candidates_for_claim(
    paper_id: str, plan: dict, claim_idx: int, claim: dict, out_dir: str
) -> list[dict]:
    """Step 2 of the "general" track: 3 candidate falsifications for one
    claim, in one call. Returns a list of {original_text, modified_text,
    explanation} dicts.

    Takes `plan` (not just the claim's own excerpt) so the model can see
    -- and, via `_editable_plan_context`, is permitted to touch -- other
    parts of the plan if leaving them unchanged would be inconsistent with
    the error it introduces here."""
    field_label = FIELD_LABEL[claim["source_field"]]
    base = f"{out_dir}/{paper_id}_general_c{claim_idx}_candidates"

    prompt = generate_general_error_candidates_prompt(claim["claim"], claim["source_excerpt"], field_label)
    completion = call_gemini(prompt + _editable_plan_context(plan, field_label), temperature=0.8)
    with open(f"{base}.txt", "w") as f:
        f.write(completion)

    sections = format_tagged_blocks(f"{base}.txt", ["candidate", "original_text", "modified_text", "explanation"])
    originals = sections.get("original_text", [])
    modifieds = sections.get("modified_text", [])
    explanations = sections.get("explanation", [])

    n = min(len(originals), len(modifieds), len(explanations))
    if n < 3:
        print(f"[{paper_id}/general_c{claim_idx}] only parsed {n}/3 candidates")

    return [
        {"original_text": originals[i], "modified_text": modifieds[i], "explanation": explanations[i]}
        for i in range(n)
    ]


def run_general_track(paper_id: str, plan: dict, out_dir: str) -> list[dict]:
    """
    Full "general" track for one paper: decompose into 5 claims, generate 3
    candidates per claim, run every candidate through `process_candidate`.
    Returns the list of surviving altered plans (0 to 15 of them) -- unlike
    the typed tracks, there's no single target to guarantee an output for,
    so a paper simply gets however many of its 15 candidates turn out to be
    genuine, non-trivial errors.
    """
    os.makedirs(out_dir, exist_ok=True)
    claims = decompose_general_claims(paper_id, plan, out_dir)
    survivors = []

    for claim_idx, claim in enumerate(claims, start=1):
        try:
            candidates = generate_candidates_for_claim(paper_id, plan, claim_idx, claim, out_dir)
        except Exception as e:
            print(f"[{paper_id}/general_c{claim_idx}] candidate generation crashed: {e}")
            continue

        field = claim["source_field"]
        for cand_idx, cand in enumerate(candidates, start=1):
            label = f"general_c{claim_idx}_v{cand_idx}"
            base = f"{out_dir}/{paper_id}_{label}"
            error_filename = f"{base}_generated.txt"
            with open(error_filename, "w") as f:
                f.write(
                    f":original_text:\n{cand['original_text']}\n\n"
                    f":modified_text:\n{cand['modified_text']}\n\n"
                    f":explanation:\n{cand['explanation']}\n"
                )
            try:
                result = process_candidate(
                    paper_id=paper_id,
                    plan=plan,
                    field=field,
                    base=base,
                    label=label,
                    original_text=[cand["original_text"]],
                    modified_text=[cand["modified_text"]],
                    explanation_list=[cand["explanation"]],
                    error_filename=error_filename,
                    out_dir=out_dir,
                    metadata={
                        "track": "general",
                        "claim_index": claim_idx,
                        "candidate_index": cand_idx,
                        "claim": claim["claim"],
                    },
                )
            except Exception as e:
                print(f"[{paper_id}/{label}] crashed: {e}")
                result = None
            if result is not None:
                survivors.append(result)

    print(f"[{paper_id}/general] {len(survivors)}/{len(claims) * 3} candidates survived")
    return survivors


ALL_PAPERS = ["AttentionIsAllYouNeed", "BERT", "FLAWS", "SoundnessBench", "InnoEval"]
ALL_TRACKS = [
    "general",
    "hypothesis_internal_contradiction",
    "hypothesis_established_belief_conflict",
    "hypothesis_premise_undermining",
    "ed",
]


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Run the plan error-insertion pipeline.")
    parser.add_argument(
        "--papers",
        default=",".join(ALL_PAPERS),
        help=f"Comma-separated paper ids to run. Default: all ({', '.join(ALL_PAPERS)}).",
    )
    parser.add_argument(
        "--tracks",
        default=",".join(ALL_TRACKS),
        help=f"Comma-separated tracks to run. Default: all ({', '.join(ALL_TRACKS)}).",
    )
    parser.add_argument(
        "--max-attempts", type=int, default=5, help="Retry budget per (paper, typed track). Default: 5."
    )
    parser.add_argument(
        "--out-dir", default="data/altered_plans", help="Output directory. Default: data/altered_plans."
    )
    return parser.parse_args()


if __name__ == "__main__":
    _load_dotenv()
    args = _parse_args()
    papers = [p.strip() for p in args.papers.split(",") if p.strip()]
    tracks = [t.strip() for t in args.tracks.split(",") if t.strip()]

    unknown_tracks = set(tracks) - set(ALL_TRACKS)
    if unknown_tracks:
        raise ValueError(f"Unknown track(s): {unknown_tracks}. Valid tracks: {ALL_TRACKS}")

    for paper_id in papers:
        with open(f"data/research_plans_structured/{paper_id}.json") as f:
            plan = json.load(f)
        for track in tracks:
            try:
                if track == "general":
                    run_general_track(paper_id, plan, args.out_dir)
                else:
                    run_track_with_retries(paper_id, plan, track, args.out_dir, max_attempts=args.max_attempts)
            except Exception as e:
                print(f"[{paper_id}/{track}] unrecoverable failure, skipping: {e}")
