# Review of the 40 inserted errors (run1)

Judged by reading original vs. modified LaTeX plus the generator's explanation. This is my read, not ground truth.
Criteria: a real, coherent flaw; not self-announcing; subtle; size of edit; no leaked artifacts.
G = good, M = weak/questionable, B = bad (should not be used as is).
The paper's own claim that the error targets is in `inserted_error/<paper>_<claim#>_gemini-2.5-pro.txt` (`:claim:` tag; `:explanation:` is the generator's account of the flaw).

| # | Paper (arxiv id, cs area) | Claim # | Verdict | Why |
|---|---|---|---|---|
| 1 | 2606.06572 (LG) | 3 | M | "Exit" swapped for "forced conversion"; both lower the human-work share, so it barely contradicts anything. Explanation is about model collapse, edit is not. |
| 2 | 2606.06572 (LG) | 2 | G | Alignment made "counterproductive" by deleting the process/provenance counterbalance. Subtle overgeneralisation. |
| 3 | 2606.19341 (CV) | 8 | M | Adds "TAURA deprioritises deterministic answer formatting". Plausible but weakly tied to the target claim. |
| 4 | 2606.19341 (CV) | 1 | G | Claims context cost is decoupled from video length although text memory grows with reasoning steps. Subtle, coherent. |
| 5 | 2606.15880 (CV) | 5 | G | Later layers "focus only on signal-level cues", contradicting the joint semantic+signal design. |
| 6 | 2606.15880 (CV) | 1 | G (large) | Inverts layer-wise finding (early-to-middle -> deep) consistently over 4 excerpts. Likely conflicts with unchanged figures; heavy-handed. |
| 7 | 2606.25325 (AI) | 2 | G (large) | Reward silently changed from cue recall to clause precision, consistently across abstract and method (121 words). |
| 8 | 2606.25325 (AI) | 4 | G | KL divergence arguments swapped. Minimal (6 words), technical, subtle. |
| 9 | 2609.00097 (LG) | 1 | G | One shared scale factor for 2-bit thumbnail and 8-bit residual; statistically unsound. |
| 10 | 2609.00097 (LG) | 5 | M | Deletes the pseudo-max defining equation and replaces it with vague text. An omission rather than a falsehood. |
| 11 | 2608.07952 (LG) | 5 | M | Recasts model-dependence as a judge/measurement artefact and says so in the text, so it is self-announcing. 148 words. |
| 12 | 2608.07952 (LG) | 3 | M | Adds "thematically coherent conversation" as a confound, but states the limitation openly (self-announcing). |
| 13 | 2606.03976 (CV) | 1 | B | Flips linear vs quadratic conclusion with invented table numbers over 7 excerpts, and leaks 7 literal `***` markers into the LaTeX (visible in the PDF). |
| 14 | 2606.03976 (CV) | 2 | G | Probe attends over all tokens including [CLS] while claiming spatial tokens alone hold the binding. Small and subtle. |
| 15 | 2608.02827 (MA) | 3 | G (large) | Wrong mechanism: heterogeneity helps via "diverse non-conforming agents" instead of smoothing the transition (173 words). |
| 16 | 2608.02827 (MA) | 5 | G | Claims sycophancy lowers conformity; conflicts with domain knowledge. |
| 17 | 2606.12146 (LG) | 5 | G | Attributes extrapolation to a periodic lattice / stable reference frame; plausible overreach. |
| 18 | 2606.12146 (LG) | 4 | G | Removes the random rotation while the isotropy/rotation-robustness claim stays. |
| 19 | 2606.25450 (LG) | 6 | G | Hint-GRPO redefined with an auxiliary imitation loss, confounding the comparison. |
| 20 | 2606.25450 (LG) | 2 | M | Stronger claim that ICL fails at abstract generalisation; arguably consistent with the paper's own data, so it may not be an error. |
| 21 | 2606.03066 (AI) | 4 | G | Redefines "conflict" as semantic distance. |
| 22 | 2606.03066 (AI) | 2 | B | Near-paraphrase ("keep unchanged" -> "use original text embedding"); no real error introduced. |
| 23 | 2608.23493 (AI) | 7 | M | Rewrites the method's identity (distillation -> RL, title and intro). Too broad (200 words); likely trivially detectable. |
| 24 | 2608.23493 (AI) | 10 | G | Invents a "representational annealing" mechanism that contradicts the reverse-KL, mode-seeking objective. |
| 25 | 2606.05793 (CL) | 1 | G | Replaces GiGPO step-level advantage with raw step reward. Technically wrong. |
| 26 | 2606.05793 (CL) | 0 | G | Rationale for rewarding long reasoning changed to "engagement", biasing the profile filter toward verbosity. |
| 27 | 2606.28182 (LG) | 4 | M | Reframes single-law grounding as an observation-to-law mapping. Speculative flaw; 81 words over 4 excerpts. |
| 28 | 2606.28182 (LG) | 0 | G (large) | Laws extracted from failures are imposed post hoc onto successful traces (187 words). |
| 29 | 2606.09145 (CR) | 3 | G | Redefines the PC-Uncond baseline so the comparison is unfair. |
| 30 | 2606.09145 (CR) | 5 | B | Only the rationale for the KL term changed; the KL does keep variance, so no real error. |
| 31 | 2607.06807 (CR) | 0 | G | Role-specific activation differences treated as zero-mean noise; unsound assumption. |
| 32 | 2607.06807 (CR) | 5 | M | Adds "assuming unimodal, well-concentrated"; states the assumption openly. |
| 33 | 2607.09921 (CL) | 2 | M | Isotonic regression "trained on validation set"; ordinary practice, weak. |
| 34 | 2607.09921 (CL) | 1 | G | Downside price made static instead of beta-scaled. |
| 35 | 2606.08656 (CL) | 1 | M | Adds "for learning immediate, exploitative responses"; an openly stated limitation. |
| 36 | 2606.08656 (CL) | 0 | G | One-step reward justified by "independent probes of a stationary opponent"; false premise across 3 excerpts. |
| 37 | 2608.07548 (RO) | 1 | G | Uses the full foresight state instead of the discrepancy Delta; undermines the method's own design. |
| 38 | 2608.07548 (RO) | 2 | G | Foresight computed from the previous refined state instead of the current one. Only 20 words. |
| 39 | 2606.13802 (SE) | 7 | M | Mostly a relabelling of operation categories; weak. |
| 40 | 2606.13802 (SE) | 11 | G | "Acceptance streak" redefined from consecutive accepts to actions saved per prediction. |

Totals: 25 G, 12 M, 3 B.
Recommendation: replace or repair the 3 B errors (#13 has a `***` leak that can be stripped cheaply; #22 and #30 introduce no real error).
Note: two errors in the same paper (e.g. 2608.23493 #7/#10, 2606.08656 #1/#0) sometimes target the same idea.
