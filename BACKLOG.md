# Backlog — Deferred Ideas

Ideas raised during the build that were deliberately deferred, with the 
reasoning and the condition under which to revisit them.

---

## Pre-generation requirement quality gate (raised 25 Aug 2026, Day 15)

Idea: before requirements reach the test case generator, run a gate that checks 
whether the requirement itself has enough information to produce a clean, 
unambiguous test case (completeness/testability check).

Decision: deferred, not built in P1.
- Bad-input requirements are a test category the harness is designed to catch 
  (Day 17 adds adversarial requirements on purpose), not something to filter 
  out beforehand.
- Day 10 human labeling already functions as a lightweight gate by inspection.
- Overlaps directly with P2 (Ambiguity Chaser) scope — a LangGraph agent 
  scoring requirement testability is already planned for Sep-Nov.
- Building it now would repeat the "starting P2 before P1 is public" risk 
  called out in the roadmap's red flags.

**Revisit trigger:** after Day 17-18's 30-requirement run (5+ adversarial 
cases). If the majority of failures trace to input-incompleteness rather than 
judge/generation issues, that's data-backed evidence for pulling a lightweight 
gate forward into P1 — otherwise it stays fully in P2 scope.

---

## Grader-output integrity check (from Cynthia Omovoiye LinkedIn feedback, 1 Sep 2026)
- Source: Cynthia Omovoiye (AI Engineer, builds memory/eval systems for LLM agents) commented
  on the eval harness LinkedIn post. Her point: the "silent wrong answer" problem applies to the
  GRADER, not just the model. She saw a real case — 8 eval fields at 0/5797 populated, zero
  errors, zero warnings, dashboard reported coverage that wasn't real.
- Her question: does the harness assert on the grader's own output (every graded row has a
  real, non-null, valid score), or only on the model's output?
- Direct link to existing finding: our LLM judge's "borderline" path is structurally unreachable
  across all 35 rows (see NOTES.md Day 14-16). That's a LIVE instance of her failure mode,
  already sitting in the codebase, currently undetected.
- PLAN: add a grader-output integrity check — every graded row must have a non-null score in
  the valid enum/range; fail loud if a field comes back empty/default.
- Natural fit: Day 24 (Scorer) or Day 25 (Reporter).
- Framing: this strengthens the existing roadmap, not scope creep. Also a stronger interview
  anecdote combined with the unreachable-borderline-path finding.

**Resolved 3 Sep 2026 (Day 24):** `Day24_scorer.py` raises `ScoreIntegrityError` if a
graded row's `assertion_result`/`judge_result` comes back missing, incomplete, or with
blank reasoning — fails loud instead of returning a partial `ScoreResult`. Also ran a
follow-up smoke test targeting the borderline path directly (5 hand-crafted requirements,
2 full runs) — still unreachable even under deliberate adversarial input, sharpening the
original finding. See NOTES.md Day 24.

---

## 1 Sep 2026

- Requirement traceability check: validate that each requirement in
  fsm_requirements.yaml actually derives from a source HLD/requirements
  doc, rather than being freeform text with no ground-truth anchor. Likely
  needs embeddings or an LLM call to check semantic alignment between the
  requirement and the source doc — not a schema-loader concern, closer to
  P2 (Ambiguity Chaser) territory. Flagged 1 Sep 2026, deliberately
  deferred out of Day 22 scope.

- Typo/grammar quality check on input requirements: run a cheaper model
  over each requirement to flag typos or unclear grammar before it enters
  the pipeline. Overlaps with the existing pre-generation requirement
  quality gate backlog item from Days 17-19 — should be designed together
  with that item, not bolted onto the Day 22 loader. Flagged 1 Sep 2026.

---
