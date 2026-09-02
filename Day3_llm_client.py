"""
Day 3 — llm_client.py

Goal: a reusable wrapper around Day 1's call functions that adds the two
things Day 1 didn't track — latency and cost — and keeps a running total
across every call made in the process.

This file is meant to outlive Day 3. P2 and P3 both import from here instead
of talking to the DeepSeek SDKs directly.

Pricing source: deepseek-v4-flash, cache-miss input rate (conservative —
we don't track cache hit/miss yet, so we price every call as a miss rather
than under-report cost).
  input:  $0.14  / 1M tokens
  output: $0.28  / 1M tokens
Verify against api-docs.deepseek.com/quick_start/pricing before trusting
this for anything beyond the Phase 1 $10 cap.
"""

import time
from dataclasses import dataclass, field
from Day1_first_call import CallResult, callAnthropicSchemaAPI, callOpenAISchemaAPI

# --- Pricing (USD per 1M tokens, deepseek-v4-flash, cache-miss input) ---
INPUT_COST_PER_1M = 0.14
OUTPUT_COST_PER_1M = 0.28

@dataclass
class MeteredResult:
    """CallResult plus the two things Day 1 didn't measure: latency and cost."""
    schema: str
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    model_name: str
    latency_ms: float
    cost_usd: float
    raw_response: dict = field(repr=False)

class LLMClient:
    def __init__(self) -> None:
        self.total_cost_usd: float = 0.0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.call_count: int = 0

    @staticmethod
    def _cost(input_tokens: int, output_tokens: int) -> float:
        return (
            (input_tokens / 1_000_000) * INPUT_COST_PER_1M
            + (output_tokens / 1_000_000) * OUTPUT_COST_PER_1M
        )

    def _wrap(self, call_fn, prompt: str, temperature: float) -> MeteredResult:
        start = time.perf_counter()
        result: CallResult = call_fn(prompt=prompt, temperature=temperature)
        latency_ms = (time.perf_counter() - start) * 1000

        cost = self._cost(result.input_tokens, result.output_tokens)

        self.total_cost_usd += cost
        self.total_input_tokens += result.input_tokens
        self.total_output_tokens += result.output_tokens
        self.call_count += 1

        return MeteredResult(
            schema=result.schema,
            text=result.text,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            stop_reason=result.stop_reason,
            model_name=result.model_name,
            latency_ms=latency_ms,
            cost_usd=cost,
            raw_response=result.raw_response,
        )

    def call_anthropic(self, prompt: str, temperature: float = 0.0) -> MeteredResult:
        return self._wrap(callAnthropicSchemaAPI, prompt, temperature)

    def call_openai(self, prompt: str, temperature: float = 0.0) -> MeteredResult:
        return self._wrap(callOpenAISchemaAPI, prompt, temperature)

    def print_running_total(self) -> None:
        print(
            f"\n[running total] calls={self.call_count}  "
            f"input_tokens={self.total_input_tokens}  "
            f"output_tokens={self.total_output_tokens}  "
            f"cost_usd=${self.total_cost_usd:.8f}"
        )


def report(result: MeteredResult) -> None:
    print(f"text:          {result.text!r}")
    print(f"input_tokens:  {result.input_tokens}")
    print(f"output_tokens: {result.output_tokens}")
    print(f"latency_ms:    {result.latency_ms:.1f}")
    print(f"cost_usd:      ${result.cost_usd:.8f}")
    print(f"stop_reason:   {result.stop_reason}")


def main() -> None:
    client = LLMClient()

    print("--- Call 1 (anthropic schema) ---")
    r1 = client.call_anthropic("Write a haiku about testing.")
    report(r1)
    client.print_running_total()

    print("\n--- Call 2 (openai schema) ---")
    r2 = client.call_openai("Write a haiku about testing.")
    report(r2)
    client.print_running_total()


if __name__ == "__main__":
    main()