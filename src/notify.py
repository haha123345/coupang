"""텔레그램 알림. 토큰이 없으면 콘솔에만 출력."""
import os

import requests


def _creds():
    return os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")


def send(text: str) -> None:
    print("[알림]", text)
    token, chat = _creds()
    if not token or not chat:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True},
            timeout=20,
        )
    except Exception as e:  # 알림 실패가 작업을 멈추면 안 됨
        print("텔레그램 전송 실패:", e)


def send_file(path: str, caption: str = "") -> None:
    token, chat = _creds()
    if not token or not chat:
        print("[파일]", path, caption)
        return
    try:
        for method, field in (("sendVideo", "video"), ("sendDocument", "document")):
            with open(path, "rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/{method}",
                    data={"chat_id": chat, "caption": caption[:1000]},
                    files={field: f},
                    timeout=300,
                )
            if r.ok:
                return
            print(f"텔레그램 {method} 실패 {r.status_code}: {r.text[:300]}")
        send(f"⚠️ 영상 파일 전송 실패 ({os.path.getsize(path) // 1_000_000}MB): {r.text[:200]}")
    except Exception as e:
        print("텔레그램 파일 전송 실패:", e)
        send(f"⚠️ 영상 파일 전송 실패: {e}")


def send_photos(urls: list[str], caption: str = "") -> None:
    """상품 사진을 앨범으로 전송 (길게 눌러 저장 → 쓰레드에 첨부)."""
    token, chat = _creds()
    urls = [u for u in urls if u][:4]
    if not token or not chat or not urls:
        print("[사진]", urls)
        return
    import json as _json
    UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36"}
    files, media = {}, []
    for i, u in enumerate(urls):
        try:
            r = requests.get(u, headers=UA, timeout=30)
            r.raise_for_status()
            files[f"p{i}"] = (f"p{i}.jpg", r.content)
            media.append({"type": "photo", "media": f"attach://p{i}"})
        except Exception as e:
            print("사진 다운로드 실패:", u, e)
    if not media:
        return
    media[0]["caption"] = caption[:1000]
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMediaGroup",
                      data={"chat_id": chat, "media": _json.dumps(media)}, files=files, timeout=120)
    except Exception as e:
        print("텔레그램 사진 전송 실패:", e)
