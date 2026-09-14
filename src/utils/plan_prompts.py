"""Prompts for the plan-text error-insertion pipeline (Phase 3).

Adapted from `src/utils/prompts.py`'s equivalents -- same benchmark-construction
framing, same `:tag:` output format so `formatting.py`'s existing parsers
(`format_generated_error`, `format_localized_error`, `format_identified_error`)
work unchanged -- but reworded for a short plain-text hypothesis/experiment-design
string instead of a full LaTeX paper source:
  - drop LaTeX-preservation rules (no `$`, `{}`, `\\emph{}` to worry about)
  - drop the separate "claim" input -- the target text (hypothesis, or one
    experiment-design step) IS the claim being undermined, not something
    extracted from a larger document
  - drop FLAWS's own paper-wide error taxonomy in the localization prompt
    (algorithm/proof, reported results, etc.) -- not applicable at this scale

Five tracks:
  - "general": no generation prompt of its own -- `generate_general_decompose_prompt`
    finds 5 distinct falsifiable claims across the whole plan (>=1 from the
    hypothesis), then `generate_general_error_candidates_prompt` generates 3
    candidate falsifications per claim. Diversity comes from genuinely
    different targets/mechanisms, not from resampling one target (see
    docs/diversity_mechanisms_reference.md).
  - three TYPED hypothesis-error variants (`generate_hypothesis_error_*`
    below), per `taxonomy_te.txt`'s thought-experiment failure-mode taxonomy:

  A. Internal Contradiction -- the hypothesis's OWN stated mechanism, taken
     to its logical conclusion, crashes into the hypothesis's own goal or
     another part of itself. No outside knowledge needed; the machinery
     breaks itself. (taxonomy_te.txt example: covariant array typing in Java
     lets you insert an Integer into a String[] at compile time, but the
     runtime array is still strictly a String[] -- the type system's own
     covariance rule directly violates its own goal of type safety.)
  B. Conflict with Established Beliefs -- the modified hypothesis stays
     internally consistent (no self-contradiction) but clashes with an
     independent, well-established result in the field. Forces a fork: the
     reader must reject either the hypothesis or the established belief, not
     a clean internal refutation. (taxonomy_te.txt example: Simpson's
     Paradox -- a treatment can be better in every subgroup yet worse
     overall under skewed weighting; the math is flawless, but it clashes
     with the intuition that "better in every subgroup" implies "better
     overall".)
  C. Undermining a Premise -- attacks a hidden or conflated assumption
     rather than the conclusion itself: two genuinely distinct concepts get
     silently treated as interchangeable. The formal reasoning remains
     fine; only the informal mapping is flawed. (taxonomy_te.txt example:
     conflating "population variance" (heritability) with "biological
     pathway" (genetic causation) -- a gene with zero variance across a
     population can still be 100% causally responsible for a trait.)
  D. Others -- a genuine, coherent flaw that doesn't cleanly fit A/B/C above.
     Used when post-hoc classifying a freely-generated (general-track) error,
     not as a generation target of its own -- forcing every naturally
     generated error into A/B/C would misclassify whatever doesn't fit.
"""

ED_ERROR_CATEGORIES = """\
1. Missing intermediate step -- breaks the logical chain between two adjacent steps.
2. Missing final step -- the design stops before it can actually evaluate the hypothesis (no measurement/analysis step).
3. Reordered step -- a step depends on output that hasn't been produced yet.
4. Insufficient step -- missing a control/baseline needed to support the causal claim (attacks sufficiency).
5. Unnecessary/redundant step -- a step that doesn't contribute to testing the hypothesis.
6. Non-sequitur step -- a step is present, but doesn't test what it needs to.
7. Wrong metric/measurement -- the measured outcome doesn't map onto what the hypothesis actually claims.
8. Confounded design -- the design fails to rule out an alternative explanation."""


def generate_general_decompose_prompt(plan_text: str) -> str:
    """Entry point for the "general" track (formerly a single-shot untyped
    prompt with post-hoc self-tagging; superseded by this decompose+3-ways
    mechanism). Mirrors FLAWS's own `extract_claims`
    (and SoundnessBench's atomic-claim decomposition, in its own appendix,
    in our dataset) -- get several genuinely distinct falsifiable targets
    instead of repeatedly resampling one target. Sources from the whole plan
    (not just the hypothesis), since a "general" error can plausibly live in
    either the hypothesis or the experiment design."""
    prompt = """I am developing a research benchmark purely for research purposes to evaluate how effectively language models (LLMs) can detect errors in research proposals.

You are given the full text of a research plan (Problem, Method, Experiment Design, and Hypothesis). Identify exactly 5 distinct, genuinely falsifiable claims or assumptions embedded in this plan -- things that, if they turned out to be false or methodologically flawed, would make this research unsound.

Requirements:
1. Each of the 5 claims must be genuinely DISTINCT from the others -- not the same underlying idea reworded twice.
2. At least 1 of the 5 claims must be drawn from the Hypothesis section specifically.
3. The remaining claims may be drawn from the Hypothesis or the Experiment Design section. Do NOT draw claims from the Problem or Method sections -- those are not being targeted by this track.
4. Each claim should be a specific, self-contained statement that could plausibly be shown wrong or insufficient -- not a vague theme or paraphrase of the whole plan.
5. You must quote the EXACT source text the claim is drawn from, copy-pasted with no modifications, so it can be located precisely later.

Output format (repeat exactly 5 times):

:claim:
<a concise statement of the falsifiable claim or assumption>

:source_field:
<either "hypothesis" or "experiment_design", whichever section source_excerpt below is drawn from>

:source_excerpt:
<EXACT excerpt from that section, copy-pasted with NO modifications, that this claim is drawn from>

STRICT FORMATTING RULES for source_excerpt:
1. Use PRECISE copy and paste from the input -- the excerpt must be exactly matchable in the source section.
2. DO NOT ALTER OR OMIT any token, punctuation, or spacing.
3. DO NOT use quotation marks around the excerpt.
4. DO NOT hallucinate text that is not in the source.

You are given the following research plan:
"""
    prompt += plan_text
    return prompt


def generate_general_error_candidates_prompt(claim: str, source_excerpt: str, field_label: str) -> str:
    """Given one claim from the decomposition step above, ask for 3 candidate
    falsifications that differ in underlying MECHANISM -- directly applying
    the one load-bearing sentence from ResearchBench's mutate prompt (see
    docs/diversity_mechanisms_reference.md): distinctness must come from a
    different mechanism, not a different wording of the same one."""
    prompt = f"""I am developing a research benchmark purely for research purposes to evaluate how effectively language models (LLMs) can detect errors in research proposals.

You will be given one specific falsifiable claim drawn from the {field_label} section of a research plan, along with the exact source text it comes from. Your task is to propose THREE genuinely different ways this specific claim could be subtly, plausibly falsified.

The three candidates must differ from each other in their underlying MECHANISM of error, not merely in wording. Do NOT produce three cosmetically different phrasings of the same underlying flaw -- each of the three must be a genuinely different kind of mistake from the other two.

Each candidate error should:
1. Be subtle but significant.
2. Avoid obvious mistakes (grammar, formatting, typos).
3. Be non-trivial to detect without domain expertise.
4. Be plausible -- a realistic mistake a researcher might actually make.
5. Actually attack THIS claim specifically, not some unrelated part of the plan.

- DO NOT state or imply that anything is wrong in the modified text.
- DO NOT correct any mistakes. Your job is to INTRODUCE an error, NOT correct one.

Output format (repeat exactly 3 times, numbering the candidate):

:candidate:
<1, 2, or 3>

:original_text:
<EXACT excerpt from the source text below -- copy-pasted with NO modifications>

:modified_text:
<Modified excerpt -- almost identical to the original but with the flaw inserted>

:explanation:
<brief explanation of the flaw, its mechanism, and why it undermines this specific claim>

STRICT FORMATTING RULES for original_text:
1. Use PRECISE copy and paste -- the excerpt must be exactly matchable in the source text below.
2. DO NOT ALTER OR OMIT any token, punctuation, or spacing.
3. DO NOT use quotation marks around the excerpt.
4. DO NOT hallucinate text that is not in the source.

CLAIM TO ATTACK:
{claim}

EXACT SOURCE TEXT:
{source_excerpt}"""
    return prompt


def generate_hypothesis_error_internal_contradiction_prompt(hypothesis: str) -> str:
    prompt = """I am developing a research benchmark purely for research purposes to evaluate how effectively language models (LLMs) can detect errors in research proposals. Your task is to modify a research hypothesis statement so that it contradicts ITSELF -- not by conflicting with anything external, but by taking the hypothesis's own stated mechanism to its logical conclusion and showing that this conclusion violates the hypothesis's own goal or another part of the same hypothesis.

This is an "Internal Contradiction" error: the machinery breaks itself. No external belief, established theorem, or outside knowledge is needed to see the flaw -- it should be derivable purely by reasoning through the hypothesis's own stated rules to their end.

Example of this error type (for calibration, not to copy): covariant array typing in Java lets the compiler treat a String[] as a valid Object[], so code can legally insert an Integer into what the compiler considers a safe Object[] -- but at runtime the array is still strictly a String[], so the insertion crashes. The type system's own covariance rule directly causes a violation of its own stated goal (type safety). The contradiction is self-contained: you don't need any belief external to the type system to see it break.

Task Instructions
You will be given the hypothesis statement of a research plan -- a single falsifiable theoretical claim the plan is testing.

Modify the hypothesis so that its own stated mechanism, followed to its logical conclusion, undermines the very goal or property the hypothesis claims to achieve. The contradiction must come from WITHIN the hypothesis's own logic -- not from clashing with outside knowledge (that would be a different error type).

IMPORTANT quality check before you answer: if you cannot find a genuine self-contained contradiction -- if the only "contradiction" you can construct relies on an assumption the hypothesis never actually states or specifies -- then a true Internal Contradiction does not exist here. In that case, do not force a fake one. Instead, output exactly "NO VALID INTERNAL CONTRADICTION FOUND" and nothing else, rather than fabricating a strained or dishonest error.

If you do find a genuine one, your modification should:
1. Be subtle but significant.
2. Avoid obvious mistakes (e.g., grammar, formatting, typos).
3. Be non-trivial to detect without domain expertise, ideally requiring graduate-level reasoning or deeper.
4. Be plausible -- the modified hypothesis should still read as reasoned to a casual or intermediate reader.
5. Not be simple or obvious where one sentence is the direct contradiction of its neighboring sentences.
6. Be similar to a GENUINE, REALISTIC mistake made by a researcher formulating this hypothesis.
7. Not be easily identified by a master's student who has not studied this area in depth.

- Make sure that the error is identifiable through the text alone.
- DO NOT state any inconsistencies or limitations of the original hypothesis.
- DO NOT correct any mistakes. Your job is to INTRODUCE an error, NOT correct one.

Modification Format
For each change, return:

:error_type:
Internal Contradiction

:original_text:
<EXACT excerpt from the original hypothesis text -- copy-pasted with NO modifications>

:modified_text:
<Modified excerpt -- almost identical to the original but with the self-contradiction inserted>

Repeat original/modified pairs as needed if the error spans multiple non-contiguous parts.

STRICT FORMATTING RULES for original_text:

1. Use PRECISE copy and paste from the input to confirm excerpts are completely identical to the original source.
2. DO NOT ALTER OR OMIT any token, punctuation, or spacing.
3. DO NOT use quotation marks around the error excerpts.
4. DO NOT use ellipses ('...') within a single excerpt. If the original error texts are non-consecutive, return them as separate excerpts.
5. DO NOT hallucinate additional text that is not in the source.
6. DO NOT ALTER OR OMIT any line breaks or new lines.
7. The excerpt you output must be exactly matchable in the input hypothesis text!

:explanation:
A brief but clear explanation of the hypothesis's own mechanism, how it was modified, and exactly how following that modified mechanism to its conclusion violates the hypothesis's own stated goal or another part of itself.

You are given the following hypothesis statement:
"""
    prompt += hypothesis
    return prompt


def generate_hypothesis_error_established_belief_conflict_prompt(hypothesis: str) -> str:
    prompt = """I am developing a research benchmark purely for research purposes to evaluate how effectively language models (LLMs) can detect errors in research proposals. Your task is to modify a research hypothesis statement so that it stays internally consistent -- it does NOT contradict itself -- but clashes with an independent, well-established result, theorem, or intuition from the relevant field.

This is a "Conflict with Established Beliefs" error: the modification is internally coherent and could be true on its own terms, but an expert who knows the field's established results would recognize that it cannot be reconciled with something already well-established. This should force a fork for the reader -- either the modified hypothesis is wrong, or the established belief is wrong -- not a clean internal refutation the way a self-contradiction would be.

Example of this error type (for calibration, not to copy): Simpson's Paradox. A hypothesis claiming "if a treatment performs better in every subgroup, it must perform better overall" is internally sensible and not self-contradictory, but it clashes with the well-established mathematical fact that aggregation under skewed subgroup weighting can flip this exact relationship. The math of the counterexample is flawless; the conflict is with an established, independent belief about how aggregation works, not with the hypothesis's own internal logic.

Task Instructions
You will be given the hypothesis statement of a research plan -- a single falsifiable theoretical claim the plan is testing.

Modify the hypothesis so that it remains internally consistent (do NOT introduce a self-contradiction -- that is a different error type) but now conflicts with a genuinely well-established result, theorem, or strong empirical consensus in the field this hypothesis belongs to. The established belief you conflict with should be real and independently verifiable, not something you invent.

Your modification should:
1. Be subtle but significant.
2. Avoid obvious mistakes (e.g., grammar, formatting, typos).
3. Be non-trivial to detect without domain expertise, ideally requiring graduate-level reasoning or deeper.
4. Be plausible -- the modified hypothesis should still read as reasoned to a casual or intermediate reader, and should NOT be internally self-contradictory.
5. Not be simple or obvious where one sentence is the direct contradiction of its neighboring sentences.
6. Be similar to a GENUINE, REALISTIC mistake made by a researcher formulating this hypothesis.
7. Not be easily identified by a master's student who has not studied this area in depth.

- Make sure that the error is identifiable through the text alone, by someone who knows the established belief being conflicted with.
- DO NOT state any inconsistencies or limitations of the original hypothesis.
- DO NOT correct any mistakes. Your job is to INTRODUCE an error, NOT correct one.

Modification Format
For each change, return:

:error_type:
Conflict with Established Beliefs

:original_text:
<EXACT excerpt from the original hypothesis text -- copy-pasted with NO modifications>

:modified_text:
<Modified excerpt -- almost identical to the original but with the conflicting claim inserted>

Repeat original/modified pairs as needed if the error spans multiple non-contiguous parts.

STRICT FORMATTING RULES for original_text:

1. Use PRECISE copy and paste from the input to confirm excerpts are completely identical to the original source.
2. DO NOT ALTER OR OMIT any token, punctuation, or spacing.
3. DO NOT use quotation marks around the error excerpts.
4. DO NOT use ellipses ('...') within a single excerpt. If the original error texts are non-consecutive, return them as separate excerpts.
5. DO NOT hallucinate additional text that is not in the source.
6. DO NOT ALTER OR OMIT any line breaks or new lines.
7. The excerpt you output must be exactly matchable in the input hypothesis text!

:explanation:
A brief but clear explanation of (a) the specific established result/theorem/consensus being conflicted with, and (b) why the modified hypothesis, while internally consistent, cannot be reconciled with it.

You are given the following hypothesis statement:
"""
    prompt += hypothesis
    return prompt


def generate_hypothesis_error_premise_undermining_prompt(hypothesis: str) -> str:
    prompt = """I am developing a research benchmark purely for research purposes to evaluate how effectively language models (LLMs) can detect errors in research proposals. Your task is to modify a research hypothesis statement so that it silently conflates two genuinely distinct concepts as if they were the same thing -- attacking a hidden premise or assumption rather than the hypothesis's final conclusion directly.

This is an "Undermining a Premise" error: the formal reasoning of the hypothesis remains fine on its own terms; what's flawed is an informal mapping where two things that are NOT actually identical get treated as interchangeable. This differs from an Internal Contradiction (where the formal rules crash into each other) and from a Conflict with Established Beliefs (where the whole hypothesis clashes with outside knowledge) -- here, the flaw is narrower and more surgical: one specific conflated term or assumption.

Example of this error type (for calibration, not to copy): the Missing Heritability Puzzle. A hypothesis might smuggle in the premise that "population variance" (heritability, a statistical quantity) is the same thing as "biological pathway" (genetic causation, a mechanistic quantity). But imagine a population where everyone shares the exact same gene for processing Vitamin D, and only sun exposure varies -- the gene contributes 0% to the variance (so 0% "heritability"), yet it is 100% causally responsible for the trait. The two concepts pull apart cleanly, without anything about the underlying genetics being internally broken.

Task Instructions
You will be given the hypothesis statement of a research plan -- a single falsifiable theoretical claim the plan is testing.

Find a term, concept, or assumption in the hypothesis that could plausibly be conflated with a distinct-but-related one, and modify the hypothesis so that it treats the two as interchangeable when they are not. The underlying formal claim should remain internally coherent -- the flaw is specifically in the conflation, not in a logical crash or an external clash.

Your modification should:
1. Be subtle but significant.
2. Avoid obvious mistakes (e.g., grammar, formatting, typos).
3. Be non-trivial to detect without domain expertise, ideally requiring graduate-level reasoning or deeper.
4. Be plausible -- the modified hypothesis should still read as reasoned to a casual or intermediate reader.
5. Not be simple or obvious where one sentence is the direct contradiction of its neighboring sentences.
6. Be similar to a GENUINE, REALISTIC mistake made by a researcher formulating this hypothesis -- conflating two related-sounding but distinct concepts is a very natural mistake to make.
7. Not be easily identified by a master's student who has not studied this area in depth.

- Make sure that the error is identifiable through the text alone.
- DO NOT state any inconsistencies or limitations of the original hypothesis.
- DO NOT correct any mistakes. Your job is to INTRODUCE an error, NOT correct one.

Modification Format
For each change, return:

:error_type:
Undermining a Premise

:original_text:
<EXACT excerpt from the original hypothesis text -- copy-pasted with NO modifications>

:modified_text:
<Modified excerpt -- almost identical to the original but with the conflated premise inserted>

Repeat original/modified pairs as needed if the error spans multiple non-contiguous parts.

STRICT FORMATTING RULES for original_text:

1. Use PRECISE copy and paste from the input to confirm excerpts are completely identical to the original source.
2. DO NOT ALTER OR OMIT any token, punctuation, or spacing.
3. DO NOT use quotation marks around the error excerpts.
4. DO NOT use ellipses ('...') within a single excerpt. If the original error texts are non-consecutive, return them as separate excerpts.
5. DO NOT hallucinate additional text that is not in the source.
6. DO NOT ALTER OR OMIT any line breaks or new lines.
7. The excerpt you output must be exactly matchable in the input hypothesis text!

:explanation:
A brief but clear explanation of (a) the two distinct concepts that were conflated, and (b) why treating them as interchangeable is a mistake, even though the hypothesis's surface-level reasoning still appears to hold together.

You are given the following hypothesis statement:
"""
    prompt += hypothesis
    return prompt


def generate_ed_error_prompt(experiment_design: str) -> str:
    prompt = """I am developing a research benchmark purely for research purposes to evaluate how effectively language models (LLMs) can detect errors in research proposals. Your task is to modify an experiment design description in a way that introduces a non-trivial, plausible methodological flaw.

This benchmark aims to test LLMs' capacity for deep understanding, contextual inference, and expert-level critique, rather than surface-level textual correction.

Task Instructions
You will be given the experiment design section of a research plan -- the description of the experiments, data collection, and analysis meant to test the plan's hypothesis.

Pick exactly ONE of the following categories of methodological flaw, and introduce ONE instance of it:

""" + ED_ERROR_CATEGORIES + """

Your introduced flaw should:

1. Be subtle but significant.
2. Avoid obvious mistakes (e.g., grammar, formatting, typos).
3. Be non-trivial to detect without domain expertise, ideally requiring graduate-level reasoning or deeper.
4. Be plausible -- the modified experiment design should still read as reasoned to a casual or intermediate reader.
5. Not be simple or obvious where one sentence is the direct contradiction of its neighboring sentences.
6. Be similar to a GENUINE, REALISTIC methodological oversight a researcher might make when designing this experiment.
7. Not be easily identified by a master's student who has not studied this area in depth.

- Make sure that the error is identifiable through the text alone.
- DO NOT state any inconsistencies or limitations of the original experiment design.
- DO NOT correct any mistakes. Your job is to INTRODUCE an error, NOT correct one.

Modification Format
For each change, return:

:error_type:
<the ONE category from the list above that this flaw belongs to, copied verbatim>

:original_text:
<EXACT excerpt from the original experiment design text -- copy-pasted with NO modifications>

:modified_text:
<Modified excerpt -- almost identical to the original but with the flaw inserted. For a "missing step" or "missing final step" flaw, the modified_text may simply omit content present in original_text.>

Repeat original/modified pairs as needed if the change spans multiple non-contiguous parts.

STRICT FORMATTING RULES for original_text:

1. Use PRECISE copy and paste from the input to confirm excerpts are completely identical to the original source.
2. DO NOT ALTER OR OMIT any token, punctuation, or spacing.
3. DO NOT use quotation marks around the error excerpts.
4. DO NOT use ellipses ('...') within a single excerpt. If the original error texts are non-consecutive, return them as separate excerpts.
5. DO NOT hallucinate additional text that is not in the source.
6. DO NOT ALTER OR OMIT any line breaks or new lines.
7. The excerpt you output must be exactly matchable in the input experiment design text!

:explanation:
A brief but clear explanation of what methodological flaw was introduced, why it undermines the experiment design's ability to test the hypothesis, and how it maps to the chosen category.

You are given the following experiment design:
"""
    prompt += experiment_design
    return prompt


def generate_filter_invalid_prompt(
    original_text: list[str], modified_text: list[str], explanation_list: list[str], field_label: str
) -> str:
    prompt = f"""I am developing a research benchmark to evaluate how effectively language models (LLMs) can detect errors in research proposals. I have modified the {field_label} of a research plan in a way that introduces a non-trivial, plausible conceptual or methodological flaw.

I am going to provide you with the following:
1. Original text (Part of the original {field_label} that was altered, i.e. such that error is introduced)
2. Modified text (Modified version of the original text to include the error)
3. Explanation (The explanation behind the introduced error)

Your job is very simple. You need to ensure that the error I have introduced through the modified text satisfies the below three sanity checks.
(a) The Modified Text should not explicitly state that there is an error.
(b) The Modified Text should not just highlight an existing weakness, shortcoming, or error in the original.
(c) The Modified Text should actually INTRODUCE a non-trivial, plausible conceptual or methodological flaw, grounded in domain-specific knowledge.

If the Modified Text satisfies the above three criteria, then simply output "No changes required" without any other padding text.

If the Modified Text does not satisfy all the above criteria or does not contain an error, then simply output "Filtering required" without any other padding text."""
    original = "\n".join(original_text)
    modified = "\n".join(modified_text)
    explanation = "\n".join(explanation_list)

    prompt += (
        "\n\nORIGINAL TEXT:\n" + original + "\n\n"
        "MODIFIED TEXT:\n" + modified + "\n\n"
        "EXPLANATION:\n" + explanation + "\n\n"
    )
    return prompt


def generate_filter_easy_prompt(
    original_text: list[str], modified_text: list[str], explanation_list: list[str], field_label: str
) -> str:
    prompt = f"""I am developing a research benchmark to evaluate how effectively language models (LLMs) can detect errors in research proposals. I have modified the {field_label} of a research plan in a way that introduces a non-trivial, plausible conceptual or methodological flaw.

I am going to provide you with the following:
1. Original text (Part of the original {field_label} that was altered, i.e. such that error is introduced)
2. Modified text (Modified version of the original text to include the error)
3. Explanation (The explanation behind the introduced error)

Your job is very simple. You need to ensure that the error I have introduced through the modified text cannot be easily identified by an LLM if it is just given this text and asked to review it. By "cannot be easily identified", I mean it should be identified on average less than 20% of the time.

If the error introduced IS easily identifiable, then simply output "Filtering required" without any other padding text.

If the error introduced is difficult to identify, then simply output "No changes required" without any other padding text."""
    original = "\n".join(original_text)
    modified = "\n".join(modified_text)
    explanation = "\n".join(explanation_list)

    prompt += (
        "\n\nORIGINAL TEXT:\n" + original + "\n\n"
        "MODIFIED TEXT:\n" + modified + "\n\n"
        "EXPLANATION:\n" + explanation + "\n\n"
    )
    return prompt


def generate_localization_prompt(
    original_text: list[str], modified_text: list[str], explanation_list: list[str], field_label: str, full_plan_text: str
) -> str:
    prompt = f"""I am developing a research benchmark to evaluate how effectively language models (LLMs) can detect errors in research proposals. I have modified the {field_label} section of a research plan in a way that introduces a non-trivial, plausible conceptual or methodological flaw.

I am going to provide you with the following:
1. Original text (Part of the original {field_label} that was altered, i.e. such that error is introduced)
2. Modified text (Modified version of the original text to include the error)
3. Explanation (The explanation behind the introduced error)
4. The full research plan text (Problem/Method/Experiment Design/Hypothesis, after modification)

Your job is to analyze the way the {field_label} has been modified and then output any OTHER part of the full research plan (besides the modified text itself) that is rendered incorrect as a result of this modification -- for example, a later part of the experiment design that depends on a step that was removed or altered, or a part of the method that no longer matches the altered hypothesis. If no other part of the plan is affected, output "None" and nothing else.

Output ONLY the EXACT excerpt(s) from the full research plan text that are incorrect as a result -- copy-pasted with NO modifications, and do not output any padding text. Start printing each excerpt by printing "error:" followed by the incorrect excerpt.

STRICT FORMATTING RULES:

1. Use PRECISE copy and paste from the input to confirm excerpts are completely identical to the source.
2. DO NOT ALTER OR OMIT any token, punctuation, or spacing.
3. DO NOT use quotation marks around the error excerpts.
4. DO NOT use ellipses ('...') within a single excerpt. If non-consecutive, return them as separate excerpts.
5. DO NOT hallucinate additional text that is not in the source."""
    original = "\n".join(original_text)
    modified = "\n".join(modified_text)
    explanation = "\n".join(explanation_list)

    prompt += (
        "\n\nORIGINAL TEXT:\n" + original + "\n\n"
        "MODIFIED TEXT:\n" + modified + "\n\n"
        "EXPLANATION:\n" + explanation + "\n\n"
        "FULL RESEARCH PLAN TEXT (after modification):\n" + full_plan_text
    )
    return prompt


def generate_internal_identification_prompt(field_label: str, num_chunks: int = 5, word_limit: int = 100) -> str:
    prompt = f"""Attached is a full research plan (Problem/Method/Experiment Design/Hypothesis). I have tried to break its validity by modifying one or more snippets within the {field_label} section. You have been provided the modified plan. Your task is to identify error text chunks that pertain to the error, and return them in ranked order where the first returned error text is the most serious. The identified error text should be a substantial conceptual or methodological flaw that could undermine the validity of this research plan.

Important constraints:
- Do not identify minor issues such as grammar, style, formatting, or typographical errors.
- Return exact excerpts from the text (do not paraphrase).
- Each excerpt must be at most {word_limit} words long.
- Return at most {num_chunks} error chunks, ranked in order of seriousness (most serious first).

Output format (strictly follow):

:error_text:
<exact excerpt from the text>

:error_text:
<exact excerpt from the text>

(...there can be a varying number of error texts for each error, the total number of error texts should be at most {num_chunks})

:explanation:
<clear and precise explanation of the error>"""
    return prompt


def generate_classify_error_prompt(original_text: str, modified_text: str, explanation: str) -> str:
    """Post-hoc classification of a "general"-track error into the A/B/C/D
    taxonomy (see module docstring) -- decoupled from generation, per the
    "classify after generating" plan: the model that invented the error is
    never asked to also grade itself in the same breath.

    Definitions and Operational Audit disambiguators copied verbatim from
    taxonomy_te.txt (not paraphrased) -- an earlier version of this prompt
    dropped the Operational Audit notes, which turned out to be exactly the
    disambiguators needed: a first classification pass without them showed
    real inconsistency at the A/D boundary (confounded-design errors --
    which are D -- getting classified A because "the mechanism undermines
    its own stated goal" was applied too loosely, without checking A's own
    caveat that a contradiction resting on an unstated assumption is NOT a
    true internal contradiction)."""
    prompt = f"""You are classifying a research-proposal error into one of four categories. The error was generated freely, without being told in advance which category to aim for -- your job is only to classify it after the fact.

Categories:

A. Internal Contradiction
Shows that the text violently violates its own internal rules. You do not need an external belief; the machinery breaks itself.
Example (Java): covariant array typing lets a String[] be treated as a valid Object[], so code can legally insert an Integer into it at compile time -- but at runtime the array is still strictly a String[], so the insertion causes a fatal crash. The type system's own rule (covariance) directly causes a violation of its own goal (type safety).
Example (ML): refutes "gradient descent always converges to the global minimum" by constructing a non-convex loss surface where a local minimum's basin is flatter and wider than the global minimum's -- proving internal failure using the theory's own dynamical rules.
Operational Audit: if the contradiction relies on an UNSTATED assumption not actually given in the text, it is NOT a true Internal Contradiction -- that is a gap in the text's specification, not the text's machinery breaking itself. Do not classify as A unless the crash is derivable purely from what the text itself states.

B. Conflict with Established Beliefs
A scenario that is internally consistent but clashes violently with independent, established results or intuitions -- it does NOT self-contradict.
Example (Stats): Simpson's Paradox -- a treatment can be strictly better in every subgroup, yet worse overall once the subgroups are aggregated with skewed weighting. The math is flawless; it just clashes with the belief that "better in every subgroup" implies "better overall."
Example (ML): "Algorithm X is universally better than all others" conflicts with the No Free Lunch theorem.
Operational Audit: a true Type B never produces a clean refutation -- it produces a FORK. The reader must choose to discard either the claim or the established belief; both cannot stand. If there's no such fork -- if it's simply "this isn't standard practice" without an independent result being violated -- it is likely not B.

C. Undermining a Premise
Attacks a conflated or hidden assumption rather than the conclusion directly. The formal rules are fine; the flaw is that a human mapped two genuinely distinct concepts onto one word or one operationalization.
Example (CS): attacks the premise "if a problem is hard to solve, it must be hard to verify" -- a SAT assignment is trivial to verify despite being hard to solve, pulling "hard to solve" and "hard to verify" apart.
Example (Biology): "population variance" (heritability) gets conflated with "biological pathway" (genetic causation) -- a gene with zero variance across a population (because everyone has it) can still be 100% causally responsible for a trait.
Operational Audit: found by identifying a CONTESTED TERM, checking how it's operationalized versus what it's taken to mean, and finding a scenario where the two diverge. This is the key test: is there one specific term/concept doing double duty here, one meaning smuggled in as another?

D. Others -- a genuine, coherent flaw that doesn't cleanly fit A, B, or C (e.g. a confounded experimental design, an inappropriate or gameable metric, a straw-man comparison, a data-leakage vector -- these are real flaw types, just not one of the three above). Confounded-design errors in particular are usually D, not A: introducing an extra variable that "prevents the stated goal from being achieved" is not the same as the text's own machinery crashing into itself (A requires the crash to be derivable from what's stated, not from an omitted control).

Read the original text, the modified text, and the explanation of why it's wrong. Apply each category's Operational Audit test before deciding, not just the one-line definition. Give one brief sentence of reasoning, then your final answer.

Output format (strictly follow):

:reasoning:
<one brief sentence, naming which Operational Audit test settled it>

:category:
<exactly one of: A, B, C, D>

ORIGINAL TEXT:
{original_text}

MODIFIED TEXT:
{modified_text}

EXPLANATION OF THE ERROR:
{explanation}"""
    return prompt
