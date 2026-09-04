"""
Day 25 — Reporter: joins Day 23's run results with Day 24's score results
and produces a human-readable report (pass rates, cost, latency, failures).

DONE WHEN: one command reads both files and prints a report, hard-stopping
on any case_id mismatch between the two sides rather than reporting on a
partial join.

Design notes:
- Join key is Day 23's `id` / Day 24's `case_id` — same case, different
  field name on each side (mirrors the `status` vs `validation_verdict`
  rename Day 24 already works around for Day 11's checks).
- The case_id-set check runs before any metric is computed, and raises
  immediately on mismatch — following the ScoreIntegrityError pattern in
  Day24_scorer.py, a join that can't be trusted is a hard stop, not a
  partial report with a caveat.
- "not run" is a literal string sentinel, never a number or blank, for any
  pass-rate or cost-split metric whose scoring mode wasn't exercised across
  the joined cases (checked from the data itself — whether any joined row
  actually carries an assertion_result / judge_result — rather than trusted
  from a single mode label, since Day 24 mode is technically per-row).
- Judge pass rate is strict: only verdict == "good" counts as a pass.
  "borderline" is a fail, same as "bad" — this is deliberate per Day 25's
  spec, not an oversight.
- api_error rows (Day 23) have no metered cost/latency at all — Day23's
  serialize_case only writes cost_usd/latency_ms when a call actually
  completed. Latency means are computed over only the rows that have a
  latency_ms value, not defaulted to 0 (a 0ms row would understate the
  mean for a failure that never made a measurable call).
"""

import argparse
import json
from collections import defaultdict

from schemas import (
    AssertionFailure,
    CostReport,
    FailureReport,
    JudgeFailure,
    LatencyReport,
    PassRates,
    Report,
    ScoreResult,
)

DEFAULT_RUN_RESULTS_FILE = "Day23_Runner_Results/Day23_run_results.json"
DEFAULT_SCORE_RESULTS_FILE = "Day24_Scorer_Results/Day24_score_results.json"


class ReportIntegrityError(Exception):
    """Raised when Day 23's and Day 24's case_id sets don't match exactly.
    No partial report is ever generated on a mismatch — the caller gets an
    exception naming exactly which case_ids are missing from which side."""


def load_run_rows(path: str) -> dict[str, dict]:
    """Loads Day 23's run_results.json, keyed by case id (`id`)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {row["id"]: row for row in data["results"]}


def load_score_results(path: str) -> dict[str, ScoreResult]:
    """Loads Day 24's score_results.json, keyed by case id (`case_id`)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = [ScoreResult.model_validate(r) for r in data["results"]]
    return {r.case_id: r for r in results}


def join_results(
    run_rows: dict[str, dict], score_results: dict[str, ScoreResult]
) -> dict[str, tuple[dict, ScoreResult]]:
    """Joins on case_id after verifying both sides have IDENTICAL case_id
    sets. Raises ReportIntegrityError on any mismatch, before computing
    anything."""
    run_ids = set(run_rows.keys())
    score_ids = set(score_results.keys())

    missing_from_scores = run_ids - score_ids
    missing_from_run = score_ids - run_ids
    if missing_from_scores or missing_from_run:
        parts = []
        if missing_from_scores:
            parts.append(f"missing from Day 24 scores: {sorted(missing_from_scores)}")
        if missing_from_run:
            parts.append(f"missing from Day 23 run results: {sorted(missing_from_run)}")
        raise ReportIntegrityError(
            "case_id sets do not match between Day 23 and Day 24 output - " + "; ".join(parts)
        )

    # Iterate run_rows (not the run_ids set) so joined output stays in Day
    # 23's original file order rather than shuffling on set-iteration order.
    return {case_id: (run_rows[case_id], score_results[case_id]) for case_id in run_rows}


def compute_pass_rates(joined: dict[str, tuple[dict, ScoreResult]]) -> PassRates:
    rows = list(joined.values())
    assertion_ran = any(score.assertion_result is not None for _, score in rows)
    judge_ran = any(score.judge_result is not None for _, score in rows)

    if assertion_ran:
        scored = [score for _, score in rows if score.assertion_result is not None]
        assertion_rate = sum(1 for s in scored if s.assertion_result.passed) / len(scored)
    else:
        assertion_rate = "not run"

    if judge_ran:
        scored = [score for _, score in rows if score.judge_result is not None]
        judge_rate = sum(1 for s in scored if s.judge_result.verdict == "good") / len(scored)
    else:
        judge_rate = "not run"

    return PassRates(assertion_pass_rate=assertion_rate, judge_pass_rate=judge_rate)


def compute_cost(joined: dict[str, tuple[dict, ScoreResult]]) -> CostReport:
    rows = list(joined.values())
    total_cost = sum(run.get("cost_usd", 0.0) or 0.0 for run, _ in rows)

    by_status: dict[str, float] = defaultdict(float)
    for run, _ in rows:
        by_status[run["status"]] += run.get("cost_usd", 0.0) or 0.0

    assertion_ran = any(score.assertion_result is not None for _, score in rows)
    if assertion_ran:
        by_assertion: dict[str, float] = {"passed": 0.0, "failed": 0.0}
        for run, score in rows:
            if score.assertion_result is None:
                continue
            key = "passed" if score.assertion_result.passed else "failed"
            by_assertion[key] += run.get("cost_usd", 0.0) or 0.0
    else:
        by_assertion = "not run"

    judge_ran = any(score.judge_result is not None for _, score in rows)
    if judge_ran:
        by_judge: dict[str, float] = {"passed": 0.0, "failed": 0.0}
        for run, score in rows:
            if score.judge_result is None:
                continue
            key = "passed" if score.judge_result.verdict == "good" else "failed"
            by_judge[key] += run.get("cost_usd", 0.0) or 0.0
    else:
        by_judge = "not run"

    return CostReport(
        total_cost_usd=total_cost,
        cost_by_day23_status=dict(by_status),
        cost_by_assertion_outcome=by_assertion,
        cost_by_judge_outcome=by_judge,
    )


def compute_latency(joined: dict[str, tuple[dict, ScoreResult]]) -> LatencyReport:
    rows = list(joined.values())

    all_latencies = [run["latency_ms"] for run, _ in rows if run.get("latency_ms") is not None]
    valid_latencies = [
        run["latency_ms"] for run, _ in rows
        if run["status"] == "valid" and run.get("latency_ms") is not None
    ]

    mean_all = sum(all_latencies) / len(all_latencies) if all_latencies else 0.0
    mean_valid = sum(valid_latencies) / len(valid_latencies) if valid_latencies else 0.0

    return LatencyReport(mean_latency_all_ms=mean_all, mean_latency_valid_only_ms=mean_valid)


def compute_failures(joined: dict[str, tuple[dict, ScoreResult]]) -> FailureReport:
    assertion_failures = []
    judge_failures = []

    for case_id, (_, score) in joined.items():
        if score.assertion_result is not None and not score.assertion_result.passed:
            failed_checks = {k: v for k, v in score.assertion_result.checks.items() if v is False}
            assertion_failures.append(AssertionFailure(case_id=case_id, failed_checks=failed_checks))

        if score.judge_result is not None and score.judge_result.verdict in ("borderline", "bad"):
            judge_failures.append(
                JudgeFailure(
                    case_id=case_id,
                    verdict=score.judge_result.verdict,
                    reasoning=score.judge_result.reasoning,
                )
            )

    assertion_fail_ids = {f.case_id for f in assertion_failures}
    judge_fail_ids = {f.case_id for f in judge_failures}
    failed_both = sorted(assertion_fail_ids & judge_fail_ids)

    return FailureReport(
        assertion_failures=assertion_failures,
        judge_failures=judge_failures,
        failed_both=failed_both,
    )


def build_report(joined: dict[str, tuple[dict, ScoreResult]]) -> Report:
    return Report(
        joined_count=len(joined),
        pass_rates=compute_pass_rates(joined),
        cost=compute_cost(joined),
        latency=compute_latency(joined),
        failures=compute_failures(joined),
    )


def generate_report(run_results_file: str, score_results_file: str) -> Report:
    run_rows = load_run_rows(run_results_file)
    score_results = load_score_results(score_results_file)
    joined = join_results(run_rows, score_results)
    return build_report(joined)


def _fmt_rate(rate: float | str) -> str:
    return rate if isinstance(rate, str) else f"{rate:.1%}"


def _fmt_cost_split(split: dict[str, float] | str) -> str:
    if isinstance(split, str):
        return split
    return ", ".join(f"{k}=${v:.4f}" for k, v in split.items())


def format_report(report: Report) -> str:
    lines = []
    lines.append(f"Day 25 Report - {report.joined_count} joined case(s)")
    lines.append("")

    lines.append("== Pass rates ==")
    lines.append(f"  Assertion pass rate: {_fmt_rate(report.pass_rates.assertion_pass_rate)}")
    lines.append(f"  Judge pass rate (strict, 'good' only): {_fmt_rate(report.pass_rates.judge_pass_rate)}")
    lines.append("")

    lines.append("== Cost ==")
    lines.append(f"  Total cost: ${report.cost.total_cost_usd:.4f}")
    lines.append(f"  By Day 23 status: {_fmt_cost_split(report.cost.cost_by_day23_status)}")
    lines.append(f"  By assertion outcome: {_fmt_cost_split(report.cost.cost_by_assertion_outcome)}")
    lines.append(f"  By judge outcome: {_fmt_cost_split(report.cost.cost_by_judge_outcome)}")
    lines.append("")

    lines.append("== Latency ==")
    lines.append(f"  Mean latency (all joined cases): {report.latency.mean_latency_all_ms:.1f} ms")
    lines.append(f"  Mean latency (status == 'valid' only): {report.latency.mean_latency_valid_only_ms:.1f} ms")
    lines.append("")

    lines.append(f"== Assertion failures ({len(report.failures.assertion_failures)}) ==")
    if not report.failures.assertion_failures:
        lines.append("  (none)")
    for f in report.failures.assertion_failures:
        checks_str = ", ".join(f"{k}: {v}" for k, v in f.failed_checks.items())
        lines.append(f"  {f.case_id}: {checks_str}")
    lines.append("")

    lines.append(f"== Judge failures ({len(report.failures.judge_failures)}) ==")
    if not report.failures.judge_failures:
        lines.append("  (none)")
    for f in report.failures.judge_failures:
        lines.append(f"  {f.case_id}: verdict={f.verdict} - {f.reasoning}")
    lines.append("")

    lines.append(f"== Failed BOTH assertions and judge ({len(report.failures.failed_both)}) ==")
    if not report.failures.failed_both:
        lines.append("  (none)")
    for case_id in report.failures.failed_both:
        lines.append(f"  {case_id}")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Day 25 — join Day 23's run results with Day 24's score results and report."
    )
    parser.add_argument(
        "--run-results",
        default=DEFAULT_RUN_RESULTS_FILE,
        help="Path to Day 23's run_results.json.",
    )
    parser.add_argument(
        "--score-results",
        default=DEFAULT_SCORE_RESULTS_FILE,
        help="Path to Day 24's score_results.json.",
    )
    args = parser.parse_args()

    report = generate_report(args.run_results, args.score_results)
    print(format_report(report))
