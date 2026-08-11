# Deepseek's legacy model names (deepseek-chat / deepseek-reasoner) were
# retired 2026-07-24. Current models: deepseek-v4-flash, deepseek-v4-pro.
# Deepseek also now exposes a native Anthropic Messages API endpoint
# (not just OpenAI-compatible) at https://api.deepseek.com/anthropic,
# which is what this script uses.

from http import client
import os
from urllib import response
import anthropic
import openai


# Import Deepseek API Key from .env file
from dotenv import load_dotenv
load_dotenv()
deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")

clientAnthropic = anthropic.Client(api_key=deepseek_api_key, base_url="https://api.deepseek.com/anthropic")
clientOpenAI = openai.OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com")

def callAnthropicSchemaAPI():
    return clientAnthropic.messages.create(
        model="deepseek-v4-flash",
        max_tokens=100,
        messages=[
        {"role": "user", "content": "Write a haiku about testing."}
        ],
        stream=False,
        thinking={
        "type": "disabled"
    }
    )

def callOpenAISchemaAPI():
    return clientOpenAI.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "user", "content": "Write a haiku about testing."}
        ],
        max_tokens=100,
        stream=False,
        extra_body={"thinking": {"type": "disabled"}}
    )


def printAnthropicResponse(response):
    # 1. The entire response object, unfiltered.
    print("=" * 60)
    print("ANTHROPIC FULL RESPONSE OBJECT")
    print("=" * 60)
    print(response.model_dump_json(indent=2))
        # 2. The five values you should be able to point at.
    print("\n" + "=" * 60)
    print("THE FIVE VALUES")
    print("=" * 60)
    
    # Anthropic-format responses put text inside a list of content blocks
    # (there can be more than one block, e.g. thinking + text) rather than
    # a single .content string like the OpenAI shape.
    text_blocks = [block.text for block in response.content if block.type == "text"]
    text = "\n".join(text_blocks)
    
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    stop_reason = response.stop_reason
    model_name = response.model
    
    print(f"1. Text:           {text!r}")
    print(f"2. Input tokens:   {input_tokens}")
    print(f"3. Output tokens:  {output_tokens}")
    print(f"4. Stop reason:    {stop_reason}")
    print(f"5. Model name:     {model_name}")

def printOpenAIResponse(response):
    # 1. The entire response object, unfiltered.
    print("=" * 60)
    print("OPENAI FULL RESPONSE OBJECT")
    print("=" * 60)
    print(response.model_dump_json(indent=2))
        # 2. The five values you should be able to point at.
    print("\n" + "=" * 60)
    print("THE FIVE VALUES")
    print("=" * 60)
    
    # OpenAI-format responses put text inside a single .content string
    # rather than a list of content blocks like the Anthropic shape.
    text = response.choices[0].message.content
    
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    stop_reason = response.choices[0].finish_reason
    model_name = response.model
    
    print(f"1. Text:           {text!r}")
    print(f"2. Input tokens:   {input_tokens}")
    print(f"3. Output tokens:  {output_tokens}")
    print(f"4. Stop reason:    {stop_reason}")
    print(f"5. Model name:     {model_name}")

responseAnthropic = callAnthropicSchemaAPI()
printAnthropicResponse(responseAnthropic)
print("\n\n\n")
responseOpenAI = callOpenAISchemaAPI()
printOpenAIResponse(responseOpenAI)