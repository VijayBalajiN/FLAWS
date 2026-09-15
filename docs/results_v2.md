# Results — v2 run

`data/altered_plans_v2/`, generated 2026-09-15 with the propagation-fixed
pipeline across all 7 papers.

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

⏳ *Currently re-running for the original 5 papers. Numbers below cover the 2
new papers only; this section gets updated when the run lands.*

8 (paper, track) pairs → 48 attempts:

| Outcome | n |
|---|---|
| filtered: too easy | 25 |
| self-identified → discarded | 10 |
| **accepted** | **3** |
| exhausted 5 attempts → best-of-rejects fallback | 5 |

Only 3 of 8 pairs produced a clean survivor. Per *attempt* the typed tracks are
far harder than the general track — **3/48 (6%) vs 23/105 (22%)** — and for a
structural reason: a typed track must hit *one* named error type against *one*
fixed field, so it can't route around a hard target the way the general track
can by moving to a different claim. The 5-attempt retry budget is what closes
the gap at the pair level.

The best-of-rejects fallback means every pair still yields a file — but check
`status` before treating one as a clean positive.

---

## Propagation

The thing this run was built to fix. **It works, and it's rare.**

Two of the 31 saved plans touched more than one field:

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

**Both cases are typed hypothesis tracks. Zero of the 23 general-track
survivors propagated**, which makes sense: general claims are decomposed
per-field and are usually self-contained, so there's nothing elsewhere to keep
in sync. Propagation fires when a claim is restated across sections — which is
what hypotheses do and what decomposed sub-claims don't.

So the mechanism is correct but low-frequency. If more propagated examples are
wanted, the lever is the corpus (plans that restate their hypothesis) or the
prompt (currently *permits* rather than *encourages* cross-field edits) — not
the anchor logic, which is working.

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
   so the A/B/C/D distribution above describes the general track only.
6. **`rejected_best_of_attempts` entries are not clean positives.** They failed
   every attempt and were kept as least-bad. Filter on `status` before use.
