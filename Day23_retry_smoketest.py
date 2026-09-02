"""
Day 23 — Retry/backoff smoke test.

Verifies the runner's retry logic against a REAL broken endpoint (not a
mock) — sets DEEPSEEK_OPENAI_BASE_URL to an unreachable host before any
other module is imported, so Day1_first_call.py's clientOpenAI is built
pointing at nothing. This should produce a genuine openai.APIConnectionError,
which is exactly one of the exceptions Day23_runner.py's RETRYABLE_EXCEPTIONS
catches.

Usage:
    python3 Day23_retry_smoketest.py

Does NOT touch your real .env, real requirements file, or Day23's normal
output file — writes to its own throwaway paths and deletes them after.

Reverts cleanly: the env var override only exists for this process; nothing
written to disk that isn't cleaned up at the end (fixture yaml + result json).
"""

import os

# MUST happen before importing Day1_first_call (or anything that imports
# it), since clientOpenAI is constructed at module import time.
os.environ["DEEPSEEK_OPENAI_BASE_URL"] = "https://api.deepseek.invalid"

import json
import yaml

from Day22_loader import load_requirements
from Day23_runner import run_all, save_results, OUTPUT_FILE

FIXTURE_PATH = "Day23_smoketest_fixture.yaml"
SOURCE_REQUIREMENTS = "Day8_Project_Requirements/fsm_requirements.yaml"


def make_one_requirement_fixture() -> None:
    """Pull just the first requirement from the real dataset so the smoke
    test exercises real data shape without burning a full run."""
    status, payload = load_requirements(SOURCE_REQUIREMENTS)
    if status != "valid":
        raise RuntimeError(f"Cannot build fixture — source file invalid: {status}: {payload}")

    first_req = payload.requirements[0]
    fixture = {"requirements": [{"id": first_req.id, "text": first_req.text}]}

    with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
        yaml.dump(fixture, f)


def cleanup() -> None:
    for path in (FIXTURE_PATH, OUTPUT_FILE):
        if os.path.exists(path):
            os.remove(path)
    # OUTPUT_FILE lives inside Day23_Runner_Results/ — remove the dir only
    # if this smoke test is the one that created it and it's now empty.
    out_dir = os.path.dirname(OUTPUT_FILE)
    if os.path.isdir(out_dir) and not os.listdir(out_dir):
        os.rmdir(out_dir)


def main() -> None:
    print(f"[smoketest] DEEPSEEK_OPENAI_BASE_URL override -> {os.environ['DEEPSEEK_OPENAI_BASE_URL']}")
    print("[smoketest] Building 1-requirement fixture from real dataset...")
    make_one_requirement_fixture()

    print("[smoketest] Running Day23's run_all against the broken endpoint...")
    print("[smoketest] Expect 3 retries with backoff (~2s, 4s, 8s), then an api_error record.\n")

    results = run_all(requirements_file=FIXTURE_PATH)
    save_results(results, FIXTURE_PATH)

    assert len(results) == 1, f"Expected 1 result, got {len(results)}"
    case = results[0]

    print("\n[smoketest] --- Result ---")
    print(f"  status:        {case.status}")
    print(f"  attempts:      {case.attempts}")
    print(f"  error_message: {case.error_message}")

    passed = (
        case.status == "api_error"
        and case.attempts == 4  # 1 initial + 3 retries
        and case.error_message is not None
        and "APIConnectionError" in case.error_message
    )

    print(f"\n[smoketest] {'PASS' if passed else 'FAIL'}")
    if not passed:
        print("[smoketest] Expected status='api_error', attempts=4, error_message containing 'APIConnectionError'.")
        print("[smoketest] Got something else — inspect the run above before trusting Day 23's retry path.")

    cleanup()
    print("[smoketest] Cleaned up fixture and output files.")

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()