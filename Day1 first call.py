# Deepseek's legacy model names (deepseek-chat / deepseek-reasoner) were
# retired 2026-07-24. Current models: deepseek-v4-flash, deepseek-v4-pro.
# Deepseek also now exposes a native Anthropic Messages API endpoint
# (not just OpenAI-compatible) at https://api.deepseek.com/anthropic,
# which is what this script uses.

import os
import anthropic


# Import Deepseek API Key from .env file
from dotenv import load_dotenv
load_dotenv()
deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")

client = anthropic.Client(api_key=deepseek_api_key, base_url="https://api.deepseek.com/anthropic")

response = client.completions.create(
    model="deepseek-v4-flash",
    max_tokens=100,
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Write a short poem about the beauty of nature."
        }
    ],
)

def printResponse(response):
    # 1. The entire response object, unfiltered.
    print("=" * 60)
    print("FULL RESPONSE OBJECT")
    print("=" * 60)
    print(response.model_dump_json(indent=2))


printResponse(response)