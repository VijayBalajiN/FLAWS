# run1 — 20 ICML-2026 papers, 2 inserted errors each

**These errors are synthetic.** Each one was written by `gemini-2.5-pro` into a copy of a real
paper to build a benchmark. The "modified text" in `inserted_error/` is *not* what the paper says,
and the files are named by arXiv id only to make the pairing traceable. Do not quote them as the
authors' claims.

| File / folder | What it is |
|---|---|
| `run_summary.json` | per paper: claims tried, outcome of each attempt (`SUCCESS`, `filtered_easy`, `self_identified`, ...) |
| `evaluation_summary.json` | per inserted error: was it identified by the external model (Levenshtein and/or LLM judge) — 11/40 |
| `ERROR_REVIEW.md` | manual review of all 40 errors (25 good, 12 weak, 3 bad) |
| `inserted_error/` | the generated error (`:original_text:`, `:modified_text:`, `:explanation:`, `:claim:`) and filter verdicts |
| `location_error/` | every excerpt the error makes wrong in the altered paper (used as gold for scoring) |
| `identified_errors/`, `evaluation_errors/` | internal (insertion-time) and external identification outputs and scores |
| `generated_claims/` | the falsifiable claims extracted from each paper |

`altered_papers/<paper>/altered_N.tex` and `altered_N_small.pdf` are the 40 papers *with the errors
inserted* (the files `agentic_framework` reads). **They look like the real papers but contain false
claims; they are not the authors' work.** Failed attempts, full-size PDFs and build files are not
versioned; see `tools/README.md`.
