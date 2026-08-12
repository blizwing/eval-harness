"""
Day 1 — What an LLM call actually is.

Goal: send one prompt, get the full response object, and be able to point at
five values in it: text, input tokens, output tokens, stop reason, model name.

Revised structure: instead of one function per schema that both calls AND
prints, this splits into:
  - two small "client call" functions (the only parts that legitimately
    differ between Anthropic-schema and OpenAI-schema)
  - one shared "extract the 5 values" step that both schemas normalize into
  - one shared print/report function

That way adding a third provider later means writing one new call function,
not one new call+print block.
"""

# Deepseek's legacy model names (deepseek-chat / deepseek-reasoner) were
# retired 2026-07-24. Current models: deepseek-v4-flash, deepseek-v4-pro.
# Deepseek also now exposes a native Anthropic Messages API endpoint
# (not just OpenAI-compatible) at https://api.deepseek.com/anthropic,
# which is what this script uses.

from dataclasses import dataclass
import json
import os
import anthropic
import openai


# Import Deepseek API Key from .env file
from dotenv import load_dotenv
load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
MODEL = "deepseek-v4-flash"
PROMPT = "Write a haiku about testing."
MAX_TOKENS = 1024


@dataclass
class CallResult:
    schema:str
    raw_response: dict
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    model_name: str


clientOpenAI = openai.OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

def callAnthropicSchemaAPI(prompt: str = PROMPT, temperature: float = 1.0) -> CallResult:
    """Call DeepSeek via the Anthropic-compatible Messages API."""
    clientAnthropic = anthropic.Client(
        api_key=DEEPSEEK_API_KEY, 
        base_url="https://api.deepseek.com/anthropic"
        )
    response = clientAnthropic.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=temperature,
        thinking={"type": "disabled"},
        messages=[{"role": "user", "content": prompt}],
        stream=False
    )
    return CallResult(
        schema="anthropic",
        raw_response=response.model_dump(),
        text=response.content[0].text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        stop_reason=response.stop_reason,
        model_name=response.model
    )

def callOpenAISchemaAPI(prompt: str = PROMPT, temperature: float = 1.0) -> CallResult:
    response = clientOpenAI.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        extra_body={"thinking": {"type": "disabled"}},
        max_tokens=MAX_TOKENS,
        temperature=temperature,
        stream=False
    )
    return CallResult(
        schema="openai",
        raw_response=response.model_dump(),
        text=response.choices[0].message.content,
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        stop_reason=response.choices[0].finish_reason,
        model_name=response.model
    )


def report(result: CallResult) -> None:
    """Shared print/report step — same shape regardless of which schema called it."""
    print(f"\n{'=' * 60}")
    print(f"SCHEMA: {result.schema}")
    print("=" * 60)
    print("\n--- Full response object ---")
    print(json.dumps(result.raw_response, indent=2, default=str))

    print("\n--- Extracted values ---")
    print(f"text:          {result.text!r}")
    print(f"input_tokens:  {result.input_tokens}")
    print(f"output_tokens: {result.output_tokens}")
    print(f"stop_reason:   {result.stop_reason}")
    print(f"model_name:    {result.model_name}")

def main() -> None:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set — check your .env")

    for call_fn in (callAnthropicSchemaAPI, callOpenAISchemaAPI):
        result = call_fn()
        report(result)

if __name__ == "__main__":
    main()
