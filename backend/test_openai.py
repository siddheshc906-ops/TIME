import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from the same folder as this script
load_dotenv(Path(__file__).resolve().parent / ".env")

from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("❌ OPENAI_API_KEY not found in .env file")
    exit(1)

print(f"✅ API key loaded: {api_key[:12]}...")

try:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Say hello in one word"}],
        max_tokens=5
    )
    print("✅ OpenAI is working! Response:", response.choices[0].message.content)

except Exception as e:
    print(f"❌ OpenAI error: {type(e).__name__}: {e}")