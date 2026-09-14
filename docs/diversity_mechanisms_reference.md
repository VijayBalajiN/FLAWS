# Diversity mechanisms: what FLAWS and ResearchBench actually do

Reference doc for the "how do we generate errors more naturally/diversely"
question. Bottom line up front: **neither system relies on temperature as its
diversity mechanism.** Both get diversity from varying the *content* fed into
generation (different claims, different inspirations), not from resampling
the same input at a higher temperature. That's the main actionable finding
here.

---

## 1. What FLAWS actually does (checked against its own source, not the paper)

`src/utils/llm_calls.py`: every provider function (`get_completion_gemini`,
`get_completion_anthropic`, `get_completion_openai`, `get_completion_grok`)
defaults `temperature=1`. This default is never overridden anywhere in
`single_error_insertion.py` or the batch pipeline — every call in the whole
pipeline (claim extraction, error generation, both filters, localization,
identification) runs at the same fixed temperature. **There is no temperature
schedule, no "try again at a different temperature" logic, anywhere in FLAWS.**

`src/pipeline/batch_process/helper.py`: the batch pipeline's loop structure is:

```python
for paper, claim_list in all_claims.items():
    for c, claim in enumerate(claim_list):
        # generate ONE error attempt for this claim
```

One attempt per claim. If it's filtered out, it's simply discarded — **there
is no retry-the-same-claim loop anywhere in FLAWS.** A paper's diversity comes
entirely from having dozens of distinct extracted claims, each tried exactly
once. A full paper naturally has that many distinct, independent targets;
a single hypothesis sentence does not.

**Implication for us**: our pipeline compressed each paper down to one
hypothesis sentence (plus one experiment-design blob), so we lost FLAWS's
actual diversity source entirely. Retrying the *same* single sentence 5x
(now 20x) with temperature variation is a problem FLAWS never had to solve,
because it never retries the same target at all.

---

## 2. What ResearchBench actually does (verified against arxiv.org/html/2503.21248v3, Appendix A.3–A.6)

### 2.1 Inspiration retrieval (where "inspirations" come from)

Not resampling — it's a real retrieval/ranking task over a constructed
candidate pool. Per benchmark paper, they build a candidate set of up to 75
papers from **three distance tiers**:

- **Level 1** ("citation-adjacent"): 100 papers via Crossref (things the
  paper actually cites) + 50 via Semantic Scholar (semantically similar
  titles).
- **Level 2** ("same-discipline"): drawn from a pool of 2,000 randomly
  collected papers per discipline (via Web of Science).
- **Level 3** ("different-discipline"): drawn from the same pool, different
  discipline than the benchmark paper.

For experiments, they randomly sample 25 negatives from *each* level (75
total candidates + 2-3 groundtruth inspirations). The three-tier design is
deliberate: if negatives were only from irrelevant disciplines, retrieval
would be trivially easy — the close-but-wrong tier (Level 1) is what makes it
a real test.

**Retrieval prompt** (Appendix A.3, verbatim):

> "You are helping with the scientific hypotheses generation process. Given a research question, the background and some of the existing methods for this research question, and several top-tier publications (including their title and abstract), try to identify which publication can potentially serve as an inspiration for the background research question so that combining the research question and the inspiration in some way, a novel, valid, and significant research hypothesis can be formed. The inspiration does not need to be similar to the research question. In fact, probably only those inspirations that are distinct with the background research question, combined with the background research question, can lead to a impactful research hypothesis. The reason is that if the inspiration and the background research question are semantically similar enough, they are probably the same, and the inspiration might not provide any additional information to the system, which might lead to a result very similar to a situation that no inspiratrions are found. An example is the backpropagation of neural networks. In backpropagation, the research question is how to use data to automatically improve the parameters of a multi-layer logistic regression, the inspiration is the chain rule in mathematics, and the research hypothesis is the backpropagation itself. In their paper, the authors have conducted experiments to verify their hypothesis. Now try to select inspirations based on background research question."

Worth noting: this prompt explicitly argues that a *useful* inspiration
should be **distinct from** the research question, not similar to it — a
near-duplicate inspiration adds no new information. This is itself a
diversity principle: pick source material that's meaningfully different from
what you already have, not just topically adjacent.

### 2.2 Hypothesis composition — this is the actual diversity mechanism

**Not a single LLM call.** They explicitly build on an external
"evolutionary unit" (cited as Yang et al., 2025b) with three operators:
**mutate → refine → recombine**. Mechanics, from the paper's own description:

- The inspiration retriever pulls inspirations **one at a time, and will
  never retrieve the same one again** — each mutation round gets genuinely
  new source material, not a resample of the same input.
- **Mutate** takes the accumulated hypotheses-so-far + one new inspiration
  and is explicitly instructed to produce something **distinct in
  methodology**, not just distinct in wording.
- **Recombine** takes the accumulated population of mutated hypotheses and
  merges their "bright parts" into a better one (genetic-algorithm-style
  crossover, not a fresh independent sample).
- **Refine** applies structured multi-axis feedback (novelty / validity /
  significance / clarity) to improve one candidate, with an explicit
  anti-cheating clause: don't fake "significance" by just claiming a bigger
  expected performance gain — actually change the method.

**Mutate prompt** (Appendix A.6, verbatim, the load-bearing paragraph):

> "Please try to explore a new meaningful way to combine the inspiration with the research background to generate a new research hypothesis that is distinct with all the previous hypotheses in terms of their main method. The new research hypothesis should ideally be novel, valid, ideally significant, and be enough specific in its methodology. [...] In addition, by generating distinct hypothesis, **please do not achieve it by simply introducing new concept(s) into the previous hypothesis to make the difference, but please focus on the difference on the methodology of integrating or leveraging the inspiration to give a better answer to the research question** (in terms of the difference on the methodology, concepts can be introduced or deleted)."

The bolded clause is the single most useful sentence in the whole paper for
our purposes: it is an explicit, direct instruction against exactly the
failure mode we hit with BERT (the model reaching for a cosmetically
different phrasing of the same underlying idea, e.g. always landing on some
version of "sounds like ELMo"). ResearchBench's fix isn't a sampling trick —
it's telling the model, in the prompt, that surface-level rewording doesn't
count as diversity, only a different underlying mechanism does.

**Refine prompt** (Appendix A.6, verbatim):

> "With them, we have already generated a preliminary research hypothesis. We have also obtain feedbacks on the hypothesis from domain experts in terms of novalty, validity, significance, and clarity. With these feedbacks, please try your best to refine the hypothesis. Please note that during refinement, **do not improve a hypothesis's significance by adding expectation of the performance gain of the method or adding description of its potential impact, but you should work on improving the method itself** (e.g., by adding or changing details of the methodology)."

**Recombine prompt** (Appendix A.6, verbatim):

> "Please find the bright parts in these hypotheses, leverage the bright parts from them, modify and combine the good parts of them to generate a better research hypothesis in terms of clarity, novelty, validness, and significance (ideally than any of the given hypotheses). It is not necessary to include methods from every given hypothesis, especially when it is not a good hypothesis. But in general you should try your best to benefit from every given hypothesis."

### 2.3 Hypothesis evaluation (6-point Likert, Appendix A.4)

Generated hypotheses are scored against groundtruth on a 0-5 scale by how
many "key points" of the groundtruth they cover, with explicit rules for
partial credit and for penalizing irrelevant additions. Not directly a
diversity mechanism, but relevant if we ever want graded (not binary)
identification scoring.

### 2.4 Pairwise ranking prompt (Appendix A.5, verbatim)

> "You are assisting scientists with their research. Given a research question and two research hypothesis candidates proposed by large language models, your task is to predict which hypothesis is a better research hypothesis. By 'better', we mean the hypothesis is more valid and effective for the research question."

---

## 3. What this means for us, concretely

Neither system uses temperature as a diversity lever. Both use **structural/
content diversity**: FLAWS gives every attempt a genuinely different claim;
ResearchBench gives every mutation round a genuinely new inspiration plus an
explicit "different mechanism, not different wording" instruction.

Directly transferable pieces, in priority order:

1. **The "distinct in mechanism, not wording" instruction** — this is a
   one-paragraph prompt addition, zero architecture change, and it's the
   single most evidence-backed fix for the exact repetition problem we
   observed (BERT converging on the same flip every attempt).
2. **Feed back prior attempts explicitly and forbid repeating their
   mechanism** — our retry loop currently starts every attempt from scratch,
   with no memory of what was already tried. ResearchBench's mutate step
   always sees the accumulated population. We should do the same: pass
   previous attempts' `explanation` text into the next attempt's prompt with
   "do not repeat this mechanism."
3. **Never reuse the same target twice** — ResearchBench's retriever
   explicitly won't return the same inspiration twice. Our analogue: rotate
   *what part of the plan* each attempt perturbs (a different premise in
   Problem, a different clause in the hypothesis, a different step in
   Experiment Design) instead of hammering the same single sentence 20 times.
4. Temperature is still worth raising off our current 0.7 (below even FLAWS's
   own fixed 1.0), but it's a minor lever, not the main fix — worth doing
   alongside 1-3, not instead of them.
