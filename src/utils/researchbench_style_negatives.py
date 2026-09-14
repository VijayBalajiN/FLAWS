"""Replicates ResearchBench's (arxiv 2503.21248) hypothesis-ranking negative
construction -- cited by the alphaxiv 2608.17270 confidence-ranking paper as
its data source -- for the Attention Is All You Need paper specifically.

Their method (Hypothesis Ranking task) does NOT surgically edit the true
hypothesis text the way our FLAWS-style pipeline does. Instead:

  1. A "hypothesis composition framework" (an LLM) synthesizes a candidate
     hypothesis from a research question + a set of "inspirations" (background/
     prior-work snippets).
  2. The gold hypothesis is composed from the question + the CORRECT/complete
     set of inspirations that actually informed the paper.
  3. Negatives come from two sources:
     (a) 5 sampled from composing with the question + WRONG/irrelevant
         inspirations (real prior work, but not what actually grounds this
         paper's hypothesis).
     (b) 10 sampled from composing with the question + an INCOMPLETE SUBSET
         of the correct inspirations (missing >=1 necessary piece).
  4. This yields 16 candidates (1 gold + 15 negatives) for a ranking/Hit@1
     evaluation, mirroring their exact evaluation shape.

Inspirations here are hand-extracted directly from Attention's own
Background/Introduction text (`data/papers/AttentionIsAllYouNeed/
background.tex`, `introduction.tex`) -- ResearchBench draws these from a real
retrieval corpus over cited references; we don't have that retrieval system,
so this substitutes the paper's own real cited prior-work content, which is
the closest faithful stand-in without building a full retrieval pipeline.
"""

from __future__ import annotations

import itertools
import json
import os
import random

import google.generativeai as genai

MODEL = "gemini-2.5-pro"

RESEARCH_QUESTION = (
    "What model architecture would best address the limitations of current sequence transduction "
    "approaches for tasks like machine translation?"
    # NOTE: earlier version of this question explicitly named "parallelization / constant operations /
    # translation quality" -- i.e. it already stated the hypothesis's own content as a question, so
    # every composed candidate converged to a near-paraphrase of the gold regardless of which
    # inspirations were given. A real background question shouldn't leak the answer; the inspirations
    # are what should differentiate gold from negatives.
)

# The four inspirations that actually ground the Transformer's hypothesis,
# extracted verbatim-in-substance from Background/Introduction:
CORRECT_INSPIRATIONS = {
    "I1_rnn_sequential": (
        "RNNs, LSTMs, and GRUs are the established state-of-the-art for sequence modeling and "
        "transduction, but factor computation sequentially along symbol positions (hidden state h_t "
        "depends on h_{t-1}), which precludes parallelization within training examples."
    ),
    "I2_attention_still_recurrent": (
        "Attention mechanisms allow modeling dependencies regardless of their distance in the input "
        "or output sequence and have become integral to sequence transduction models, but in nearly "
        "all prior work attention is used IN CONJUNCTION WITH a recurrent network, not as a "
        "replacement for it."
    ),
    "I3_conv_scales_with_distance": (
        "Convolutional approaches (Extended Neural GPU, ByteNet, ConvS2S) compute hidden "
        "representations in parallel for all positions, reducing sequential computation, but the "
        "number of operations needed to relate two positions grows with the distance between them "
        "(linearly for ConvS2S, logarithmically for ByteNet), making long-range dependencies harder "
        "to learn."
    ),
    "I4_self_attention_works_alone": (
        "Self-attention (intra-attention), which relates different positions of a SINGLE sequence to "
        "compute a representation of that sequence, has already been used successfully on its own in "
        "tasks like reading comprehension, summarization, textual entailment, and sentence "
        "representation learning."
    ),
}

# Real prior work mentioned in the paper, but NOT what actually grounds this
# specific hypothesis -- plausible-sounding, wrong direction for this paper.
WRONG_INSPIRATIONS = {
    "W1_memory_networks": (
        "End-to-end memory networks are based on a recurrent attention mechanism instead of "
        "sequence-aligned recurrence and have been shown to perform well on simple-language question "
        "answering and language modeling tasks."
    ),
    "W2_factorization_tricks": (
        "Factorization tricks and conditional computation have achieved significant improvements in "
        "the computational efficiency of recurrent models, and also improve model performance in the "
        "case of conditional computation, while the fundamental constraint of sequential computation "
        "remains unaddressed by these techniques."
    ),
    "W3_scaling_recurrent_encoder_decoder": (
        "Numerous efforts have continued to push the boundaries of recurrent language models and "
        "encoder-decoder architectures through architectural refinements and larger-scale training, "
        "continuing to advance the state of the art within the recurrent paradigm."
    ),
}

_COMPOSE_PROMPT = """You are a research-hypothesis composition system. Given a research question and a set of background inspirations (prior findings or established facts), synthesize ONE coherent, falsifiable research hypothesis that follows naturally from combining the research question with these specific inspirations. Do not use any other prior knowledge beyond what's given -- ground the hypothesis strictly in the provided inspirations.

Research question:
{question}

Inspirations:
{inspirations}

Output ONLY the single resulting hypothesis statement, one to two sentences, no preamble, no explanation."""


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def compose_hypothesis(
    question: str, inspirations: list[str], temperature: float = 0.7, max_retries: int = 3, retry_delay: float = 15.0
) -> str:
    import time

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(model_name=MODEL)
    prompt = _COMPOSE_PROMPT.format(
        question=question, inspirations="\n".join(f"- {i}" for i in inspirations)
    )
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(
                prompt, generation_config=genai.GenerationConfig(temperature=temperature)
            )
            return response.text.strip()
        except Exception as e:
            last_exc = e
            print(f"[compose_hypothesis] attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
    raise RuntimeError(f"compose_hypothesis failed after {max_retries} attempts") from last_exc


def build_candidate_set(seed: int = 0, out_path: str | None = None) -> dict:
    random.seed(seed)
    correct_keys = list(CORRECT_INSPIRATIONS.keys())
    wrong_keys = list(WRONG_INSPIRATIONS.keys())

    result = {
        "paper_id": "AttentionIsAllYouNeed",
        "research_question": RESEARCH_QUESTION,
        "gold": None,
        "wrong_inspiration_negatives": [],
        "incomplete_inspiration_negatives": [],
    }

    def _save() -> None:
        if out_path:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)

    # gold: composed from the full correct set
    gold = compose_hypothesis(RESEARCH_QUESTION, list(CORRECT_INSPIRATIONS.values()), temperature=0.3)
    result["gold"] = {"inspiration_keys": correct_keys, "hypothesis": gold}
    _save()

    # 5 negatives from wrong/irrelevant inspirations (mix 1-2 wrong ones,
    # optionally with 1 correct one, to keep them "plausible" rather than
    # nonsensical -- mirrors "top-ranked negative inspirations", which in the
    # real retrieval system are topically plausible, not random)
    for i in range(5):
        n_wrong = random.choice([1, 2])
        chosen_wrong = random.sample(wrong_keys, min(n_wrong, len(wrong_keys)))
        include_one_correct = random.random() < 0.5
        combo_keys = chosen_wrong + (random.sample(correct_keys, 1) if include_one_correct else [])
        inspirations = [WRONG_INSPIRATIONS.get(k) or CORRECT_INSPIRATIONS.get(k) for k in combo_keys]
        hyp = compose_hypothesis(RESEARCH_QUESTION, inspirations, temperature=0.8)
        result["wrong_inspiration_negatives"].append(
            {"source": "wrong_inspiration", "inspiration_keys": combo_keys, "hypothesis": hyp}
        )
        _save()

    # 10 negatives from incomplete subsets of the correct inspirations
    # (proper subsets only, missing >=1 of the 4)
    all_proper_subsets = [
        list(c)
        for r in range(1, len(correct_keys))
        for c in itertools.combinations(correct_keys, r)
    ]
    random.shuffle(all_proper_subsets)
    for combo_keys in all_proper_subsets[:10]:
        inspirations = [CORRECT_INSPIRATIONS[k] for k in combo_keys]
        hyp = compose_hypothesis(RESEARCH_QUESTION, inspirations, temperature=0.8)
        result["incomplete_inspiration_negatives"].append(
            {"source": "incomplete_inspiration", "inspiration_keys": list(combo_keys), "hypothesis": hyp}
        )
        _save()

    return result


if __name__ == "__main__":
    _load_dotenv()
    out_path = "data/researchbench_style/AttentionIsAllYouNeed_candidates.json"
    result = build_candidate_set(out_path=out_path)
    print(f"Wrote {out_path}")
