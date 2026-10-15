"""유튜브 업로드. config.yaml 의 shorts.backend 로 방식 선택.

youtube_api : YouTube Data API v3 (무료, OAuth 리프레시 토큰)
              ※ 구글 감사(audit)를 통과하지 않은 프로젝트로 올린 영상은 '비공개'로 잠김
upload_post : Upload-Post API (무료 월 10회, 그 이상은 유료)
telegram_only: 업로드 안 함
auto        : Upload-Post 비밀값(UPLOAD_POST_API_KEY, UPLOAD_POST_USER)이 있으면 upload_post,
              없으면 telegram_only
"""
import os

import requests

from common import env


def _youtube_api(path: str, title: str, description: str, tags: list[str], cfg: dict) -> str:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        token=None,
        refresh_token=env("YT_REFRESH_TOKEN"),
        client_id=env("YT_CLIENT_ID"),
        client_secret=env("YT_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": [t.lstrip("#") for t in tags][:15],
            "categoryId": cfg["shorts"].get("category_id", "26"),
            "defaultLanguage": "ko",
        },
        "status": {
            "privacyStatus": cfg["shorts"].get("privacy", "public"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # AI 음성 사용 고지
        },
        "paidProductPlacementDetails": {"hasPaidProductPlacement": True},  # 유료 광고 포함 표시
    }
    def _send(part, b):
        req = yt.videos().insert(
            part=part, body=b, media_body=MediaFileUpload(path, mimetype="video/mp4", resumable=True)
        )
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        return resp

    try:
        resp = _send("snippet,status,paidProductPlacementDetails", body)
    except Exception as e:  # 유료 광고 표시 항목을 API가 거부하면 그것만 빼고 재시도
        print("유료 광고 표시 없이 재시도:", e)
        body.pop("paidProductPlacementDetails", None)
        resp = _send("snippet,status", body)
    return f"https://youtube.com/shorts/{resp['id']}"


def _upload_post(path: str, title: str, description: str, tags: list[str], cfg: dict) -> str:
    data = [
        ("user", env("UPLOAD_POST_USER")),
        ("platform[]", "youtube"),
        ("title", title[:100]),
        ("description", description[:4900]),
        ("privacyStatus", cfg["shorts"].get("privacy", "public")),
        ("categoryId", cfg["shorts"].get("category_id", "26")),
        ("selfDeclaredMadeForKids", "false"),
        ("hasPaidProductPlacement", "true"),   # 유료 프로모션 포함 표시 (쿠팡 수수료)
        ("containsSyntheticMedia", "true"),     # AI 음성 사용 고지
        ("defaultLanguage", "ko"),
        ("defaultAudioLanguage", "ko"),
    ] + [("tags[]", t.lstrip("#")) for t in tags[:15]]
    with open(path, "rb") as f:
        r = requests.post(
            "https://api.upload-post.com/api/upload",
            headers={"Authorization": f"Apikey {env('UPLOAD_POST_API_KEY')}"},
            data=data, files={"video": f}, timeout=900,
        )
    if r.status_code >= 400:
        raise RuntimeError(f"Upload-Post 업로드 오류 {r.status_code}: {r.text[:300]}")
    js = r.json()
    yt = (js.get("results") or {}).get("youtube") or {}
    if yt and not yt.get("success", True):
        raise RuntimeError(f"Upload-Post 유튜브 실패: {yt.get('error')}")
    usage = js.get("usage") or {}
    note = f" (이번 달 {usage.get('count')}/{usage.get('limit')})" if usage else ""
    return (yt.get("url") or (f"https://youtube.com/shorts/{yt['video_id']}" if yt.get("video_id") else "")
            or f"Upload-Post 업로드 요청 완료 {js.get('request_id', '')}") + note


def upload(path: str, title: str, description: str, tags: list[str], cfg: dict) -> str | None:
    backend = cfg["shorts"].get("backend", "auto")
    if backend == "auto":
        backend = ("upload_post" if os.environ.get("UPLOAD_POST_API_KEY") and os.environ.get("UPLOAD_POST_USER")
                   else "telegram_only")
    if backend == "youtube_api":
        return _youtube_api(path, title, description, tags, cfg)
    if backend == "upload_post":
        return _upload_post(path, title, description, tags, cfg)
    return None
