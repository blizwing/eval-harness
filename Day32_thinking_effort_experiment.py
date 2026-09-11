"""
Follow-up (Fri 11 Sep 2026) — does generator thinking effort reduce the
hedging behavior in `expected_result` that collapsed judge_pass_rate after
DeepSeek's V4.1-Flash swap (see NOTES.md's "Incident closed" entry)?

Unlike Day24_model_variant_experiment.py (which swapped model AND thinking
on BOTH generation and judging together, so an effect couldn't be
attributed to either side alone), this isolates the generator: thinking
effort varies only for the requirement -> test-case generation step. The
judge is held fixed (deepseek-v4-flash, thinking disabled, judge_v2.txt) —
exactly the harness's current default judge config — so any verdict shift
is attributable to what changed on the generator side.

Requirement set: the two existing curated "ambiguous" sets, rather than a
fresh one-off sample —
  - Day24_Borderline_Smoketest/borderline_requirements.yaml (5, hand-
    written to target good/borderline/bad specifically)
  - Day17's 5 real-dataset adversarial requirements (req_24, req_25,
    req_33, req_34, req_35), pulled live from
    Day8_Project_Requirements/fsm_requirements.yaml by id rather than
    copy-pasted, so this can't silently drift from the real dataset text.

Thinking configs tried per requirement: disabled (current harness
default), low, high, max.

Round 1 (this repo's history) ran disabled/low/high at max_tokens=2048
and found req_b03's `low` config got truncated into invalid_json — 1998
of the 2048 budget went to reasoning, leaving too little room for the
actual JSON. Round 2 (this version) raises max_tokens to 8192 (~4x the
worst reasoning-token count observed in round 1) and reruns ALL FOUR
configs, including the previously-skipped disabled/low/high, so nothing
here is confounded by mixing an old token-capped run with new data.
`max` still isn't given the full 384K DeepSeek's docs describe as the
truncation-safe ceiling — 8192 is a deliberate, cost-bounded R&D choice,
not an attempt to guarantee zero truncation at every effort level.

Usage:
    python Day32_thinking_effort_experiment.py
"""

import json
from pathlib import Path

from Day1_first_call import clientOpenAI, MODEL
from Day5_validate import validate_response
from Day12_LLM_Judge import NO_OUTPUT_MARKER, judge_single_case, load_prompt_template
from Day22_loader import load_requirements
from Day24_scorer import score_assertions
from schemas import TestCase, JudgeScore

BORDERLINE_FIXTURE = "Day24_Borderline_Smoketest/borderline_requirements.yaml"
REAL_DATASET = "Day8_Project_Requirements/fsm_requirements.yaml"
ADVERSARIAL_IDS = ("req_24", "req_25", "req_33", "req_34", "req_35")

GEN_PROMPT_FILE = "Day7_prompt_file/prompt_testcase_v1.txt"
JUDGE_PROMPT_FILE = "Day15_Judge_Rubric_V2/judge_v2.txt"
EXPERIMENT_MAX_TOKENS = 8192

THINKING_CONFIGS = [
    ("disabled", False, None),
    ("low", True, "low"),
    ("high", True, "high"),
    ("max", True, "max"),
]

def _output_file(max_tokens: int) -> str:
    """Bakes max_tokens into the filename so a rerun under different token
    budgets (round 1 was 2048, this round is 8192) can't silently overwrite
    a prior round's data the way a fixed filename did."""
    return f"Day32_thinking_effort_experiment_results_maxtok{max_tokens}.json"


OUTPUT_FILE = _output_file(EXPERIMENT_MAX_TOKENS)


def load_ambiguous_requirements() -> list[dict]:
    reqs = []

    status, payload = load_requirements(BORDERLINE_FIXTURE)
    if status != "valid":
        raise RuntimeError(f"Cannot load {BORDERLINE_FIXTURE}: {status}: {payload}")
    for r in payload.requirements:
        reqs.append({"id": r.id, "text": r.text.strip(), "source": "day24_borderline"})

    status, payload = load_requirements(REAL_DATASET)
    if status != "valid":
        raise RuntimeError(f"Cannot load {REAL_DATASET}: {status}: {payload}")
    for r in payload.requirements:
        if r.id in ADVERSARIAL_IDS:
            reqs.append({"id": r.id, "text": r.text.strip(), "source": "day17_adversarial"})

    return reqs


def generate(req_text: str, gen_prompt_template: str, thinking_enabled: bool, reasoning_effort: str | None) -> dict:
    prompt = gen_prompt_template.format(requirement=req_text)
    kwargs = dict(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        extra_body={"thinking": {"type": "enabled" if thinking_enabled else "disabled"}},
        max_tokens=EXPERIMENT_MAX_TOKENS,
        temperature=0.0,
        stream=False,
    )
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort

    response = clientOpenAI.chat.completions.create(**kwargs)
    text = response.choices[0].message.content
    usage = response.usage
    reasoning_tokens = 0
    details = getattr(usage, "completion_tokens_details", None)
    if details is not None and getattr(details, "reasoning_tokens", None) is not None:
        reasoning_tokens = details.reasoning_tokens

    status, detail = validate_response(text, TestCase)
    return {
        "status": status,
        "parsed_output": detail.model_dump() if status == "valid" else None,
        "raw_response_text": text,
        "output_tokens": usage.completion_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def format_test_case_for_row(row: dict) -> str:
    if row["status"] != "valid" or row["parsed_output"] is None:
        return NO_OUTPUT_MARKER
    return json.dumps(row["parsed_output"], indent=2, ensure_ascii=False)


def main() -> None:
    requirements = load_ambiguous_requirements()
    gen_prompt_template = load_prompt_template(GEN_PROMPT_FILE)
    judge_prompt_template = load_prompt_template(JUDGE_PROMPT_FILE)

    results = []

    for req in requirements:
        for config_label, thinking_enabled, reasoning_effort in THINKING_CONFIGS:
            print(f"{req['id']} [{config_label}]: generating...", flush=True)
            gen_row = generate(req["text"], gen_prompt_template, thinking_enabled, reasoning_effort)
            gen_row["id"] = req["id"]

            assertion_result = score_assertions(
                {**gen_row, "validation_verdict": gen_row["status"]}
            )

            print(f"{req['id']} [{config_label}]: judging (judge fixed: thinking disabled)...", flush=True)
            test_case_str = format_test_case_for_row(gen_row)
            _, judge_status, judge_detail = judge_single_case(
                req["text"], test_case_str, judge_prompt_template, JudgeScore,
                model=MODEL, thinking_enabled=False,
            )

            entry = {
                "id": req["id"],
                "source": req["source"],
                "requirement_text": req["text"],
                "thinking_config": config_label,
                "gen_status": gen_row["status"],
                "gen_output_tokens": gen_row["output_tokens"],
                "gen_reasoning_tokens": gen_row["reasoning_tokens"],
                "parsed_output": gen_row["parsed_output"],
                "assertion_passed": assertion_result.passed,
                "judge_status": judge_status,
            }
            if judge_status == "valid":
                assert isinstance(judge_detail, JudgeScore)
                entry["judge_verdict"] = judge_detail.verdict
                entry["judge_reasoning"] = judge_detail.reasoning
            else:
                entry["judge_verdict"] = f"JUDGE_{judge_status.upper()}"
                entry["judge_reasoning"] = None

            results.append(entry)
            print(
                f"  -> gen_status={entry['gen_status']:<10} "
                f"reasoning_tokens={entry['gen_reasoning_tokens']:<5} "
                f"assertions_passed={entry['assertion_passed']} "
                f"judge_verdict={entry['judge_verdict']}"
            )

            # Checkpoint after every row, not just once at the end — a crash
            # or a long `max`-effort call hanging shouldn't lose every row
            # that already completed and was already paid for.
            Path(OUTPUT_FILE).write_text(
                json.dumps({"results": results}, indent=2, ensure_ascii=False)
            )

    print(f"\nSaved {len(results)} rows -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
