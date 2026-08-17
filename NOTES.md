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

---

## Day 4 — JSON mode and untrustworthy structured output (14 Aug 2026)

**Goal:** request a small structured JSON object from the model, then
deliberately ask for a field it has no way to know, and observe exactly
what happens — does it invent a value, refuse, or return something
malformed?

**Build:** `Day4_json_mode.py`. `call_OpenAI_json_mode()` calls DeepSeek's
OpenAI-compatible endpoint with `response_format={"type": "json_object"}`
(DeepSeek's JSON mode is OpenAI-schema only — no equivalent flag exists on
the Anthropic-compatible endpoint, so this file only extends
`callOpenAISchemaAPI`, not the Anthropic one). Two prompts run against the
same fixed paragraph (a QA regression-testing scenario with two low- and
one medium-severity defect):

- `PROMPT` — asks for `summary` and `risk_level` only (both answerable
  from the paragraph)
- `BREAK_IT_PROMPT` — identical, plus a third field, `estimated_fix_hours`,
  which the paragraph gives zero basis for

**Finding 1 — the impossible field gets confidently fabricated, not flagged.**

`BREAK_IT_PROMPT` returned:
```json
{"summary": "...", "risk_level": "low", "estimated_fix_hours": 6}
```

No refusal, no `null`, no error, no malformed JSON — `estimated_fix_hours`
came back as a clean integer, formatted identically to the two fields that
*are* grounded in the paragraph. Nothing in the response shape signals
that this field is fabricated while the other two are derived from the
source text. A downstream consumer parsing this JSON has no way to tell
the difference from the response alone — the failure is silent, not loud,
and would sail straight through a `try/except json.JSONDecodeError` check
without tripping it.

**Finding 2 — `risk_level` was inconsistent across repeated calls, even at
`temperature=0`.**

Running the *normal* (non-broken) prompt three times at `temperature=0`
against the identical paragraph returned `risk_level` as `medium`,
`medium`, and `low` across the three runs. This is notable against Day
2's own data: on this same OpenAI-schema endpoint, Day 2 measured 1/10
unique outputs at `temperature=0` (fully deterministic) for a free-text
haiku prompt. That determinism didn't hold here. Open question, not yet
answered: whether this is a property of JSON-mode sampling specifically,
or of subjective/borderline classification tasks generally (the paragraph
sits genuinely between "low" and "medium" — 2 minor defects, 1 moderate
one — so even small amounts of residual randomness are enough to flip the
label). Worth revisiting once more evidence exists.

**Why this matters going forward**

Two distinct failure modes now confirmed, not just theorized:
1. Fabrication on fields with no grounding — silent, well-formatted, and
   indistinguishable from legitimate output without an external check.
2. Inconsistent judgment-based output even at `temperature=0` — meaning
   even "the field the model *can* answer" isn't safe to trust from a
   single run.

Both point the same direction as Day 2's finding: exact-match or
single-run trust doesn't work for this system. The eval harness needs
checks that go beyond "did it parse" — grounding/hallucination checks for
fields like `estimated_fix_hours`, and pass-rate thresholds across
repeated runs for judgment fields like `risk_level`.

**Raw examples:** see `Day4_json_mode.py` output — normal vs. break-it
prompt and result pasted in Day 4 build discussion.

---

## Day 5 — `/advanced-learn` Session 1: structured output & schema validation (15 Aug 2026)

**Goal:** build a Pydantic validation layer that fails loud and distinguishes
three failure modes on a raw LLM string response — invalid JSON, valid JSON
missing a required field, and valid JSON with a wrong/out-of-range value.
Directly downstream of Day 4's finding that malformed and fabricated output
both need to be caught before they reach the eval harness.

**Build:** `day5_validate.py`. `validate_response(raw_text)` runs two
separate stages instead of one blanket `except Exception`:
1. `json.loads()` — is this parseable JSON at all? Failure here means the
   model didn't even produce valid syntax (truncation, prose wrapping the
   JSON, etc.) — caught as `json.JSONDecodeError`, tagged `invalid_json`.
2. `EvalResult.model_validate()` — a Pydantic model with
   `risk_level: Literal["low", "medium", "high"]` rather than a bare `str`.
   Using `str` would have silently accepted `"extreme"` as valid, since it
   *is* a string — `Literal` is what actually enforces the allowed value
   set. Failures caught as `pydantic.ValidationError`.

The triage inside stage 2 comes from `ValidationError.errors()`, which
returns one dict per broken field, each tagged with a `type` string:
`"missing"` when a required key is absent entirely, and a value-specific
string (`"literal_error"`, `"string_type"`, etc.) when the key is present
but the value doesn't fit the schema. Branching on that tag is the entire
mechanism — no custom detection logic needed.

**Extended past the DONE WHEN bar:** the first pass used `if missing: return
... else: return ...`, which silently dropped every other problem once the
first category was found — a payload with two simultaneous issues would
only ever report one of them. Fixed by computing `missing` and `wrong_type`
independently from the full `errors()` list and appending both to a
`failures` list when both are present, instead of short-circuiting.

**Confirmed working live** — four cases, four correct outcomes:
```
broken_json   -> ('invalid_json', ["Expecting ',' delimiter: line 1 column 47 (char 46)"])
missing_field -> ('invalid', [('missing_field', "Missing required field(s): ['risk_level']")])
wrong_type    -> ('invalid', [('wrong_type', [('risk_level', 'literal_error', "Input should be 'low', 'medium' or 'high'")])])
both_at_once  -> ('invalid', [('missing_field', "Missing required field(s): ['summary']"),
                               ('wrong_type', [('risk_level', 'literal_error', "Input should be 'low', 'medium' or 'high'")])])
```
`both_at_once` (`{"risk_level": "extreme"}` — missing `summary` *and* a bad
`risk_level`) returns both failure entries in one list, proving the fix
actually works rather than just not-crashing.

**Known gap, not yet solved:** this layer only catches structural/type
violations. Day 4's harder finding — a well-formed, correctly-typed but
*fabricated* value (e.g. a plausible `estimated_fix_hours` invented from
nothing) — passes this validator cleanly, because nothing about the shape
signals fabrication. Schema validation and grounding/hallucination checks
are separate concerns; this only solves the first one.

**Why this matters going forward:** this becomes the parsing layer beneath
the four hard assertions planned for Day 11 (Week 2) and the pluggable
scorer in Week 4 — "did it even parse, and how" needs to be answered before
assertion- or judge-based scoring runs at all.

**Checkpoint met:** three (then four, including the combined case)
deliberately broken responses each produced a distinct, readable, correctly
categorized error.

**Raw file:** `day5_validate.py`

---

## Day 6 — Buffer/Rest Day (16 Aug 2026)

Recharging yourself is necessary in order to achieve great things.

---

## Day 7 — zero-shot requirement → structured test case (17 Aug 2026)

**Goal:** turn a plain-English requirement into a structured JSON test case via
a zero-shot prompt, with the prompt stored in its own file rather than inlined.
Output validated through a generalized version of Day 5's `validate_response`.

**Build:** `Day7_zeroshot_testcase.py`, prompt externalized to
`Day7_prompt_file/prompt_testcase_v1.txt`. `TestCase` Pydantic model (`title`,
`description`, `preconditions`, `test_steps`, `expected_result`, `priority`)
mirrored exactly against the prompt's required JSON fields. `day5_validate.py`'s
`validate_response` was generalized to take a `model: type[BaseModel]` param
instead of a hardcoded `EvalResult`, so the same two-stage json.loads() →
model_validate() pattern is reusable across days; its demo/test block was also
moved behind `if __name__ == "__main__":` after discovering it silently
re-ran and printed on every import (see side lesson below). 10 real
requirements written by hand (secrets/burn-after-read service — token
generation, passcode validation, single-view enforcement, race condition on
concurrent access) run through `call_OpenAI_json_mode` and validated against
`TestCase`, three separate runs.

**Result across 3 runs — failure rate and failure set both unstable, but not
fully random:**

| Run | Missing `priority` | Which requirements |
|---|---|---|
| 1 | 2/10 | Create secret note successfully; Wrong passcode denies access |
| 2 | 3/10 | above two + Brute-force protection / lockout |
| 3 | 2/10 | Wrong passcode denies access; Race condition: two recipients opening simultaneously |

Every failure across all 3 runs was `missing_field: ['priority']` — never a
different field, never a wrong type, never invalid JSON. **"Wrong passcode
denies access" failed in all 3 runs**, the only requirement to do so
consistently; every other failure was a one-off. That consistency on one
specific item, against inconsistency everywhere else, suggests this isn't
pure random noise — something about that requirement's phrasing, length, or
position in the batch may correlate with the drop, worth investigating later
rather than writing off as noise.

**Second finding, no validator would catch this:** every valid response
across all 3 runs returned `priority='high'` — including requirements that
shouldn't obviously all be equally critical (e.g. "reject empty message" vs.
"race condition on concurrent access"). Schema validation passes cleanly on
all of them; nothing about `priority='high'` looks structurally wrong to
Pydantic. This is a judgment/laziness failure, not a shape failure — same
category as Day 4's fabricated `estimated_fix_hours`, but inverted: instead
of inventing a specific-looking wrong value, the model appears to default to
the "safe" value regardless of actual content, every time.

**Why this matters going forward:** the `priority` drop is the same
non-determinism/inconsistency pattern from Day 2 and Day 4, now confirmed on
a third, unrelated task, and specifically isolated to one field rather than
spread randomly across the schema. `priority` being the *last* field in both
the prompt's field list and the Pydantic model is a plausible suspect
(positional effects in structured generation are a known failure mode) —
worth testing later by reordering the schema. Reinforces that the harness's
assertions (Week 2) and scorer (Week 4) need per-field reliability checks
across repeated runs, not just "did it parse once." The `priority='high'`
uniformity is a new failure category worth carrying into Day 10-11's
labeling: a test case can pass every hard assertion and still be
low-quality, because assertions check shape, not judgment.

**Side lesson — module-level code runs on import:** `day5_validate.py`'s
self-test loop (4 hardcoded broken-JSON cases) was sitting at module level,
not behind `if __name__ == "__main__":`. Every `from day5_validate import
validate_response` — including in this file — silently re-ran and printed
all four of Day 5's test cases before Day 7's real output. Fixed by gating
behind `__main__`. Good reminder to do this in every reusable file going
forward, not just ones that happen to get imported.

**Checkpoint met:** requirement in, parseable JSON out — confirmed
repeatedly across 3 full runs of 10 requirements each.

**Raw files:** `Day7_zeroshot_testcase.py`, `Day7_prompt_file/prompt_testcase_v1.txt`