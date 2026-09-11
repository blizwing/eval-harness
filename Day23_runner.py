"""
Day 23 — Runner: prompt against every case in a requirement set, with API
errors and rate limits handled via retry + backoff.

DONE WHEN: a run over the full requirement set completes even when some
calls fail.

Design notes:
- Retry/backoff wraps ONLY the API call (transient network/rate-limit
  errors). It does NOT wrap Day5_validate's schema validation — a
  malformed JSON response is a different failure mode (explored Day 4)
  and retrying won't fix a prompt/schema mismatch, it'll just burn calls.
- Uses Day3's LLMClient (not Day4's bare json_mode call) so latency and
  cost are captured now rather than bolted on later for Day 25 (Reporter).
  NOTE: LLMClient.call_openai defaults to temperature=1.0, but Day 9 and
  Day 18 both ran at temperature=0 (call_OpenAI_json_mode's default).
  TEMPERATURE below is set explicitly to 0.0 and passed on every call so
  Day 23's results stay comparable to prior runs and to Day 26's baseline.
- Input is Day22's typed RequirementSet, not a raw YAML dict — this is
  the first script in the repo that consumes Day 22's loader instead of
  re-parsing YAML itself.
- A case that exhausts retries is recorded with status "api_error" and
  the run continues — per Pratham's call, a single bad case should not
  kill a 35-case run.
- Day 31 cost guardrail: after each case, projects total spend as
  (cost accumulated so far / cases with a metered cost) * total case
  count, and aborts the run the moment that projection exceeds
  --cost-cap. This is a projection, not a hard per-call limit — it can
  only fire once at least one case has returned a real cost, so a cap
  smaller than a single call's cost (e.g. the $0.001 test value) aborts
  after case 1, not case 0. Partial results (everything completed
  before the abort) are still saved to the output file — those calls
  were already paid for — and the process exits 1 with a clear
  message. No cap is applied by default (--cost-cap omitted =
  unlimited), so this never changes behavior for existing local runs.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

import anthropic
import openai

from Day3_llm_client import LLMClient, MeteredResult
from Day5_validate import validate_response
from Day7_zeroshot_testcase import TestCase
from Day22_loader import load_requirements, RequirementSet
from schemas import CaseResult

REQUIREMENTS_FILE = "Day8_Project_Requirements/fsm_requirements.yaml"
PROMPT_FILE = "Day7_prompt_file/prompt_testcase_v1.txt"
OUTPUT_DIR = "Day23_Runner_Results"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Day23_run_results.json")

# Day 9 / Day 18 both ran via call_OpenAI_json_mode, whose default is
# temperature=0 — kept explicit here (LLMClient's own default is 1.0)
# so this runner stays comparable to those prior runs and to whatever
# baseline.json ends up being (Day 26).
TEMPERATURE = 0.0

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2.0  # doubles each retry: 2s, 4s, 8s

# Exceptions worth retrying — transient / rate-limit / server-side.
# Deliberately NOT catching auth errors (openai.AuthenticationError,
# anthropic.AuthenticationError) or bad-request errors — those won't
# fix themselves on retry and should surface immediately.
RETRYABLE_EXCEPTIONS = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
)

BAR_WIDTH = 30


def project_total_cost(cost_so_far: float, cases_with_cost: int, total_cases: int) -> float | None:
    """Extrapolates total run cost from cases completed so far. Returns
    None if no case has produced a real cost yet (nothing to project from)."""
    if cases_with_cost == 0:
        return None
    return (cost_so_far / cases_with_cost) * total_cases


def print_progress(current: int, total: int, req_id: str, status: str) -> None:
    filled = int(BAR_WIDTH * current / total)
    bar = "#" * filled + "-" * (BAR_WIDTH - filled)
    pct = int(100 * current / total)
    end = "\n" if current == total else ""
    print(f"\r[{bar}] {current}/{total} ({pct}%) last: {req_id} -> {status}", end=end, flush=True)


def load_prompt_template(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def call_with_retry(client: LLMClient, prompt: str) -> tuple[MeteredResult | None, int, str | None]:
    """
    Attempts client.call_openai(prompt) up to MAX_RETRIES+1 times with
    exponential backoff on retryable exceptions.

    Returns (metered_result, attempts_used, error_message).
    On success: (MeteredResult, N, None)
    On exhausted retries: (None, MAX_RETRIES + 1, "<last exception message>")
    """
    last_error: str | None = None
    for attempt in range(1, MAX_RETRIES + 2):  # +1 initial attempt, +1 for range exclusivity
        try:
            result = client.call_openai(prompt, temperature=TEMPERATURE)
            return result, attempt, None
        except RETRYABLE_EXCEPTIONS as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt <= MAX_RETRIES:
                backoff = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                print(f"\n  [retry] {last_error} — waiting {backoff:.0f}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(backoff)
            # else: fall through, loop ends, exhausted
    return None, MAX_RETRIES + 1, last_error


def run_all(
    requirements_file: str = REQUIREMENTS_FILE,
    prompt_file: str = PROMPT_FILE,
    cost_cap: float | None = None,
) -> tuple[list[CaseResult], str | None]:
    """
    Returns (results, abort_reason). abort_reason is None when every case
    ran to completion; otherwise it's a human-readable message explaining
    why the run stopped early (currently only the cost cap can trigger
    this).
    """
    status, payload = load_requirements(requirements_file)
    if status != "valid":
        raise RuntimeError(f"Cannot run — requirements file invalid: {status}: {payload}")

    req_set: RequirementSet = payload
    prompt_template = load_prompt_template(prompt_file)
    client = LLMClient()

    total = len(req_set.requirements)
    results: list[CaseResult] = []
    cost_so_far = 0.0
    cases_with_cost = 0
    abort_reason: str | None = None

    for i, req in enumerate(req_set.requirements, start=1):
        req_text = req.text.strip()
        prompt = prompt_template.format(requirement=req_text)

        metered, attempts, error_message = call_with_retry(client, prompt)

        if metered is None:
            case_result = CaseResult(
                id=req.id,
                requirement_text=req_text,
                status="api_error",
                attempts=attempts,
                error_message=error_message,
            )
            results.append(case_result)
            print_progress(i, total, req.id, "api_error")
            continue

        verdict, detail = validate_response(metered.text, TestCase)

        if verdict == "valid":
            parsed_output = detail.model_dump()
            validation_detail = None
        else:
            parsed_output = None
            validation_detail = detail

        case_result = CaseResult(
            id=req.id,
            requirement_text=req_text,
            status=verdict,
            parsed_output=parsed_output,
            raw_response_text=metered.text,
            validation_detail=validation_detail,
            attempts=attempts,
            metered=metered,
        )
        results.append(case_result)
        print_progress(i, total, req.id, verdict)

        cost_so_far += metered.cost_usd
        cases_with_cost += 1

        if cost_cap is not None:
            projected = project_total_cost(cost_so_far, cases_with_cost, total)
            if projected is not None and projected > cost_cap:
                abort_reason = (
                    f"projected total cost ${projected:.4f} exceeds cap ${cost_cap:.4f} "
                    f"(based on {cases_with_cost} case(s) costing ${cost_so_far:.4f} so far, "
                    f"projected across {total} total cases). Stopped after case {i}/{total}."
                )
                break

    client.print_running_total()
    return results, abort_reason


def serialize_case(r: CaseResult) -> dict:
    """Flattens a CaseResult into the dict row shape used by
    Day23_run_results.json (and consumed by Day24_scorer.score_case)."""
    entry = {
        "id": r.id,
        "requirement_text": r.requirement_text,
        "status": r.status,
        "attempts": r.attempts,
        "parsed_output": r.parsed_output,
        "raw_response_text": r.raw_response_text,
        "validation_detail": r.validation_detail,
        "error_message": r.error_message,
    }
    if r.metered is not None:
        entry["input_tokens"] = r.metered.input_tokens
        entry["output_tokens"] = r.metered.output_tokens
        entry["latency_ms"] = r.metered.latency_ms
        entry["cost_usd"] = r.metered.cost_usd
        entry["pricing_tier"] = r.metered.pricing_tier
    return entry


def save_results(
    results: list[CaseResult],
    source_file: str,
    prompt_file: str = PROMPT_FILE,
    output_file: str = OUTPUT_FILE,
    abort_reason: str | None = None,
) -> None:
    out_dir = os.path.dirname(output_file) or "."
    os.makedirs(out_dir, exist_ok=True)

    serializable = [serialize_case(r) for r in results]

    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_requirements_file": source_file,
        "prompt_file": prompt_file,
        "count": len(results),
        "status_counts": counts,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
        "results": serializable,
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(results)} results -> {output_file}")
    print(f"Status breakdown: {counts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 23 — run every requirement through the model.")
    parser.add_argument("--requirements-file", default=REQUIREMENTS_FILE)
    parser.add_argument(
        "--prompt-file",
        default=PROMPT_FILE,
        help="Override the prompt template — e.g. a sabotaged copy for Day 26 regression testing.",
    )
    parser.add_argument(
        "--output-file",
        default=OUTPUT_FILE,
        help="Where to save results. Use a different path for a sabotage run so it doesn't overwrite the real Day23_run_results.json.",
    )
    parser.add_argument(
        "--cost-cap",
        type=float,
        default=None,
        help="Abort the run if projected total cost (extrapolated from cases completed so far) exceeds this many USD. Default: no cap.",
    )
    args = parser.parse_args()

    results, abort_reason = run_all(args.requirements_file, args.prompt_file, args.cost_cap)
    save_results(results, args.requirements_file, args.prompt_file, args.output_file, abort_reason)

    if abort_reason:
        print(f"\n[COST CAP EXCEEDED] {abort_reason}")
        raise SystemExit(1)