"""명령:
  python src/main.py weekly        # 매주: 인기 상품 10개 선정 (+상품 페이지 갱신)
  python src/main.py prep          # 매일 아침: 오늘 쇼츠 대본·쓰레드 글 생성
  python src/main.py shorts        # 쇼츠 1편 렌더링 + 업로드 (하루 2번 실행)
  python src/main.py threads       # 쓰레드 글 1개 게시 (하루 9번 실행)
  python src/main.py refresh-threads-token
"""
import os
import sys
import traceback

import compliance
import content
import notify
import pages
import products
import render
import threads_post
import youtube_upload
from common import OUT, load_config, queue_file, read_json, today_str, write_json


def _queue():
    q = read_json(queue_file())
    if q is None:
        q = content.build_day()
    return q


def cmd_weekly():
    products.weekly()
    pages.build()


def cmd_prep():
    pages.build()  # 사용자가 수동 목록을 채웠으면 페이지에 반영
    q = content.build_day()
    notify.send(f"[쿠팡] {q['day']} 콘텐츠 준비: 쇼츠 {len(q['shorts'])}개, 쓰레드 {len(q['threads'])}개")


def cmd_shorts():
    cfg = load_config()
    q = _queue()
    item = next((s for s in q["shorts"] if not s["done"]), None)
    if not item:
        print("오늘 남은 쇼츠 없음")
        return
    s = item["script"]
    disclosure = cfg["disclosure"]
    description = (
        f"{disclosure['tag']}\n{disclosure['short']}\n\n"
        f"{s['description']}\n\n"
        f"▶ 상품은 채널 프로필 링크에서 {item['number']}번을 찾아주세요.\n"
        "가격은 작성 시점 기준이며 바뀔 수 있어요.\n\n"
        + " ".join(s.get("hashtags", [])[:8])
    )
    issues = compliance.problems(description, need_disclosure=True)
    if issues:
        raise RuntimeError("업로드 전 점검 실패: " + ", ".join(issues))

    video = render.render(item, cfg, OUT / f"{q['day']}_{item['number']}_{item['format']}")
    url = youtube_upload.upload(str(video), s["title"], description, s.get("hashtags", []), cfg)
    item["done"] = True
    item["url"] = url
    write_json(queue_file(q["day"]), q)
    if url:
        notify.send(f"[쿠팡] 쇼츠 업로드 완료 ({item['product']['keyword']})\n{s['title']}\n{url}")
    else:
        notify.send_file(str(video), f"[쿠팡] 쇼츠 완성 (업로드는 직접): {s['title']}\n\n{description}")


def cmd_preview():
    """오늘 첫 쇼츠를 렌더링만 해서 텔레그램으로 보낸다 (업로드·완료 처리 안 함)."""
    import subprocess
    cfg = load_config()
    q = _queue()
    item = next((s for s in q["shorts"] if not s["done"]), q["shorts"][0])
    video = render.render(item, cfg, OUT / "preview")
    dbg = OUT.parent / "data" / "debug"
    dbg.mkdir(parents=True, exist_ok=True)
    for t in (1, 6, 12, 20):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video),
                        "-frames:v", "1", "-vf", "scale=540:-1", str(dbg / f"preview_{t}.jpg")])
    s = item["script"]
    notify.send_file(str(video), f"[쿠팡] 미리보기 — {s['title']}\n(업로드 안 함)")


def cmd_threads():
    cfg = load_config()
    q = _queue()
    item = next((t for t in q["threads"] if not t["done"]), None)
    if not item:
        print("오늘 남은 쓰레드 글 없음")
        return
    tag = cfg["disclosure"]["tag"]
    if item["kind"] == "link":
        text = f"{tag} 쿠팡 파트너스 활동으로 수수료를 받아요\n\n{item['text']}"
        reply = f"{item['product'].get('name') or item['product']['keyword']}\n{item['product']['partner_url']}\n\n" \
                f"{cfg['disclosure']['short']}"
        for t, need in ((text, True), (reply, True)):
            issues = compliance.problems(t, need_disclosure=need)
            if issues:
                raise RuntimeError("게시 전 점검 실패: " + ", ".join(issues))
    else:
        text, reply = item["text"], None
    text = text[: cfg["threads"]["max_chars"]]
    url = threads_post.post(text, link_reply=reply, backend=cfg["threads"].get("backend", "threads_api"))
    item["done"] = True
    item["url"] = url
    write_json(queue_file(q["day"]), q)
    left = sum(1 for t in q["threads"] if not t["done"])
    notify.send(f"[쿠팡] 쓰레드 게시 ({'링크' if reply else '팁'}) · 오늘 남은 글 {left}개\n{url}")


def cmd_refresh_threads_token():
    new = threads_post.refresh_token()
    # GH_PAT 가 있으면 워크플로에서 이 값을 Secret 으로 다시 저장한다
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        print(f"::add-mask::{new}")
        with open(path, "a") as f:
            f.write(f"token={new}\n")
    notify.send("[쿠팡] 쓰레드 토큰 연장 완료")


COMMANDS = {
    "weekly": cmd_weekly,
    "prep": cmd_prep,
    "shorts": cmd_shorts,
    "threads": cmd_threads,
    "preview": cmd_preview,
    "refresh-threads-token": cmd_refresh_threads_token,
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    try:
        COMMANDS[name]()
    except Exception as e:
        traceback.print_exc()
        notify.send(f"[쿠팡] ❌ {name} 실패: {e}")
        sys.exit(1)
