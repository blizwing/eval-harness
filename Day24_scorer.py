"""
Day 24 — Scorer: assertion-scoring and judge-scoring pluggable behind one
interface.

DONE WHEN: you can run assertions-only, judge-only, or both, via a flag.

Design notes:
- Assertion checks are reused unchanged from Day11_assertions.py. Those
  functions were written against Day 9's row shape (key `validation_verdict`)
  but Day 23's rows use `status` for the same concept — so rows are adapted
  (a shallow copy with `validation_verdict` aliased from `status`) before
  being handed to Day 11's functions, rather than touching Day 11 itself.
- Judge scoring reuses Day 12's single-case pattern (judge_single_case,
  extracted there for this purpose) but validates against JudgeScore, not
  JudgeVerdict — judge_v2.txt's rubric (Day 15/16) asks for 5 pass/fail
  criteria, and JudgeVerdict only has 3. Validating a v2 response against
  the v1 model would silently drop verification_fidelity and
  pass_fail_clarity instead of erroring, which is exactly the kind of
  grader-output blind spot this file's integrity check exists to catch.
- A row with status == "api_error" has no parsed_output and never reached
  the model — conservative default (Pratham's call): score it an automatic
  assertion fail and an automatic judge fail, skipping the judge API call
  entirely, rather than raising an integrity error over a row that was
  never a candidate for a real score.
- Integrity check runs after scoring, before returning, and raises rather
  than downgrading to a per-row error status — an API hiccup (Day 23) and
  a harness producing an untrustworthy score (Day 24) are different
  severities.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Literal

from Day11_assertions import (
    check_valid_json,
    check_fields_present,
    check_non_empty,
    check_under_token_cap,
)
from Day12_LLM_Judge import NO_OUTPUT_MARKER, judge_single_case, load_prompt_template
from schemas import AssertionScore, JudgeScore, ScoreResult

DEFAULT_JUDGE_PROMPT_FILE = "Day15_Judge_Rubric_V2/judge_v2.txt"

OUTPUT_DIR = "Day24_Scorer_Results"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Day24_score_results.json")

ASSERTION_CHECK_KEYS = ("valid_json", "fields_present", "non_empty", "under_token_cap")

API_ERROR_JUDGE_REASONING = (
    "Skipped: case has status 'api_error' - no generated output to judge."
)


class ScoreIntegrityError(Exception):
    """Raised when a ScoreResult would be returned incomplete or malformed
    for the mode it was scored in. No partial ScoreResult is ever returned
    on this path — the caller gets an exception, not a degraded result."""


def _all_checks_false() -> AssertionScore:
    return AssertionScore(checks={k: False for k in ASSERTION_CHECK_KEYS}, passed=False)


def score_assertions(row: dict) -> AssertionScore:
    """Runs Day 11's four checks against a Day 23 row. api_error rows have
    no parsed_output and several fields (output_tokens, etc.) Day 11's
    checks assume exist — scored as an automatic fail instead of KeyError-ing."""
    if row["status"] == "api_error":
        return _all_checks_false()

    adapted = {**row, "validation_verdict": row["status"]}
    checks = {
        "valid_json": check_valid_json(adapted),
        "fields_present": check_fields_present(adapted),
        "non_empty": check_non_empty(adapted),
        "under_token_cap": check_under_token_cap(adapted),
    }
    return AssertionScore(checks=checks, passed=all(checks.values()))


def _format_test_case_for_row(row: dict) -> str:
    if row["status"] != "valid" or row.get("parsed_output") is None:
        return NO_OUTPUT_MARKER
    return json.dumps(row["parsed_output"], indent=2, ensure_ascii=False)


def score_judge(row: dict, prompt_template: str | None = None) -> JudgeScore:
    if row["status"] == "api_error":
        return JudgeScore(
            verdict="bad",
            field_completeness="fail",
            requirement_coverage="fail",
            specificity="fail",
            verification_fidelity="fail",
            pass_fail_clarity="fail",
            reasoning=API_ERROR_JUDGE_REASONING,
        )

    if prompt_template is None:
        prompt_template = load_prompt_template(DEFAULT_JUDGE_PROMPT_FILE)

    test_case_str = _format_test_case_for_row(row)
    _, judge_status, judge_detail = judge_single_case(
        row["requirement_text"], test_case_str, prompt_template, JudgeScore
    )
    if judge_status != "valid":
        raise ScoreIntegrityError(
            f"case {row['id']}: judge response failed validation ({judge_status}): {judge_detail}"
        )
    assert isinstance(judge_detail, JudgeScore)
    return judge_detail


def _check_assertion_integrity(case_id: str, ar: AssertionScore | None) -> str | None:
    if ar is None:
        return "assertion_result is missing"
    keys = set(ar.checks.keys())
    if keys != set(ASSERTION_CHECK_KEYS):
        return f"assertion_result.checks has keys {sorted(keys)}, expected {sorted(ASSERTION_CHECK_KEYS)}"
    if not all(isinstance(v, bool) for v in ar.checks.values()):
        return "assertion_result.checks contains a non-bool value"
    return None


def _check_judge_integrity(case_id: str, jr: JudgeScore | None) -> str | None:
    if jr is None:
        return "judge_result is missing"
    if not jr.reasoning or not jr.reasoning.strip():
        return "judge_result.reasoning is blank"
    return None


def _check_integrity(result: ScoreResult) -> None:
    errors: list[str] = []
    if result.mode in ("assertions", "both"):
        err = _check_assertion_integrity(result.case_id, result.assertion_result)
        if err:
            errors.append(err)
    if result.mode in ("judge", "both"):
        err = _check_judge_integrity(result.case_id, result.judge_result)
        if err:
            errors.append(err)
    if errors:
        raise ScoreIntegrityError(f"case {result.case_id}: " + "; ".join(errors))


def score_case(
    row: dict,
    mode: Literal["assertions", "judge", "both"],
    judge_prompt_template: str | None = None,
) -> ScoreResult:
    """Thin dispatcher: runs assertion scoring, judge scoring, or both over
    one Day 23 row, then integrity-checks the result before returning it."""
    assertion_result = score_assertions(row) if mode in ("assertions", "both") else None
    judge_result = score_judge(row, judge_prompt_template) if mode in ("judge", "both") else None

    result = ScoreResult(
        case_id=row["id"],
        mode=mode,
        assertion_result=assertion_result,
        judge_result=judge_result,
    )
    _check_integrity(result)
    return result


def score_all(
    results_file: str,
    mode: str,
    judge_prompt_file: str = DEFAULT_JUDGE_PROMPT_FILE,
) -> list[ScoreResult]:
    """Loads Day 23's results and scores every row. A ScoreIntegrityError
    for any single case propagates and halts the run — an integrity failure
    means the harness produced a row it can't trust, not a per-row hiccup
    to record and move past the way Day 23 handles api_error."""
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    judge_prompt_template = (
        load_prompt_template(judge_prompt_file) if mode in ("judge", "both") else None
    )

    return [score_case(row, mode, judge_prompt_template) for row in data["results"]]


def serialize_score(r: ScoreResult) -> dict:
    """Flattens a ScoreResult into the dict row shape used by
    Day24_score_results.json (case_id, mode, and the full assertion_result /
    judge_result payloads Day 25 joins against Day 23's rows)."""
    return r.model_dump()


def save_scores(results: list[ScoreResult], mode: str, source_results_file: str) -> None:
    """Persists score_all()'s output, following Day23_runner.save_results's
    envelope shape (generated_at, source file, count, results)."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_results_file": source_results_file,
        "mode": mode,
        "count": len(results),
        "results": [serialize_score(r) for r in results],
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(results)} score(s) -> {OUTPUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 24 — score Day 23's run results.")
    parser.add_argument(
        "--results-file",
        default="Day23_Runner_Results/Day23_run_results.json",
        help="Path to Day 23's run_results.json.",
    )
    parser.add_argument(
        "--mode",
        choices=["assertions", "judge", "both"],
        default="both",
        help="Which scoring to run.",
    )
    parser.add_argument(
        "--judge-prompt",
        default=DEFAULT_JUDGE_PROMPT_FILE,
        help="Override the default judge_v2.txt rubric file.",
    )
    parser.add_argument(
        "--save",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist results to Day24_Scorer_Results/Day24_score_results.json (default: on; use --no-save to skip).",
    )
    args = parser.parse_args()

    scored = score_all(args.results_file, args.mode, args.judge_prompt)

    if args.save:
        save_scores(scored, args.mode, args.results_file)

    print(f"Scored {len(scored)} case(s) in mode={args.mode}.")
    for r in scored:
        summary = []
        if r.assertion_result is not None:
            summary.append(f"assertions_passed={r.assertion_result.passed}")
        if r.judge_result is not None:
            summary.append(f"judge_verdict={r.judge_result.verdict}")
        print(f"  {r.case_id}: {', '.join(summary)}")
