"""내 컴퓨터에서 한 번만 실행: 유튜브 업로드용 리프레시 토큰 발급.

1) 구글 클라우드 콘솔에서 'OAuth 클라이언트 ID (데스크톱 앱)' 를 만들고 JSON을 내려받아
   이 파일과 같은 폴더에 client_secret.json 으로 저장
2) pip install google-auth-oauthlib
3) python get_youtube_token.py  → 브라우저에서 '쇼핑 채널' 구글 계정으로 로그인
4) 출력되는 세 값을 GitHub Secrets 에 등록
"""
import json

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", scopes=["https://www.googleapis.com/auth/youtube.upload"]
)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
info = json.load(open("client_secret.json"))["installed"]
print("\n아래 세 값을 GitHub > Settings > Secrets and variables > Actions 에 등록하세요\n")
print("YT_CLIENT_ID     =", info["client_id"])
print("YT_CLIENT_SECRET =", info["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
