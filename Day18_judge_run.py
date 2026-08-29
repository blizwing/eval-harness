"""
Day 18 — extend Day 16's judge v2 run to all 35 rows.

Reuses the existing Day16_judge_v2_verdicts.json verdicts for req_01-req_10
unchanged (same reasoning as Day18_run_outputs.py: rerunning the judge on
already-judged rows would introduce fresh non-determinism noise into rows
that already have a settled comparison against Day10_labels.json). Only
calls the judge on the 25 new rows from Day18_outputs.json (req_11-req_35).

Same rubric as Day 16 (Day15_Judge_Rubric_V2/judge_v2.txt), same JudgeVerdictV2
schema -- nothing about the judge itself changes, only the input set.

DONE WHEN: Day18_Judge_Results/Day18_judge_verdicts.json exists with 35
total verdicts (10 carried over + 25 new).
"""

import json
import os
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from Day4_json_mode import call_OpenAI_json_mode
from Day5_validate import validate_response

DAY18_OUTPUTS_FILE = "Day18_Full_Set/Day18_outputs.json"
EXISTING_VERDICTS_FILE = "Day16_Judge_V2_Results/Day16_judge_v2_verdicts.json"
JUDGE_PROMPT_FILE = "Day15_Judge_Rubric_V2/judge_v2.txt"
OUTPUT_DIR = "Day18_Judge_Results"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Day18_judge_verdicts.json")

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


def load_day18_outputs(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["results"]


def load_existing_verdicts(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("results", [])


def load_prompt_template(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def format_test_case(entry: dict) -> str:
    """Same NO_OUTPUT_MARKER convention as Day 16 -- distinguishes a genuine
    generation failure from the literal string 'None' that could otherwise
    read as a plausible field value to the judge."""
    if entry["validation_verdict"] != "valid" or entry["parsed_output"] is None:
        return NO_OUTPUT_MARKER
    return json.dumps(entry["parsed_output"], indent=2, ensure_ascii=False)


def run_new(day18_results: list[dict], already_judged_ids: set[str]) -> list[dict]:
    prompt_template = load_prompt_template(JUDGE_PROMPT_FILE)
    to_run = [r for r in day18_results if r["id"] not in already_judged_ids]

    total = len(to_run)
    if total == 0:
        print("Nothing new to judge -- all requirement ids already have verdicts.")
        return []

    results = []
    for i, entry in enumerate(to_run, start=1):
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
            "day18_validation_verdict": entry["validation_verdict"],
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
    results_sorted = sorted(results, key=lambda r: int(r["id"].split("_")[-1]))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_day18_file": DAY18_OUTPUTS_FILE,
        "judge_prompt_file": JUDGE_PROMPT_FILE,
        "carried_over_from": EXISTING_VERDICTS_FILE,
        "note": (
            "req_01-req_10 carried over unchanged from Day16_judge_v2_verdicts.json. "
            "req_11-req_35 judged fresh on Day 18."
        ),
        "count": len(results_sorted),
        "results": results_sorted,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(results_sorted)} verdicts -> {OUTPUT_FILE}")


if __name__ == "__main__":
    day18_results = load_day18_outputs(DAY18_OUTPUTS_FILE)
    existing_verdicts = load_existing_verdicts(EXISTING_VERDICTS_FILE)
    existing_ids = {r["id"] for r in existing_verdicts}

    new_verdicts = run_new(day18_results, existing_ids)
    all_verdicts = existing_verdicts + new_verdicts
    save_results(all_verdicts)