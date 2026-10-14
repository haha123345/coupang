"""Threads API 로 글 게시 + (링크 글이면) 첫 답글에 파트너스 링크."""
import time

import requests

from common import env

BASE = "https://graph.threads.net/v1.0"


def _create_and_publish(text: str, reply_to: str | None = None) -> str:
    token = env("THREADS_ACCESS_TOKEN")
    params = {"media_type": "TEXT", "text": text, "access_token": token}
    if reply_to:
        params["reply_to_id"] = reply_to
    r = requests.post(f"{BASE}/me/threads", params=params, timeout=30)
    r.raise_for_status()
    creation_id = r.json()["id"]
    time.sleep(5)  # 컨테이너 준비 대기
    for attempt in range(4):
        p = requests.post(
            f"{BASE}/me/threads_publish",
            params={"creation_id": creation_id, "access_token": token},
            timeout=30,
        )
        if p.ok:
            return p.json()["id"]
        time.sleep(10 * (attempt + 1))
    p.raise_for_status()
    return ""


def permalink(media_id: str) -> str:
    r = requests.get(
        f"{BASE}/{media_id}",
        params={"fields": "permalink", "access_token": env("THREADS_ACCESS_TOKEN")},
        timeout=30,
    )
    return r.json().get("permalink", "") if r.ok else ""


def post(text: str, link_reply: str | None = None) -> str:
    post_id = _create_and_publish(text)
    if link_reply:
        time.sleep(15)
        _create_and_publish(link_reply, reply_to=post_id)
    return permalink(post_id)


def refresh_token() -> str:
    """장기 토큰(60일) 연장. 새 토큰 문자열을 돌려준다."""
    r = requests.get(
        "https://graph.threads.net/refresh_access_token",
        params={"grant_type": "th_refresh_token", "access_token": env("THREADS_ACCESS_TOKEN")},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]
