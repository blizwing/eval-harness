"""
Day 26 — Regression baseline: save a Day 25 Report's pass rates as a
baseline, diff a subsequent run against it, flag regressions.

DONE WHEN: deliberately worsening prompt_testcase_v1.txt (on a sabotaged
copy, not the real file) and rerunning the pipeline makes `diff` report a
regression.

Design notes:
- Outputs are non-deterministic (Day 2): the OpenAI-schema endpoint was
  fully deterministic at temp=0, the Anthropic-schema endpoint was not
  (5/10 unique outputs against the same model, same prompt). Diffing must
  use pass-rate thresholds, not exact-match — two runs of the identical
  prompt can legitimately land a case or two differently with zero real
  regression.
- Only assertion_pass_rate and judge_pass_rate are diffed against a
  threshold. Cost and latency are recorded in baseline.json for visibility
  (so the file is a full historical snapshot, not just two numbers) but are
  not regression signals here — a cost/latency guardrail is Day 30/31's
  job on the roadmap, not this one.
- REGRESSION_THRESHOLD (0.05 = 5 percentage points) is a judgment call, not
  a value derived from measured pass-rate variance — we have Day 2's
  finding that raw output is non-deterministic, but no data yet on how
  much a pass RATE itself swings run-to-run under an unchanged prompt.
  5 points is roughly "more than one case flips out of 35" — small enough
  to catch a deliberately worsened prompt, generous enough not to fire on
  ordinary single-case noise. Override with --threshold if a run needs a
  different tolerance; revisit once a few real baseline/diff cycles show
  what actual run-to-run noise looks like.
- A "not run" pass rate on either side (baseline scored in a different
  mode than the current run) is reported as MODE_MISMATCH, not silently
  skipped and not scored as a regression — comparing a number against the
  string "not run" isn't a real threshold comparison, and pretending
  otherwise is exactly the kind of silent-wrong-answer failure mode this
  harness exists to catch (see CLAUDE.md's Day 24 grader-integrity note).
- `diff` exits with code 1 when any metric regresses, 0 otherwise — free
  now, and it's the exact hook Day 29-33's CI pass-rate gate needs later.
"""

import argparse
import json
import os
from datetime import datetime, timezone

from Day25_reporter import (
    DEFAULT_RUN_RESULTS_FILE,
    DEFAULT_SCORE_RESULTS_FILE,
    generate_report,
)
from schemas import Report

BASELINE_FILE = "baseline.json"

REGRESSION_THRESHOLD = 0.05


class BaselineNotFoundError(Exception):
    """Raised when `diff` is requested but no baseline file exists yet."""


def save_baseline(
    run_results_file: str,
    score_results_file: str,
    baseline_file: str = BASELINE_FILE,
) -> Report:
    """Generates a Day 25 Report from the given result files and persists
    it as the baseline. Overwrites any existing baseline_file."""
    report = generate_report(run_results_file, score_results_file)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_run_results_file": run_results_file,
        "source_score_results_file": score_results_file,
        "report": report.model_dump(),
    }
    with open(baseline_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Saved baseline ({report.joined_count} case(s)) -> {baseline_file}")
    return report


def load_baseline(baseline_file: str = BASELINE_FILE) -> Report:
    if not os.path.exists(baseline_file):
        raise BaselineNotFoundError(
            f"No baseline found at {baseline_file} — run `python Day26_baseline.py save` first."
        )
    with open(baseline_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Report.model_validate(data["report"])


def _diff_rate(name: str, baseline_rate, current_rate, threshold: float) -> dict:
    """Compares one pass-rate metric between baseline and current. Never
    raises — a regression is a reported outcome, not an exception."""
    if baseline_rate == "not run" or current_rate == "not run":
        return {
            "metric": name,
            "status": "MODE_MISMATCH",
            "baseline": baseline_rate,
            "current": current_rate,
        }

    delta = current_rate - baseline_rate
    status = "REGRESSION" if delta < -threshold else "OK"
    return {
        "metric": name,
        "status": status,
        "baseline": baseline_rate,
        "current": current_rate,
        "delta": delta,
        "threshold": threshold,
    }


def diff_against_baseline(
    current: Report, baseline: Report, threshold: float = REGRESSION_THRESHOLD
) -> list[dict]:
    return [
        _diff_rate(
            "assertion_pass_rate",
            baseline.pass_rates.assertion_pass_rate,
            current.pass_rates.assertion_pass_rate,
            threshold,
        ),
        _diff_rate(
            "judge_pass_rate",
            baseline.pass_rates.judge_pass_rate,
            current.pass_rates.judge_pass_rate,
            threshold,
        ),
    ]


def format_diff(diffs: list[dict]) -> str:
    lines = ["Day 26 Regression Diff", ""]
    any_regression = False
    for d in diffs:
        if d["status"] == "REGRESSION":
            any_regression = True
            lines.append(
                f"  [REGRESSION] {d['metric']}: {d['baseline']:.1%} -> {d['current']:.1%} "
                f"(delta {d['delta']:+.1%}, threshold -{d['threshold']:.1%})"
            )
        elif d["status"] == "MODE_MISMATCH":
            lines.append(
                f"  [MODE MISMATCH] {d['metric']}: baseline={d['baseline']} current={d['current']} "
                f"(not comparable — different scoring modes)"
            )
        else:
            lines.append(
                f"  [OK] {d['metric']}: {d['baseline']:.1%} -> {d['current']:.1%} (delta {d['delta']:+.1%})"
            )
    lines.append("")
    lines.append("REGRESSION DETECTED" if any_regression else "No regression.")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Day 26 — save or diff a pass-rate regression baseline."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    save_p = sub.add_parser("save", help="Generate a report and save it as the baseline.")
    save_p.add_argument("--run-results", default=DEFAULT_RUN_RESULTS_FILE)
    save_p.add_argument("--score-results", default=DEFAULT_SCORE_RESULTS_FILE)
    save_p.add_argument("--baseline-file", default=BASELINE_FILE)

    diff_p = sub.add_parser("diff", help="Generate a report and diff it against the saved baseline.")
    diff_p.add_argument("--run-results", default=DEFAULT_RUN_RESULTS_FILE)
    diff_p.add_argument("--score-results", default=DEFAULT_SCORE_RESULTS_FILE)
    diff_p.add_argument("--baseline-file", default=BASELINE_FILE)
    diff_p.add_argument("--threshold", type=float, default=REGRESSION_THRESHOLD)

    args = parser.parse_args()

    if args.command == "save":
        for path in (args.run_results, args.score_results):
            if not os.path.exists(path):
                raise SystemExit(f"Pre-flight failed: {path} does not exist.")
        save_baseline(args.run_results, args.score_results, args.baseline_file)

    elif args.command == "diff":
        for path in (args.run_results, args.score_results):
            if not os.path.exists(path):
                raise SystemExit(f"Pre-flight failed: {path} does not exist.")
        baseline_report = load_baseline(args.baseline_file)
        current_report = generate_report(args.run_results, args.score_results)
        diffs = diff_against_baseline(current_report, baseline_report, args.threshold)
        print(format_diff(diffs))
        if any(d["status"] == "REGRESSION" for d in diffs):
            raise SystemExit(1)
