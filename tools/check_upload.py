"""Upload-Post 연결 확인: 요금제·남은 횟수·프로필별 연결된 SNS 를 텔레그램으로 알려준다 (업로드는 안 함)."""
import os
import sys

import requests

sys.path.insert(0, "src")
import notify  # noqa: E402

key, user = os.environ.get("UPLOAD_POST_API_KEY", ""), os.environ.get("UPLOAD_POST_USER", "")
lines = ["[쿠팡] 유튜브 자동 업로드 연결 확인"]
if not key:
    lines.append("❌ UPLOAD_POST_API_KEY 비밀값이 없어요")
if not user:
    lines.append("❌ UPLOAD_POST_USER 비밀값이 없어요")
if key:
    h = {"Authorization": f"Apikey {key}"}
    r = requests.get("https://api.upload-post.com/api/uploadposts/users", headers=h, timeout=30)
    if r.status_code >= 400:
        lines.append(f"❌ API 키 확인 실패 {r.status_code}: {r.text[:200]}")
    else:
        js = r.json()
        lines.append(f"요금제: {js.get('plan')} · 프로필 최대 {js.get('limit')}개")
        names = []
        for p in js.get("profiles", []):
            acc = p.get("social_accounts") or {}
            on = [k for k, v in acc.items() if v]
            names.append(p.get("username"))
            yt = acc.get("youtube")
            yt_name = yt.get("display_name", "") if isinstance(yt, dict) else ""
            mark = "👉 " if p.get("username") == user else "· "
            lines.append(f"{mark}{p.get('username')}: {', '.join(on) or '연결 없음'}"
                         + (f" (유튜브: {yt_name})" if yt_name else ""))
        if user and user not in names:
            lines.append(f"❌ UPLOAD_POST_USER='{user}' 와 같은 이름의 프로필이 없어요 (위 이름 중 하나로)")
        elif user:
            prof = next(p for p in js["profiles"] if p.get("username") == user)
            ok = bool((prof.get("social_accounts") or {}).get("youtube"))
            lines.append("✅ 이 프로필로 유튜브 자동 업로드 준비 완료" if ok
                         else "❌ 이 프로필에 유튜브가 아직 연결 안 됐어요")
    try:
        u = requests.get("https://api.upload-post.com/api/uploadposts/me", headers=h, timeout=30)
        if u.ok:
            lines.append(f"계정 정보: {str(u.json())[:300]}")
    except Exception:
        pass
msg = "\n".join(lines)
print(msg)
notify.send(msg)
