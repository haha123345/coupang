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
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendVideo",
                data={"chat_id": chat, "caption": caption[:1000]},
                files={"video": f},
                timeout=300,
            )
    except Exception as e:
        print("텔레그램 파일 전송 실패:", e)
