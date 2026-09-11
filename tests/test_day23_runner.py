import httpx
import openai
import anthropic
import pytest

import Day23_runner as runner
from Day3_llm_client import MeteredResult
from schemas import Requirement, RequirementSet

VALID_TESTCASE_JSON = (
    '{"title": "Login works", "description": "Verify login", '
    '"preconditions": ["user exists"], "test_steps": ["enter creds", "submit"], '
    '"expected_result": "dashboard shown", "priority": "high"}'
)


def make_metered(text=VALID_TESTCASE_JSON, cost=0.0001):
    return MeteredResult(
        schema="openai",
        text=text,
        input_tokens=10,
        output_tokens=20,
        stop_reason="stop",
        model_name="deepseek-v4-flash",
        latency_ms=5.0,
        cost_usd=cost,
        raw_response={},
    )


def openai_connection_error():
    return openai.APIConnectionError(request=httpx.Request("POST", "https://test.invalid"))


def anthropic_connection_error():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://test.invalid"))


class FakeClient:
    """Stands in for LLMClient — call_openai plays back a scripted list of
    outcomes (MeteredResult to return, or an Exception instance to raise),
    consumed one per call. No network, no real SDK involved."""

    def __init__(self, side_effects):
        self._side_effects = list(side_effects)
        self._i = 0

    def call_openai(self, prompt, temperature=0.0):
        outcome = self._side_effects[self._i]
        self._i += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def print_running_total(self):
        pass


def _fake_req_set(n):
    return RequirementSet(
        requirements=[Requirement(id=f"req_{i}", text=f"Requirement {i}") for i in range(1, n + 1)]
    )


# --- project_total_cost ---

def test_project_total_cost_none_when_no_costed_cases():
    assert runner.project_total_cost(0.0, 0, 10) is None


def test_project_total_cost_extrapolates():
    assert runner.project_total_cost(0.02, 2, 10) == pytest.approx(0.1)


# --- call_with_retry ---

def test_call_with_retry_succeeds_first_try():
    client = FakeClient([make_metered()])
    result, attempts, error = runner.call_with_retry(client, "prompt")
    assert result is not None
    assert attempts == 1
    assert error is None


def test_call_with_retry_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    client = FakeClient([openai_connection_error(), openai_connection_error(), make_metered()])
    result, attempts, error = runner.call_with_retry(client, "prompt")
    assert result is not None
    assert attempts == 3
    assert error is None


def test_call_with_retry_catches_both_provider_exception_families(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    client = FakeClient([openai_connection_error(), anthropic_connection_error(), make_metered()])
    result, attempts, error = runner.call_with_retry(client, "prompt")
    assert result is not None
    assert attempts == 3


def test_call_with_retry_exhausts_and_reports_error(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    client = FakeClient([openai_connection_error()] * (runner.MAX_RETRIES + 1))
    result, attempts, error = runner.call_with_retry(client, "prompt")
    assert result is None
    assert attempts == runner.MAX_RETRIES + 1
    assert "APIConnectionError" in error


def test_call_with_retry_does_not_retry_non_retryable_errors():
    client = FakeClient([ValueError("not retryable")])
    with pytest.raises(ValueError):
        runner.call_with_retry(client, "prompt")


# --- run_all: cost-cap abort + api_error handling ---

def test_run_all_aborts_when_projected_cost_exceeds_cap(monkeypatch):
    fake_client = FakeClient([make_metered(cost=0.01) for _ in range(3)])
    monkeypatch.setattr(runner, "load_requirements", lambda path: ("valid", _fake_req_set(3)))
    monkeypatch.setattr(runner, "load_prompt_template", lambda path: "{requirement}")
    monkeypatch.setattr(runner, "LLMClient", lambda: fake_client)

    results, abort_reason = runner.run_all(cost_cap=0.02)

    assert len(results) == 1
    assert abort_reason is not None
    assert "exceeds cap" in abort_reason


def test_run_all_completes_without_cap(monkeypatch):
    fake_client = FakeClient([make_metered(cost=0.01) for _ in range(3)])
    monkeypatch.setattr(runner, "load_requirements", lambda path: ("valid", _fake_req_set(3)))
    monkeypatch.setattr(runner, "load_prompt_template", lambda path: "{requirement}")
    monkeypatch.setattr(runner, "LLMClient", lambda: fake_client)

    results, abort_reason = runner.run_all(cost_cap=None)

    assert len(results) == 3
    assert abort_reason is None
    assert all(r.status == "valid" for r in results)


def test_run_all_records_api_error_and_continues(monkeypatch):
    fake_client = FakeClient(
        [openai_connection_error()] * (runner.MAX_RETRIES + 1) + [make_metered()]
    )
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setattr(runner, "load_requirements", lambda path: ("valid", _fake_req_set(2)))
    monkeypatch.setattr(runner, "load_prompt_template", lambda path: "{requirement}")
    monkeypatch.setattr(runner, "LLMClient", lambda: fake_client)

    results, abort_reason = runner.run_all(cost_cap=None)

    assert len(results) == 2
    assert results[0].status == "api_error"
    assert results[1].status == "valid"
    assert abort_reason is None
