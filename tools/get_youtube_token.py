"""내 컴퓨터에서 한 번만 실행: 쇼핑 채널 유튜브 업로드용 값 3개 만들기.

hookshorts 폴더처럼 client_secret*.json (구글 OAuth 데스크톱 앱 파일)이 있는 폴더에서
youtube_login_coupang.bat 을 실행하면 이 파일을 받아 실행합니다.
"""
import json
import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

here = Path.cwd()
cands = sorted(here.glob("client_secret*.json")) + sorted(Path(__file__).resolve().parent.glob("client_secret*.json"))
if not cands:
    print("client_secret.json 파일이 이 폴더에 없어요:", here)
    print("hookshorts 폴더(유튜브 로그인 파일이 있는 곳)에 넣고 실행해 주세요.")
    sys.exit(1)
secret = cands[0]
info = json.load(open(secret, encoding="utf-8"))
info = info.get("installed") or info.get("web")

print("브라우저가 열리면 ★쇼핑 채널(goditem20xx)★ 계정을 고르고 '허용'을 눌러 주세요.")
print("('Google에서 확인하지 않은 앱' 화면 → 고급 → 이동(안전하지 않음))")
flow = InstalledAppFlow.from_client_secrets_file(
    str(secret), scopes=["https://www.googleapis.com/auth/youtube.upload",
                         "https://www.googleapis.com/auth/youtube.readonly"])
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline",
                              success_message="완료! 이 창은 닫아도 돼요.")

name = "?"
try:
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    name = items[0]["snippet"]["title"] if items else "(채널 없음)"
except Exception as e:
    name = f"(확인 실패: {e})"

text = (f"연결된 유튜브 채널: {name}\n"
        "↑ 쇼핑 채널이 맞는지 확인하세요. 다른 채널이면 다시 실행해서 계정을 바꿔 고르세요.\n\n"
        "아래 3개를 GitHub coupang 저장소 비밀값에 하나씩 등록하세요\n"
        "https://github.com/haha123345/coupang/settings/secrets/actions/new\n\n"
        f"Name: YT_CLIENT_ID\nSecret: {info['client_id']}\n\n"
        f"Name: YT_CLIENT_SECRET\nSecret: {info['client_secret']}\n\n"
        f"Name: YT_REFRESH_TOKEN\nSecret: {creds.refresh_token}\n\n"
        "등록이 끝나면 이 파일은 지워 주세요.\n")
out = here / "coupang_youtube_values.txt"
out.write_text(text, encoding="utf-8")
print("\n" + text)
if os.name == "nt":
    os.startfile(str(out))  # 메모장으로 열기 (복사하기 쉽게)
