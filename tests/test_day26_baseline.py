import Day26_baseline as baseline
from schemas import CostReport, FailureReport, LatencyReport, PassRates, Report


def make_report(assertion_rate, judge_rate):
    return Report(
        joined_count=35,
        pass_rates=PassRates(assertion_pass_rate=assertion_rate, judge_pass_rate=judge_rate),
        cost=CostReport(
            total_cost_usd=0.005,
            cost_by_day23_status={"valid": 0.005},
            cost_by_assertion_outcome="not run",
            cost_by_judge_outcome="not run",
        ),
        latency=LatencyReport(mean_latency_all_ms=2989.0, mean_latency_valid_only_ms=2989.0),
        failures=FailureReport(assertion_failures=[], judge_failures=[], failed_both=[]),
    )


def test_diff_reports_ok_on_improvement():
    current = make_report(1.0, 0.971)
    base = make_report(0.971, 0.943)
    diffs = baseline.diff_against_baseline(current, base)
    assert all(d["status"] == "OK" for d in diffs)


def test_diff_flags_regression_beyond_threshold():
    current = make_report(0.80, 0.943)  # 17-point drop
    base = make_report(0.971, 0.943)
    diffs = baseline.diff_against_baseline(current, base)
    assertion_diff = next(d for d in diffs if d["metric"] == "assertion_pass_rate")
    assert assertion_diff["status"] == "REGRESSION"


def test_diff_ignores_noise_within_threshold():
    current = make_report(0.94, 0.943)  # within the 5-point threshold
    base = make_report(0.971, 0.943)
    diffs = baseline.diff_against_baseline(current, base)
    assertion_diff = next(d for d in diffs if d["metric"] == "assertion_pass_rate")
    assert assertion_diff["status"] == "OK"


def test_diff_reports_mode_mismatch_instead_of_comparing_strings():
    current = make_report(1.0, "not run")
    base = make_report(0.971, 0.943)
    diffs = baseline.diff_against_baseline(current, base)
    judge_diff = next(d for d in diffs if d["metric"] == "judge_pass_rate")
    assert judge_diff["status"] == "MODE_MISMATCH"


def test_format_diff_reports_regression_detected():
    diffs = baseline.diff_against_baseline(make_report(0.5, 0.943), make_report(0.971, 0.943))
    assert "REGRESSION DETECTED" in baseline.format_diff(diffs)


def test_format_diff_reports_no_regression():
    diffs = baseline.diff_against_baseline(make_report(1.0, 0.943), make_report(0.971, 0.943))
    assert "No regression." in baseline.format_diff(diffs)
