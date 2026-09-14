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

## Not yet done

The rest of the 75 were NOT re-classified with the fixed prompt -- only
these 2 confirmed cases were hand-corrected. A handful of other borderline
calls were flagged during the audit (mostly at the same A/D boundary, and a
recurring pattern where explicit "category error" language got D when C's
definition arguably covers it) but weren't clear-cut enough to hand-correct
without re-running. A full re-classification with the fixed prompt would
likely change more than these 2 and is worth doing if the classification
data is going to be relied on for anything beyond a rough distribution.
