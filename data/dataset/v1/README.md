# FLAWS-style altered research plans — v1

> **Superseded by v2.** This run predates the propagation fix and covers only 5
> papers; its classifications used the prompt later found to over-assign
> category A (see `docs/classification_audit_log.md`). Kept for comparison and
> because the confidence-ranking and ResearchBench-style work below exists
> nowhere else. For current data use `data/dataset/v2/`.
>
> Contents: `altered_plans/` (25 JSONs), `txt/` (human-readable renderings),
> `originals/` (the unaltered plans), `researchbench_style/` (the replication
> described below, Attention only). Full raw run output, including every
> intermediate, is in `data/runs/v1/`.

25 research plans (5 papers x 5 tracks), each with one synthetic error inserted
via FLAWS's error-insertion pipeline. Tracks: `hypothesis` (untyped),
`hypothesis_internal_contradiction` / `hypothesis_established_belief_conflict` /
`hypothesis_premise_undermining` (typed, per `taxonomy_te.txt`), and `ed`
(typed, 8-category experiment-design taxonomy).

**Second acceptance signal added**: alongside the original LLM-judge pipeline,
hypothesis-track plans were also scored with a confidence-based check (see
`confidence_ranking.py` in FLAWS) inspired by a hypothesis-ranking paper
(alphaxiv 2608.17270) that ranks candidate hypotheses by a model's intrinsic
confidence rather than explicit judge reasoning. True logit/energy scoring
needs Vertex AI (logprobs are disabled for every model on the public Gemini
API); this uses a sampling proxy instead -- forced single-letter A/B choice
between the true and altered hypothesis, no reasoning allowed, repeated 10x.
`win_rate` = fraction of votes for the true original; low win-rate means the
model can't reliably tell the error from the truth even without reasoning.

**ResearchBench-style negative construction (`researchbench_style/`, Attention only)**:
the 2608.17270 paper's actual data source is ResearchBench (arxiv 2503.21248,
not to be confused with the differently-named GAIR-NLP/ResearcherBench repo,
which is an unrelated Deep-Research-agent benchmark). ResearchBench doesn't
edit the true hypothesis text at all -- it *composes* a hypothesis from a
research question + "inspirations" (background/prior-work snippets), and
gets its 15 negatives from two sources: (a) 5 composed from the question +
wrong/irrelevant inspirations, (b) 10 composed from the question + an
incomplete subset of the correct inspirations. Replicated this for Attention
using its own real Background/Introduction content as inspirations
(`researchbench_style_negatives.py`), then ran their exact head-to-head
comparison (`researchbench_style_ranking.py`): confidence-style forced pick
vs. prompted-judge-with-reasoning pick, over the 16 candidates. Result across
5 shuffles: confidence-style 1/5 correct, prompted-judge 0/5 -- directionally
consistent with the paper's finding, but n=5 is far too small to be a real
statistical result, just an honest single-paper spot check.

| Paper | Track | Error type | Status | Confidence win-rate |
|---|---|---|---|---|
| Attention Is All You Need | hypothesis | rests on a false premise | ✅ accepted (via confidence check) | 0.0 |
| Attention Is All You Need | hypothesis_internal_contradiction | N/A | ⚠️ not perfect | 1.0 |
| Attention Is All You Need | hypothesis_established_belief_conflict | N/A | ⚠️ not perfect | 1.0 |
| Attention Is All You Need | hypothesis_premise_undermining | N/A | ✅ accepted (via confidence check) | 0.2 |
| Attention Is All You Need | ed | Confounded design | ⚠️ not perfect | 1.0 |
| BERT | hypothesis | conflicts with established knowledge | ⚠️ not perfect | 1.0 |
| BERT | hypothesis_internal_contradiction | Internal Contradiction | ✅ accepted | 1.0 |
| BERT | hypothesis_established_belief_conflict | N/A | ⚠️ not perfect | 1.0 |
| BERT | hypothesis_premise_undermining | Undermining a Premise | ✅ accepted | 1.0 |
| BERT | ed | Confounded design | ✅ accepted | n/a |
| FLAWS | hypothesis | rests on a false premise | ✅ accepted | 1.0 |
| FLAWS | hypothesis_internal_contradiction | Internal Contradiction | ✅ accepted | 0.0 |
| FLAWS | hypothesis_established_belief_conflict | N/A | ⚠️ not perfect | 1.0 |
| FLAWS | hypothesis_premise_undermining | N/A | ⚠️ not perfect | 1.0 |
| FLAWS | ed | Insufficient step | ✅ accepted | n/a |
| SoundnessBench | hypothesis | internal contradiction | ✅ accepted | 1.0 |
| SoundnessBench | hypothesis_internal_contradiction | Internal Contradiction | ✅ accepted | 1.0 |
| SoundnessBench | hypothesis_established_belief_conflict | N/A | ⚠️ not perfect | 1.0 |
| SoundnessBench | hypothesis_premise_undermining | Undermining a Premise | ✅ accepted | 1.0 |
| SoundnessBench | ed | Wrong metric/measurement | ✅ accepted | n/a |
| InnoEval | hypothesis | rests on a false premise | ✅ accepted | 1.0 |
| InnoEval | hypothesis_internal_contradiction | Internal Contradiction | ✅ accepted | 1.0 |
| InnoEval | hypothesis_established_belief_conflict | Conflict with Established Beliefs | ✅ accepted | 1.0 |
| InnoEval | hypothesis_premise_undermining | Undermining a Premise | ✅ accepted | 1.0 |
| InnoEval | ed | Confounded design | ✅ accepted | n/a |

**17/25 accepted** (15 via the original pipeline + 2 for Attention rescued
via the confidence check), 8/25 "not perfect" (best of 5 rejected attempts,
kept anyway rather than discarding). Note the confidence check mostly agrees
with the original pipeline (win-rate 1.0 almost everywhere) -- it caught two
genuinely hard-to-detect Attention errors the reasoning-based judge had
dismissed as "too easy" for unrelated reasons, without over-turning anything
else.
