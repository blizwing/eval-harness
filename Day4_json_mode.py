import json

from Day1_first_call import CallResult, clientOpenAI, MODEL, MAX_TOKENS

def call_OpenAI_json_mode(
    prompt: str,
    temperature: float = 0,
    model: str = MODEL,
    thinking_enabled: bool = False,
    max_tokens: int = MAX_TOKENS,
) -> CallResult:
    response = clientOpenAI.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        extra_body={"thinking": {"type": "enabled" if thinking_enabled else "disabled"}},
        max_tokens=max_tokens,
        temperature=temperature,
        stream=False,
        response_format={
        'type': 'json_object'
    }
    )

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("OpenAI response had no content (message.content was None)")

    usage = response.usage
    if usage is None:
        raise ValueError("OpenAI response had no usage data")

    return CallResult(
        schema="openai",
        raw_response=response.model_dump(),
        text=content,
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        stop_reason=response.choices[0].finish_reason,
        model_name=response.model
    )

def print_result(result: CallResult):
    try: 
        parsed = json.loads(result.text)
        print(f"summary:       {parsed['summary']!r}")
        print(f"risk_level:    {parsed['risk_level']!r}")
        print(f"estimated_fix_hours: {parsed.get('estimated_fix_hours', '<missing>')!r}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("Raw text output:", result.text)

if __name__ == "__main__":
    PARAGRAPH = (
    "During regression testing on the technician dispatch module, the QA "
    "team ran 45 test cases covering job reassignment during active shifts. "
    "Three defects were found: two low-severity UI glitches in the "
    "scheduling calendar, and one medium-severity issue where a "
    "reassigned job briefly showed the wrong technician's contact info. "
    "All three were logged in the tracker and assigned to the backend team "
    "for the next sprint."
    )   

    PROMPT = (
        "Read the following paragraph and respond in json only, matching this exact shape: "
        "{\"summary\": \"<one sentence summary>\", "
        "\"risk_level\": \"low\" | \"medium\" | \"high\"}"
        "\n\n Paragraph:\n"
        f"{PARAGRAPH}"
    )
        
    BREAK_IT_PROMPT = (
        "Read the following paragraph and respond in json only, matching this exact shape: "
        "{\"summary\": \"<one sentence summary>\", "
        "\"risk_level\": \"low\" | \"medium\" | \"high\", \"estimated_fix_hours\": <number>}"
        "\n\n Paragraph:\n"
        f"{PARAGRAPH}"
    )

    result_normal = call_OpenAI_json_mode(PROMPT)
    result_break = call_OpenAI_json_mode(BREAK_IT_PROMPT)

    print("Normal Result:")
    print_result(result_normal)
    print("\nBreak It Result:")
    print_result(result_break)
