"""
Day 18 — run Day 7's zero-shot test-case prompt against the 25 new FSM
requirements added on Day 17 (req_11–req_35). Carry over the existing 10
results from Day 9 unchanged and merge everything into one combined file.

Same per-entry schema and pipeline as Day9_run_outputs.py
(call_OpenAI_json_mode -> validate_response -> TestCase). The 10 Day 9
entries are copied verbatim from Day9_outputs.json — not regenerated.

DONE WHEN: Day18_Full_Set/Day18_outputs.json exists with 35 total results
(10 carried over + 25 new).
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
CARRYOVER_FILE = "Day9_Requirements_JSON_Outputs/Day9_outputs.json"
OUTPUT_DIR = "Day18_Full_Set"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Day18_outputs.json")

BAR_WIDTH = 30


def print_progress(current: int, total: int, req_id: str, verdict: str) -> None:
    filled = int(BAR_WIDTH * current / total)
    bar = "#" * filled + "-" * (BAR_WIDTH - filled)
    pct = int(100 * current / total)
    end = "\n" if current == total else ""
    print(f"\r[{bar}] {current}/{total} ({pct}%) last: {req_id} -> {verdict}", end=end, flush=True)


def load_requirements(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["requirements"]


def load_prompt_template(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_carryover(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["results"]


def generate_entry(req: dict, prompt_template: str) -> dict:
    req_id = req["id"]
    req_text = req["text"].strip()

    prompt = prompt_template.format(requirement=req_text)
    call_result = call_OpenAI_json_mode(prompt)
    verdict, detail = validate_response(call_result.text, TestCase)

    if verdict == "valid":
        parsed_output = detail.model_dump()
        failure_detail = None
    else:
        parsed_output = None
        failure_detail = detail

    return {
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


def run() -> tuple[list[dict], list[dict]]:
    requirements = load_requirements(REQUIREMENTS_FILE)
    prompt_template = load_prompt_template(PROMPT_FILE)
    carried = load_carryover(CARRYOVER_FILE)

    carried_ids = {entry["id"] for entry in carried}
    new_requirements = [req for req in requirements if req["id"] not in carried_ids]

    total = len(new_requirements)
    new_results = []
    for i, req in enumerate(new_requirements, start=1):
        entry = generate_entry(req, prompt_template)
        new_results.append(entry)
        print_progress(i, total, entry["id"], entry["validation_verdict"])

    return carried, new_results


def save_results(carried: list[dict], new_results: list[dict]) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    merged = carried + new_results
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_requirements_file": REQUIREMENTS_FILE,
        "prompt_file": PROMPT_FILE,
        "carried_over_from": CARRYOVER_FILE,
        "carried_over_count": len(carried),
        "new_count": len(new_results),
        "count": len(merged),
        "results": merged,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(merged)} results ({len(carried)} carried + {len(new_results)} new) -> {OUTPUT_FILE}")


def report_new(new_results: list[dict]) -> None:
    valid = [e for e in new_results if e["validation_verdict"] == "valid"]
    other = [e for e in new_results if e["validation_verdict"] != "valid"]
    print(f"\nnew results: {len(valid)}/{len(new_results)} valid, {len(other)} not valid")
    for e in other:
        print(f"  {e['id']}: {e['validation_verdict']} -> {e['validation_detail']}")


if __name__ == "__main__":
    carried, new_results = run()
    save_results(carried, new_results)
    report_new(new_results)
