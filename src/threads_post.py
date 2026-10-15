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


def _post_threads_api(text: str, link_reply: str | None) -> str:
    post_id = _create_and_publish(text)
    if link_reply:
        time.sleep(15)
        _create_and_publish(link_reply, reply_to=post_id)
    return permalink(post_id)


def _post_upload_post(text: str, link_reply: str | None) -> str:
    """Upload-Post 경유 (Meta 개발자 앱 없이 쓰레드 게시). 첫 답글로 링크."""
    data = {"user": env("UPLOAD_POST_USER"), "platform[]": "threads", "title": text,
            "threads_long_text_as_post": "true"}
    if link_reply:
        data["threads_first_comment"] = link_reply
    r = requests.post("https://api.upload-post.com/api/upload_text",
                      headers={"Authorization": f"Apikey {env('UPLOAD_POST_API_KEY')}"},
                      data=data, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Upload-Post 쓰레드 오류 {r.status_code}: {r.text[:300]}")
    js = r.json()
    res = (js.get("results") or {}).get("threads") or {}
    if res and not res.get("success", True):
        raise RuntimeError(f"Upload-Post 쓰레드 실패: {res.get('error')}")
    return res.get("url") or js.get("request_id", "Upload-Post 게시 요청 완료")


def _post_telegram(text: str, link_reply: str | None, images: list[str] | None = None,
                   video: str | None = None) -> str:
    """수동 모드: 지금 올릴 글을 텔레그램으로 보내준다 (복사해서 쓰레드 앱에 붙여넣기)."""
    import notify
    if video:
        notify.send_file(video, "🎬 영상 — 저장해서 아래 사진들과 함께 본문에 첨부하세요 (영상을 첫 번째로)")
    if images:
        notify.send_photos(images, "📷 사진 — 길게 눌러 저장한 뒤 본문에 첨부하세요")
    notify.send(text)
    if link_reply:
        notify.send(link_reply)
        notify.send("☝️ 위 두 메시지: 첫 번째는 본문, 두 번째는 '스레드에 추가' 칸에 붙여넣기 (주제: 살림 추천)")
    else:
        notify.send("☝️ 위 메시지를 그대로 복사해서 게시 (주제: 살림 추천)")
    return "텔레그램 전송 (직접 게시)"


def post(text: str, link_reply: str | None = None, backend: str = "threads_api",
         images: list[str] | None = None, video: str | None = None) -> str:
    if backend == "upload_post":
        return _post_upload_post(text, link_reply)
    if backend == "telegram":
        return _post_telegram(text, link_reply, images, video)
    return _post_threads_api(text, link_reply)


def refresh_token() -> str:
    """장기 토큰(60일) 연장. 새 토큰 문자열을 돌려준다."""
    r = requests.get(
        "https://graph.threads.net/refresh_access_token",
        params={"grant_type": "th_refresh_token", "access_token": env("THREADS_ACCESS_TOKEN")},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]
