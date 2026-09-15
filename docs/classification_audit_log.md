# Classification audit log

Manual audit of all 75 general-track classifications (13 survivors + 62
rejects) against the A/B/C/D taxonomy, done by reading every original/
modified/explanation triple against the taxonomy definitions -- not by
running an automated check.

## What was found

The first classification prompt (`generate_classify_error_prompt` v1) only
had the one-line definitions of A/B/C/D, missing `taxonomy_te.txt`'s
**Operational Audit** disambiguators. This produced a real, confirmed
inconsistency: **confounded-design errors sometimes got classified A instead
of D**, because "the mechanism prevents the stated goal from being achieved"
was applied loosely enough to justify A for almost anything, without
checking A's actual caveat (Operational Audit: a contradiction resting on an
unstated/omitted assumption -- like a missing control -- is not a true
internal contradiction, it's a specification gap).

Proof this was a real inconsistency, not just a subjective disagreement:
within the SAME paper's own classification run, structurally identical
self-described confounds landed in different categories:

- **`InnoEval_general_c2_v1`** (non-anonymized review -> reviewer-bias
  confound) got **A**, while **`InnoEval_general_c5_v1`** in the same list
  (also self-described as "a confounding variable" in its own explanation)
  correctly got **D**.
- **`BERT_general_c2_v1`** (NSP-removal necessitates smaller LR -> a
  confound) got **A**, while 7 structurally identical sibling confounds in
  BERT's own list (`c2_v2`, `c2_v3`, `c3_v1/2/3`, `c4_v2`, `c5_v3`) all
  correctly got **D**.

`BERT_general_c2_v1` is one of the 13 dataset survivors, so this wasn't just
a reject-pool curiosity -- it affected a real dataset entry.

## Fix applied

1. Corrected `plan_prompts.py`: `generate_classify_error_prompt` now quotes
   the Operational Audit test for each category verbatim from
   `taxonomy_te.txt`, not just the one-line definitions.
2. Manually corrected the 2 confirmed errors in the dataset:
   - `BERT_general_c2_v1_altered.json`: `classification.category`
     `A -> D`.
   - `InnoEval_general_c2_v1_classification.json`: `category` `A -> D`
     (this one was a reject, no `_altered.json` to update).

## Not done for v1

The rest of the 75 v1 candidates were NOT re-classified with the fixed prompt
-- only these 2 confirmed cases were hand-corrected. A handful of other
borderline calls were flagged during the audit (mostly at the same A/D
boundary, and a recurring pattern where explicit "category error" language got
D when C's definition arguably covers it) but weren't clear-cut enough to
hand-correct without re-running.

**v1's classifications should therefore be treated as unreliable.** Use v2.

## Resolved in v2 (2026-09-15)

The v2 run re-generated the general track for all 7 papers and classified all
105 candidates from scratch with the **corrected** prompt -- the one that
quotes each category's Operational Audit verbatim. So the defect described
above does not exist in `data/altered_plans_v2/`.

The correction visibly moved the distribution in the predicted direction:

| | v1 (75 candidates, loose prompt) | v2 (105 candidates, fixed prompt) |
|---|---|---|
| A -- Internal Contradiction | over-assigned; the bug | 6 (6%) |
| D -- Others | under-assigned | 59 (56%) |

A is now rare, which is the correct outcome: a genuine internal contradiction
requires the text's *own stated rules* to break it, and most generated errors
rest on an unstated assumption instead -- which the Operational Audit
explicitly routes to D rather than A. That was precisely the distinction the
v1 prompt was missing.

Full v2 distribution and caveats: `docs/results_v2.md`.

## Standing caveat: category D is not in the source

`taxonomy_te.txt` defines **only** A, B and C. "D. Others" was added by us so
the classifier had somewhere to put errors the three real categories don't
cover. This matters in two ways:

1. Any audit of D against "the taxonomy" is self-referential -- D's definition
   is ours, so it can't be checked against the source document.
2. The 56% D figure is a statement about *what the three source categories
   don't cover*, not a finding from the source itself. Say so when quoting it.

One known borderline case from the original audit: `InnoEval_general_c2_v1`
was corrected A -> D, but could defensibly have been B. D is not wrong there;
it just isn't the only defensible call.
