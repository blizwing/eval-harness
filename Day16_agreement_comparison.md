# Day 16 — Judge v2 vs. Human Comparison

Source files:
- Human ground truth: `Day10_Ground_Truth/Day10_labels.json`
- Judge v2 verdicts: `Day16_Judge_V2_Results/Day16_judge_v2_verdicts.json`
- Judge v2 rubric: `Day15_Judge_Rubric_V2/judge_v2.txt`

---

## Confusion Matrix

Rows = human label, columns = judge v2 verdict.

|                   | judge: good | judge: bad | judge: borderline |
|-------------------|:-----------:|:----------:|:------------------:|
| human: good       |      7      |     0      |         0          |
| human: bad        |      1      |     1      |         0          |
| human: borderline |      1      |     0      |         0          |

**Agreement:** 8 / 10 = 80%

---

## Disagreement Log

One entry per req_id where human_label != judge_verdict.

### req_01
- **Human label:** bad — the expected duration format was not captured, and more importantly, not flagged.
- **Judge v2 verdict:** good — passed all five criteria, including the two added for v2: `verification_fidelity: pass`, `pass_fail_clarity: pass`.
- **Does it now agree?** No — same disagreement as v1 (Day 14). v2 was built specifically to catch this gap and didn't.
- **Why it still diverges:** The generated test case's `expected_result` says the task "contains ... the specified duration" — it mentions duration but never states a format or exact-value check on it. The judge's reasoning ("verifies the specific details mentioned in the requirement") treated "duration is present in the output" as satisfying `verification_fidelity`, rather than checking whether the *format* of that duration is verified — which is the exact distinction the human label turned on. The rubric criterion asks the right question in the abstract, but the judge's application of it here still credits presence-of-detail over correctness-of-format, so the added criterion didn't bite on this row.

### req_02
- **Human label:** borderline — the requirement bundles two distinct behaviors (skill-matched assignment and travel-to-completion within a time window) into one sentence; the generated test case's steps followed that same conflation.
- **Judge v2 verdict:** good — passed all five criteria.
- **Does it now agree?** No — this is a **new** disagreement. Under v1 (Day 12/14), the judge scored this `borderline` (failed `specificity`) and agreed with the human label, even though the reasoning paths differed. Under v2, the same test case scored `specificity: pass` and `verdict: good`, losing the agreement v1 had.
- **Why it changed:** v2's prompt reordered/reweighted the criteria (verification_fidelity is now a hard-fail alongside field_completeness and requirement_coverage; specificity is soft-fail alongside the new pass_fail_clarity). The judge's `specificity` judgment for this exact test case flipped from fail to pass between runs — not something a v1→v2 wording diff in the *other* criteria should have caused. This looks like judgment instability on a borderline-quality artifact (consistent with Day 4/Day 7's known non-determinism findings) rather than a rubric-content effect, but the two runs weren't controlled for temperature/repetition, so it can't be fully separated from a real behavior change in this single-run comparison.

---

## Summary

- **v1 agreement (Day 14):** 9/10 = 90%. One disagreement: req_01.
- **v2 agreement (Day 16):** 8/10 = 80%. Two disagreements: req_01 (unchanged) and req_02 (new).
- **Verdict: regressed, not improved.** The criterion added specifically to catch req_01 (`verification_fidelity`) passed it anyway, so the targeted fix didn't land — and a previously-correct call on req_02 flipped to wrong, for reasons that look more like single-run judgment noise on a genuinely borderline case than a rubric-content effect. Net: v2 did not deliver the fix it was built for, and introduced a new miss.
- **What this doesn't yet tell us:** at n=10 with no repeated runs, one flipped verdict (req_02) is not enough to separate "the v2 prompt changed the judge's behavior" from "this is the same run-to-run instability already documented on judgment-based fields since Day 4/Day 7." Before concluding v2 is worse in general, this needs either repeated runs per row (pass-rate across N calls, not a single verdict) or the larger 30-requirement set planned for Week 3 — both already on the roadmap, not new asks.
