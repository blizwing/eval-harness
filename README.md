# eval-harness

An LLM evaluation harness, built from scratch to bring QA rigor to
non-deterministic AI outputs — the first of a three-project, six-month
plan moving from AI Quality into agentic GenAI engineering.

**Status:** Week 1, Day 3 of Phase 1 (see [NOTES.md](NOTES.md) for the
day-by-day build log).

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

## Build log

Full rationale, findings, and data per day live in [NOTES.md](NOTES.md).
The plan this repo follows — checkpoints, learning sessions, and the
week-by-week schedule through Phase 3 — is in [ROADMAP.md](ROADMAP.md),
kept separate from NOTES.md so the plan and what actually got built don't
drift into the same file.
