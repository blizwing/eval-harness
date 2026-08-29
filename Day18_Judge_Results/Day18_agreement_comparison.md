# Day 18 — Judge v2 vs. Human Comparison (35 requirements)

Source files:
- Human ground truth: `Day18_Full_Set/Day18_labels.json` (req_01-req_10 carried over from `Day10_Ground_Truth/Day10_labels.json`)
- Judge v2 verdicts: `Day18_Judge_Results/Day18_judge_verdicts.json` (req_01-req_10 carried over from `Day16_Judge_V2_Results/Day16_judge_v2_verdicts.json`)
- Judge v2 rubric: `Day15_Judge_Rubric_V2/judge_v2.txt`

---

## Confusion Matrix

Rows = human label, columns = judge v2 verdict.

|                   | judge: good | judge: bad | judge: borderline |
|-------------------|:-----------:|:----------:|:------------------:|
| human: good       |     22      |     2      |         0          |
| human: bad        |      2      |     3      |         0          |
| human: borderline |      6      |     0      |         0          |

**Agreement: 25/35 = 71.4%** (v2 on 10 was 80% — see `Day16_agreement_comparison.md`)

---

## Finding 0 — the judge never once verdicts "borderline"

Across all 35 rows, `verdict: "borderline"` appears **zero times**. Every one of the 8 human `borderline` labels landed on `good`. This isn't a sampling gap — it's structural, and the rubric's own arithmetic explains it:

Per `judge_v2.txt`, `borderline` requires the three hard criteria (`field_completeness`, `requirement_coverage`, `verification_fidelity`) to **all pass**, while at least one soft criterion (`specificity`, `pass_fail_clarity`) **fails**. Looking at the actual per-criterion data across all 35 rows:

- `specificity` is `pass` on every single row that produced any output at all (32/32) — it only ever shows `fail` on the 3 structurally-invalid rows (`req_07`, `req_13`, `req_26`), where it fails automatically alongside everything else because no test case was generated.
- `pass_fail_clarity` fails on exactly 1 row (`req_35`) out of 35 — and that row *also* fails `verification_fidelity`, so it lands on `bad`, not `borderline`.

So the two soft criteria that are supposed to carve out the `borderline` middle ground essentially never fail on their own for genuine quality reasons. The judge's specificity bar is set so low that almost anything with numbered steps clears it. In practice, v2 is a binary good/bad classifier wearing a three-way rubric. Worth deciding whether to loosen `specificity`'s pass bar or redesign what pushes a verdict into `borderline` before trusting this rubric's three-way output anywhere.

---

## Disagreement Log

10 of 35 rows disagree. Grouped by root cause rather than listed id-by-id, since several share the same underlying gap.

### Group A — judge rewards "sounds specific" without checking if the specific detail is grounded in the requirement

**req_01** (human: bad, judge: good)
- Human: the test case never verifies the *format* of the duration field — it confirms duration is present, not that it's captured correctly.
- Judge: `verification_fidelity: pass` — reasoning says it "verifies the specific details mentioned in the requirement."
- Same disagreement as v1 (Day 14) and v2 on the original 10 (Day 16) — unchanged, already documented. The judge credits *presence* of the duration detail, not *correctness of format*, which is the exact distinction the human label turns on.

**req_11** (human: borderline, judge: good)
- Human: the model invented the status label `'Pending Approval'` — nowhere in the requirement.
- Judge: `verification_fidelity: pass`, reasoning explicitly praises that the test "checks the specific pending approval state."
- This is the sharper version of req_01's problem: the judge isn't just under-verifying a real detail, it's rewarding a **fabricated** one as if it were grounded. Nothing in the rubric checks whether a "specific" detail traces back to the requirement text versus being invented by the generator.

**req_29** (human: borderline, judge: good)
- Human: the model assumed a "Technician application" / interface that the requirement never names.
- Judge: all pass, reasoning credits "concrete steps and preconditions" without noting the interface was assumed, not stated.
- Same pattern as req_11 — concreteness rewarded regardless of whether it's grounded.

**Takeaway:** `specificity` and `verification_fidelity` currently measure "does this read as concrete" rather than "is this concreteness traceable to the requirement." Three separate rows fail the same way. Worth adding an explicit criterion (or rewording `verification_fidelity`) that asks whether cited specifics actually appear in the requirement text.

### Group B — rubric has no criterion for test-case scope/atomicity

**req_02** (human: borderline, judge: good)
- Human: the requirement bundles two distinct behaviors into one sentence; the test steps followed that conflation.
- Judge: all pass. Same flip already logged in `Day16_agreement_comparison.md` — v1 correctly caught this via `specificity: fail`, v2 doesn't.

**req_15** (human: borderline, judge: good)
- Human: the test walks through an unnecessary happy-path (approve) before the actual behavior under test (reject-without-reason). Two behaviors in one test case.
- Judge: all pass, reasoning focuses only on whether the mandatory-reason behavior is covered, not on whether the test case is doing more than it should.

**Takeaway:** none of the five rubric criteria evaluate test-case scope or atomicity — "does this test one behavior or several." Both disagreements in this group are invisible to the current rubric by design, not by judge error.

### Group C — single-requirement architecture can't catch cross-requirement inconsistency, on either side of the pipeline

**req_18** (human: bad, judge: good)
- Human: priority should be `high` given Skills' criticality to scheduling — but that criticality is only established in `req_02`/`req_03`, a different requirement the judge (and generator) never saw.
- Judge: all pass — has no way to evaluate priority correctness at all; `field_completeness` only checks the field exists, not whether the value is justified.

**req_19** / **req_21** (human: borderline, judge: good, same root cause both rows)
- Human: the generated test case references a nonexistent "Resource Planner module" — the actual module is "FSM Workforce module," established in `req_18`/`req_20`, requirements the judge never sees.
- Judge: all pass in both cases — nothing in the rubric checks entity names against anything outside the single requirement handed to it.

**Takeaway:** this is the same limitation already flagged for the generator on the `req_25`/`req_34` contradictory pair, now showing up identically on the judge side. Given Phase 1's per-requirement architecture, no amount of rubric tuning fixes this — it needs shared context across requirements, which is P2/P3 territory, not a Day 18 fix.

### Group D — `verification_fidelity` structurally punishes honest hedging on ambiguous requirements

**req_33** (human: good, judge: bad)
- Requirement never names which security headers are required.
- Generated test case, correctly per the generation prompt's own rule: hedges — "presence of any security headers is expected... the exact set is not defined."
- Judge: `verification_fidelity: fail`, reasoning: *"only that 'any' security headers are present, which fails to verify the specific detail named in the requirement."*
- The judge is penalizing the test case for not inventing header names the requirement never gave it — exactly the behavior the generation prompt explicitly tells the model to avoid.

**req_35** (human: good, judge: bad)
- Requirement's only criterion is subjective and unmeasurable ("clear and easy-to-follow").
- Generated test case hedges honestly, same as req_33.
- Judge: `verification_fidelity: fail` **and** `pass_fail_clarity: fail`, reasoning: *"does not specify exact fields or ordering... failing to verify the specific details required."*
- Same conflict as req_33, on the requirement Day 17 built specifically to have no exact answer.

**Why req_24 (also adversarial, also missing a precondition) didn't fail the same way:** req_24's ambiguity ("certain task types") sits on *when* the test applies, not *what* it checks — the actual verifiable claim (the Provisioning page shows activate/deactivate/reprovision options and a serial input box) is fully specified regardless. req_33 and req_35's ambiguity sits directly on *what to verify* — there is no fully-specified claim underneath the hedge. `verification_fidelity` can't tell these apart: it fails any test case that doesn't name an exact value, whether or not the requirement ever supplied one.

**Takeaway — this is the sharpest finding in this batch.** The generation prompt (Day 5's rule) and the judge rubric (v2's `verification_fidelity`) have **contradictory incentives** on genuinely ambiguous requirements: the generator is told to hedge honestly rather than invent certainty, and the judge then fails exactly that hedge for not being certain. A generator that instead fabricated a plausible-sounding header list would likely have *passed* `verification_fidelity` and scored `good` — rewarding the behavior the harness is explicitly trying to discourage. Worth fixing before Week 3's rubric work goes further: `verification_fidelity` needs a carve-out for cases where the requirement itself supplies no exact value to check.

---

## Summary

- **v2 agreement, 10 rows (Day 16):** 8/10 = 80%.
- **v2 agreement, 35 rows (Day 18):** 25/35 = 71.4%. Same two original disagreements (`req_01`, `req_02`) persist unchanged; 8 new disagreements surfaced by the expanded and adversarial set.
- **The `borderline` verdict is architecturally unreachable in practice** — `specificity` passes on literally every valid row, `pass_fail_clarity` fails on exactly one, and that one already has a hard-criterion failure alongside it. v2 behaves as a binary classifier despite the three-way rubric.
- **Four disagreements (Group A) trace to the same root cause:** the judge rewards test cases that *sound* specific without checking whether the specifics are grounded in the requirement — it can't distinguish honest concreteness from fabrication.
- **Two disagreements (Group B)** fall in a blind spot the rubric was never designed to cover: test-case scope/atomicity.
- **Three disagreements (Group C)** are a known, already-documented architectural limit (single-requirement context) now confirmed to affect the judge exactly as it affects the generator.
- **Two disagreements (Group D) are the most actionable finding here:** the rubric actively contradicts the generation prompt's own instructions on ambiguous requirements, and does so on precisely the two adversarial cases (of five) that were built to test honest hedging under missing/vague information.