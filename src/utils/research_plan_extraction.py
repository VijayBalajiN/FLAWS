"""Port of AIScientist's `analysis/contribution_dimension/extract_research_plan.py`.

Takes the GROBID-extracted paper content (`data/paper_content/<paper>.txt`,
produced by `paper_content_extraction.py`) and makes one LLM call that
rewrites it into the Problem/Method/Experiment Design research-plan shape --
same output format as `AIScientist/data/attention_is_all_you_need.txt`.

The prompt (`GEN_RESEARCH_PLAN_PROMPT`) is copied verbatim from the source
script; only the LLM client is swapped (source script used a generic OpenAI-
compatible client, we use Gemini directly via `google-generativeai`, matching
what FLAWS's own `llm_calls.py` already uses for Gemini).
"""

from __future__ import annotations

import os

import google.generativeai as genai

GEN_RESEARCH_PLAN_PROMPT = """You are a highly skilled assistant tasked with thoroughly reading the content of a research paper and extracting its research plan. The research plan should reflect the state of the research at the time it was proposed, before any experiments or conclusions were drawn.

    A research plan consists of the following key sections:

    Problem:

    - This section provides the background of the problem being addressed, the motivation for pursuing it, and any hypotheses that the authors have formed at the start of their research.
    - Focus on the initial framing of the problem, why it's important, and the research questions that guide the study.

    Method:

    - Summarize the methodology that the authors will follow to address the problem. This includes the overall approach, any theoretical frameworks, models, or algorithms to be used, and the rationale behind the chosen methodology.
    - Do not include any references to specific results or findings - only the proposed methods and strategies.

    Experiment Design:

    - Describe the experiments that the authors will conduct to test their hypotheses. This should include the design, variables, procedures, and any tools or techniques that will be employed.
    - Provide details about how the authors plan to gather data, measure outcomes, and assess the effectiveness of the methods, but do not include any results.
    - However, make sure not to make any reference to experimental setups that the authors could not have known before conducting the experiments (e.g. specific values for hyperparameters or other design choices that were made through trial and error).

    Key Constraints:

    - No results or conclusions: Exclude any findings, outcomes, or conclusions that were reached after conducting the experiments. The research plan should represent the research at the proposal stage, not the completion stage.
    - First-person perspective: Write the research plan from the authors' point of view, as if the authors themselves are outlining their proposed work. Avoid referring to the authors in the third person.
    - Concise and focused: The research plan should be clear, concise, and direct. Include only the information necessary to describe the research as it was proposed, not the outcomes.
    - Represent the status before experimentation: Ensure the plan reflects the status of the project when it was still in the idea or proposal phase, prior to conducting any experiments.

    General Writing Guidelines:

    - Use active voice as if it's written by the authors themselves.
    - Maintain a formal yet straightforward tone typical of research proposals.
    - Keep the text brief and to the point, and avoid extraneous details or unnecessary elaboration.

    The research plans should be faithful to the original research proposal, concise, and aligned with the intent of the authors at the time of the project ideation phase.

    Generate the research plan for the following paper:
    {paper_content}"""


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


def generate_research_plan(paper_content: str, model: str = "gemini-2.5-pro") -> str:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    gen_model = genai.GenerativeModel(model_name=model)
    prompt = GEN_RESEARCH_PLAN_PROMPT.format(paper_content=paper_content)
    response = gen_model.generate_content(
        prompt, generation_config=genai.GenerationConfig(temperature=0.1)
    )
    return response.text


if __name__ == "__main__":
    import sys

    _load_dotenv()

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, "r", encoding="utf-8") as f:
        paper_content = f.read()

    plan = generate_research_plan(paper_content)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(plan)
    print(f"Saved research plan to {output_path}")
