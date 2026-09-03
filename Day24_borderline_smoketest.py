"""
Day 24 — Borderline smoke test.

Runs Day24_Borderline_Smoketest/borderline_requirements.yaml (4 hand-crafted
requirements aimed at judge_v2.txt's good/borderline/bad buckets) through
Day 23's real runner and Day 24's real scorer, in mode="both", and reports
which verdict buckets actually got hit. This is a live check of the Day
14/17 finding that "borderline" is never reached across the real 35-item
dataset — not a re-run of that dataset.

Does NOT call Day23_runner.save_results — that writes to the same
Day23_Runner_Results/Day23_run_results.json path the real 35-item run
uses (see Day23_retry_smoketest.py's cleanup(), which deletes that same
shared path — fine for a smoke test that expects to clean up after
itself, but worth knowing before running it against real results you want
to keep). This script keeps everything in memory instead.

Usage:
    python3 Day24_borderline_smoketest.py
"""

from Day23_runner import run_all, serialize_case
from Day24_scorer import score_case, ScoreIntegrityError

FIXTURE_PATH = "Day24_Borderline_Smoketest/borderline_requirements.yaml"

EXPECTED_VERDICT = {
    "req_b01": "good",
    "req_b02": "borderline",
    "req_b03": "borderline",
    "req_b04": "bad",
    "req_b05": "borderline",
}


def main() -> None:
    print(f"[smoketest] Running Day23's run_all against {FIXTURE_PATH}...\n")
    results = run_all(requirements_file=FIXTURE_PATH)
    rows = [serialize_case(r) for r in results]

    print("\n[smoketest] Scoring each case in mode='both'...\n")
    observed_verdicts: set[str] = set()

    for row in rows:
        try:
            scored = score_case(row, "both")
        except ScoreIntegrityError as e:
            print(f"  {row['id']}: INTEGRITY ERROR -> {e}")
            continue

        verdict = scored.judge_result.verdict
        observed_verdicts.add(verdict)
        expected = EXPECTED_VERDICT.get(row["id"], "?")
        flag = "OK" if verdict == expected else "DIFFERENT FROM EXPECTED"

        print(f"  {row['id']} (status={row['status']})")
        print(f"    assertions_passed = {scored.assertion_result.passed}")
        print(f"    judge_verdict     = {verdict}  (expected: {expected})  [{flag}]")
        print(f"    reasoning         = {scored.judge_result.reasoning}")
        print()

    print(f"[smoketest] Verdict buckets observed: {sorted(observed_verdicts)}")
    print(f"[smoketest] Borderline path reached: {'borderline' in observed_verdicts}")


if __name__ == "__main__":
    main()
