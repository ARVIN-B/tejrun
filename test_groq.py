"""Manual Groq smoke test.

Run directly when credentials are available; importing this module must not
make a paid external API call during Django/unittest discovery.
"""

import os

from dotenv import load_dotenv
from groq import Groq


def main() -> None:
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")
    if not api_key:
        raise ValueError("LLM_API_KEY is not set")
    if not model:
        raise ValueError("LLM_MODEL is not set")
    client = Groq(api_key=api_key, base_url="https://api.groq.com")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Hello. Introduce yourself in one sentence."}],
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
