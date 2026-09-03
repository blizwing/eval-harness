"""
Day 24 — Model-variant experiment: can a stronger/reasoning model reach the
judge's "borderline" verdict where deepseek-v4-flash (thinking disabled)
never did across two full smoketest runs?

Runs the same 5 requirements from Day24_Borderline_Smoketest/ through
BOTH the generation step (Day 7's prompt) and the judge step (judge_v2.txt)
using the same model config per trial — this is a whole-pipeline swap, not
an isolated ablation, so a shift in verdict can't be attributed to the
generator or the judge alone from this data. If a config surfaces
something interesting, follow up by varying just one side to isolate it.

Configs tried, each once (deliberately not repeated — this is a
"can it happen at all" check, not a statistical run):
  1. deepseek-v4-flash, thinking enabled
  2. deepseek-v4-pro,   thinking disabled
  3. deepseek-v4-pro,   thinking enabled

max_tokens raised to 2048 for all calls here (vs. the harness's normal
1024) — thinking-enabled responses spend real output tokens on reasoning
before the final answer; 1024 risked truncating that mid-JSON.

Bypasses Day23_runner.run_all() and Day24_scorer.score_case() by design —
neither accepts a model override, and this is a one-off experiment, not a
change to the harness's actual run/score path. Reuses score_assertions
(already row-shape-generic) and judge_single_case (now accepts overrides)
directly instead.

Usage:
    python3 Day24_model_variant_experiment.py
"""

import json

from Day1_first_call import callOpenAISchemaAPI
from Day5_validate import validate_response
from Day12_LLM_Judge import NO_OUTPUT_MARKER, judge_single_case, load_prompt_template
from Day22_loader import load_requirements
from Day24_scorer import score_assertions
from schemas import TestCase, JudgeScore

FIXTURE_PATH = "Day24_Borderline_Smoketest/borderline_requirements.yaml"
GEN_PROMPT_FILE = "Day7_prompt_file/prompt_testcase_v1.txt"
JUDGE_PROMPT_FILE = "Day15_Judge_Rubric_V2/judge_v2.txt"
EXPERIMENT_MAX_TOKENS = 4096

CONFIGS = [
    ("flash+thinking", "deepseek-v4-flash", True),
    ("pro", "deepseek-v4-pro", False),
    ("pro+thinking", "deepseek-v4-pro", True),
]


def build_row(req_id: str, req_text: str, gen_prompt: str, model: str, thinking: bool) -> dict:
    call_result = callOpenAISchemaAPI(
        gen_prompt, temperature=0.0, model=model, thinking_enabled=thinking, max_tokens=EXPERIMENT_MAX_TOKENS
    )
    status, detail = validate_response(call_result.text, TestCase)
    return {
        "id": req_id,
        "requirement_text": req_text,
        "status": status,
        "parsed_output": detail.model_dump() if status == "valid" else None,
        "raw_response_text": call_result.text,
        "validation_detail": None if status == "valid" else detail,
        "output_tokens": call_result.output_tokens,
    }


def format_test_case_for_row(row: dict) -> str:
    if row["status"] != "valid" or row["parsed_output"] is None:
        return NO_OUTPUT_MARKER
    return json.dumps(row["parsed_output"], indent=2, ensure_ascii=False)


def main() -> None:
    status, payload = load_requirements(FIXTURE_PATH)
    if status != "valid":
        raise RuntimeError(f"Cannot run — fixture invalid: {status}: {payload}")

    gen_prompt_template = load_prompt_template(GEN_PROMPT_FILE)
    judge_prompt_template = load_prompt_template(JUDGE_PROMPT_FILE)

    observed_verdicts: set[str] = set()

    for label, model, thinking in CONFIGS:
        print(f"\n{'=' * 60}\nCONFIG: {label} (model={model}, thinking_enabled={thinking})\n{'=' * 60}")

        for req in payload.requirements:
            req_text = req.text.strip()
            print(f"\n  {req.id}: generating...", flush=True)
            gen_prompt = gen_prompt_template.format(requirement=req_text)
            row = build_row(req.id, req_text, gen_prompt, model, thinking)
            assertion_result = score_assertions(row)

            print(f"  {req.id}: judging...", flush=True)
            test_case_str = format_test_case_for_row(row)
            call_result, judge_status, judge_detail = judge_single_case(
                req_text, test_case_str, judge_prompt_template, JudgeScore,
                model=model, thinking_enabled=thinking, max_tokens=EXPERIMENT_MAX_TOKENS,
            )

            if judge_status != "valid":
                print(
                    f"  {req.id}: JUDGE VALIDATION FAILED ({judge_status}): {judge_detail} "
                    f"[stop_reason={call_result.stop_reason} output_tokens={call_result.output_tokens} "
                    f"raw_text={call_result.text!r}]"
                )
                continue

            assert isinstance(judge_detail, JudgeScore)
            observed_verdicts.add(judge_detail.verdict)
            print(
                f"  {req.id}: gen_status={row['status']:<10} assertions_passed={assertion_result.passed} "
                f"judge_verdict={judge_detail.verdict}"
            )
            print(f"    reasoning: {judge_detail.reasoning}")

    print(f"\n{'=' * 60}")
    print(f"Verdict buckets observed across all configs: {sorted(observed_verdicts)}")
    print(f"Borderline path reached: {'borderline' in observed_verdicts}")


if __name__ == "__main__":
    main()
