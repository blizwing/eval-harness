"""
Day 11 — Four hard assertions over Day 9's generated outputs.

Does NOT call the model. Reads Day9_outputs.json (already generated) and
Day10_labels.json (ground truth, for context only — not used to pass/fail
anything here) and runs four deterministic checks per row:

    1. valid_json        — did the raw response parse as JSON at all?
    2. fields_present     — are all required schema fields present?
    3. non_empty          — are the present fields actually non-empty?
    4. under_token_cap    — is output_tokens under the cap?

Checks 1 and 2 are NOT reimplemented here. Day5_validate.py (via Day 9's
run) already computed this and stored the verdict in `validation_verdict`
and `validation_detail` — re-deriving JSON/field-presence logic in a second
place would create two validators that could silently drift apart. Day 11
reads that existing signal instead of recomputing it.

Checks 3 and 4 are new. Day 5's Pydantic schema enforces that a field
EXISTS and has the right type, but an empty string or empty list still
satisfies `str` / `list` — so emptiness slips through unnoticed today.
Nothing before Day 11 checks token count at all.

Token cap: 583 (2x median output_tokens across all 10 Day 9 rows, including
req_07 despite its validation failure — it still cost tokens to generate,
so it still belongs in the "what does normal generation cost look like"
calculation). This is a length-anomaly guardrail, not a hard cost ceiling:
it exists to flag a run that unexpectedly balloons (rambling, repetition,
disproportionate elaboration for a simple requirement), not to police
every run against a fixed budget. Expect all 10 rows to pass today — the
cap has nothing to catch yet. Revisit once Week 3's expanded requirement
set (30, with adversarial cases) gives it something to actually flag.
"""

import json
import urllib.request
from pathlib import Path

TOKEN_CAP = 583

# Fields the Day 7 prompt schema requires. Kept here (not imported) since
# Day 11 checks emptiness independently of whatever Day 5's Pydantic model
# enforces for presence/type.
REQUIRED_FIELDS = ["title", "description", "preconditions", "test_steps", "expected_result", "priority"]


def check_valid_json(row: dict) -> bool:
    """Reuses Day 9's validation_verdict rather than re-parsing raw_response_text.
    A verdict of 'invalid' due to malformed JSON would fail here; a verdict
    of 'invalid' due to a missing field (req_07's case) still means the JSON
    itself parsed fine, so this check passes independently of check 2.

    Checks validation_verdict directly rather than scanning validation_detail:
    Day5_validate.validate_response never actually tags a failure
    "json_error" — its invalid_json status carries a bare list of
    exception-message strings, not the (kind, msg) tuples the invalid
    (schema-mismatch) status uses. The old detail-scanning logic matched
    every prior "valid"/"invalid" row correctly by coincidence (the tag it
    searched for never occurs, so it never fired), but crashed on a real
    invalid_json row, whose detail list doesn't unpack as (kind, msg) at
    all. Found via Day 24's model-variant experiment — the first run to
    actually produce a malformed (non-JSON) response."""
    return row["validation_verdict"] != "invalid_json"


def check_fields_present(row: dict) -> bool:
    """Also reuses Day 9's validation_verdict — this IS what caught req_07."""
    return row["validation_verdict"] == "valid"


def check_non_empty(row: dict) -> bool:
    """New check. Only meaningful if parsed_output exists at all — a row
    that failed field-presence has nothing to check here, so it's marked
    False rather than trivially True."""
    parsed = row.get("parsed_output")
    if parsed is None:
        return False
    for field in REQUIRED_FIELDS:
        value = parsed.get(field)
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, list) and len(value) == 0:
            return False
    return True


def check_under_token_cap(row: dict) -> bool:
    """New check. Independent of validation outcome — token cost is real
    whether or not the output was usable."""
    return row["output_tokens"] <= TOKEN_CAP


def run_assertions(outputs: dict) -> list[dict]:
    results = []
    for row in outputs["results"]:
        results.append({
            "id": row["id"],
            "valid_json": check_valid_json(row),
            "fields_present": check_fields_present(row),
            "non_empty": check_non_empty(row),
            "under_token_cap": check_under_token_cap(row),
            "output_tokens": row["output_tokens"],
        })
    return results


def print_table(results: list[dict]) -> None:
    header = f"{'req_id':<8} {'valid_json':<12} {'fields_present':<16} {'non_empty':<11} {'under_cap':<11} {'tokens':<7}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['id']:<8} "
            f"{str(r['valid_json']):<12} "
            f"{str(r['fields_present']):<16} "
            f"{str(r['non_empty']):<11} "
            f"{str(r['under_token_cap']):<11} "
            f"{r['output_tokens']:<7}"
        )
    total_checks = len(results) * 4
    passed = sum(
        r["valid_json"] + r["fields_present"] + r["non_empty"] + r["under_token_cap"]
        for r in results
    )
    print("-" * len(header))
    print(f"Passed {passed}/{total_checks} checks across {len(results)} rows.")


def main():
    outputs = "Day9_Requirements_JSON_Outputs/Day9_outputs.json"
    results = run_assertions(json.load(open(outputs)))
    print_table(results)

    out_dir = Path(__file__).parent / "Day11_Assertion_Results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "Day11_results.json"
    with open(out_path, "w") as f:
        json.dump({"token_cap": TOKEN_CAP, "results": results}, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()