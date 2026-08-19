"""
Day 9 — run Day 7's zero-shot test-case prompt against all 10 of Day 8's
hand-written FSM requirements. Save every raw response + validation verdict
to one combined JSON file so they can be read and manually labeled.

DONE WHEN: 10 output files, plus a note of which are wrong.
(Interpreted per Pratham's choice: 10 results in one combined file, not
10 separate files — folder still named per-requirement in spirit.)
"""

import json
import os
from datetime import datetime, timezone

import yaml

from Day4_json_mode import call_OpenAI_json_mode
from Day5_validate import validate_response
from Day7_zeroshot_testcase import TestCase

REQUIREMENTS_FILE = "Day8_Project_Requirements/fsm_requirements.yaml"
PROMPT_FILE = "Day7_prompt_file/prompt_testcase_v1.txt"
OUTPUT_DIR = "Day9_Requirements_JSON_Outputs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Day9_outputs.json")

BAR_WIDTH = 30


def print_progress(current: int, total: int, req_id: str, verdict: str) -> None:
    filled = int(BAR_WIDTH * current / total)
    bar = "#" * filled + "-" * (BAR_WIDTH - filled)
    pct = int(100 * current / total)
    # \r overwrites the same line; final call adds a newline so the summary
    # print afterward doesn't collide with the bar.
    end = "\n" if current == total else ""
    print(f"\r[{bar}] {current}/{total} ({pct}%) last: {req_id} -> {verdict}", end=end, flush=True)


def load_requirements(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["requirements"]


def load_prompt_template(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def run_all() -> list[dict]:
    requirements = load_requirements(REQUIREMENTS_FILE)
    prompt_template = load_prompt_template(PROMPT_FILE)

    total = len(requirements)
    results = []
    for i, req in enumerate(requirements, start=1):
        req_id = req["id"]
        req_text = req["text"].strip()

        prompt = prompt_template.format(requirement=req_text)
        call_result = call_OpenAI_json_mode(prompt)
        verdict, detail = validate_response(call_result.text, TestCase)

        if verdict == "valid":
            # detail is a TestCase instance here — make it JSON-serializable
            parsed_output = detail.model_dump()
            failure_detail = None
        else:
            parsed_output = None
            failure_detail = detail

        entry = {
            "id": req_id,
            "requirement_text": req_text,
            "raw_response_text": call_result.text,
            "validation_verdict": verdict,
            "validation_detail": failure_detail,
            "parsed_output": parsed_output,
            "input_tokens": call_result.input_tokens,
            "output_tokens": call_result.output_tokens,
            "model_name": call_result.model_name,
        }
        results.append(entry)
        print_progress(i, total, req_id, verdict)

    return results


def save_results(results: list[dict]) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_requirements_file": REQUIREMENTS_FILE,
        "prompt_file": PROMPT_FILE,
        "count": len(results),
        "results": results,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(results)} results -> {OUTPUT_FILE}")


if __name__ == "__main__":
    results = run_all()
    save_results(results)