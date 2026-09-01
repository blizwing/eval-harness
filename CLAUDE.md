# CLAUDE.md

Project context for Claude Code sessions in this repo.

## What this is
An LLM evaluation harness for scoring LLM-generated test cases against a 
labeled dataset, using deterministic assertions and an LLM-as-judge. Phase 1 
of a three-project, six-month plan (see README.md).

## Where things live
- `NOTES.md` — daily build log, one dated entry per roadmap day.
- `BACKLOG.md` — deferred ideas that were deliberately not built yet, each 
  with a stated revisit trigger. Check this before proposing new components 
  or features, so we don't rebuild something already considered and parked.
- Per-day data artifacts live in `DayN_Description/` subfolders; code files 
  are flat at repo root.

## Known gap: grader-output integrity (flagged 1 Sep 2026)
Before Day 24 (Scorer) / Day 25 (Reporter): add an assertion that every graded row has a
non-null, valid-range score — not just assertions on the model's output. Source: external
LinkedIn feedback, see BACKLOG.md for full context. Do not let this get silently dropped.
