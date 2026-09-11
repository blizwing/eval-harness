from Day11_assertions import (
    TOKEN_CAP,
    check_fields_present,
    check_non_empty,
    check_under_token_cap,
    check_valid_json,
    run_assertions,
)


def full_parsed_output():
    return {
        "title": "t",
        "description": "d",
        "preconditions": ["p"],
        "test_steps": ["s"],
        "expected_result": "r",
        "priority": "high",
    }


def test_check_valid_json_true_for_schema_mismatch_not_malformed_json():
    # "invalid" (schema mismatch) still means the JSON itself parsed fine.
    assert check_valid_json({"validation_verdict": "invalid"}) is True


def test_check_valid_json_false_for_malformed_json():
    assert check_valid_json({"validation_verdict": "invalid_json"}) is False


def test_check_fields_present():
    assert check_fields_present({"validation_verdict": "valid"}) is True
    assert check_fields_present({"validation_verdict": "invalid"}) is False


def test_check_non_empty_true_when_all_fields_populated():
    assert check_non_empty({"parsed_output": full_parsed_output()}) is True


def test_check_non_empty_false_when_parsed_output_missing():
    assert check_non_empty({"parsed_output": None}) is False


def test_check_non_empty_false_for_blank_string_field():
    parsed = full_parsed_output()
    parsed["title"] = "   "
    assert check_non_empty({"parsed_output": parsed}) is False


def test_check_non_empty_false_for_empty_list_field():
    parsed = full_parsed_output()
    parsed["preconditions"] = []
    assert check_non_empty({"parsed_output": parsed}) is False


def test_check_under_token_cap():
    assert check_under_token_cap({"output_tokens": TOKEN_CAP}) is True
    assert check_under_token_cap({"output_tokens": TOKEN_CAP + 1}) is False


def test_run_assertions_builds_row_summaries():
    outputs = {
        "results": [
            {
                "id": "req_01",
                "validation_verdict": "valid",
                "parsed_output": full_parsed_output(),
                "output_tokens": 100,
            },
            {
                "id": "req_02",
                "validation_verdict": "invalid_json",
                "parsed_output": None,
                "output_tokens": 50,
            },
        ]
    }
    results = run_assertions(outputs)
    assert results[0]["id"] == "req_01"
    assert results[0]["valid_json"] is True
    assert results[0]["fields_present"] is True
    assert results[1]["valid_json"] is False
    assert results[1]["fields_present"] is False
