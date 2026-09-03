"""
Day 24 — schemas.py: every domain Pydantic model in one place.

Consolidates models that were previously scattered across the files that
first needed them (Day22_loader.py, Day7_zeroshot_testcase.py,
Day12_LLM_Judge.py, Day23_runner.py). Pure extraction — no behavior change
to any of those models. MeteredResult stays in Day3_llm_client.py (it's a
metering concern, not a domain schema) and is only imported here for
CaseResult's field annotation.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from Day3_llm_client import MeteredResult


# --- Day 22: dataset loader ---

class Requirement(BaseModel):
    id: str
    text: str = Field(min_length=1)


class RequirementSet(BaseModel):
    requirements: list[Requirement]

    @model_validator(mode="after")
    def check_unique_ids(self):
        ids = [r.id for r in self.requirements]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"Duplicate requirement id(s): {sorted(dupes)}")
        return self


# --- Day 7: zero-shot test case generation ---

class TestCase(BaseModel):
    title: str
    description: str
    preconditions: list[str]
    test_steps: list[str]
    expected_result: str
    priority: Literal["low", "medium", "high"]


# --- Day 12: LLM-as-a-judge (v1, 3 criteria) ---

class JudgeVerdict(BaseModel):
    field_completeness: Literal["pass", "fail"]
    requirement_coverage: Literal["pass", "fail"]
    specificity: Literal["pass", "fail"]
    verdict: Literal["good", "bad", "borderline"]
    reasoning: str


# --- Day 23: runner ---

class CaseResult(BaseModel):
    id: str
    requirement_text: str
    status: str  # "valid" | "invalid_schema" | "invalid_json" | "api_error"
    parsed_output: dict | None = None
    raw_response_text: str | None = None
    validation_detail: object = None
    attempts: int = 1
    metered: MeteredResult | None = Field(default=None, repr=False)
    error_message: str | None = None
