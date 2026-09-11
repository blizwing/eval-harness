from datetime import datetime, timezone

import Day3_llm_client as llm_client
from Day3_llm_client import LLMClient, is_peak_hour

MON = (2026, 9, 14)  # Monday
SAT = (2026, 9, 19)  # Saturday
SUN = (2026, 9, 20)  # Sunday


def utc(date_tuple, hour, minute=0):
    y, m, d = date_tuple
    return datetime(y, m, d, hour, minute, tzinfo=timezone.utc)


# --- is_peak_hour: window boundaries ---

def test_peak_window_one_start_inclusive():
    assert is_peak_hour(utc(MON, 1, 0)) is True


def test_just_before_peak_window_one_is_off_peak():
    assert is_peak_hour(utc(MON, 0, 59)) is False


def test_peak_window_one_end_is_exclusive_and_off_peak():
    assert is_peak_hour(utc(MON, 4, 0)) is False


def test_gap_between_peak_windows_is_off_peak():
    assert is_peak_hour(utc(MON, 5, 0)) is False


def test_peak_window_two_start_inclusive():
    assert is_peak_hour(utc(MON, 6, 0)) is True


def test_peak_window_two_last_included_minute():
    assert is_peak_hour(utc(MON, 9, 59)) is True


def test_peak_window_two_end_is_exclusive_and_off_peak():
    assert is_peak_hour(utc(MON, 10, 0)) is False


# --- is_peak_hour: weekend override ---

def test_saturday_is_off_peak_even_during_peak_hour():
    assert is_peak_hour(utc(SAT, 2, 0)) is False


def test_sunday_is_off_peak_even_during_peak_hour():
    assert is_peak_hour(utc(SUN, 7, 0)) is False


# --- LLMClient._cost: correct rate applied per tier ---

def test_cost_uses_off_peak_rate():
    cost = LLMClient._cost(input_tokens=1_000_000, output_tokens=1_000_000, peak=False)
    expected = llm_client.OFF_PEAK_INPUT_COST_PER_1M + llm_client.OFF_PEAK_OUTPUT_COST_PER_1M
    assert cost == expected


def test_cost_uses_peak_rate():
    cost = LLMClient._cost(input_tokens=1_000_000, output_tokens=1_000_000, peak=True)
    expected = llm_client.PEAK_INPUT_COST_PER_1M + llm_client.PEAK_OUTPUT_COST_PER_1M
    assert cost == expected


def test_peak_rate_is_strictly_more_expensive_than_off_peak():
    off_peak = LLMClient._cost(input_tokens=1000, output_tokens=1000, peak=False)
    peak = LLMClient._cost(input_tokens=1000, output_tokens=1000, peak=True)
    assert peak > off_peak
