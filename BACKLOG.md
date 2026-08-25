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
