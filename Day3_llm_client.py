"""
Day 3 — llm_client.py

Goal: a reusable wrapper around Day 1's call functions that adds the two
things Day 1 didn't track — latency and cost — and keeps a running total
across every call made in the process.

This file is meant to outlive Day 3. P2 and P3 both import from here instead
of talking to the DeepSeek SDKs directly.

Pricing source: deepseek-flash, cache-miss input rate (conservative — we
don't track cache hit/miss yet, so we price every call as a miss rather
than under-report cost). Confirmed 11 Sep 2026 against
api-docs.deepseek.com/quick_start/pricing.

Updated Day 32 follow-up (11 Sep 2026): the original flat-rate constants
here (input $0.14 / output $0.28, from Day 3, 13 Aug 2026) were found
stale while investigating a separate CI incident (the `deepseek-v4-flash`
alias silently started resolving to a new model, DeepSeek-V4.1-Flash).
Current published pricing is peak/off-peak split, and both rates are
higher than what was hardcoded here — output cost in particular is
roughly 2x (off-peak) to 4x (peak) the old constant. Every cost figure
this harness has reported before today (Day 25 reports, `baseline.json`,
Day 31's cost-cap comparisons) was computed against an under-priced
constant — exactly the kind of number this harness exists to catch, just
found in its own cost layer instead of the score layer.

Peak/off-peak schedule per DeepSeek's docs: peak hours are 01:00-04:00
and 06:00-10:00 UTC, Monday-Friday (treated as half-open intervals — hour
4 and hour 10 are already off-peak); everything else, including all
weekend hours, is off-peak.
  off-peak: input $0.15 / 1M tokens, output $0.60 / 1M tokens
  peak:     input $0.30 / 1M tokens, output $1.20 / 1M tokens
Verify against api-docs.deepseek.com/quick_start/pricing before trusting
this for anything beyond Phase 1's $10 cap — this alias has already moved
pricing once without any change to the model name we request.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from Day1_first_call import CallResult, callAnthropicSchemaAPI, callOpenAISchemaAPI

# --- Pricing (USD per 1M tokens, deepseek-flash, cache-miss input) ---
OFF_PEAK_INPUT_COST_PER_1M = 0.15
OFF_PEAK_OUTPUT_COST_PER_1M = 0.60
PEAK_INPUT_COST_PER_1M = 0.30
PEAK_OUTPUT_COST_PER_1M = 1.20

# (start_hour, end_hour) in UTC, end exclusive. Weekends are always
# off-peak regardless of hour — the published schedule is Mon-Fri only.
PEAK_HOUR_RANGES_UTC = ((1, 4), (6, 10))
WEEKEND_ISO_WEEKDAYS = (6, 7)  # datetime.isoweekday(): 6=Saturday, 7=Sunday


def is_peak_hour(dt: datetime) -> bool:
    """True if dt falls in one of DeepSeek's published peak pricing windows.
    dt is converted to UTC first so a naive local timestamp isn't silently
    treated as if it were already UTC."""
    dt_utc = dt.astimezone(timezone.utc)
    if dt_utc.isoweekday() in WEEKEND_ISO_WEEKDAYS:
        return False
    return any(start <= dt_utc.hour < end for start, end in PEAK_HOUR_RANGES_UTC)

@dataclass
class MeteredResult:
    """CallResult plus the three things Day 1 didn't measure: latency, cost,
    and (Day 32 follow-up) which pricing tier the cost was computed under —
    kept alongside cost_usd so a reported number is auditable after the
    fact instead of a black box ("why did this cost more than that one?")."""
    schema: str
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    model_name: str
    latency_ms: float
    cost_usd: float
    pricing_tier: str  # "peak" or "off_peak" — see is_peak_hour()
    raw_response: dict = field(repr=False)

class LLMClient:
    def __init__(self) -> None:
        self.total_cost_usd: float = 0.0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.call_count: int = 0

    @staticmethod
    def _cost(input_tokens: int, output_tokens: int, peak: bool) -> float:
        input_rate = PEAK_INPUT_COST_PER_1M if peak else OFF_PEAK_INPUT_COST_PER_1M
        output_rate = PEAK_OUTPUT_COST_PER_1M if peak else OFF_PEAK_OUTPUT_COST_PER_1M
        return (
            (input_tokens / 1_000_000) * input_rate
            + (output_tokens / 1_000_000) * output_rate
        )

    def _wrap(self, call_fn, prompt: str, temperature: float) -> MeteredResult:
        start = time.perf_counter()
        call_time = datetime.now(timezone.utc)
        result: CallResult = call_fn(prompt=prompt, temperature=temperature)
        latency_ms = (time.perf_counter() - start) * 1000

        peak = is_peak_hour(call_time)
        cost = self._cost(result.input_tokens, result.output_tokens, peak)

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
            pricing_tier="peak" if peak else "off_peak",
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
    print(f"cost_usd:      ${result.cost_usd:.8f} ({result.pricing_tier})")
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