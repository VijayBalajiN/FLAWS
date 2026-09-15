# Docs

A FLAWS-style error-insertion benchmark, adapted from full LaTeX papers to
short structured **research plans** (Problem / Method / Experiment Design /
Hypothesis) extracted with AIScientist's GROBID pipeline.

One item = one research plan with exactly one deliberately-planted flaw, plus
ground truth on where it is, why it's wrong, and what kind of error it is.

## Start here

| Doc | What it answers |
|---|---|
| [`pipeline.md`](pipeline.md) | How it works — every stage, prompt, threshold, and output file |
| [`corpus.md`](corpus.md) | Which papers, where they came from, how to add one |
| [`results_v2.md`](results_v2.md) | What the current run produced, and what's wrong with it |
| [`classification_audit_log.md`](classification_audit_log.md) | A real classification bug, how it was found, how it was fixed |
| [`diversity_mechanisms_reference.md`](diversity_mechanisms_reference.md) | How FLAWS and ResearcherBench actually get diversity (neither uses temperature) |

Diagrams: <https://claude.ai/code/artifact/5f3624a6-e690-4eba-a998-ed660cb8e9a3>

## Where things live

```
data/
  papers/pdfs/                 source PDFs
  paper_content/               GROBID output (text + TEI XML)
  research_plans/              LLM-written plans, markdown
  research_plans_structured/   ← canonical pipeline input, one JSON per paper

  dataset/                     ← curated deliverables
    v1/  altered_plans · txt · originals · researchbench_style · README
    v2/  current

  runs/                        ← full raw output, every intermediate
    v1/
    v2/

src/
  utils/                       extraction, prompts, classification, formatting
  pipeline/plan_error_insertion.py   the orchestrator

taxonomy_te.txt                error taxonomy (A/B/C only — D is ours)
```

`dataset/` is what you'd hand to someone. `runs/` is the full paper trail —
every generation, filter verdict, localization and self-identification
attempt, kept so any entry can be traced back to why it survived.

## Run it

```bash
# 1. extraction, per paper
python3 src/utils/paper_content_extraction.py data/papers/pdfs/X.pdf data/paper_content
python3 src/utils/research_plan_extraction.py data/paper_content/X.txt data/research_plans/X.txt
python3 -m src.utils.build_research_plan_json X data/research_plans/X.txt data/research_plans_structured/X.json

# 2. error insertion — defaults to all papers, all 5 tracks
python3 -m src.pipeline.plan_error_insertion --out-dir data/altered_plans_v2

# 3. classification (general track only)
python3 -m src.utils.classify_general_errors data/altered_plans_v2
```

Needs GROBID on `localhost:8070` for step 1 and `GOOGLE_API_KEY` in `.env` for
2 and 3. Runs take hours; use `nohup`/background and read the logs.

## Reading a result

Every dataset entry is a `*_altered.json`: the four plan fields hold the
**altered** text, and `_error_metadata` holds the ground truth.

Two fields to check before trusting an entry:

- **`status`** — `accepted` means it survived every filter.
  `rejected_best_of_attempts` means every attempt failed and this was kept as
  the least-bad; it is not a clean positive.
- **`touched_fields`** — more than one entry means the error propagated across
  sections to keep the plan internally coherent.
