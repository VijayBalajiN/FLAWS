# The pipeline

How a published paper becomes a benchmark item: a research plan with exactly
one deliberately-introduced flaw, plus ground truth about where that flaw is
and what kind it is.

Two phases, run by two different entry points.

---

## Phase 1 — Extraction

Turns a PDF into a structured research plan. One paper at a time.

| # | Step | Code | Notes |
|---|------|------|-------|
| 1 | PDF → TEI XML | `src/utils/paper_content_extraction.py` | GROBID at `localhost:8070` (Docker, `lfoppiano/grobid:0.8.0`). Falls back to PyPDF2 if GROBID fails. |
| 2 | Drop outcome sections | same | Any heading containing `result`, `conclusion`, `discussion`, `findings` is skipped. Title, abstract, intro, method, related work, appendix are kept. |
| 3 | Rewrite as a plan | `src/utils/research_plan_extraction.py` | One `gemini-2.5-pro` call, temp 0.1. Prompt is copied verbatim from AIScientist's `extract_research_plan.py`. Output: `## Problem` / `## Method` / `## Experiment Design`, first person, proposal-stage framing only. |
| 4 | Split sections | `src/utils/plan_txt_parser.py` | Regex header split. Also recognises an optional `## Hypothesis` header (added for phase 2's re-split). |
| 5 | Derive the hypothesis | `src/utils/ref_theory_deriver.py` | One LLM call over the Problem section, producing a single falsifiable claim. This is AIScientist's `ref_theory` under a clearer name. |
| 6 | Assemble | `src/utils/build_research_plan_json.py` | Writes `data/research_plans_structured/<paper>.json`. |

Output schema:

```json
{
  "paper_id":          "BERT",
  "problem":           "...",
  "method":            "...",
  "experiment_design": "...",
  "hypothesis":        "..."
}
```

This file is the canonical input to phase 2. Everything upstream of it is
disposable.

Run it:

```bash
python3 src/utils/paper_content_extraction.py data/papers/pdfs/X.pdf data/paper_content
python3 src/utils/research_plan_extraction.py data/paper_content/X.txt data/research_plans/X.txt
python3 -m src.utils.build_research_plan_json X data/research_plans/X.txt data/research_plans_structured/X.json
```

---

## Phase 2 — Error insertion

`src/pipeline/plan_error_insertion.py`. Five tracks, one shared verification
chain.

```bash
python3 -m src.pipeline.plan_error_insertion \
  --papers BERT,FLAWS --tracks general,ed --out-dir data/runs/v2
```

`--papers` and `--tracks` both default to everything.

### The five tracks

| Track | Target field | How many candidates |
|-------|--------------|---------------------|
| `general` | hypothesis **or** experiment_design (per claim) | 15 per paper |
| `hypothesis_internal_contradiction` | hypothesis | 1 per attempt, ≤5 attempts |
| `hypothesis_established_belief_conflict` | hypothesis | 1 per attempt, ≤5 attempts |
| `hypothesis_premise_undermining` | hypothesis | 1 per attempt, ≤5 attempts |
| `ed` | experiment_design | 1 per attempt, ≤5 attempts |

**The general track** (`run_general_track`) works in two stages:

1. `decompose_general_claims` asks for **5 falsifiable claims** drawn from the
   plan, each tagged with the field it came from. At least one must come from
   the hypothesis. Saved as `<paper>_general_claims.json`.
2. For each claim, `generate_candidates_for_claim` asks for **3 candidate
   falsifications**, with an explicit instruction that they must differ in
   *underlying mechanism*, not wording.

5 × 3 = 15 candidates per paper, each processed independently. There is no
retry — diversity comes from having many distinct claims, not from resampling
the same one. (See `docs/diversity_mechanisms_reference.md` for why: neither
original FLAWS nor ResearcherBench uses temperature for diversity either.)

**The typed tracks** (`run_track_with_retries`) generate one candidate per
attempt against a fixed error type, retrying up to 5 times. If all 5 fail,
`rank_attempts` scores the rejects on how close they got and the best one is
saved anyway with `status: "rejected_best_of_attempts"` — so every
(paper, typed track) pair always produces a file.

Reject ranking tiers, best first:

1. Passed both filters, only caught by self-identification (ranked by *lowest*
   Levenshtein match — hardest to re-find)
2. Passed the invalid filter, failed the "too easy" filter
3. Failed the invalid filter
4. Generation didn't parse (excluded entirely)

### Propagation: the whole plan is editable

Every generation prompt is appended with `_editable_plan_context`, which shows
the model the **entire plan** and says:

- at least one edit **must** anchor in the track's target field
- further edits elsewhere are **permitted**, but only when truly necessary to
  keep the plan internally coherent

This exists because a hypothesis-level error that doesn't ripple into a
restatement of that hypothesis elsewhere leaves the altered plan visibly
self-inconsistent — two versions of its own claim sitting side by side — which
is a giveaway unrelated to the actual flaw.

Because instructions aren't always followed, `process_candidate` also enforces
the anchor **in code**:

```python
if not any(o.strip() and o.strip() in plan[field] for o in original_text):
    reject
```

In the v2 run this fired 22 times out of 105 general candidates. It is not a
no-op.

### The shared verification chain (`process_candidate`)

Every candidate from every track goes through the same gauntlet:

| Stage | What it does | Rejects if |
|-------|--------------|------------|
| anchor check | code-level, see above | no edit landed in the target field |
| `generate_filter_invalid_prompt` | is the "error" actually an error, and not self-announcing? | response isn't `No changes required` |
| `generate_filter_easy_prompt` | is it too obvious? | response isn't `No changes required` |
| `modify_source` | splices every original→modified pair into `plan_as_text(plan)` — the whole plan, not just the target field | fuzzy match fails (threshold 0.9) |
| `parse_sections` | re-splits the altered blob back into fields; diffing against the original yields `touched_fields` | the splice broke a section header |
| `generate_localization_prompt` | finds any *other* excerpt the edit has now made incorrect | — (records `localized_errors`) |
| `generate_internal_identification_prompt` | shows the model the whole altered plan and asks it to find the flaw | — |
| `levenshtein_identify` | scores the model's guesses against ground truth (threshold 0.5, top-5) | the model found it → too easy |

Survivors are written to `<out_dir>/<paper>_<label>_altered.json`.

All filter/localize/identify calls run at temperature 0.0; generation runs at
0.7. Model is `gemini-2.5-pro` throughout, with retry-and-backoff in
`call_gemini`.

---

## Phase 3 — Classification (post-hoc, general track only)

`src/utils/classify_general_errors.py` tags each general-track candidate
against the taxonomy in `taxonomy_te.txt`:

| | Category | Operational audit (the disambiguator that actually decides it) |
|---|---|---|
| **A** | Internal Contradiction | The text's own rules break it. If the contradiction relies on an *unstated* assumption, it's a specification gap, not a contradiction — that's D. |
| **B** | Conflict with Established Beliefs | Must produce a *fork*: the text says one thing, the field says another. |
| **C** | Undermining a Premise | Find a contested term, then construct a scenario where its operationalisation and its intended meaning diverge. |
| **D** | Others | Everything else — confounded designs, omitted controls, gameable metrics, timescale mismatches. |

**D is not in `taxonomy_te.txt`.** It was added as a catch-all so the
classifier has somewhere to put things the three real categories don't cover.
Worth remembering when quoting the distribution: D's boundary is ours, not the
source document's.

Classification is deliberately decoupled from generation — the generator is
never told which category to aim for, so the distribution is a measurement
rather than a quota.

```bash
python3 -m src.utils.classify_general_errors data/runs/v2
```

Survivors get the result merged into `_error_metadata.classification`; rejects
get a `_classification.json` sidecar. Uses `gemini-2.5-flash` with thinking
disabled (`gemini-2.5-pro` can't disable it).

Typed tracks are **not** classified — their category is fixed by construction.

---

## Output files

Per candidate, under `--out-dir`:

| File | Contents |
|------|----------|
| `<paper>_general_claims.json` | the 5 decomposed claims (general track only, once per paper) |
| `<label>_generated.txt` | raw generation: `:original_text:` / `:modified_text:` / `:explanation:` |
| `<label>_filter_invalid.txt` | invalid-filter verdict |
| `<label>_filter_easy.txt` | easy-filter verdict |
| `<label>_localized.txt` | knock-on excerpts made incorrect by the edit |
| `<label>_internal_id.txt` | the model's attempt to find its own planted flaw |
| `<label>_<model>_score.txt` | Levenshtein scores for that attempt |
| `<label>_altered.json` | **the dataset entry** — full altered plan + metadata |
| `<label>_classification.json` | taxonomy tag for rejects (survivors carry it inline) |

Labels are `general_c<claim>_v<candidate>` or `<track>` / `<track>_attempt<n>`.

`_altered.json` schema:

```json
{
  "paper_id": "...", "problem": "...", "method": "...",
  "experiment_design": "...", "hypothesis": "...",
  "_error_metadata": {
    "status": "accepted" | "rejected_best_of_attempts",
    "field": "hypothesis",
    "touched_fields": ["hypothesis", "problem"],
    "original_text": [...], "modified_text": [...], "explanation": [...],
    "localized_errors": [...],
    "track": "...", "claim_index": 1, "candidate_index": 3, "claim": "...",
    "classification": { "category": "C", "category_name": "...", "reasoning": "..." }
  }
}
```

The four plan fields hold the **altered** text. `touched_fields` says which
ones changed — a list longer than one means propagation fired.

---

## Diagrams

Rendered versions of the above: <https://claude.ai/code/artifact/5f3624a6-e690-4eba-a998-ed660cb8e9a3>
