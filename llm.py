"""Optional LLM polish for answer text.

Set ``LOVABLE_API_KEY`` (Lovable AI Gateway) or ``OPENAI_API_KEY`` to enable.
Without a key the deterministic template answer is returned unchanged.
"""

from __future__ import annotations

import os

import httpx

GATEWAY_URL = "https://ai.gateway.lovable.dev/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are FloatChat, an assistant for ARGO ocean float data. Rewrite the given "
    "factual summary so it reads naturally in the user's language. Never invent "
    "numbers: use only the values provided. Keep it under 120 words, markdown allowed."
)


def _endpoint() -> tuple[str, str, str] | None:
    key = os.getenv("LOVABLE_API_KEY")
    if key:
        return GATEWAY_URL, key, "google/gemini-2.5-flash"
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return OPENAI_URL, key, "gpt-4o-mini"
    return None


async def polish(summary: str, question: str, language: str) -> str:
    target = _endpoint()
    if target is None:
        return summary
    url, key, model = target
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question ({language}): {question}\n\n"
                    f"Factual summary to rewrite in {language}:\n{summary}"
                ),
            },
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                url, json=payload, headers={"Authorization": f"Bearer {key}"}
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip() or summary
    except Exception:  # network/quota failures must not break the query
        return summary