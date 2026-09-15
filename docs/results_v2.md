# Results — v2 run

`data/dataset/v2/` (51 entries), raw output in `data/runs/v2/`. Generated
2026-09-15 with the propagation-fixed pipeline across all 7 papers.

This supersedes v1 (`data/dataset/v1/`, raw output in `data/runs/v1/`), which
used the pre-propagation code and covered only 5 papers. v1 is kept for
comparison; don't build on it.

---

## General track

5 claims × 3 candidates × 7 papers = **105 candidates**. No retries.

### Survivors

| Paper | Survivors / 15 |
|---|---|
| FLAWS | 5 |
| AttentionIsAllYouNeed | 4 |
| SoundnessBench | 4 |
| InnoEval | 3 |
| McCammonProteinDynamics | 3 |
| BERT | 2 |
| GrapheneFieldEffect | 2 |
| **Total** | **23** |

On the **identical 5-paper subset** — same papers, same 75 candidates — v1
produced 13 survivors and v2 produced 18 (17% → 24%).

Resist reading that as a measured effect of the propagation fix. It is a single
pair of runs at n=75 with a stochastic generator; nothing here separates the
code change from ordinary run-to-run variance. Establishing the effect would
take repeated runs of both versions, which hasn't been done.

### Where all 105 went

| Outcome | n | % |
|---|---|---|
| filtered: too easy | 34 | 32% |
| self-identified by the model → discarded | 25 | 24% |
| **survived** | **23** | **22%** |
| rejected: no edit landed in the required field | 22 | 21% |
| filtered: invalid | 1 | 1% |

The 22 anchor rejections split 16 hypothesis / 6 experiment_design. That check
is load-bearing: without it those 22 would have become errors sitting in a
field the track never meant to target, and the hypothesis tracks would
quietly have become "edit anything" tracks.

Only 1 candidate in 105 was rejected as *invalid*. The generator reliably
produces real errors; the difficulty is making them **hard**, not making them
wrong — "too easy" plus "the model found it itself" accounts for 59 of the 82
losses (72%).

### Classification

Post-hoc A/B/C/D against `taxonomy_te.txt`, generator never told what to aim
for.

| | All 105 | The 23 survivors |
|---|---|---|
| A — Internal Contradiction | 6 (6%) | 1 |
| B — Conflict with Established Beliefs | 4 (4%) | 1 |
| C — Undermining a Premise | 36 (34%) | 10 |
| D — Others | 59 (56%) | 11 |

Per paper (all 15 candidates each):

| Paper | A | B | C | D |
|---|---|---|---|---|
| AttentionIsAllYouNeed | 2 | – | 2 | 11 |
| BERT | – | – | 5 | 10 |
| FLAWS | 1 | – | 10 | 4 |
| SoundnessBench | 1 | – | 7 | 7 |
| InnoEval | – | 1 | 7 | 7 |
| McCammonProteinDynamics | 1 | 2 | 2 | 10 |
| GrapheneFieldEffect | 1 | 1 | 3 | 10 |

**The headline finding: 56% of naturally-generated plan errors fall outside
the taxonomy entirely.** When you let a model find its own falsifiable claims
and break them, what it mostly produces is *experimental-design* flaws —
confounds, omitted controls, gameable metrics, timescale mismatches — not the
textual/logical failures A, B and C describe.

Two caveats before quoting that number:

- **D is ours, not the source's.** `taxonomy_te.txt` defines only A, B and C.
  D was added as a catch-all. Its boundary is a decision we made.
- FLAWS is the outlier (C=10, D=4). Its plan is about evaluation methodology,
  so its claims are *about* definitions — which is exactly C's territory.
  Distribution is a function of subject matter, not just of the generator.

---

## Typed tracks

7 papers × 4 tracks = **28 pairs**, 99 attempts (retry budget 5 per pair).

| Outcome per attempt | n | % |
|---|---|---|
| filtered: too easy | 50 | 51% |
| self-identified → discarded | 29 | 29% |
| **accepted** | **16** | **16%** |
| rejected: no edit landed in the required field | 4 | 4% |

At the pair level: **16 of 28 clean accepts**, 12 exhausted all 5 attempts and
fell back to the best-ranked reject.

| Track | Accepted | Fallback |
|---|---|---|
| `hypothesis_premise_undermining` | 5 | 2 |
| `hypothesis_established_belief_conflict` | 4 | 3 |
| `ed` | 4 | 3 |
| `hypothesis_internal_contradiction` | 3 | 4 |

Per *attempt* the typed tracks are harder than the general track — 16% vs 22% —
for a structural reason: a typed track must hit *one* named error type against
*one* fixed field, so it can't route around a hard target the way the general
track can by moving to a different claim. The retry budget is what closes the
gap at the pair level.

Internal contradiction is the hardest of the four, which is consistent with the
classification result below: genuine internal contradictions are rare, because
most plausible-looking flaws rest on an unstated assumption rather than on the
text's own stated rules breaking.

The best-of-rejects fallback means every pair still yields a file — check
`status` before treating one as a clean positive.

---

## Propagation

The thing this run was built to fix. **It works, and it is common in exactly
the place it should be.**

**7 of the 28 typed entries (25%) touched more than one field. Zero of the 23
general-track entries did.**

| Entry | Fields touched | Status |
|---|---|---|
| `BERT_hypothesis_premise_undermining` | hypothesis + problem | accepted |
| `McCammon…_hypothesis_established_belief_conflict` | hypothesis + problem | accepted |
| `AttentionIsAllYouNeed_hypothesis_internal_contradiction` | hypothesis + method | fallback |
| `AttentionIsAllYouNeed_hypothesis_established_belief_conflict` | hypothesis + method | fallback |
| `BERT_hypothesis_internal_contradiction` | hypothesis + method | fallback |
| `BERT_hypothesis_established_belief_conflict` | hypothesis + problem | fallback |
| `GrapheneFieldEffect_hypothesis_premise_undermining` | hypothesis + problem + experiment_design | fallback |

Every one is a hypothesis track. That is the expected shape: a hypothesis gets
restated elsewhere in the plan — in the Problem section's framing, or implied
by a Method choice — so editing it in one place alone leaves the plan
contradicting itself. Decomposed general-track claims are per-field and
self-contained, so there is nothing to keep in sync.

The two edit patterns are distinct and both legitimate:

- **hypothesis + problem** — the Problem section restates the hypothesis, and
  both copies are edited to match.
- **hypothesis + method** — the hypothesis is given a mechanism, and the Method
  is rewritten so it actually implements (or fails to implement) that
  mechanism. In `AttentionIsAllYouNeed_hypothesis_internal_contradiction` the
  Method's positional-encoding step is removed, which is what makes the
  hypothesis's contradiction real rather than merely asserted.

Two worked examples:

**`McCammonProteinDynamics_hypothesis_established_belief_conflict`** —
`status: accepted`, touched `hypothesis` + `problem`.

> *"…local atomic motions exhibit a **simple** diffusional character, **with
> mean-squared displacement increasing linearly with time across all
> femtosecond-to-picosecond timescales**."*

The error: at femtosecond scales motion is *ballistic* (MSD ∝ t²), not
diffusive (MSD ∝ t) — diffusion only emerges after many collisions. Real
statistical mechanics, and an expert would catch it.

The propagation: the Problem section restates the hypothesis nearly verbatim,
and the model edited **both**. Had it edited only the hypothesis field, the
plan would contain two conflicting versions of its own central claim — a
tell that has nothing to do with the physics. This is exactly the failure the
fix was for.

**`GrapheneFieldEffect_hypothesis_premise_undermining`** —
`status: rejected_best_of_attempts`, touched `hypothesis` + `problem` +
`experiment_design`. Swaps "tune carrier *concentration*" for "tune
*conductivity and carrier type*" consistently across all three sections,
including the ED's measurement plan. A hypothesis-level change rippling into
the experiment design — the case originally raised as the motivating concern.

The third accepted-and-propagated entry is
**`BERT_hypothesis_premise_undermining`**, which substitutes the *training
objective* for the *representational property* — "jointly conditioned on both
left and right context" becomes "trained to predict masked tokens using the
full unmasked context" — and edits the Problem section's restatement to match.
A reader who knows BERT has to notice that the objective and the property
aren't the same claim.

### Why this works

The anchor requirement is doing the load-bearing work, in both directions. It
forces an edit into the track's target field (22 general-track candidates were
rejected for failing this), while the surrounding context explicitly permits
further edits where coherence demands them. Loosening the anchor was what
originally let an entire hypothesis-track edit drift into Method — the bug this
design fixes.

Frequency looks right rather than tuned: 25% of typed entries, concentrated
entirely in hypothesis tracks, with none in general. The model is not
propagating for its own sake.

---

## Highlights worth reading

The physical-science papers produced errors that need real domain knowledge —
the strongest argument for having expanded beyond AI/ML:

| Item | The error |
|---|---|
| `McCammon…_hypothesis_established_belief_conflict` | Ballistic vs diffusive MSD at femtosecond timescales *(the propagation example above)* |
| `McCammon…_general_c3_v1` | Periodic velocity rescaling (Berendsen-type) doesn't generate a correct canonical ensemble — suppresses fluctuations, which is precisely what the study set out to measure |
| `McCammon…_general_c2_v1` | Plan targets tyrosine ring-flip transitions, which take ns–µs, with a simulation "several picoseconds" long — orders of magnitude too short |
| `Graphene…_general_c4_v1` | Unidirectional −100 V → +100 V gate sweep can't detect hysteresis from oxide charge traps |
| `Graphene…_general_c5_v2` | Narrows the goal to carrier mobility alone, dropping on/off ratio — graphene's known weakness, since it has no bandgap |

`McCammon_general_c3_v1` is the pick of them: a thermostat choice that is
subtly wrong *for this specific study's purpose*. A reader would have to know
both the thermostat literature and what the paper is measuring.

---

## Known issues

1. **Corpus is small.** 7 papers, 23 general survivors. Enough to characterise
   the method, not to train or benchmark on.
2. **The "too easy" filter dominates losses** (34 + 25 = 56% of general-track
   candidates). Either the filters are strict or the generator is shallow —
   this hasn't been separated, and it's the highest-value thing to investigate.
3. **D was invented by us.** See above. Any published distribution needs to say
   so.
4. **v1 and v2 disagree by construction.** v1's classifications used the
   pre-fix prompt that over-assigned A; see `classification_audit_log.md`.
   Don't pool them.
5. **Typed tracks aren't classified.** Their category is fixed by construction,
   so the A/B/C/D distribution above describes the general track only — 105 of
   the pipeline's candidates, not all 204.
6. **`rejected_best_of_attempts` entries are not clean positives.** They failed
   every attempt and were kept as least-bad. Filter on `status` before use.
