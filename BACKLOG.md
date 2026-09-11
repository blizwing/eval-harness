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

## Judge model upgrade: deepseek-v4-pro + thinking (raised 3 Sep 2026, Day 24)

Idea: switch the default judge model (currently `deepseek-v4-flash`, thinking
disabled) to `deepseek-v4-pro` with thinking enabled.

Why raised: a one-off model-variant experiment (5 borderline-targeting
requirements × 3 configs, see NOTES.md Day 24) reached the judge's
`borderline` verdict once, under `pro+thinking`, on a case that both
`flash+thinking` and plain `pro` scored at an extreme (`good` and `bad`
respectively). Suggests flash-without-thinking behaves close to a binary
good/bad classifier and pro+thinking discriminates real vagueness that
flash lets through — a live counter to Day 18's "borderline is
structurally unreachable" finding, but only n=1.

Decision: deferred, not changed in P1.
- One sample is not evidence a stronger/slower/more expensive model
  should become the production default — could easily be noise from a
  single generation+judge draw, and the experiment varied generation and
  judging together, so the effect can't yet be attributed to the judge
  specifically rather than the test case it was judging.
- `pro+thinking` is markedly more expensive per call (hundreds of
  reasoning tokens vs. tens) and slower (~8-10s vs ~2-3s observed) —
  a real cost/latency tradeoff against Day 30/31's cost-guardrail goals,
  not a free upgrade.

**Revisit trigger:** before locking in Day 26's baseline, or if judge
agreement is ever re-measured (Day 14/16/18-style), re-run judge_v2
against a proper sample (the full 35-item set, or a larger dedicated
batch) with `pro+thinking` as the judge only (generation held fixed on
the current default) to isolate whether the effect is really the judge,
and check whether the agreement/verdict-distribution shift is large
enough to justify the added cost and latency.

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

## Hard network-block guarantee for the Day 32 test suite (raised 11 Sep 2026, Day 32)

Idea: add `pytest-socket` (or equivalent) to `tests/` so any test that
skips mocking and tries a real network call fails loudly, instead of
relying on "every test happens to mock the client" holding forever.

Decision: deferred, not built in Day 32.
- Day 32's suite already achieves the DONE WHEN (`pytest` passes, zero
  network calls) by mocking at the API boundary (`LLMClient.call_openai`,
  `judge_single_case`) in every test that would otherwise reach it — the
  guarantee today is "nothing currently calls out," not "nothing ever
  could."
- Adding a new test dependency plus its own config (a socket allow-list
  for legitimate local I/O like `tmp_path` fixtures) is a small design
  decision of its own, not a mechanical extension of today's plumbing.

**Revisit trigger:** if a future test change accidentally makes a real
(paid) call and it isn't caught until a cost/CI anomaly shows up, or when
Day 33's README is being written and a stronger "how do we know this
never burns tokens" claim would strengthen it.

---

## Generator-side thinking effort as a hedging fix (raised 11 Sep 2026, Day 32 follow-up)

Idea: enable thinking (some reasoning-effort level) on the *generator*
step specifically, as a fix for the hedging behavior that collapsed
judge_pass_rate after the DeepSeek model swap — distinct from both
"re-baseline" (done) and "tighten the prompt" (not started).

Decision: deferred — inconclusive on the data gathered so far, not
adopted, not investigated further today.
- `Day32_thinking_effort_experiment.py` tested disabled/low/high/max
  thinking effort on 10 curated ambiguous requirements (5 from
  `Day24_Borderline_Smoketest`, 5 real-dataset adversarial cases from Day
  17), judge held fixed to isolate the generator's effect. See NOTES.md's
  "generator thinking-effort experiment" entry for the full account,
  including a first-round result (thinking doesn't help, `low` hurts)
  that turned out to be an artifact of an under-provisioned token budget
  causing truncation, and a corrected second round that showed the
  opposite direction (40%/50%/60%/60% good-rate across
  disabled/low/high/max) but couldn't be trusted at face value either —
  the `disabled` control itself swung 20 points between the two rounds
  with zero config change, which is larger than the effect being
  measured.
- The only credible signal from round 2 was per-requirement, not
  aggregate: 3 of 10 requirements improved consistently across all three
  thinking-enabled configs, 2 of 10 stayed bad regardless, and the rest
  moved non-monotonically (noise). That's suggestive, not sufficient.
- Cost is real regardless of outcome: reasoning tokens averaged ~750-935
  per call vs. 0 for disabled, roughly 4-5x the generation cost per call.

**Revisit trigger:** if this is worth resolving, it needs repeated runs
per config (pass-rate thresholds across multiple runs, per Day 2's
non-determinism finding and Day 26's regression-detection approach) —
not another single-run experiment at n=10. Also worth deciding then
whether to test on the full 35-case dataset rather than only the curated
ambiguous subset, since the incident's hedging was observed broadly, not
only on adversarial cases.

---
