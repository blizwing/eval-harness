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

---

## Day 8 — 10 hand-written requirements from real FSM work (18 Aug 2026)

**Goal:** write 10 requirements by hand from real Field Service Management
(FSM) work, anonymized — no company, client, or internal system names — and
store them as `requirements.yaml`, in a state a stranger could read.

**Build:** `fsm_requirements.yaml`. 10 requirements covering the FSM domain
end to end: task creation with customer details (`req_01`), technician
skill-matched assignment and on-site completion within a time window
(`req_02`), the scheduling engine's assignment parameters — distance, mode
of transport, skillset, task duration (`req_03`), the mobile technician
workflow of approval → work → evidence capture (`req_04`), signature
capture and return-to-base (`req_05`), reassignment triggers when a
technician can't work the task — sick, on leave, reassigned elsewhere
(`req_06`), the web app surfacing completed task data (`req_07`), evidence
visibility with no errors (`req_08`), and role-gated login for both the web
app — Dispatcher/Admin only (`req_09`) — and the mobile app — technician
only (`req_10`).

No anonymization was actually load-bearing here — the requirements as
drafted never named a company, client, or internal system, so "anonymize"
mostly meant not introducing any while writing. The real editing pass was
copyediting for consistency: normalizing capitalization ("FSM Web
Application" → "FSM web application" throughout, matching `req_01`'s
lowercase style) and fixing parallelism in `req_06`'s list ("falling sick,
be on leave, gets assigned" → "falling sick, being on leave, or getting
assigned").

**Why this matters going forward:** this is the ground-truth input for Day
9 (run Day 7's zero-shot prompt against all 10, save outputs) and Day 10
(label each `good`/`bad`/`borderline`). Because these come from real FSM
work rather than invented examples, they carry real-world irregularities —
`req_08` is a one-line, almost under-specified requirement ("The evidences
should be visible without any error") sitting next to much more detailed
ones like `req_03` — which is exactly the kind of unevenness Week 2's
labeling and assertion work needs to be tested against, not a curated set
where every item is equally well-formed.

**Checkpoint met:** 10 requirements exist in `fsm_requirements.yaml`,
covering task creation, scheduling, mobile workflow, evidence capture,
reassignment, and access control — none reference a real company, client,
or internal system name.

**Raw file:** `fsm_requirements.yaml` (moved to `Day8_Project_Requirements/`
as part of Day 9's setup — see below)

---

## Day 9 — run Day 7's prompt against all 10 Day 8 requirements (19 Aug 2026)

**Goal:** run Day 7's zero-shot test-case prompt against all 10 of Day 8's
hand-written FSM requirements, and save every raw response plus its
validation verdict to one place so they can be read and manually labeled
in Day 10.

**Build:** `Day9_run_outputs.py`. Moved `fsm_requirements.yaml` into its own
`Day8_Project_Requirements/` folder rather than leaving it at repo root.
Loads the 10 requirements via `yaml.safe_load` (added `pyyaml` to
`requirements.txt`), runs each through `call_OpenAI_json_mode` with Day 7's
prompt template, validates each response against Day 7's `TestCase` model
via `validate_response`, and writes one combined JSON file —
`Day9_Requirements_JSON_Outputs/Day9_outputs.json` — containing per-requirement
id, requirement text, raw response text, verdict, failure detail (if any),
parsed output (if valid), token counts, and model name, plus a
`generated_at` timestamp and source file paths at the top level.

**Interpreted per Pratham's choice:** the DONE WHEN bar as originally phrased
("10 output files, plus a note of which are wrong") was interpreted as one
combined JSON file holding all 10 results rather than 10 separate files —
folder name kept plural/per-requirement in spirit, content consolidated.

**Result — the Day 7 `priority`-drop pattern reproduced on entirely new
requirements:** 9/10 valid, 1/10 (`req_07` — "the FSM web application needs
to show the entire result of the task...") failed with the exact same
`missing_field: ['priority']` verdict as every Day 7 failure. Every one of
the 9 valid responses again returned `priority: "high"`, continuing Day 7's
finding that the model defaults to `"high"` regardless of the requirement's
actual content or apparent severity. Nothing new in kind — but confirms the
pattern isn't specific to the Day 7 requirement set, and holds on a
completely different (real-world, FSM-domain) set of inputs.

**Side fix, not yet verified cross-platform:** while wiring this up, found
`Day7_zeroshot_testcase.py` importing `from day5_validate import
validate_response` (lowercase `d`) against a file tracked in git as
`day5_validate.py`. Changed both `Day7_zeroshot_testcase.py` and
`Day9_run_outputs.py` to import `Day5_validate` (capital `D`) — this only
works silently on Windows because its filesystem is case-insensitive; the
file is still tracked in git under the lowercase name, so this will break
on a case-sensitive filesystem (Linux CI, GitHub Actions) until either the
import or the tracked filename is made consistent. Flagged, not fixed, since
it doesn't block local work.

**Why this matters going forward:** two independent requirement sets now
both show the same two failure modes (occasional `priority` omission,
uniform `priority="high"` when present) — this is no longer a one-batch
fluke and should be treated as a real property of the current prompt/model
combination going into Day 10's labeling and Week 2's assertion design.
The case-sensitivity import issue should be resolved before this project
ever runs in CI or on a non-Windows machine.

**Checkpoint met:** all 10 requirements run, one combined JSON file with
verdict + raw response per requirement saved to
`Day9_Requirements_JSON_Outputs/Day9_outputs.json`.

**Raw files:** `Day9_run_outputs.py`, `Day9_Requirements_JSON_Outputs/Day9_outputs.json`

---

## Day 10 — label all 10 Day 9 outputs good/bad/borderline (20 Aug 2026)

**Goal:** read all 10 requirement → generated-test-case pairs from
`Day9_outputs.json` and hand-label each `good`/`bad`/`borderline` with a
one-line reason — this is the ground truth every later comparison (Day 12's
judge, Day 14's judge-vs-human agreement, Day 19's precision/recall) gets
measured against.

**Build:** `Day10_Ground_Truth/Day10_labels.json`. Keyed by `req_id` to join
cleanly against `Day9_outputs.json`. Each entry carries three fields:
`label` (good/bad/borderline), `requirement_ambiguous` (bool), and `reason`
(one line). The `requirement_ambiguous` field was added after an initial
pass folded requirement-level ambiguity and output-quality judgment into
the same `label` value — splitting them out keeps "the requirement itself
was compound/vague" separate from "the model's output was wrong," since
those are different failure sources and Week 2/3's assertion and rubric
work need to be able to tell them apart.

**Result:** 7/10 `good`, 2/10 `bad`, 1/10 `borderline`.
`requirement_ambiguous: true` on exactly one entry, `req_02`, which bundles
two distinct behaviors (skill-matched assignment *and* travel-to-completion
within a time window) into a single requirement — the generated test case's
steps followed that same conflation rather than resolving it, which is
requirement-level ambiguity feeding directly into output quality.

Both `bad` labels trace to concrete, specific failures rather than vague
dissatisfaction: `req_01`'s test case didn't capture the duration input in
expected format, and `req_07` is the same validator-confirmed
`missing_field: priority` failure already logged in Day 9 — initially
labeled `good` with the reasoning "content is fine despite the missing
field," then corrected to `bad` on review, since the row's own
`validation_verdict` was `invalid` with `parsed_output: null`. A ground
truth label disagreeing with the harness's own assertion layer on the same
row would have been a silent inconsistency baked into Day 12 and Day 14
before it was ever noticed.

**Why this matters going forward:** this is the first artifact in the
project that is pure human judgment with no model involved in producing
it — everything before this (Day 7's prompt, Day 9's outputs) was
model-generated and then read; this is Pratham's own read, unassisted,
and it's what the LLM-judge gets checked against starting Day 12. The
`req_07` correction is worth remembering specifically: a label and its
own reason can look internally consistent while still contradicting a
fact already sitting in the source data (the validator's verdict) — worth
a fast cross-check against `Day9_outputs.json`'s `validation_verdict`
field before trusting any label as final, not just a read of the reason
text in isolation.

**Checkpoint met:** all 10 requirements labeled, `Day10_labels.json`
committed as the ground-truth file for Phase 1's remaining weeks.

**Raw file:** `Day10_Ground_Truth/Day10_labels.json`

---

### Day 11 — Thu 21 Aug 2026 — four hard assertions on Day 9's outputs

**Goal:** run four deterministic checks — valid JSON, all fields present,
non-empty, under a token cap — against all 10 of Day 9's generated test
cases, producing a 10×4 pass/fail table.

**Build:** `Day11_assertions.py`. Two of the four checks aren't new logic —
`valid_json` and `fields_present` both read Day 9's existing
`validation_verdict`/`validation_detail` (computed by `Day5_validate.py`
during the Day 9 run) rather than re-parsing `raw_response_text` from
scratch. Re-deriving JSON/field-presence logic in a second place would
create two validators that could quietly drift apart over time. The two
genuinely new checks are `non_empty` (Pydantic enforces a field exists and
has the right type, but an empty string or empty list still satisfies
`str`/`list` — so blank output was slipping through unnoticed) and
`under_token_cap` (nothing before today checked generation length at all).

**Token cap:** 583, calculated as 2× the median `output_tokens` across all
10 Day 9 rows — including `req_07`, despite it failing validation, since it
still cost tokens to generate and belongs in the "what does normal
generation cost look like" baseline. This is a length-anomaly guardrail,
not a hard cost ceiling: it exists to catch a run that unexpectedly
balloons (rambling, repetition, disproportionate elaboration for a simple
requirement), not to police every run against a fixed budget. All 10 rows
pass today (max was 377) — the cap has nothing to catch yet on this small,
consistent dataset. Revisit once Week 3's expanded 30-requirement set
(with adversarial cases) gives it something real to flag.

**Result:** 38/40 checks passed. `req_07` fails `fields_present` and
`non_empty` — consistent with Day 9's `missing_field: priority` verdict and
Day 10's ground-truth `bad` label on the same row. `non_empty` returns
`False` for `req_07` via an explicit `parsed_output is None` guard rather
than falling through an empty loop to a vacuous `True` — a row with no
parsed output at all has no fields to be non-empty, so "nothing to check,
therefore pass" would have been the wrong default.

**Checkpoint met:** 10×4 table produced, saved to
`Day11_Assertion_Results/Day11_results.json`.

**Raw file:** `Day11_assertions.py`, `Day11_Assertion_Results/Day11_results.json`

---

### Day 12 — Sat 22 Aug 2026 — `/advanced-learn` Session 2: LLM-as-a-judge

**Goal:** build a model-graded judge, run it on all 10 of Day 9's generated
test cases, and produce 10 judge verdicts to sit alongside Day 10's human
ground-truth labels.

**Build:** `Day12_LLM_Judge.py` + `Day12_Judge_LLM_Data/judge_llm_prompt.txt`.
The judge prompt scores each generated test case against three named,
independent criteria rather than a single vague "is this good?" question:
**field completeness** (are required fields present and non-empty),
**requirement coverage** (does the test case test what the requirement
actually describes), and **specificity** (are steps and preconditions
concrete enough to execute). Field completeness and requirement coverage
are treated as load-bearing — a fail on either forces the verdict to `bad`,
since a test case missing fields or testing the wrong thing is unusable
regardless of how well-written it is. Specificity failing alone drops the
verdict to `borderline` rather than `bad`, since vague steps are a quality
problem, not a correctness problem — the requirement itself is sometimes
underspecified, so a certain amount of vagueness in preconditions/steps is
inherited from the source, not invented by the model. All three passing is
what produces a `good` verdict. The runner reuses Day 3's
`call_OpenAI_json_mode` and Day 5's `validate_response` exactly as Day 9
did, so judge output goes through the same validation path as generation
output.

**`req_07` handling:** Day 9's `parsed_output` was `None` for this row
(failed Day 5 validation, missing `priority`). Rather than formatting the
literal string `None` into the judge prompt — which would read as a
plausible-if-odd field value — the runner substitutes an explicit marker
sentence stating no valid output was produced. The judge correctly read
this as an absence signal and failed all three criteria, landing on `bad`
with reasoning that named the missing output directly. This is the one row
with independently known ground truth (Day 10 also labeled it `bad`), and
the judge matched it for the right reason, not by chance.

**Result:** 8 `good`, 1 `borderline` (`req_02`), 1 `bad` (`req_07`) —
against Day 10's 7 `good`, 2 `bad`, 1 `borderline`. Two points of note:

- `req_02` — both the judge and Day 10's human label flagged this row as
  imperfect, but via different diagnostic paths. Day 10 called out
  requirement-level ambiguity (the requirement bundles two distinct
  behaviors — skill-matched assignment and travel-to-completion — into one
  sentence). The judge didn't name that ambiguity directly; it failed
  `specificity` for vague simulation steps in the generated test case.
  Different reasoning, same row flagged — worth noting as partial
  agreement, not full agreement, in Day 14's comparison.
- `req_01` — the one real disagreement. Day 10 labeled this `bad` because
  the test case never verifies the *duration is captured in the correct
  format*, only that a duration step exists. The judge marked it `good`
  (`specificity: pass`), and on inspection this isn't the judge reasoning
  poorly — the generated test case does structurally satisfy all three
  current criteria (fields present, duration step included,
  concrete-looking steps). The rubric has no criterion asking whether the
  expected result *actually verifies* the specific behavior the
  requirement calls out, versus merely touching the general area. This is
  a rubric gap, not a judge-reasoning failure, and it's the concrete
  example to carry into Day 14 and Week 3's rubric revision.

**Self-preference bias (flagged, not yet measured):** using the same model
(DeepSeek) as both generator and judge means the judge may be predisposed
to rate its own family's output favorably — a documented effect, not a
theoretical worry. Today's 10-row run is too small and too lopsided (8/10
good) to confirm or rule this out. Revisit once Week 3 expands to 30
requirements with adversarial cases, where a skewed judge would have more
opportunity to be caught out.

**Checkpoint met:** 10 judge verdicts saved, sitting alongside
`Day10_labels.json`.

**Raw file:** `Day12_LLM_Judge.py`, `Day12_Judge_LLM_Data/judge_llm_prompt.txt`,
`Day12_Judge_LLM_Data/Day12_judge_llm_verdicts.json`

---

## Day 13 — Buffer/Rest Day (23 Aug 2026)

Recharging yourself is necessary in order to achieve great things.

---

## Day 14 — Judge vs. Human Comparison (Mon 24 Aug 2026)

Compared Day 12's judge verdicts against Day 10's human ground truth labels
across all 10 requirements. Confusion matrix + disagreement log in
`Day14_comparisions.md`.

**Agreement: 9/10 = 90%.** One disagreement: `req_01` (human: bad, judge: good).

The `req_01` miss traces to a duration-format gap in the generated test case
that was never flagged. Splitting this into two separate questions mattered:
was the judge's *verdict* correct, and was the judge's *reasoning process*
correct. They're not the same thing. Here, the verdict was wrong — the test
case really is incomplete — but the process wasn't at fault. Given its rubric
and the artifact it was shown, the judge scored consistently. The gap is in
what the judge was given to grade against, not in how it graded it. Same
category of fix Week 3 is already aimed at with the priority-field grounding
experiment, just for field-completeness/formatting instead.

At n=1 disagreement, too little data to call this a pattern — revisit once
the dataset expands to 30 in Week 3 (Day 17).

Net effect on trust going into Week 3: not fully trusting the judge yet.
Internally consistent reasoning still produced a wrong final verdict, and
that's the more dangerous failure mode — a judge that's confidently wrong
doesn't announce itself the way a broken one does. Going into the rubric
rework still owed proof rather than assuming the grounding-criteria fix will
just work.
## Day 15 � Judge v2: Named-Criteria Rubric (Tue 25 Aug 2026)

v1 copied as-is to Day15_Judge_Rubric_V2/judge_v1.txt. v2 adds two criteria
targeting the req_01 gap from Day 14: verification_fidelity (does the expected
result check the exact detail/format the requirement names) and pass_fail_clarity
(does the test case state an unambiguous pass/fail condition). Both added to the
output JSON; tiering extended - completeness, coverage, and verification_fidelity
are hard-fail; specificity and pass_fail_clarity are soft-fail (borderline).

An earlier draft of these two criteria asked the judge to grade whether the
*requirement* was ambiguous, not the test case. Dropped that framing - it's a
different job (already parked in BACKLOG.md) and wouldn't have caught req_01,
since that requirement wasn't ambiguous, it was under-tested. Retargeted both
criteria at the test case's fidelity to the requirement instead.

Not yet run - Day 16 recomputes agreement on all 10 using v2.

---

## Day 16 — Judge v2 run and agreement recompute (Wed 26 Aug 2026)

**Goal:** run Day 15's v2 rubric (`judge_v2.txt`) against all 10 of Day 9's
generated test cases and recompute agreement against Day 10's human labels.

**Build:** `Day16_judge_v2_run.py`, same structure as `Day12_LLM_Judge.py`
(same Day 9 source, same `call_OpenAI_json_mode` + `validate_response`
pattern), pointed at `Day15_Judge_Rubric_V2/judge_v2.txt` instead of Day 12's
prompt, with `JudgeVerdictV2` extending the Pydantic model to the two new
fields (`verification_fidelity`, `pass_fail_clarity`). Verdicts saved to
`Day16_Judge_V2_Results/Day16_judge_v2_verdicts.json`. Comparison written to
`Day16_agreement_comparison.md`.

**Result: agreement regressed, 9/10 (90%, Day 14) -> 8/10 (80%).** Two
disagreements against Day 10's human labels: `req_01` and `req_02`.

- `req_01` — the exact row v2 was built to fix — still disagrees. The judge
  passed `verification_fidelity` even though the test case's expected
  result only confirms duration is *present*, never checks its *format*,
  which is precisely the human label's complaint. The criterion asks the
  right question in principle; the judge's application of it here still
  credited presence-of-detail over correctness-of-format.
- `req_02` — a **new** disagreement. Under v1 the judge scored this
  `borderline` (failed `specificity`) and agreed with the human label; under
  v2, `specificity` flipped to `pass` on the same underlying test case and
  the verdict became `good`. No wording in v2 obviously targets
  `specificity` itself, so this looks more like the run-to-run judgment
  instability already documented since Day 4/Day 7 than a real effect of
  the new criteria — but this was a single uncontrolled run per rubric
  version, so that can't be confirmed from this data alone.

**Why this matters going forward:** the rubric rework did not deliver the
fix it targeted, and cost a previously-correct call elsewhere. Before
concluding v2 is actually worse, need repeated runs per row (not one verdict
each) or the larger 30-requirement Week 3 set to separate real rubric effect
from single-run noise — both already planned, not new work.

**Checkpoint met:** both agreement numbers stated — v1 90%, v2 80% —
computed from a real run, not assumed.

**Raw files:** `Day16_judge_v2_run.py`,
`Day16_Judge_V2_Results/Day16_judge_v2_verdicts.json`,
`Day16_agreement_comparison.md`

---

## Day 17 — Requirement set expansion to 35, adversarial set introduced (Thu 27 Aug 2026)

**Goal:** expand `fsm_requirements.yaml` from 10 to 30+ requirements,
including 5+ deliberately adversarial cases (vague / contradictory /
missing-precondition), per the Week 3 plan.

**Build:** two new feature areas added to source material from — Workforce
Management Service (Timesheets, Skills, Licenses) and External Systems
Integration (EIPS: activate/deactivate/reprovision for router, modem,
internet, TV, and telephone service). Requirements drafted from raw,
unstructured stakeholder-ask material rather than pre-formed requirement
statements, then translated into formal requirement text by hand — same
process as Day 8, not skipped just because the volume went up. `req_11`–
`req_35` appended to `fsm_requirements.yaml`.

**Result: 35 total requirements (10 existing + 25 new), 5 tagged
adversarial.**

- `req_24` — missing_precondition: task types that trigger the
  Provisioning page left undefined. Deliberately kept this way rather
  than filling in a task-type list that hadn't actually been confirmed.
- `req_33` — missing_precondition: "security headers" left unspecified,
  unlike `req_31`/`req_32` which name the exact headers required.
- `req_25` / `req_34` — contradictory pair: both describe a device-swap
  ordering (activate-new → deactivate-old → verify, vs. activate-new →
  verify → deactivate-old) for the same scenario. Sourced from an actual
  disagreement between Field Technicians and Security in the raw
  stakeholder notes, not manufactured.
- `req_35` — vague: "clear and easy-to-follow view" of provisioning
  logs, no measurable pass/fail condition.

Adversarial tags kept out of `fsm_requirements.yaml` itself and tracked
in `Day17_adversarial_flags.json` — same split Day 10 used between
requirements and human labels.

**Why this matters going forward:** the contradictory pair exposed a real
scope gap, not a manufactured one. Each requirement, read alone, is
completely unambiguous — the LLM will generate a clean, well-formed test
case for either one individually. The contradiction only exists when both
requirements are held next to each other. Day 10-style human labeling and
Day 12's judge both operate per-requirement; neither has any mechanism to
catch a cross-requirement contradiction. This category is structurally
out of reach for Phase 1's architecture as built — it's really P2
(Ambiguity Chaser) territory, where an agent reasoning over the
requirement set as a whole is the actual fix. Not treating this as a
Phase 1 bug to patch; treating it as an honest limitation to state.

**Checkpoint met:** 35 requirements exist (past the 30 floor), 5
adversarial across all three named categories (2 missing-precondition, 2
contradictory, 1 vague).

**Raw files:** `fsm_requirements_additions.yaml` (appended to
`Day8_Project_Requirements/fsm_requirements.yaml`),
`Day17_adversarial_flags.json`.

---

## Day 18 — Full 35-requirement run: generation, labeling, assertions, judge, agreement (Fri 28 Aug – Sat 29 Aug 2026)

**Goal:** run generation, assertions, and the judge across the full
requirement set (35, not the roadmap's 30 floor — Day 17 overshot it) and
recalculate agreement against human ground truth.

**Build:** `Day18_run_outputs.py` extends Day 9's generator to `req_11`–
`req_35`, carrying over the original 10 generated outputs unchanged
(regenerating them would introduce fresh non-determinism per Day 2's
finding, breaking the correspondence with `Day10_labels.json`). 32/35
valid, 3 invalid — `req_07` (known from Day 10), plus two new: `req_13`,
`req_26`, all three missing the `priority` field, all three on rows where
the model wrote a long ambiguity-hedge into `expected_result`.

Manually labeled `req_11`–`req_35` against Day 10's good/bad/borderline
criteria, merged into `Day18_labels.json`. Two real catches during
labeling:
- `req_19`/`req_21` — the model invented a "Resource Planner module"
  that doesn't exist; the actual module (established in `req_18`/`req_20`)
  is "FSM Workforce module." Resource Planner is a *role*, not a module —
  the model conflated the two.
- A `requirement_ambiguous` flag pattern initially mislabeled on 4/25
  items (`req_12`, `req_24`, `req_33`, `req_35`) — three of them the
  Day 17 adversarial cases specifically built to be ambiguous. Caught on
  review, corrected before locking in the labels.

`Day18_assertions.py` extends Day 11's four checks to all 35 (no API
call, pure computation). 134/140 passed — the 6 failures are exactly the
3 invalid rows failing `fields_present` + `non_empty`. The 583-token cap
from Day 11 still caught nothing, even with 35 rows and 5 adversarial
cases designed to provoke longer hedged responses (longest: 377 tokens).

`Day18_judge_run.py` extends Day 16's judge v2 to all 35, carrying over
the existing 10 verdicts unchanged, judging only the 25 new rows.

**Result: agreement 25/35 = 71.4%, down from v2's 80% on the original 10.**

Full disagreement log in `Day18_agreement_comparison.md`. Four grouped
findings:
- **The judge never emits `borderline`, on any of the 35 rows.** Traced
  to the rubric's arithmetic: `specificity` passes on every row that
  produced output (32/32), so the soft-fail path into `borderline` is
  nearly unreachable regardless of actual test-case quality. v2 behaves
  as a binary good/bad classifier despite the three-way rubric.
- **`verification_fidelity` structurally contradicts the generation
  prompt's own hedging instruction.** On `req_33` and `req_35` — two of
  the five adversarial cases — the model hedged honestly on details the
  requirement never specified (per the generation prompt's explicit
  rule), and the judge failed `verification_fidelity` for exactly that,
  reasoning that the expected result didn't name the exact detail. A
  fabricated-but-confident answer would likely have scored `good`. This
  is the sharpest finding of the day — the two halves of the harness
  are pulling against each other on ambiguous requirements.
- Three disagreements (`req_18`, `req_19`, `req_21`) confirm the
  single-requirement architecture limits the judge exactly as it limits
  the generator (same root cause as the Day 17 contradictory-pair
  finding) — nothing to fix in the rubric, this is P2/P3 territory.
- Two disagreements (`req_02`, `req_15`) fall in a gap the rubric has no
  criterion for at all: test-case scope/atomicity (one test case testing
  more than one behavior).

**Why this matters going forward:** before trusting v2's `bad` verdicts
on ambiguous requirements, `verification_fidelity` needs a carve-out for
cases where the requirement itself supplies no exact value to check —
otherwise the rubric actively penalizes the harness's own intended
behavior. Also worth deciding whether `specificity`'s pass bar should be
tightened, since it's not currently doing any discriminating work at all.

**Checkpoint met:** agreement recalculated on all 35 (roadmap asked for
30 — exceeded, matching Day 17's actual requirement count).

**Raw files:** `Day18_run_outputs.py`, `Day18_Full_Set/Day18_outputs.json`,
`Day18_Full_Set/Day18_labels.json`, `Day18_assertions.py`,
`Day18_Assertion_Results/Day18_assertion_results.json`,
`Day18_judge_run.py`, `Day18_Judge_Results/Day18_judge_verdicts.json`,
`Day18_agreement_comparison.md`.

---

## Day 21 — CLI Interface Design (Sun 31 Aug 2026)

Designed the harness CLI before writing any code. Worked through it as a
staged decision loop rather than settling everything at once.

**Round 1 decisions:**
- Requirements input: file path as a CLI arg, not a config file.
- Scoring mode: runtime flag `--mode assertions|judge|both`.
- Command structure: **subcommands**, not a single command with flags —
  explicitly chosen with a future GUI tool in mind.

**Why subcommands, and why the GUI reasoning mattered more than the
command-structure choice itself:** the roadmap's own build days are
distinct verbs, not one action with variations — run generation+scoring
(Day 23-24), produce a report (Day 25), diff against a saved baseline
(Day 26), CI/cost-guardrail check (Day 30-31). Cramming that into one
command means flags that only make sense for some invocations
(`--baseline` is meaningless unless diffing). The sharper point: command
structure barely matters for GUI-readiness on its own — what matters is
whether `run`/`report`/`diff` are real plain Python functions
(`run_eval()`, `generate_report()`, `diff_baseline()`) that the CLI just
calls and prints, versus logic buried inside argparse handlers. Done
right, a future GUI imports those functions directly and never touches
the CLI at all.

**Final locked CLI shape:**
```
eval-harness run <requirements.yaml> --mode assertions|judge|both --out results.json
eval-harness report results.json
eval-harness diff results.json --baseline baseline.json --threshold 0.05
```

`diff` returns a non-zero exit code on regression — this is what Week 5's
CI (Day 30) hooks into.

Documented as a `## CLI Design` block in README, replacing/extending the
old `## Running` section.

**Checkpoint met:** README describes a tool that doesn't exist yet, in
enough detail to build against.

---

## Day 22 — Dataset Loader (Mon 1 Sep 2026)

Built as a pairing day: Claude scaffolded the plumbing (file I/O, YAML
parsing, `(status, payload)` tuple pattern matching `day5_validate.py`),
Pratham filled in the judgment calls — field constraints, uniqueness
rules, and what actually counts as "malformed."

`Day22_loader.py` — YAML → typed Pydantic objects (`Requirement`,
`RequirementSet`), returning `("not_found" | "invalid_yaml" |
"invalid_schema" | "valid", payload)` instead of raising, so callers can
branch on status without try/except at every call site.

**Two real design decisions made and implemented today, not just
scaffolded:**
- **Empty `text` field.** First instinct was a custom exception type for
  this case specifically. Pushed back on that — an empty string is a
  schema validation failure, same category as a missing field or wrong
  type, not a new kind of error. Fixed with `Field(min_length=1)` on
  `Requirement.text` instead, so it flows through the same
  `ValidationError` → `"invalid_schema"` path as everything else. One
  error path, not two.
- **Duplicate requirement IDs.** Pydantic field constraints only
  validate one field at a time — they can't compare across list items.
  Needed a model-level validator instead: `check_unique_ids` on
  `RequirementSet` (`@model_validator(mode="after")`), raising
  `ValueError` on any duplicate `id`, still caught by the same
  `except ValidationError` block.

**Two ideas raised and deliberately deferred to `BACKLOG.md`, not
built today:**
- Requirement-to-source-doc traceability (does a requirement actually
  derive from an HLD/spec doc?) — flagged as a semantic-similarity
  problem needing embeddings or an LLM call, and suspiciously close to
  P2 (Ambiguity Chaser) scope three weeks early.
- Typo/grammar validation via a cheaper model — same verdict, overlaps
  with the existing pre-generation quality-gate backlog item from
  Days 17-19.

**Fixture set:** started as the natural 4 (one per status branch —
missing file, broken YAML, missing `requirements:` key, missing `text`
field), expanded to 6 after deciding to also prove the two new checks
directly: empty `text: ""`, and duplicate `id`s across two entries.
All 6 live in `Day22_fixtures/`.

**Checkpoint met:** broken YAML gives a readable error, not a stack
trace — confirmed across all 6 fixture cases, each landing on a
distinct, readable status.

**Raw files:** `Day22_loader.py`, `Day22_fixtures/` (6 files).

---

## Day 23 — Runner with Retry/Backoff (Tue 1 Sep 2026)

`Day23_runner.py` — prompts against every case in a requirement set via
Day 22's typed loader, with retry + exponential backoff (2s/4s/8s, 3
retries) wrapping the API call specifically. Schema validation
(`Day5_validate`) is deliberately NOT inside the retry — a malformed
JSON response is a prompt/schema mismatch, not a transient failure, and
retrying it just burns calls without fixing anything.

Uses `LLMClient` (Day 3) instead of Day 9/18's bare `call_OpenAI_json_mode`
call, so latency and per-call cost are captured now rather than bolted
on later for Day 25's Reporter.

**Silent-default bug caught before it shipped:** first draft called
`client.call_openai(prompt)` with no explicit temperature, which meant
it silently inherited `LLMClient`'s default of `temperature=1.0` — while
every prior run (Day 9, Day 18) used `temperature=0` via
`call_OpenAI_json_mode`'s own default. Would have made Day 23's results
non-comparable to the existing baseline for reasons that wouldn't show
up anywhere except a subtly different pass rate. Fixed two ways:
`Day23_runner.py` now passes `temperature=0.0` explicitly on every call,
and `LLMClient`'s own defaults were changed from `1.0` to `0.0` in
`Day3_llm_client.py`, since an eval-focused client defaulting to the
*less* deterministic temperature was a landmine for any future caller,
not just this one.

**A case that exhausts retries does not stop the run** — it's recorded
with `status="api_error"` and the loop continues. Verified this for
real, not just by reading the code: added a `DEEPSEEK_OPENAI_BASE_URL`
env override to `Day1_first_call.py` (defaults preserve normal behavior
for every existing script), then temporarily pointed it at an
unreachable host and ran one real requirement through it via a
standalone, reusable smoke test (`Day23_retry_smoketest.py`). Got a
genuine `openai.APIConnectionError`, 3 retries with correct 2s/4s/8s
backoff, final record `status=api_error, attempts=4`, and `LLMClient`'s
cost/token totals stayed at zero for the failed case — confirmed the
running-total update in `_wrap` only fires after a successful return,
so a fully-failed case can't corrupt the cost tracking.

Full 35-case run against `fsm_requirements.yaml` completed clean: 35/35
`valid`, 0 retries needed, $0.0049 total cost. `priority` still defaults
to `"high"` on all but 2 of 35 rows (`req_18`, `req_20` → `"medium"`) —
same finding as Day 9, still unresolved, still on the backlog for the
planned grounding-criteria experiment. Every response also included
ambiguity-hedging language in `expected_result`, consistent with the
generation prompt's hedging instruction — the same behavior that
clashed with `verification_fidelity` in the Day 18 judge run.

**Checkpoint met:** a 35-case run completes even when some calls fail —
confirmed against a real broken endpoint, not assumed from code review.

**Raw files:** `Day23_runner.py`, `Day23_retry_smoketest.py`,
`Day23_Runner_Results/Day23_run_results.json`. `Day1_first_call.py`
(base URL override) and `Day3_llm_client.py` (temperature default fix)
both modified — see individual commits for rationale.

---

## Day 24 — Scorer (Thu 3 Sep 2026)

Consolidated every scattered Pydantic model (`Requirement`/`RequirementSet`
from Day 22, `TestCase` from Day 7, `JudgeVerdict` from Day 12, `CaseResult`
from Day 23 — promoted from a plain `@dataclass` to a `BaseModel`, the
`metered` field's `repr=False` behavior verified unchanged) into a new
`schemas.py`. Pure extraction, re-verified against all four consuming
files: Day 22's fixture suite still returns identical statuses, Day 23's
runner still saves and loads the same shape.

`Day24_scorer.py` — assertion-scoring and judge-scoring behind one
interface, dispatched by `score_case(row, mode)` where `mode` is
`"assertions" | "judge" | "both"`. Two real mismatches surfaced against
actual Day 23 output rather than the shape originally assumed, both
caught and fixed before writing the scorer, not discovered after:
- **Row-key mismatch.** Day 11's four check functions read
  `row["validation_verdict"]` (Day 9's key); Day 23's rows use
  `row["status"]` for the same concept. Fixed with a row adapter inside
  `Day24_scorer.py` (`{**row, "validation_verdict": row["status"]}`)
  rather than touching Day 11's checks.
- **`JudgeScore` field mismatch.** The originally specced `JudgeScore`
  had 3 pass/fail criteria, matching Day 12's `JudgeVerdict` (v1) — but
  the default judge prompt is `judge_v2.txt` (Day 15/16), whose rubric
  asks for 5. Validating a v2 response against the 3-field model would
  have silently dropped `verification_fidelity` and `pass_fail_clarity`
  from every score with no error raised — exactly the "silent wrong
  answer, but for the grader" failure mode Cynthia Omovoiye flagged (see
  below). `JudgeScore` expanded to all 5 fields instead.

Judge-scoring reuses Day 12's pattern via a newly extracted
`judge_single_case()` (prompt format + call + validate, parameterized by
verdict model) instead of duplicating it — `run_all()` in
`Day12_LLM_Judge.py` now calls this too, its own behavior unchanged.

**`ScoreIntegrityError`** — the harness now asserts on its own grader
output, not just the model's. After scoring, `assertion_result`/
`judge_result` are checked for presence, correct key sets, and non-blank
reasoning before a `ScoreResult` is ever returned; any failure raises and
halts `score_all()` rather than degrading to a per-row status the way
Day 23 handles `api_error` — an untrustworthy score is a different
severity than an API hiccup. **This closes the "grader-output integrity"
backlog item** raised from Cynthia Omovoiye's LinkedIn feedback
(1 Sep 2026) — see BACKLOG.md.

`api_error` rows (no `parsed_output`, never reached the model) score as
an automatic fail on both assertions and judge, skipping the judge API
call entirely — the conservative option, so a row that was never a
scoring candidate doesn't trip the integrity check or burn a call.

Verified all three modes end-to-end against the real 35-row
`Day23_run_results.json`: 0 integrity errors, assertions matched the
known invalid row (`req_13`), judge mode validated cleanly against the
expanded 5-field schema.

**Borderline-path investigation.** Built
`Day24_Borderline_Smoketest/borderline_requirements.yaml` — 5
hand-crafted requirements aimed at each of judge_v2's three verdict
buckets, to check whether Day 18's "borderline is structurally
unreachable" finding holds up against deliberately-targeted input, not
just the real 35-item corpus. Two attempts (`req_b02`, `req_b03`) paired
a concrete, checkable anchor (an SLA threshold, a cancellation-fee
window) with a subjective qualifier that has no natural default value; a
third (`req_b05`) paired a hard state transition with a sufficiency
condition that has no canonical placeholder value at all. **None landed
on `borderline` across two full runs (7 judge calls).** `req_b03` even
flipped from `good` to `bad` between runs at temperature=0 — real judge
variance — landing on the opposite pole rather than the middle. Sharper
conclusion than Day 18's: this isn't just the real dataset never
sampling a borderline case, the judge appears to behave as a near-binary
classifier regardless of how deliberately the input is engineered.

**Incidental finding, not investigated further:** the first borderline
smoketest run hung indefinitely on one API call — near-zero CPU, no
`[retry]` message from Day 23's backoff logic, meaning the underlying
HTTP client's own timeout hadn't fired at all. Killed and retried; the
second attempt succeeded immediately. Worth revisiting if hangs recur —
the OpenAI/Anthropic SDK's default request timeout may be long enough
that a genuinely dead connection looks indistinguishable from a slow one
for several minutes.

**Follow-up: model-variant experiment reverses the conclusion above.**
The two smoketest runs both used `deepseek-v4-flash` with thinking
disabled — the harness's default — for both generation and judging.
Re-ran the same 5 requirements through 3 other whole-pipeline configs
(same model/thinking setting used for *both* generation and judging per
config, so a shift can't be attributed to one side alone from this data):
`flash+thinking`, `deepseek-v4-pro`, `deepseek-v4-pro+thinking`.
**`borderline` was reached once, under `pro+thinking`, on `req_b04`** —
the requirement deliberately drafted as unambiguously vague specifically
to force `bad`. Reasoning: "the test case covers the high-level
requirement and has a clear expected outcome, but its preconditions and
steps contain vague placeholders like 'involved parties' and
'appropriate notification,' making execution insufficiently concrete" —
exactly the specificity soft-fail the rubric describes, hard criteria
intact. Notably it didn't come from either purpose-built borderline
candidate (`req_b02`/`req_b03` — both still `good` under `pro+thinking`);
it came from a stronger, more deliberate model catching real vagueness
in a case the flash judge had been content to call outright `bad` (under
plain `pro`) or `good` (under `flash+thinking`).

**Revised conclusion:** `borderline` is not structurally unreachable —
`deepseek-v4-flash` without thinking just isn't discriminating enough to
land there. It behaves close to a binary classifier: either credits a
test case as fully specific, or rejects it outright, with nothing
in between. This is one sample, not a statistically meaningful
comparison — see the new BACKLOG.md item on a proper judge-model
comparison before changing anything in the default pipeline.

`flash+thinking` also surfaced two new failure modes in the same run,
neither investigated further: `req_b01`'s generation call returned
non-JSON output entirely (`status=invalid_json` — the first time this
status has ever actually occurred in this codebase in 24 days of runs,
and what surfaced the `check_valid_json` crash bug below), and
`req_b02`'s judge call exhausted its full 4096-token budget on reasoning
without ever emitting an answer (`stop_reason=length`, empty content).

**Crash bug found and fixed: `Day11_assertions.check_valid_json`.** It
scans `validation_detail` for a `"json_error"`-tagged tuple to decide
whether a row's raw response was parseable JSON — but
`Day5_validate.validate_response` never actually emits that tag anywhere;
its `invalid_json` status carries a bare list of exception-message
strings, not `(kind, msg)` tuples. The old logic happened to return the
right answer on every row seen before today, purely by coincidence (the
tag it searched for never occurs, so the scan never matched, so it always
fell through to `True`) — it had simply never been exercised on a real
`invalid_json` row until `req_b01` produced one just now, at which point
`for kind, _ in detail` crashed trying to unpack a bare string. Fixed to
check `validation_verdict != "invalid_json"` directly. Re-ran Day 11's
original 10-row/40-check baseline afterward — still 38/40, unchanged.

**Checkpoint met:** assertions-only, judge-only, and both run via a
single `--mode` flag, confirmed against real data in all three
configurations.

**Raw files:** `schemas.py`, `Day24_scorer.py`,
`Day24_Borderline_Smoketest/borderline_requirements.yaml`,
`Day24_borderline_smoketest.py`, `Day24_model_variant_experiment.py`.
Also modified: `Day22_loader.py`, `Day7_zeroshot_testcase.py`,
`Day12_LLM_Judge.py`, `Day23_runner.py` (schema imports +
`serialize_case()` extraction), `Day11_assertions.py` (`check_valid_json`
fix), `Day1_first_call.py`/`Day4_json_mode.py` (`model`/
`thinking_enabled`/`max_tokens` made overridable, defaults unchanged).

---

## Day 25 — Reporter (Fri 4 Sep 2026)

`Day25_reporter.py` — joins Day 23's run results with Day 24's score
results on case_id, computes pass rates/cost/latency, and lists every
failure with its reason, via a single flat-argparse command. Designed
end-to-end through six rounds of back-and-forth before any code was
written — the resulting decisions all visibly mattered once real data
ran through them, not just in the abstract.

**Join integrity, mirroring Day 24's `ScoreIntegrityError` pattern.**
Before any metric is computed, the case_id sets from both files are
checked for exact equality. A mismatch — either direction — raises
`ReportIntegrityError` naming exactly which IDs are missing from which
side, and no partial report is ever generated. Considered letting a
partial report through with a loud warning instead; rejected because the
reporter never makes API calls itself, so there's no cost tradeoff to
weigh — the only real question was "see partial data now" vs "forced to
fix the gap first," and hard-stop keeps that decision consistent with
Day 24's own severity model (an untrustworthy result halts, it doesn't
degrade).

**Assertion pass rate and judge pass rate are reported separately, never
combined.** A case can be well-formed but semantically weak, or vice
versa, and those are different problems needing different fixes — a
combined number would hide which one is happening. Judge pass rate is
strict: only `verdict == "good"` counts as a pass, `borderline` counts as
a fail alongside `bad`. Deliberate, given today's own finding (see
below) that `borderline` tends to mean "real vagueness a stronger judge
caught," not a safe middle ground.

Any metric whose mode wasn't run across the joined cases (e.g. judge pass
rate when scoring was `assertions`-only) shows the literal string `"not
run"`, never a number or blank — checked from the data itself (whether
any joined row actually carries a result) rather than trusted from a
single mode label, since Day 24's `mode` is technically per-row.

**Cost and latency both split two ways, deliberately kept from
collapsing into one number** — same reasoning as the pass-rate split.
Confirmed on real data that the two cost splits diverge in exactly the
way that matters: `req_13` (status `invalid`) is the sole assertion
failure, so cost-by-assertion-outcome isolates just its $0.0002. But
cost-by-judge-outcome shows $0.0003 failed, because `req_33` passed
assertions cleanly but failed judge — money spent on an output that
*looks* fine mechanically but isn't semantically. A combined split would
have hidden that `req_33` costs anything at all. Latency is reported
both across all joined cases and across `status == "valid"` only, since
retries on failed calls inflate wall-clock time in a way that would
misrepresent "how long does a normal call take."

**Failure lists ("every failure with its reason") kept separate per
Day 25's spec — assertion failures (case_id + which of the 4 named checks
failed) and judge failures (case_id + verdict + reasoning) — plus a
"Failed BOTH" callout: case_ids present in both lists, surfaced without
requiring manual cross-referencing.** This is the same instinct behind
the Day 14 `req_01` finding made structural: the interesting cases are
where multiple signals disagree or agree on the same thing, and that
shouldn't require inspection to notice. Confirmed against real data:
`req_13` correctly appears in all three sections (it fails both checks);
`req_33` correctly appears only in judge failures, and correctly does
*not* appear in "Failed BOTH."

**Smoke-tested the `api_error` path directly, not deferred.** A synthetic
`api_error` row was appended to scratch copies of both input files (real
files untouched, scratch files removed after) to verify the one status
value with zero real occurrences in the current 35-case dataset. Behaved
correctly: $0 cost attributed rather than silently dropped from the total,
excluded from both latency means (not defaulted to 0, which would have
understated them), and surfaced in both failure sections plus "Failed
BOTH."

**Real numbers on the actual 35-case run:** assertion pass rate 97.1%
(34/35), judge pass rate 94.3% strict-good (33/35), total cost $0.0050,
mean latency 2989.3ms all cases / 2985.2ms valid-only — close together
because the one non-valid row (`req_13`, `invalid`) still made a real API
call and carries real latency, unlike a true `api_error` row would.

**Day 24 addendum:** `--save` flag added to `Day24_scorer.py`
(`argparse.BooleanOptionalAction`, default on) persisting `score_all()`'s
output to `Day24_Scorer_Results/Day24_score_results.json`, following
Day 23's `save_results` envelope shape (`generated_at`, source file, mode,
count, results). No change to `score_all()`'s scoring logic itself.

**Checkpoint met:** one command reads both files and prints a readable
report — pass rate, total cost, mean latency, every failure with its
reason — hard-stopping cleanly on a verified join mismatch rather than
degrading to a partial view.

**Raw files:** `Day25_reporter.py`, `Day24_Scorer_Results/` (new).
Modified: `Day24_scorer.py` (`--save` flag), `schemas.py` (`PassRates`,
`CostReport`, `LatencyReport`, `AssertionFailure`, `JudgeFailure`,
`FailureReport`, `Report`).

## Day 26 — Regression baseline/diffing (Sat 5 Sep 2026)

`Day26_baseline.py` — `save` generates a Day 25 `Report` from a pair of
run/score result files and persists it as `baseline.json`; `diff`
generates a fresh `Report` and compares its `assertion_pass_rate` /
`judge_pass_rate` against the saved baseline, per Day 2's founding
constraint that outputs are non-deterministic and diffing therefore can't
be exact-match.

**Threshold-based, not exact-match.** A pass rate has to drop by more
than `REGRESSION_THRESHOLD` (0.05, i.e. 5 percentage points — roughly
"more than one case flips out of 35") to be flagged `REGRESSION`;
anything smaller is `OK`. This threshold is a judgment call, not a value
derived from measured pass-rate variance — Day 2's finding was about raw
output uniqueness, not how much a pass rate itself swings run-to-run
under an unchanged prompt. Revisit once a few real baseline/diff cycles
show what that noise actually looks like. Cost and latency are recorded
in `baseline.json` for the historical record but aren't diffed — that's
Day 30/31's guardrail, not this one.

**A "not run" pass rate on either side is `MODE_MISMATCH`, not silently
skipped and not scored as a regression** — comparing a number against the
string `"not run"` isn't a real threshold comparison, and treating it as
either an automatic pass or fail would be exactly the silent-wrong-answer
grader failure mode the Day 24 integrity check exists to catch.

**Smoke-tested two ways before touching real data.** (1) `save` then
`diff` against the same Day 23/24 files → both metrics `OK`, delta 0%. (2)
A scratch copy of Day 24's score results with 4 judge verdicts flipped
`good` → `bad` → `judge_pass_rate` correctly flagged `REGRESSION`
(94.3% → 82.9%), `assertion_pass_rate` (untouched) correctly stayed `OK`,
exit code 1. Real `baseline.json` was saved from the actual 35-case Day
23/24 output (97.1% assertion, 94.3% judge — same numbers as Day 25's
report), not from either smoke test.

**Added minimal CLI overrides to `Day23_runner.py` and `Day24_scorer.py`**
(`--prompt-file`/`--output-file` on the runner, `--output-file` on the
scorer) — both hardcoded their output paths, which would have made any
sabotage run silently overwrite the real Day 23/24 result files backing
today's baseline. Purely additive: every new flag defaults to the
existing hardcoded constant, so default invocation behavior is unchanged.

**First real sabotage attempt did NOT trip a regression — an honest
negative result, not a bug in the detector.** Pratham's sabotaged copy
(`Day26_Regression_Baseline_N_Diffing/broken_prompt_testcase_v1.txt`)
dropped three things from `prompt_testcase_v1.txt`: "output ONLY the JSON
object, no prose/fences," the ambiguity-handling instruction, and the
don't-fabricate-specific-data instruction. Result on the real 35-case
set: all 35 rows `status=valid`, all 35 judge verdicts `good` —
`assertion_pass_rate` 97.1% → 100%, `judge_pass_rate` 94.3% → 100%, both
`OK`, no regression flagged. Root-caused: `Day1_first_call.py`'s
`callOpenAISchemaAPI` (what the runner ultimately calls) is a plain chat
completion with no `response_format`/JSON-mode enforcement — so removing
the "output only JSON" line had no lever to pull, the model already
produces clean JSON on this dataset without being told to. Why the
ambiguity/fabrication instructions removal didn't move the judge either
is still open — could be genuinely non-load-bearing for these 35
requirements, or could be single-run noise (only run once, per Day 2).
DONE WHEN not yet met on this attempt — next attempt needs a more
structurally damaging cut (e.g. the field list/schema description itself)
to actually give the detector something to catch, and arguably a second
run of the same sabotage before concluding "no effect" either way.

**Second sabotage attempt: DONE WHEN met.** Stripped the entire JSON
schema/field list and the "as JSON" framing from the same scratch copy —
down to "write a test case for it" with no structure specified at all.
Result: all 35 rows came back `status=invalid_json` (the model wrote
free-text test cases, not JSON), `assertions_passed=False` and
`judge_verdict=bad` across the board. `Day26_baseline.py diff` correctly
flagged both metrics `REGRESSION` (`assertion_pass_rate` 97.1% → 0.0%,
`judge_pass_rate` 94.3% → 0.0%), exit code 1. Confirms the detector fires
on a real, structurally-broken prompt — the first attempt's null result
was a genuine finding about this specific weakening (see above), not a
gap in the detector.

**Three more sabotage variants, each targeting a different check, to stress
the detector across the harness's actual failure surface rather than just
one blunt break:**

- **Schema mismatch** (`broken_prompt_schema_mismatch.txt`) — kept the
  JSON framing but renamed `test_steps` → `steps` and changed `priority`
  to an integer 1-5 instead of the `Literal["low","medium","high"]` the
  real `TestCase` schema expects. All 35 rows came back `status=invalid`
  (JSON parsed fine, schema didn't match) — a cleanly different signature
  from the earlier full-schema-removal sabotage's `invalid_json`, and one
  that specifically exercises `check_fields_present` rather than
  `check_valid_json`. `diff`: both pass rates `REGRESSION`, 97.1%→0%,
  94.3%→0%.
- **Token-cap blowout** (`broken_prompt_token_blowout.txt`) — kept the
  real schema, instructed maximal verbosity on every field ("write as much
  detail as you possibly can... longer is always better"). Intended to
  trip `check_under_token_cap` (cap 583) in isolation while everything
  else stayed valid. Didn't land as designed: all 35 rows came back
  `invalid_json` instead — output_tokens averaged exactly 1024
  (`MAX_TOKENS` in `Day1_first_call.py`), meaning every response got
  hard-truncated mid-JSON before it could close, never reaching a
  "valid-but-over-cap" state. **Real finding, not noise:** with
  `TOKEN_CAP=583` sitting well under `MAX_TOKENS=1024`, a verbosity
  sabotage severe enough to threaten the cap is also severe enough to hit
  the truncation ceiling first — there's a narrow, hard-to-hit band where
  output would be valid JSON *and* over 583 tokens. This may explain part
  of why Day 11 never saw the cap catch anything organically. Flagging as
  a BACKLOG candidate: isolating `under_token_cap` cleanly would need a
  request that's verbose in prose but still schema-shaped, not a blanket
  "write more" instruction. `diff`: both pass rates `REGRESSION` (same
  97.1%→0%, 94.3%→0%) — for the wrong reason relative to what was being
  tested, worth remembering if this file gets reused later.
- **Judge-only vagueness** (`broken_prompt_vague_judge.txt`) — kept the
  real schema exactly, instructed generic/boilerplate content per field
  ("never anything specific to the requirement"). This is the one that
  landed as designed: all 35 rows `status=valid`, `assertions_passed=True`
  across the board (`assertion_pass_rate` 97.1%→**100%**, `OK`) while
  judge verdicts were `bad` for 34/35 and, notably, `borderline` for
  `req_34` — `judge_pass_rate` 94.3%→**0%**, `REGRESSION`. This is the
  cleanest proof yet that the two pass rates genuinely move independently
  (Day 25's whole reason for reporting them separately), and it's a
  second real occurrence of `borderline` under the *default* judge model
  (flash, no thinking) — worth setting alongside the Day 24 model-variant
  finding that `borderline` was reached only once before, under
  `pro+thinking`. `req_34`'s reasoning: "lacks concrete steps and a clear
  pass/fail condition" (`specificity: fail`, `pass_fail_clarity: fail`,
  everything else `pass`) — a genuinely borderline case, not a
  fluke label.

**Raw files:** `Day26_baseline.py`, `baseline.json`,
`Day26_Regression_Baseline_N_Diffing/` (5 sabotaged prompt variants +
their run/score result files). Modified: `Day23_runner.py`,
`Day24_scorer.py` (additive `--output-file` overrides).