from typing import Literal
from pydantic import BaseModel
from Day4_json_mode import call_OpenAI_json_mode
from Day5_validate import validate_response


class TestCase(BaseModel):
    title: str
    description: str
    preconditions: list[str]
    test_steps: list[str]
    expected_result: str
    priority: Literal["low", "medium", "high"]

test_cases = {
    "Create secret note successfully": (
        "User opens /create, enters message \"Meet at 7 PM behind library\", optional burn-after-read enabled, submits form. "
        "System generates unique tokenized URL like https://<host>/v/<token> and 6-digit passcode, stores encrypted payload with " 
        "status UNREAD, view_count=0, max_views=1, and expiry created_at + configured TTL. "
        "Expected: response page shows shareable link + passcode once, DB record exists, no plaintext message stored."
    ),
    "Reject empty message": (
        "User submits create form with message field empty or whitespace only, burn-after-read checked or unchecked. "
        "Expected: HTTP 400 (or validation message), no link/passcode generated, no DB insert."
    ),
    "Enforce max message size": (
        "User submits message exceeding allowed length (e.g., 10,001 chars if limit=10,000). "
        "Expected: validation error with size limit text, no secret created, no partial persistence."
    ),
    "Passcode format validation on create": (
    "Force passcode generator output checks for exactly 6 numeric digits; create 1,000 notes in loop. "
    r"Expected: each passcode matches regex `^\d{6}$`; no null/alpha/special chars."
    ),
    "Access note landing page with valid token" : (
        "Recipient opens valid link /v/<token>, sees passcode prompt only (not note content). "
        "Expected: token recognized, note state still UNREAD, no content leak in HTML/source/meta tags."
    ),
    "Access note with invalid token" :(
        "Recipient opens /v/not-a-real-token. "
        "Expected: generic \"not found or expired\" page, no hint whether token ever existed, HTTP 404/410 based on design."
    ),
    "Correct passcode reveals note first time": (
        "Given valid token + correct passcode, recipient submits passcode. "
        "Expected: note content rendered once, state transitions UNREAD -> READ/DESTROYED, view_count increments to 1, destruction timestamp recorded."
    ),
    "Wrong passcode denies access" : (
        "Given valid token + wrong passcode, recipient submits incorrect code. "
        "Expected: access denied message, state remains UNREAD, view_count unchanged, failed-attempt counter increments."
    ),
    "Brute-force protection / lockout" : (
        "After successful first read, same recipient refreshes page or revisits link and passcode. "
        "Expected: message unavailable (\"already viewed\"), no content returned from backend, state remains destroyed."
    ),
    "Race condition: two recipients opening simultaneously": (
        "Two clients submit correct passcode for same token at near-same time (parallel requests). "
        "Expected: exactly one request receives content, other gets already viewed/invalid response; no duplicate successful reads."
    )
}

if __name__ == "__main__":
    for name, requirement in test_cases.items():
        with open("Day7_prompt_file/prompt_testcase_v1.txt", "r", encoding="utf-8") as f:
            PROMPT = f.read()
        raw_response = call_OpenAI_json_mode(PROMPT.format(requirement=requirement))
        result = validate_response(raw_response.text, TestCase)
        print(name, "->", result)
