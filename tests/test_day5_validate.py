from Day5_validate import validate_response, EvalResult


def test_valid_response():
    status, result = validate_response('{"summary": "ok", "risk_level": "low"}', EvalResult)
    assert status == "valid"
    assert result.summary == "ok"
    assert result.risk_level == "low"


def test_broken_json():
    status, errors = validate_response(
        '{"summary": "Login works", "risk_level": "low"', EvalResult
    )
    assert status == "invalid_json"
    assert isinstance(errors, list) and errors


def test_missing_field():
    status, failures = validate_response('{"summary": "Login works"}', EvalResult)
    assert status == "invalid"
    assert "missing_field" in [f[0] for f in failures]


def test_wrong_type():
    status, failures = validate_response(
        '{"summary": "Login works", "risk_level": "extreme"}', EvalResult
    )
    assert status == "invalid"
    assert "wrong_type" in [f[0] for f in failures]


def test_both_missing_and_wrong_type_reported_together():
    status, failures = validate_response('{"risk_level": "extreme"}', EvalResult)
    assert status == "invalid"
    assert {f[0] for f in failures} == {"missing_field", "wrong_type"}
