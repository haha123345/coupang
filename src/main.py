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
    """오늘 남은 쇼츠를 전부 만들어 올린다 (하루 1번, 12시쯤 실행)."""
    for _ in range(10):
        if not _one_short():
            break


def _one_short() -> bool:
    cfg = load_config()
    q = _queue()
    item = next((s for s in q["shorts"] if not s["done"]), None)
    if not item:
        print("오늘 남은 쇼츠 없음")
        return False
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
    try:
        url = youtube_upload.upload(str(video), s["title"], description, s.get("hashtags", []), cfg)
    except Exception as e:  # 업로드가 막혀도 영상은 잃지 않게 텔레그램으로
        notify.send_file(str(video), f"[쿠팡] ⚠️ 자동 업로드 실패 — 직접 올려주세요\n사유: {str(e)[:300]}\n\n"
                                     f"제목: {s['title']}\n\n{description}")
        item["done"] = True
        item["url"] = "업로드 실패(텔레그램 전송)"
        write_json(queue_file(q["day"]), q)
        return True
    item["done"] = True
    item["url"] = url
    write_json(queue_file(q["day"]), q)
    if url:
        notify.send(f"[쿠팡] ✅ 유튜브 업로드 완료 ({item['product']['keyword']}) — 비공개 상태예요\n"
                    f"{s['title']}\n\n확인 후 공개로 바꾸기 👉 {url}")
    else:
        notify.send_file(str(video), f"[쿠팡] 쇼츠 완성 (업로드는 직접): {s['title']}\n\n{description}")
    return True


def cmd_preview():
    """오늘 첫 쇼츠를 렌더링만 해서 텔레그램으로 보낸다 (업로드·완료 처리 안 함)."""
    import subprocess
    cfg = load_config()
    if os.environ.get("PREVIEW_FRESH", "1") == "1":
        # 지금 상품 목록·지금 코드로 새 대본을 만들어 본다 (오늘 업로드 순서엔 영향 없음)
        import random
        pool = products.load_pool()
        cands = [(i, p) for i, p in enumerate(pool, 1) if p.get("top_reviews")] or list(enumerate(pool, 1))
        number, prod = random.choice(cands)
        fmt = random.choice(cfg["shorts"]["formats"])
        item = {"number": number, "format": fmt, "product": prod,
                "script": content._shorts(cfg, number, prod, fmt), "done": False}
    else:
        q = _queue()
        item = next((s for s in q["shorts"] if not s["done"]), q["shorts"][0])
    video = render.render(item, cfg, OUT / "preview")
    dbg = OUT.parent / "data" / "debug"
    dbg.mkdir(parents=True, exist_ok=True)
    for t in (1, 6, 9, 12, 15, 20):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video),
                        "-frames:v", "1", "-vf", "scale=540:-1", str(dbg / f"preview_{t}.jpg")])
    s = item["script"]
    write_json(dbg / "preview_script.json", item)
    if os.environ.get("PREVIEW_UPLOAD") == "1":  # 유튜브 연결 테스트: 비공개로 올려 본다
        desc = (f"{cfg['disclosure']['tag']}\n{cfg['disclosure']['short']}\n\n{s['description']}\n\n"
                f"▶ 상품은 채널 프로필 링크에서 {item['number']}번을 찾아주세요.\n\n" + " ".join(s.get("hashtags", [])[:8]))
        url = youtube_upload.upload(str(video), s["title"], desc, s.get("hashtags", []), cfg)
        (dbg / "upload_test.txt").write_text(str(url), encoding="utf-8")
        notify.send(f"[쿠팡] ✅ 유튜브 업로드 테스트 성공 — 비공개로 올라갔어요\n{s['title']}\n\n확인 👉 {url}"
                    if url else "[쿠팡] 유튜브 값이 없어 업로드하지 않았어요 (텔레그램 전송만)")
    import shutil
    shutil.copy(video, dbg / "preview.mp4")
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
        text = f"[광고] 쿠팡파트너스 활동으로 수수료를 받아요\n\n{item['text']}"
        name = item['product'].get('name') or item['product']['keyword']
        # 잘 되는 계정들의 답글 형식: 광고 문구 → 상품명 한 줄 → 링크
        reply = f"[광고] 쿠팡파트너스 활동으로 일정 수수료를 지급받습니다\n\n{name}\n{item['product']['partner_url']}"
        for t, need in ((text, True), (reply, True)):
            issues = compliance.problems(content.strip_quotes(t), need_disclosure=need)
            if issues:
                raise RuntimeError("게시 전 점검 실패: " + ", ".join(issues))
    else:
        text, reply = item["text"], None
    text = text[: cfg["threads"]["max_chars"]]
    video = None
    if reply:
        prod = item.get("product") or {}
        work = OUT / f"threads_{q['day']}_{item.get('number', 0)}"
        imgs = []
        try:  # 상품 정보 카드 (가격·할인·별점·실제 후기)
            imgs.append(str(render.info_card(prod, work / "card.jpg")))
        except Exception as e:
            print("정보 카드 실패:", e)
        imgs += prod.get("image_urls", [])[:2]
        if not item.get("script"):  # 아침에 대본을 못 만들었으면 지금 만든다
            try:
                fmt = cfg["shorts"]["formats"][hash(prod.get("keyword", "")) % len(cfg["shorts"]["formats"])]
                item["format"], item["script"] = fmt, content._shorts(cfg, item.get("number", 0), prod, fmt)
            except Exception as e:
                print("쓰레드 영상 대본 실패:", e)
        if item.get("script"):
            try:  # 쇼츠와 같은 영상, 끝 화면만 '구매 링크는 답글에'
                video = str(render.render({**item, "cta": "threads"}, cfg, work))
            except Exception as e:
                print("쓰레드 영상 실패(사진만 보냄):", e)
    else:
        import stock
        imgs = stock.photos(item.get("photo_query", ""), 1)
    url = threads_post.post(text, link_reply=reply, backend=cfg["threads"].get("backend", "threads_api"),
                            images=imgs, video=video)
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
        try:
            from common import DATA
            (DATA / "debug").mkdir(parents=True, exist_ok=True)
            (DATA / "debug" / f"error_{name}.txt").write_text(traceback.format_exc()[-3000:], encoding="utf-8")
        except Exception:
            pass
        notify.send(f"[쿠팡] ❌ {name} 실패: {e}")
        sys.exit(1)
