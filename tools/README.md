# tools/ — cost-guarded runner for the original FLAWS LaTeX pipeline

Wraps the unmodified upstream steps (`src/pipeline/single_process/single_error_insertion.py`,
`single_error_identification.py`) with preflight checks, per-paper claim caps, deadlines and a
call budget. Run everything from the repo root.

| Step | Command | Cost |
|---|---|---|
| 1. pick ICML-2026 candidates from arXiv | `python tools/sample_candidates.py "ICML 2026"` | none |
| 2. download LaTeX + zero-cost compile check | `python tools/fetch_and_preflight.py [max_candidates]` | none |
| 3. insert errors, two papers at a time, halting on a real fault | `python -m tools.run_sets --version run1` | LLM calls |
| 4. external identification + scoring | `python -m tools.run_eval_batches --version run1` | LLM calls |

`tools/preflight_state.json` records which candidates were accepted (it is also read by the
`agentic_framework` report scripts). Needs `GOOGLE_API_KEY` in `.env`, a TeX Live install and
`ghostscript`. Spend is capped by `FLAWS_MAX_API_CALLS` (default 400), with pacing and retries via
`FLAWS_MIN_CALL_INTERVAL`, `FLAWS_MAX_ATTEMPTS`, `FLAWS_CALL_TIMEOUT` and the audit log `FLAWS_CALL_LOG`.

Tests (no network): `python -m unittest discover -s tests -t .`

## What is and is not in git

Tracked: the code, `preflight_state.json`, the small text results in `data/run1/`
(`run_summary.json`, `evaluation_summary.json`, `ERROR_REVIEW.md`, and the inserted-error, location,
identification and evaluation files), and the **40 successful altered papers** in
`data/run1/altered_papers/<paper>/` (`altered_N.tex` and the compressed `altered_N_small.pdf`, 50 MB).
These are real papers with **synthetic errors inserted** — see `data/run1/README.md`.
**Not tracked** (see `.gitignore`): `data/papers/` (arXiv sources), `data/_preflight/`, and the rest of
`altered_papers/` (failed attempts, full-size PDFs, build files). To regenerate the untracked parts, run step 2
to fetch the sources; step 3 will not redo papers that `run_summary.json` already marks satisfied, so remove a
paper's entry to force a rebuild (the stored per-claim files should be reused without new API calls — not tested).
