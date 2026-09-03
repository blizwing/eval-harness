"""
Day 12 — LLM-as-a-judge. Run the named-criteria judge prompt against all 10
of Day 9's generated test cases (requirement + generated output pairs).
Save verdicts alongside Day 10's human ground-truth labels.

DONE WHEN: 10 judge verdicts saved alongside your 10 human labels.

Note: req_07 has parsed_output=None (Day 9's validator marked it invalid).
That's a real state, not a bug — the judge must be able to score "no usable
output was produced" as a failure of field_completeness, so we pass an
explicit marker string instead of silently formatting None into the prompt.
"""

import json
import os
from datetime import datetime, timezone

from pydantic import BaseModel

from Day1_first_call import MODEL, MAX_TOKENS
from Day4_json_mode import call_OpenAI_json_mode
from Day5_validate import validate_response
from schemas import JudgeVerdict

DAY9_OUTPUTS_FILE = "Day9_Requirements_JSON_Outputs/Day9_outputs.json"
JUDGE_PROMPT_FILE = "Day12_Judge_LLM_Data/judge_llm_prompt.txt"
OUTPUT_DIR = "Day12_Judge_LLM_Data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Day12_judge_llm_verdicts.json")

BAR_WIDTH = 30

NO_OUTPUT_MARKER = "NO VALID OUTPUT WAS PRODUCED (validation_verdict != 'valid')"


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


def judge_single_case(
    requirement_text: str,
    test_case_str: str,
    prompt_template: str,
    verdict_model: type[BaseModel] = JudgeVerdict,
    model: str = MODEL,
    thinking_enabled: bool = False,
    max_tokens: int = MAX_TOKENS,
):
    """Formats the judge prompt for one (requirement, test case) pair, calls
    the model, and validates the response against verdict_model. Extracted
    so callers other than run_all() (e.g. Day 24's scorer, which judges
    Day 23's rows rather than Day 9's file) can judge a single case without
    going through run_all()'s Day-9-shaped loop. model/thinking_enabled/
    max_tokens default to run_all()'s existing behavior (deepseek-v4-flash,
    thinking disabled) — added for the Day 24 model-variant experiment,
    which needs to swap these per call."""
    prompt = prompt_template.format(
        requirement_text=requirement_text,
        test_case_json=test_case_str,
    )
    call_result = call_OpenAI_json_mode(
        prompt, model=model, thinking_enabled=thinking_enabled, max_tokens=max_tokens
    )
    judge_status, judge_detail = validate_response(call_result.text, verdict_model)
    return call_result, judge_status, judge_detail


def run_all() -> list[dict]:
    day9_results = load_day9_outputs(DAY9_OUTPUTS_FILE)
    prompt_template = load_prompt_template(JUDGE_PROMPT_FILE)

    total = len(day9_results)
    results = []
    for i, entry in enumerate(day9_results, start=1):
        req_id = entry["id"]
        req_text = entry["requirement_text"]
        test_case_str = format_test_case(entry)

        call_result, judge_status, judge_detail = judge_single_case(
            req_text, test_case_str, prompt_template, JudgeVerdict
        )

        if judge_status == "valid":
            assert isinstance(judge_detail, JudgeVerdict)
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