@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 쿠팡 쇼핑 채널 유튜브 연결 준비 중...
python -m pip install -q --disable-pip-version-check --no-warn-script-location google-api-python-client google-auth-oauthlib
powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing https://raw.githubusercontent.com/haha123345/coupang/main/tools/get_youtube_token.py -OutFile coupang_token.py"
python coupang_token.py
pause
