# Notes

## Day 0 — Setup (11 Aug 2026)

**Goal:** environment ready, nothing else. No learning, no build beyond scaffolding.

**Done:**
- Confirmed compute: Weeks 1–14 need only a laptop; GPU (RTX 4050, 6GB VRAM)
  isn't needed until Week 16/Phase 3. Flagged early rather than discovered
  in December.
- Python 3.11+ confirmed installed.
- Public GitHub repo created: [`blizwing/eval-harness`](https://github.com/blizwing/eval-harness).
- Virtual environment set up, `.venv/` added to `.gitignore`.
- DeepSeek API key obtained, placed in `.env`, `.env` added to `.gitignore`
  (never committed).

**Checkpoint met:** repo live on GitHub with an initial commit (`Init Project`),
`.env` not present in it.

---

## Day 1 — What an LLM call actually is (11–12 Aug 2026)

**Goal:** send one prompt, get the full response object back, and be able
to point at five values in it: text, input tokens, output tokens, stop
reason, model name.

**Build:** `Day1_first_call.py`. Sends "Write a haiku about testing." to
`deepseek-v4-flash`, once via the Anthropic-compatible Messages API
(`api.deepseek.com/anthropic`) and once via the OpenAI-compatible Chat
Completions API (`api.deepseek.com`), thinking disabled on both.

Went through one structural revision across the day: the original version
had two functions that each called their API *and* printed the result
(duplicated print logic). Refactored to:
- a shared `CallResult` dataclass that both schema calls normalize into
- `callAnthropicSchemaAPI()` / `callOpenAISchemaAPI()` — client setup and
  response parsing only, no printing
- one shared `report()` function that prints the full response JSON, then
  the five extracted values, for either schema

This makes the file the reusable base for Day 2 onward (temperature and
prompt were later added as parameters) rather than a one-off script.

**Confirmed working live** — both schemas returned:
- `input_tokens`: 11, `output_tokens`: 17
- `model_name`: `deepseek-v4-flash`
- `stop_reason`: `"end_turn"` (Anthropic) / `"stop"` (OpenAI) — same
  underlying event, different label per schema

**Key schema differences worth remembering:**
- Anthropic: text at `response.content[i].text`; usage as
  `input_tokens`/`output_tokens`
- OpenAI: text at `response.choices[0].message.content`; usage as
  `prompt_tokens`/`completion_tokens`

**Checkpoint met:** all five values pointed at, in terminal, for both schemas.

---

## Day 2 — Temperature and non-determinism (12 Aug 2026)

**Setup:** Same prompt ("Write a haiku about testing."), same model
(`deepseek-v4-flash`), 10 runs each at `temperature=0` and `temperature=1`,
across both the Anthropic-schema and OpenAI-schema endpoints.

**Finding: `temperature=0` does not guarantee determinism — and the degree
of non-determinism differs by API surface, not just by temperature.**

| Schema    | temp=0 unique outputs | temp=1 unique outputs |
|-----------|------------------------|-------------------------|
| OpenAI    | 1 / 10                 | 10 / 10                 |
| Anthropic | 5 / 10                 | 10 / 10                 |

### temp=0, OpenAI schema — fully deterministic
All 10 runs byte-identical:
> Assertions align, / Red builds fail, then green appears— / Truth in every run.

### temp=0, Anthropic schema — deterministic-ish, but leaky
6 of 10 runs matched that exact same OpenAI output. The other 4 drifted to
near-neighbor variants — same opening line every time ("Assertions align,"),
divergence confined to lines 2–3:
- "Red bar breaks the quiet calm—"
- "Red bar bleeds across the screen—"
- "Red failures light the dark path—"
- "Red bar bleeds into the dawn—"

The drift isn't random across the whole haiku — it's the model landing in
the same high-probability basin most of the time, occasionally slipping to
a nearby token at one specific branch point (after line 1).

### temp=1, both schemas — fully open
10/10 unique in both. Structurally different haikus each run; some drift
entirely off the testing metaphor (e.g. one output moved to a
medical/blood-vial image, another to a pregnancy/blooming image).

### Why this matters going forward
For the eval harness (Week 4+), "regression" against a baseline can't mean
exact-match on non-deterministic output — confirmed directly by this data,
not just by the general "temp 0 ≠ deterministic" claim from the LEARN step.
Pass-rate thresholds over multiple runs, not single-run diffing, are the
right approach. Also worth remembering later: if comparing providers or API
surfaces for consistency, the surface itself is a variable, not just the
model/temperature settings.

**Raw data:** `temp0_runs_anthropic.txt`, `temp0_runs_openai.txt`,
`temp1_runs_anthropic.txt`, `temp1_runs_openai.txt`

---

## Day 3 — Latency and cost tracking (13 Aug 2026)

**Goal:** wrap Day 1's call functions so every call also reports latency
and cost, and so the process can keep a running total across many calls —
without duplicating the Anthropic/OpenAI call logic itself.

**Build:** `Day3_llm_client.py`. `LLMClient` wraps `callAnthropicSchemaAPI`
/ `callOpenAISchemaAPI` from `Day1_first_call.py` through a shared `_wrap()`
method:
- times each call with `time.perf_counter()` around the request
- prices each call from token counts using `deepseek-v4-flash` cache-miss
  rates (`$0.14`/1M input, `$0.28`/1M output) — priced as a miss
  unconditionally since cache hit/miss isn't tracked yet, so cost is never
  under-reported
- accumulates `total_cost_usd`, `total_input_tokens`, `total_output_tokens`,
  `call_count` on the client instance across calls
- returns a `MeteredResult` dataclass — `CallResult`'s fields plus
  `latency_ms` and `cost_usd`

This file is meant to outlive Day 3: it's the intended import point for P2
and P3 instead of talking to the DeepSeek SDKs directly.

**Note for later:** pricing is hardcoded from a point-in-time check of
api-docs.deepseek.com/quick_start/pricing — needs re-verifying before
relying on it beyond the Phase 1 $10 cap.