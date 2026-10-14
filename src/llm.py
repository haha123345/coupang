"""Gemini 무료 API 호출 (JSON 응답).

모델 이름은 자주 바뀌고 사라지므로, 실행할 때마다 '지금 쓸 수 있는 모델 목록'을
구글에 물어보고 최신 flash 모델부터 시도한다. 붐비면(503·429) 다음 모델로 넘어간다.
API 키는 헤더로 보내서 오류 메시지에 키가 찍히지 않게 한다.
"""
import json
import re
import time

import requests

from common import env

BASE = "https://generativelanguage.googleapis.com/v1beta"
SKIP = ("image", "tts", "audio", "live", "embedding", "aqa", "robotics", "computer", "native")
_cache: list[str] | None = None


def _headers():
    return {"x-goog-api-key": env("GEMINI_API_KEY"), "Content-Type": "application/json"}


def _version(name: str) -> float:
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else 0.0


def available_models(preferred: str | None = None) -> list[str]:
    """generateContent 를 지원하는 flash 계열 모델을 좋은 순서로."""
    global _cache
    if _cache is None:
        names = []
        try:
            token = ""
            for _ in range(5):
                r = requests.get(f"{BASE}/models", headers=_headers(),
                                 params={"pageSize": 200, "pageToken": token}, timeout=30)
                r.raise_for_status()
                js = r.json()
                for m in js.get("models", []):
                    n = m["name"].split("/", 1)[-1]
                    if "generateContent" in m.get("supportedGenerationMethods", []) \
                            and "flash" in n and not any(s in n for s in SKIP):
                        names.append(n)
                token = js.get("nextPageToken", "")
                if not token:
                    break
        except Exception as e:
            print("모델 목록 조회 실패:", e)
        # 정렬: 정식(non-preview) 먼저 → 버전 높은 순 → lite 는 뒤로
        names.sort(key=lambda n: ("lite" in n, "preview" in n or "exp" in n, -_version(n), "latest" not in n))
        _cache = names or ["gemini-flash-latest", "gemini-flash-lite-latest"]
    order = list(_cache)
    if preferred and preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)
    return order


def generate_json(prompt: str, model: str | None = None, temperature: float = 0.9):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    errors = []
    for rnd in range(3):  # 모든 모델이 붐비면 잠시 쉬고 다시 한 바퀴
        for m in available_models(model)[:6]:
            try:
                resp = requests.post(f"{BASE}/models/{m}:generateContent",
                                     headers=_headers(), json=body, timeout=150)
            except requests.RequestException as e:
                errors.append(f"{m}: 연결 오류 {type(e).__name__}")
                continue
            if resp.status_code in (400, 401, 403) and "API key" in resp.text:
                raise RuntimeError(f"Gemini 키 오류 {resp.status_code}: {resp.text[:300]}")
            if resp.status_code != 200:
                errors.append(f"{m}: {resp.status_code}")
                continue
            try:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
            except Exception as e:
                errors.append(f"{m}: 응답 해석 실패 {e}")
        time.sleep(30 * (rnd + 1))
    raise RuntimeError("Gemini 호출 실패: " + " / ".join(errors[-8:]))
