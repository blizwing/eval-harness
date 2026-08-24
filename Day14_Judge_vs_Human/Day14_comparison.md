# Day 14 — Judge vs. Human Comparison

Source files:
- Human ground truth: `Day10_Ground_Truth/Day10_labels.json`
- Judge verdicts: `Day12_Judge_LLM_Data/Day12_judge_llm_verdicts.json`

---

## Confusion Matrix

Rows = human label, columns = judge verdict.

|                   | judge: good | judge: bad | judge: borderline |
|-------------------|:-----------:|:----------:|:------------------:|
| human: good       |      7      |     0      |         0          |
| human: bad        |      1      |     1      |         0          |
| human: borderline |      0      |     0      |         1          |

**Agreement:** 9 / 10 = 90%

---

## Disagreement Log

One entry per req_id where human_label != judge_verdict.

### req_01
- **Human label:** bad — the expected duration format was not captured, and more importantly, not flagged.
- **Judge verdict:** good — passed all three rubric dimensions: field_completeness, requirement_coverage, specificity.
- **Why they diverged:** At generation time, the output constraints given to the test-case generator were thin, so the duration-format gap made it into the "final" test case unflagged. The criteria given to the judge were applied correctly against what it was shown.
- **Verdict vs. process:** The `good` verdict itself was wrong — the test case is genuinely incomplete. But the judge's *process* wasn't at fault: given its rubric and the artifact it was shown, it scored consistently. This is an input/rubric coverage gap, not a judge reasoning failure — the same category of fix Week 3 is already aimed at (adding explicit grounding criteria, this time for field completeness/formatting rather than priority).

---

## Summary

- **Overall agreement:** 9/10 = 90%
- **Pattern across disagreements:** Only one disagreement found. Too little data to call it a pattern yet — worth re-checking once the dataset expands to 30 in Week 3 (Day 17).
- **Trust going into Week 3's rubric rework:** Not fully trusting the judge yet. Its reasoning was internally consistent on req_01, but it still landed on the wrong final verdict — and consistency isn't the same as correctness. That's the failure mode that actually matters: a judge that reasons cleanly off a flawed or incomplete signal produces confident wrong verdicts, which don't announce themselves. Going into the rubric rework still owed proof, not assuming the fix will just work.