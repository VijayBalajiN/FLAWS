# Altered research plans — v2

**51 research plans, 7 papers, each with exactly one deliberately planted
error**, produced by the propagation-fixed pipeline on 2026-09-15.

This is the current dataset. v1 (`../v1/`) is superseded — it predates the
propagation fix, covers 5 papers, and its classifications used a prompt later
found to over-assign category A.

## Layout

| | |
|---|---|
| `altered_plans/` | 51 JSONs — the dataset. Plan fields hold the **altered** text; `_error_metadata` holds ground truth. |
| `txt/` | the same 51 as readable markdown, no metadata |
| `originals/` | the 7 unaltered plans, same format |

Full raw output — every generation, filter verdict, localization and
self-identification attempt, plus run logs — is in `../../runs/v2/`.

## What's in it

| Source | Entries | Notes |
|---|---|---|
| general track | 23 | survivors of 105 candidates (5 claims × 3 candidates × 7 papers) |
| typed tracks | 28 | 7 papers × 4 tracks, one entry each |

Typed tracks always emit an entry; **16 of 28 are clean accepts** and 12 are
`rejected_best_of_attempts` — every attempt failed and the least-bad was kept.
General-track entries are all clean accepts.

**Check `_error_metadata.status` before using an entry.**

## Two fields that matter

**`status`** — `accepted` survived every filter; `rejected_best_of_attempts`
did not and is not a clean positive.

**`touched_fields`** — which plan sections the edit changed. More than one
means the error propagated across sections to keep the plan internally
coherent, which is the point: a hypothesis-level error that leaves a
restatement of that hypothesis untouched elsewhere makes the plan visibly
self-contradictory, and that's a giveaway with nothing to do with the planted
flaw.

7 of the 28 typed entries propagated (2 of them accepted). No general-track
entry did — decomposed claims are per-field and self-contained, so there's
nothing elsewhere to keep in sync.

## Classification

General-track entries carry `_error_metadata.classification` (A/B/C/D against
`taxonomy_te.txt`). Typed entries don't — their category is fixed by the track
that generated them, so classifying them would be circular.

Across all 105 general candidates: **A 6% · B 4% · C 34% · D 56%**. Note that
D ("Others") is not in `taxonomy_te.txt` — it was added as a catch-all, so its
boundary is ours.

Full analysis: `docs/results_v2.md`. Pipeline mechanics: `docs/pipeline.md`.
