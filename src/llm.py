"""Gemini 무료 API 호출 (JSON 응답)."""
import json
import time

import requests

from common import env

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def generate_json(prompt: str, model: str, temperature: float = 0.9, retries: int = 4):
    key = env("GEMINI_API_KEY")
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    last = None
    for attempt in range(retries):
        try:
            resp = requests.post(URL.format(model=model), params={"key": key}, json=body, timeout=120)
            if resp.status_code in (429, 500, 503):
                raise RuntimeError(f"Gemini {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as e:
            last = e
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Gemini 호출 실패: {last}")
