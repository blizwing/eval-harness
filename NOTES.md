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