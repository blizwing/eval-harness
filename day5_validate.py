import json
from typing import Literal
from pydantic import BaseModel, ValidationError

class EvalResult(BaseModel):
    summary: str
    risk_level: Literal["low", "medium", "high"]

def validate_response(raw_text: str, model: type[BaseModel]):
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        return ("invalid_json", [str(e)])

    try:
        result = model.model_validate(parsed)
    except ValidationError as e:
        errors = e.errors()
        missing = [err["loc"][0] for err in errors if err["type"] == "missing"]
        wrong_type = [(err["loc"][0], err["type"], err["msg"]) for err in errors if err["type"] != "missing"]

        failures = []
        if missing:
            failures.append(("missing_field", f"Missing required field(s): {missing}"))
        if wrong_type:
            failures.append(("wrong_type", wrong_type))
        return ("invalid", failures)

    return ("valid", result)


test_cases = {
    "broken_json":     '{"summary": "Login works", "risk_level": "low"',
    "missing_field":   '{"summary": "Login works"}',
    "wrong_type":      '{"summary": "Login works", "risk_level": "extreme"}',
    "both_at_once":    '{"risk_level": "extreme"}',   # missing summary AND bad risk_level
}

if __name__ == "__main__":
    for name, raw in test_cases.items():
        print(name, "->", validate_response(raw, EvalResult))