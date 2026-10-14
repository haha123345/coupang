"""Gemini 무료 API 호출 (JSON 응답).

설정한 모델이 없어졌거나(404) 막히면 다음 모델로 자동 전환한다.
API 키는 URL이 아니라 헤더로 보내서 오류 메시지에 키가 찍히지 않게 한다.
"""
import json
import time

import requests

from common import env

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
FALLBACK_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"]


def generate_json(prompt: str, model: str, temperature: float = 0.9, retries: int = 3):
    key = env("GEMINI_API_KEY")
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    models = [model] + [m for m in FALLBACK_MODELS if m != model]
    errors = []
    for m in models:
        for attempt in range(retries):
            try:
                resp = requests.post(
                    URL.format(model=m),
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json=body,
                    timeout=120,
                )
            except requests.RequestException as e:
                errors.append(f"{m}: 연결 오류 {type(e).__name__}")
                time.sleep(5)
                continue
            if resp.status_code == 404:
                errors.append(f"{m}: 모델 없음(404)")
                break  # 다음 모델로
            if resp.status_code in (400, 401, 403):
                raise RuntimeError(f"Gemini 키 오류 {resp.status_code}: {resp.text[:300]}")
            if resp.status_code in (429, 500, 503):
                errors.append(f"{m}: {resp.status_code}")
                time.sleep(15 * (attempt + 1))
                continue
            try:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
            except Exception as e:
                errors.append(f"{m}: 응답 해석 실패 {e}")
                time.sleep(3)
    raise RuntimeError("Gemini 호출 실패: " + " / ".join(errors[-6:]))
