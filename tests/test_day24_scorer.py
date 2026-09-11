import json

import pytest

import Day24_scorer as scorer
from schemas import AssertionScore, JudgeScore, ScoreResult

VALID_ROW = {
    "id": "req_01",
    "status": "valid",
    "requirement_text": "Do the thing.",
    "output_tokens": 100,
    "parsed_output": {
        "title": "t",
        "description": "d",
        "preconditions": ["p"],
        "test_steps": ["s"],
        "expected_result": "r",
        "priority": "high",
    },
}

API_ERROR_ROW = {"id": "req_02", "status": "api_error", "requirement_text": "Unreachable."}

INVALID_ROW = {
    "id": "req_03",
    "status": "invalid_schema",
    "requirement_text": "Missing fields.",
    "output_tokens": 50,
    "parsed_output": None,
}


def make_judge_score(**overrides):
    base = dict(
        verdict="good",
        field_completeness="pass",
        requirement_coverage="pass",
        specificity="pass",
        verification_fidelity="pass",
        pass_fail_clarity="pass",
        reasoning="Looks solid.",
    )
    base.update(overrides)
    return JudgeScore(**base)


# --- score_assertions: pure, no API ---

def test_score_assertions_passes_clean_row():
    result = scorer.score_assertions(VALID_ROW)
    assert result.passed is True
    assert all(result.checks.values())


def test_score_assertions_api_error_row_is_all_false():
    result = scorer.score_assertions(API_ERROR_ROW)
    assert result.passed is False
    assert all(v is False for v in result.checks.values())


def test_score_assertions_invalid_row_fails_fields_present():
    result = scorer.score_assertions(INVALID_ROW)
    assert result.checks["fields_present"] is False
    assert result.passed is False


# --- score_judge: mocked judge_single_case, no API ---

def test_score_judge_api_error_skips_model_call(monkeypatch):
    called = []
    monkeypatch.setattr(scorer, "judge_single_case", lambda *a, **k: called.append(1))

    result = scorer.score_judge(API_ERROR_ROW, prompt_template="unused")

    assert called == []
    assert result.verdict == "bad"
    assert result.reasoning == scorer.API_ERROR_JUDGE_REASONING


def test_score_judge_returns_valid_response(monkeypatch):
    expected = make_judge_score(verdict="good")
    monkeypatch.setattr(
        scorer, "judge_single_case",
        lambda req_text, tc_str, template, model: (None, "valid", expected),
    )

    result = scorer.score_judge(VALID_ROW, prompt_template="template")
    assert result == expected


def test_score_judge_raises_integrity_error_on_bad_response(monkeypatch):
    monkeypatch.setattr(
        scorer, "judge_single_case",
        lambda req_text, tc_str, template, model: (None, "invalid_json", ["bad json"]),
    )
    with pytest.raises(scorer.ScoreIntegrityError):
        scorer.score_judge(VALID_ROW, prompt_template="template")


# --- score_case dispatcher ---

def test_score_case_assertions_mode_never_calls_judge(monkeypatch):
    called = []
    monkeypatch.setattr(scorer, "judge_single_case", lambda *a, **k: called.append(1))

    result = scorer.score_case(VALID_ROW, mode="assertions")

    assert result.judge_result is None
    assert result.assertion_result is not None
    assert called == []


def test_score_case_both_mode(monkeypatch):
    expected = make_judge_score()
    monkeypatch.setattr(
        scorer, "judge_single_case",
        lambda req_text, tc_str, template, model: (None, "valid", expected),
    )

    result = scorer.score_case(VALID_ROW, mode="both", judge_prompt_template="template")

    assert result.assertion_result is not None
    assert result.judge_result == expected


# --- integrity checks (the Day 24 grader-output-integrity feature) ---

def test_check_integrity_passes_for_well_formed_result():
    result = ScoreResult(
        case_id="req_01",
        mode="both",
        assertion_result=AssertionScore(
            checks={k: True for k in scorer.ASSERTION_CHECK_KEYS}, passed=True
        ),
        judge_result=make_judge_score(),
    )
    scorer._check_integrity(result)  # should not raise


def test_check_integrity_raises_on_blank_judge_reasoning():
    result = ScoreResult(
        case_id="req_01", mode="judge", judge_result=make_judge_score(reasoning="")
    )
    with pytest.raises(scorer.ScoreIntegrityError):
        scorer._check_integrity(result)


def test_check_integrity_raises_on_missing_assertion_result():
    result = ScoreResult(case_id="req_01", mode="assertions", assertion_result=None)
    with pytest.raises(scorer.ScoreIntegrityError):
        scorer._check_integrity(result)


# --- score_all: file-driven, still fully mocked ---

def test_score_all_assertions_only(tmp_path):
    results_file = tmp_path / "run_results.json"
    results_file.write_text(json.dumps({"results": [VALID_ROW, API_ERROR_ROW]}))

    scored = scorer.score_all(str(results_file), mode="assertions")

    assert [s.case_id for s in scored] == ["req_01", "req_02"]
    assert scored[0].assertion_result.passed is True
    assert scored[1].assertion_result.passed is False
