# eval-harness

An LLM evaluation harness, built from scratch to bring QA rigor to
non-deterministic AI outputs — the first of a three-project, six-month
plan moving from AI Quality into agentic GenAI engineering.

**Status:** Week 3, Day 19 of Phase 1 (see [NOTES.md](NOTES.md) for the day-by-day build log).

**Backlog:** see [BACKLOG.md](BACKLOG.md) for deferred ideas awaiting a
revisit trigger.

**Project context for agents:** see [CLAUDE.md](CLAUDE.md).

---

## What this proves

Phase 1 (this repo) is a CLI harness that scores LLM-generated test cases
against a labeled dataset using both deterministic assertions and an
LLM-as-judge, tracks cost/latency per call, and gates CI on regressions —
without assuming "temperature 0" or exact-match diffing, since neither
holds for real LLM output.

| # | Project | Proves | Dates |
|---|---------|--------|-------|
| P1 | **Eval Harness** (this repo) | AI Quality / Evaluation | 11 Aug – 13 Sep 2026 |
| P2 | **Ambiguity Chaser** | Agentic dev + GenAI | Sep – Nov 2026 |
| P3 | **Agent Eval Layer** | QA for non-deterministic systems | Dec 2026 – Jan 2027 |

## Running

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt   # once added
# API key goes in .env (never committed) — see .gitignore
```

Day-by-day scripts (`Day1_first_call.py`, `Day2_temperature.py`,
`Day3_llm_client.py`, …) are runnable standalone and build on each other —
`Day3_llm_client.py`'s `LLMClient` wraps Day 1's call functions and is the
intended import point for later projects.

## CLI Design

Three subcommands, each a thin wrapper around a plain function
(`run_eval()`, `generate_report()`, `diff_baseline()`) — so a future GUI
can call the same functions directly, no argparse in the middle.

### `run <requirements_file>`
Generates test cases for every requirement in the file, scores them, saves results.
- `--mode assertions|judge|both` — which scorer(s) to run (default: `both`)
- `--out <path>` — where to save the results JSON (default: `results.json`)

### `report <results_file>`
Prints a human-readable summary to stdout: pass rate, total cost, mean latency,
every failure with its reason.

### `diff <results_file> --baseline <baseline_file>`
Compares a results file against a saved baseline, flags regressions.
- `--threshold <float>` — pass-rate drop that counts as a regression (default: `0.05`)
- Non-zero exit code on regression — this is what CI (Week 5) hooks into.

**Input:** requirements file path, always a CLI arg — no config file.
**Output:** `run` writes JSON to disk; `report`/`diff` print to stdout.

## Metrics

Judge v2 vs. 35 human-labeled requirements (`Day18_labels.json` vs.
`Day18_judge_verdicts.json`; full disagreement log in
`Day18_agreement_comparison.md`).

| Metric | Value | Definition here |
|---|---|---|
| Agreement | 25/35 = **71.4%** | judge verdict exactly matches human label (good/bad/borderline, 3-way) |
| Precision | 3/5 = **60.0%** | of the test cases the judge flagged `bad`, how many had a real human-flagged problem |
| Recall (strict) | 3/5 = **60.0%** | of test cases the judge should have flagged, catching only the ones humans called outright `bad` |
| Recall (inclusive) | 3/11 = **27.3%** | same, but counting `borderline` human labels as issues the judge should also have caught |

**Why two recall numbers, not one:** a false positive here is the judge
calling a genuinely fine test case `bad` (2 cases: `req_33`, `req_35` —
both honestly-hedged adversarial cases the judge penalized for not
inventing false certainty). A false negative is the judge missing a real
problem. Precision is stable at 60% either way, since it only depends on
whether the judge's own `bad` calls were justified. Recall swings from
60% to 27% depending entirely on whether `borderline` counts as "should
have been caught" — because the judge never once outputs `borderline`
across all 35 rows (see `Day18_agreement_comparison.md`, Finding 0), every
human `borderline` label is automatically a miss under the inclusive
framing. The gap between the two numbers **is** the cost of the judge's
missing middle verdict, made quantitative.

## Build log

Full rationale, findings, and data per day live in [NOTES.md](NOTES.md).
The plan this repo follows — checkpoints, learning sessions, and the
week-by-week schedule through Phase 3 — is in [ROADMAP.md](ROADMAP.md),
kept separate from NOTES.md so the plan and what actually got built don't
drift into the same file.
