import os
import base64

import fitz

import openai
from openai import OpenAI
import anthropic
import google.generativeai as gemini

from src.utils.resilient_call import (
    ResilientCaller, RetryPolicy, Throttle, CallBudget, UsageLog, HardTimeout,
)
from src.utils.latex_to_pdf import (
    find_main_tex_file_to_combine,
)



def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader so keys never need to be hardcoded in this file."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()

# SETUP OPENAI API KEY
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "unset"  # newer openai clients reject an empty key at import
openai.api_key = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI()

# SETUP ANTHROPIC API KEY
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY") or "unset")

# SETUP GROK API KEY
XAI_API_KEY = os.getenv("XAI_API_KEY") or "unset"
grok_client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
)

# SETUP DEEPSEEK API KEY
deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY") or "unset",
    base_url="https://api.deepseek.com/v1",
)

# SETUP GEMINI API KEY
# REST transport: the default gRPC transport was observed to hang indefinitely on a call
gemini.configure(api_key=os.getenv("GOOGLE_API_KEY", ""), transport="rest")


def get_completion_gemini(
    prompt: str,
    model: str = "gemini-2.5-pro",
    file: str | None = None,
    temperature: float = 1,
) -> str:
    config = gemini.GenerationConfig(temperature=temperature)
    gen_model = gemini.GenerativeModel(model_name=model, generation_config=config)
    if file is not None:
        with open(file, "rb") as f:
            pdf_bytes = f.read()
        messages = [
            {
                "mime_type": "application/pdf",
                "data": pdf_bytes,
            },
            prompt,
        ]
    else:
        messages = [prompt]
    response = gen_model.generate_content(messages, request_options={"timeout": 900})
    usage = getattr(response, "usage_metadata", None)
    _last_usage.update(
        prompt_tokens=getattr(usage, "prompt_token_count", None),
        output_tokens=getattr(usage, "candidates_token_count", None),
        thinking_tokens=getattr(usage, "thoughts_token_count", None),
    )
    return response.text


def get_completion_anthropic(
    prompt: str,
    model: str = "claude-sonnet-4-5",
    file: str | None = None,
    temperature: float = 1,
) -> str:
    if file is not None:
        with open(file, "rb") as f:
            pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
    else:
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    response = anthropic_client.beta.messages.create(
        betas=["context-1m-2025-08-07"],
        model=model,
        max_tokens=4096,
        messages=messages,
        temperature=temperature,
    )
    generated_text = ""
    for content_block in response.content:
        if content_block.type == "text":
            generated_text += content_block.text
    return generated_text


def get_completion_openai(
    prompt: str,
    model: str = "gpt-5-2025-08-07",
    file: str | None = None,
    temperature: float = 1,
) -> str:
    if file is not None:
        file_obj = openai_client.files.create(
            file=open(file, "rb"), purpose="user_data"
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "file_id": file_obj.id,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
    else:
        messages = [{"role": "user", "content": prompt}]
    response = openai_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        safety_identifier="user0",
    )
    return str(response.choices[0].message.content)


def get_completion_deepseek(
    prompt: str,
    model: str = "deepseek-reasoner",
    file: str | None = None,
    temperature: float = 1,
) -> str | None:
    if file is not None:
        content = fitz.open(file)
        full_content = ""
        for _, page in enumerate(content, start=1):
            text = page.get_text("text")
            full_content += text
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                        + "\n\nThis is the input file:\n\n"
                        + full_content,
                    },
                ],
            }
        ]
    else:
        messages = [{"role": "user", "content": prompt}]
    response = deepseek_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


def get_completion_grok(
    prompt: str, model: str = "grok-4", file: str | None = None, temperature: float = 1
) -> str | None:
    if file is not None:
        content = fitz.open(file)
        full_content = ""
        for _, page in enumerate(content, start=1):
            text = page.get_text("text")
            full_content += text
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                        + "\n\nThis is the input file:\n\n"
                        + full_content,
                    },
                ],
            }
        ]
    else:
        messages = [{"role": "user", "content": prompt}]
    response = grok_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        extra_body={"search_parameters": {"mode": "off"}},
    )
    return response.choices[0].message.content


def get_completion_openthought(
    prompt: str,
    model: str = "open-thoughts/OpenThinker2-7B",
    file: str | None = None,
    temperature: float = 1,
):
    if file is not None:
        content = fitz.open(file)
        full_content = ""
        for _, page in enumerate(content, start=1):
            text = page.get_text("text")
            full_content += text
        full_prompt = prompt + "\n\nThis is the input file:\n\n" + full_content
    else:
        full_prompt = prompt
    from transformers import AutoTokenizer, AutoModelForCausalLM  # heavy, optional

    tokenizer = AutoTokenizer.from_pretrained(model)
    transformer_model = AutoModelForCausalLM.from_pretrained(model)
    messages = [
        {"role": "user", "content": full_prompt},
    ]
    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(transformer_model.device)

    outputs = transformer_model.generate(**inputs, max_new_tokens=40)
    return tokenizer.decode(outputs[0][inputs["input_ids"].shape[-1] :])


def call_api(
    prompt: str,
    model: str,
    folder: str,
    paper: str,
    model_family: str,
    latex_file: str | None = None,
    pdf_path: str | None = None,
) -> tuple[str, str]:
    if folder is not None:
        os.makedirs(folder, exist_ok=True)

    if pdf_path is not None:
        full_prompt = prompt
    else:
        if latex_file is not None:
            with open(latex_file, "r") as f:
                latex = f.read()
        else:
            paper_folder = f"data/papers/{paper}"
            latex_file = find_main_tex_file_to_combine(paper_folder)
            with open(f"{paper_folder}/{latex_file}", "r") as f:
                latex = f.read()
        full_prompt = prompt + "\n\nInput Latex Source:\n" + latex

    llm_output = completion_response(model_family, model, full_prompt, pdf_path)
    return llm_output, full_prompt


# ---- resilience is composed here, implemented in resilient_call.py ---------------
_last_usage: dict = {}

_caller = ResilientCaller(
    policy=RetryPolicy(max_attempts=int(os.getenv("FLAWS_MAX_ATTEMPTS", "6"))),
    throttle=Throttle(float(os.getenv("FLAWS_MIN_CALL_INTERVAL", "6"))),
    budget=CallBudget(int(os.getenv("FLAWS_MAX_API_CALLS", "400"))),
    log=UsageLog(os.getenv("FLAWS_CALL_LOG", "data/api_calls.jsonl")),
    timeout=HardTimeout(float(os.getenv("FLAWS_CALL_TIMEOUT", "480"))),
)

# Provider registry: supporting a new provider is one new entry (open for extension).
PROVIDERS = {
    "openai": get_completion_openai,
    "gemini": get_completion_gemini,
    "anthropic": get_completion_anthropic,
    "xai": get_completion_grok,
    "deepseek": get_completion_deepseek,
    "openthought": get_completion_openthought,
}


def completion_response(
    model_family: str, model: str, prompt: str, pdf_path: str | None
) -> str:
    """Dispatch to the provider through the shared resilient caller."""
    _last_usage.clear()
    return _caller.call(
        PROVIDERS[model_family], prompt=prompt, model=model, file=pdf_path,
        usage=lambda: dict(_last_usage),
    )
