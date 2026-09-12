# eval-harness

A CLI harness that scores LLM-generated test cases against a labeled dataset,
using deterministic assertions and an LLM-as-judge, with cost/latency
tracking and a CI regression gate. Built from scratch as the first of a
three-project, six-month plan moving from AI Quality into agentic GenAI
engineering.

**Status:** Phase 1 complete (Day 33 of 34, 11 Aug to 13 Sep 2026). Full
day-by-day build log in [NOTES.md](NOTES.md). Deferred ideas and their
revisit triggers in [BACKLOG.md](BACKLOG.md). The plan this repo followed
is in [ROADMAP.md](ROADMAP.md). Project context for AI coding agents is in
[CLAUDE.md](CLAUDE.md).

## The three-project plan

| # | Project | Proves | Dates |
|---|---------|--------|-------|
| P1 | **Eval Harness** (this repo) | AI Quality / Evaluation | 11 Aug to 13 Sep 2026 |
| P2 | **Ambiguity Chaser** | Agentic dev + GenAI | Sep to Nov 2026 |
| P3 | **Agent Eval Layer** | QA for non-deterministic systems | Dec 2026 to Jan 2027 |

## The problem

An LLM that turns a plain-English requirement into a structured test case
will hand back a clean, well-typed JSON object almost every time. What it
won't do is tell you when that object is wrong. Across this build, three
separate failure modes showed up, none of which a `try/except
json.JSONDecodeError` would ever catch:

1. **Fabrication.** Asked for a field it has no way to know, the model
   invents a plausible value instead of refusing or returning null (Day 4).
2. **Judgment drift.** A `priority` field defaulted to `"high"` on
   effectively every valid response, regardless of the requirement's
   actual content (Day 7, Day 9, still open).
3. **Non-determinism.** `temperature=0` does not mean identical output run
   to run, and the degree of drift differs by API surface, not just by
   temperature (Day 2). This is the reason the whole harness is built
   around pass-rate thresholds rather than exact-match diffing.

A schema check catches malformed JSON. It does not catch a well-formed,
correctly-typed answer that is quietly wrong. That gap is what the
assertion layer and the LLM-judge layer are each built to close, from two
different angles.

## Approach

```
requirements.yaml
      |
      v
Day22_loader.py    -> typed Requirement/RequirementSet objects, or a named
      |                 failure status (not_found / invalid_yaml / invalid_schema)
      v
Day23_runner.py    -> calls the model once per requirement, retry + backoff
      |                 on transient API errors, cost-cap abort if projected
      |                 spend exceeds a cap, saves Day23_run_results.json
      v
Day24_scorer.py    -> scores each case two ways behind one --mode flag:
      |                 - assertions: valid JSON, fields present, non-empty,
      |                   under a token cap (deterministic, no API call)
      |                 - judge: an LLM graded against a named-criteria
      |                   rubric (judge_v2.txt), same model family as the
      |                   generator
      |                 raises loud on a malformed grader output itself,
      |                 not just a malformed model output
      v
Day25_reporter.py  -> joins run + score results on case_id, reports pass
      |                 rates, cost, latency and every failure with its
      |                 reason, hard-stops on a join mismatch
      v
Day26_baseline.py  -> save/diff against baseline.json, using pass-rate
                        thresholds (default 5 points) rather than
                        exact-match, since Day 2 already ruled exact-match
                        out
```

Assertions and the judge are reported separately, never combined into one
score. A test case can be structurally fine and semantically weak, or the
reverse, and collapsing those into a single number would hide which one is
happening.

## How to run

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows
pip install -r requirements.txt

# DEEPSEEK_API_KEY goes in .env, which is gitignored and never committed.
# .env
DEEPSEEK_API_KEY=your-key-here
```

Run the pipeline against the bundled 35-requirement FSM dataset
(`Day8_Project_Requirements/fsm_requirements.yaml`):

```bash
python Day23_runner.py                 # generate + save Day23_run_results.json
python Day24_scorer.py                 # score assertions + judge, save Day24_score_results.json
python Day25_reporter.py               # join both and print a readable report
python Day26_baseline.py diff          # compare against baseline.json, exit 1 on regression
```

Each script also runs standalone against its own saved output, and each
takes overrides for its input/output paths and key parameters, for example:

```bash
python Day23_runner.py --requirements-file <path> --cost-cap 0.02
python Day24_scorer.py --mode judge --judge-prompt <path>
python Day26_baseline.py save          # regenerate baseline.json from a fresh run
python Day26_baseline.py diff --threshold 0.03
```

There is no single unified `eval-harness` entry point. Day 21 designed one
on paper before any code existed; once built, four scripts each doing one
job, callable in sequence or on their own, turned out to be the simpler
real shape, and nothing since has needed a wrapper on top.

**Tests:** `pytest` runs 63 tests with the API boundary mocked
(`LLMClient.call_openai`, `judge_single_case`) end to end, including retry
and backoff, the cost-cap abort math, and the grader-integrity check. No
network access, no cost.

```bash
pytest
```

**CI:** `.github/workflows/harness.yml` runs the full pipeline against the
live API on every push (skipping doc-only changes), then runs
`Day26_baseline.py diff` as a gate. A regression fails the build. See Day
30's entry in NOTES.md for a live demonstration: a deliberately broken
prompt pushed to a throwaway branch turned the gate red with the exact
metric deltas printed, then the branch was deleted.

### Example output (`Day25_reporter.py`, current `baseline.json`)

```
Day 25 Report - 35 joined case(s)

== Pass rates ==
  Assertion pass rate: 91.4% (32/35)
  Judge pass rate (strict, 'good' only): 42.9% (15/35)

== Cost ==
  Total cost: $0.0070
  By Day 23 status: valid: $0.0063, invalid: $0.0006
  By assertion outcome: passed: $0.0063, failed: $0.0006
  By judge outcome: passed: $0.0029, failed: $0.0041

== Latency ==
  Mean latency (all joined cases): 1634.9 ms
  Mean latency (status == 'valid' only): 1637.7 ms

== Assertion failures (3) ==
  req_11: fields_present: False, non_empty: False
  req_28: fields_present: False, non_empty: False
  req_35: fields_present: False, non_empty: False

== Judge failures (20) ==
  req_01: verdict=bad - expected result admits ambiguity about duration
    format and uniqueness scope instead of verifying the specific detail.
  req_06: verdict=borderline - covers the requirement with concrete steps,
    but an ambiguous fallback undermines a clear pass/fail condition.
  ... (18 more, full list in Day24_Scorer_Results/Day24_score_results.json)

== Failed BOTH assertions and judge (3) ==
  req_11
  req_28
  req_35
```

These numbers are lower than the harness reported through Day 28
(97.1% / 94.3%) because of a third-party model swap on 10 Sep 2026,
covered under "What changed after Day 30" below.

## Metrics (Day 19, judge v2 vs. 35 human labels)

Computed once, against `Day18_labels.json` and
`Day18_judge_verdicts.json` (full disagreement log in
`Day18_agreement_comparison.md`), and kept as-is rather than
recomputed, since it documents a specific point-in-time evaluation of the
judge's reliability, not a live number.

| Metric | Value | Definition here |
|---|---|---|
| Agreement | 25/35 = **71.4%** | judge verdict exactly matches human label (good/bad/borderline, 3-way) |
| Precision | 3/5 = **60.0%** | of the cases the judge flagged `bad`, how many had a real human-flagged problem |
| Recall (strict) | 3/5 = **60.0%** | of cases the judge should have flagged, counting only ones humans called outright `bad` |
| Recall (inclusive) | 3/11 = **27.3%** | same, but also counting human `borderline` labels as issues the judge should have caught |

Two false positives drive precision down: `req_33` and `req_35`, both
adversarial cases where the model hedged honestly on details the
requirement never specified, and the judge penalized the hedge instead of
crediting the honesty. Recall swings from 60% to 27% depending entirely on
whether `borderline` counts as "should have been caught": across all 35
rows at the time of this measurement, the judge never once output
`borderline`, so every human `borderline` label was automatically a miss
under the inclusive framing. That gap is the cost of the judge's missing
middle verdict, made quantitative. (Section 19 of NOTES.md later found
`borderline` is reachable under a more discriminating judge model, and a
21 Sep re-baseline saw it land 6 times out of 35 once the generator's own
output actually got more ambiguous. See "What changed after Day 30" below.)

## What changed after Day 30

The numbers above are frozen at the point they were measured. Two things
happened afterward worth stating plainly rather than papering over:

- **10 Sep 2026:** DeepSeek repointed the `deepseek-v4-flash` alias to a
  new model (V4.1 Flash) with no code change on our side, and also moved
  pricing to a peak/off-peak split the harness hadn't modeled. The new
  model hedges far more in `expected_result`, which the judge correctly
  penalizes under its `verification_fidelity`/`pass_fail_clarity`
  criteria. `judge_pass_rate` collapsed from 94.3% to roughly 43%, and
  `baseline.json` was deliberately re-baselined to the new numbers rather
  than patched around, since there is no pinned model snapshot to fall
  back to. This lowers the bar CI enforces; it does not fix a quality
  regression. Full account in NOTES.md's "Incident" and "Incident closed"
  entries.
- **Pricing constants were also stale independent of the model swap** and
  have since been corrected to model DeepSeek's real peak/off-peak rates,
  with the tier recorded per call (`pricing_tier`) so every cost figure is
  auditable after the fact rather than trusted as a black box.

## The Day 14 finding: where the judge and the human disagreed, and why it mattered

Day 12 built a model-graded judge scoring each generated test case against
three criteria: field completeness, requirement coverage, and specificity.
Day 14 compared its 10 verdicts against Day 10's human labels on the same
10 test cases. Agreement came out to 9 out of 10, a number that on its own
would read as a strong result. The value of the exercise was in the one
disagreement, not the nine matches.

The disagreement was `req_01`, a requirement about generating a unique
token with a bounded lifetime. The generated test case included a step
that set a duration and a step that confirmed a duration was present, but
never checked that the duration was captured in the correct format or
units. Day 10's human label called this `bad`, specifically for that gap.
The judge called it `good`: field completeness passed, requirement
coverage passed, and specificity passed, because the steps were concrete
and the fields were populated. Nothing in the rubric asked whether the
expected result actually verified the exact detail the requirement named,
as opposed to a detail in the same general area.

The important distinction this forced was between two different questions
that are easy to collapse into one: was the judge's verdict correct, and
was the judge's reasoning process correct. Those are not the same
question, and here the answers pointed in opposite directions. The
verdict was wrong: the test case really was incomplete in a way that
mattered. The reasoning was not at fault: given the rubric it was handed
and the artifact it was shown, the judge scored consistently and its
stated reasons matched its stated criteria. The gap lived in what the
judge had been given to grade against, not in how it applied that
standard. A judge that reasons badly announces itself, because its logic
doesn't hold together. A judge that reasons well from an incomplete
rubric is more dangerous precisely because it doesn't announce itself:
every step of its argument checks out, and the wrong answer arrives
wearing the shape of a right one.

That distinction, not the 90% agreement figure, is what shaped Week 3.
Day 15 rewrote the rubric specifically to add a criterion asking whether
the expected result verifies the exact detail or format the requirement
names, targeted directly at the `req_01` gap. It did not close the gap on
the first attempt (Day 16 recomputed agreement at 80%, with `req_01` still
disagreeing on a subtler version of the same failure), which is its own
finding: naming the right criterion in a rubric does not guarantee the
judge applies it correctly against a specific artifact, and that has to be
checked again after every rubric change rather than assumed from the
wording alone.

## What is deliberately out of scope

- **Cross-requirement contradictions** (Day 17: two requirements that
  individually read as unambiguous but conflict with each other) are
  structurally unreachable by a per-requirement judge and generator. This
  is P2 (Ambiguity Chaser) territory, not a Phase 1 gap.
- **Pre-generation requirement quality gating** and **typo/grammar
  checking on input requirements** are parked in BACKLOG.md with revisit
  triggers, both overlapping P2 scope.
- **A judge-model upgrade** (`deepseek-v4-pro` + thinking) showed a
  promising single data point (Day 24) but was not adopted on n=1
  evidence. Also in BACKLOG.md.

## Build log

Full rationale, findings, and data for every day live in
[NOTES.md](NOTES.md). The plan this repo followed, including the Day 19
learning-session prompts and Phase 2/3 outlines, is in
[ROADMAP.md](ROADMAP.md), kept separate from NOTES.md so the plan and what
actually got built don't drift into the same file.
