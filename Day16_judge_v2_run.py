"""
Day 16 — Run Day 15's v2 judge rubric (verification_fidelity + pass_fail_clarity
added to Day 12's three criteria) against all 10 of Day 9's generated test cases.
Save verdicts, then recompute agreement against Day 10's human ground truth.

DONE WHEN: can state both agreement numbers, v1 (Day 14: 9/10 = 90%) and v2
(computed here).
"""

import json
import os
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from Day4_json_mode import call_OpenAI_json_mode
from Day5_validate import validate_response

DAY9_OUTPUTS_FILE = "Day9_Requirements_JSON_Outputs/Day9_outputs.json"
JUDGE_PROMPT_FILE = "Day15_Judge_Rubric_V2/judge_v2.txt"
OUTPUT_DIR = "Day16_Judge_V2_Results"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Day16_judge_v2_verdicts.json")

BAR_WIDTH = 30

NO_OUTPUT_MARKER = "NO VALID OUTPUT WAS PRODUCED (validation_verdict != 'valid')"


class JudgeVerdictV2(BaseModel):
    field_completeness: Literal["pass", "fail"]
    requirement_coverage: Literal["pass", "fail"]
    specificity: Literal["pass", "fail"]
    verification_fidelity: Literal["pass", "fail"]
    pass_fail_clarity: Literal["pass", "fail"]
    verdict: Literal["good", "bad", "borderline"]
    reasoning: str


def print_progress(current: int, total: int, req_id: str, verdict: str) -> None:
    filled = int(BAR_WIDTH * current / total)
    bar = "#" * filled + "-" * (BAR_WIDTH - filled)
    pct = int(100 * current / total)
    end = "\n" if current == total else ""
    print(f"\r[{bar}] {current}/{total} ({pct}%) last: {req_id} -> {verdict}", end=end, flush=True)


def load_day9_outputs(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["results"]


def load_prompt_template(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def format_test_case(entry: dict) -> str:
    """Day 9's parsed_output is None for any row that failed Day 5's
    validation. Pass an explicit marker rather than the literal string
    'None', which would look like a plausible field value to the judge
    rather than an absence signal."""
    if entry["validation_verdict"] != "valid" or entry["parsed_output"] is None:
        return NO_OUTPUT_MARKER
    return json.dumps(entry["parsed_output"], indent=2, ensure_ascii=False)


def run_all() -> list[dict]:
    day9_results = load_day9_outputs(DAY9_OUTPUTS_FILE)
    prompt_template = load_prompt_template(JUDGE_PROMPT_FILE)

    total = len(day9_results)
    results = []
    for i, entry in enumerate(day9_results, start=1):
        req_id = entry["id"]
        req_text = entry["requirement_text"]
        test_case_str = format_test_case(entry)

        prompt = prompt_template.format(
            requirement_text=req_text,
            test_case_json=test_case_str,
        )
        call_result = call_OpenAI_json_mode(prompt)
        judge_status, judge_detail = validate_response(call_result.text, JudgeVerdictV2)

        if judge_status == "valid":
            assert isinstance(judge_detail, JudgeVerdictV2)
            judge_output = judge_detail.model_dump()
            judge_failure = None
            display_verdict = judge_output["verdict"]
        else:
            judge_output = None
            judge_failure = judge_detail
            display_verdict = f"JUDGE_{judge_status.upper()}"

        result_entry = {
            "id": req_id,
            "requirement_text": req_text,
            "generated_test_case": None if test_case_str == NO_OUTPUT_MARKER else entry["parsed_output"],
            "day9_validation_verdict": entry["validation_verdict"],
            "judge_raw_response_text": call_result.text,
            "judge_validation_verdict": judge_status,
            "judge_validation_detail": judge_failure,
            "judge_output": judge_output,
            "input_tokens": call_result.input_tokens,
            "output_tokens": call_result.output_tokens,
            "model_name": call_result.model_name,
        }
        results.append(result_entry)
        print_progress(i, total, req_id, display_verdict)

    return results


def save_results(results: list[dict]) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_day9_file": DAY9_OUTPUTS_FILE,
        "judge_prompt_file": JUDGE_PROMPT_FILE,
        "count": len(results),
        "results": results,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(results)} judge verdicts -> {OUTPUT_FILE}")


if __name__ == "__main__":
    results = run_all()
    save_results(results)
