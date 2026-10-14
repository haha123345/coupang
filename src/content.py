"""하루치 콘텐츠 생성: 쇼츠 대본 N개 + 쓰레드 글 N개 → data/queue/YYYY-MM-DD.json"""
import random

import compliance
import products
from common import DATA, load_config, queue_file, read_json, today_str, write_json
from llm import generate_json

USAGE = DATA / "usage.json"

FORMAT_GUIDE = {
    "top3_points": "이 상품을 찾는 사람이 궁금해할 포인트 3가지를 하나씩 짚는 구성",
    "before_after": "이 상품이 없을 때 생기는 불편 → 있을 때 달라지는 점을 대비하는 구성",
    "dont_buy_instead": "'이런 걸 사면 후회해요' 식으로 고를 때 피할 점을 먼저 말하고, 고르는 기준으로 이 상품을 보여주는 구성",
    "price_check": "가격대와 고를 때 볼 기준(용량·크기·재질 등 일반적인 기준)을 정리해주는 구성",
}

SHORTS_PROMPT = """너는 한국 유튜브 쇼핑 쇼츠 대본 작가야. 아래 상품으로 25~35초짜리 쇼츠 대본을 써.

[상품]
- 검색 키워드: {keyword}
- 상품명: {name}
- 가격(작성 시점): {price}
- 카테고리: {category}
- 메모: {notes}
- 이 상품의 소개 번호: {number}번

[구성] {format_guide}

[반드시 지킬 것]
- 직접 써봤다, 샀다, 우리 집에서 등 '사용 경험'처럼 들리는 말은 절대 쓰지 마. 우리는 써보지 않았어.
- 위 정보에 없는 구체적 수치(용량, 배터리 시간, 판매량, 별점, 리뷰 수)를 지어내지 마.
  모르는 건 "상세페이지에서 꼭 확인하세요"처럼 확인을 권하는 말로 대신해.
- 효능·치료·건강 개선 같은 의학적 표현 금지. 과장(무조건, 100%, 최저가 보장) 금지.
- 가격을 말할 땐 "지금 기준", "가격은 바뀔 수 있어요"를 붙여.
- 첫 문장은 2초 안에 멈추게 만드는 질문이나 상황 제시. 결말은 "프로필 링크에서 {number}번 확인하세요".
- 자연스러운 구어체 한국어. 문장은 짧게.

JSON으로만 답해:
{{
 "title": "유튜브 제목 (40자 이내, 끝에 #shorts)",
 "hook": "첫 화면 큰 글자 (12자 이내)",
 "scenes": [
   {{"caption": "화면 큰 글자 (14자 이내)", "narration": "이 장면에서 읽을 문장 1~2개"}}
 ],
 "description": "영상 설명 2~3줄 (링크 넣지 마)",
 "hashtags": ["#태그", "..."]
}}
scenes 는 5~7개.
"""

THREADS_LINK_PROMPT = """너는 한국 스레드(Threads)에서 살림·생활 정보를 쓰는 계정이야.
아래 상품을 소개하는 글 1개를 써.

[상품] 키워드: {keyword} / 상품명: {name} / 가격(작성 시점): {price} / 메모: {notes}

규칙:
- 직접 써봤다, 샀다 같은 사용 경험처럼 들리는 말 금지 (우리는 써보지 않았어).
- 정보에 없는 수치·후기·별점을 지어내지 마. 효능·의학 표현, 과장 금지.
- '고를 때 이것만 보세요' 같은 실용 정보가 중심이고, 상품은 그 기준의 예시로 소개.
- 링크는 본문에 넣지 마 (답글에 따로 단다). 마지막 줄은 "링크는 답글에 둘게요" 정도로.
- 350자 이내, 줄바꿈 자주, 이모지는 0~2개, 해시태그는 넣지 마.
JSON으로만: {{"text": "..."}}
"""

THREADS_TIP_PROMPT = """너는 한국 스레드(Threads)에서 살림·생활 정보를 쓰는 계정이야.
링크 없는 정보·공감 글 {n}개를 써. 주제는 아래 카테고리의 생활 팁에서 골라:
{categories}

규칙:
- 상품 홍보·브랜드명·링크 금지. 순수하게 도움 되거나 공감되는 글.
- 글마다 형식을 다르게: 짧은 꿀팁 리스트 / 흔한 실수 / 질문형(답글 유도) / 계절 팁 등.
- 확실하지 않은 정보, 의학·건강 효능 주장 금지.
- 각 글 300자 이내, 줄바꿈 자주, 이모지 0~2개, 해시태그 금지.
JSON으로만: {{"posts": ["...", "..."]}}
"""


def _usage():
    return read_json(USAGE, {"product": {}, "format_idx": 0}) or {"product": {}, "format_idx": 0}


def _pick(pool: list[dict], k: int, usage: dict) -> list[tuple[int, dict]]:
    """적게 쓰인 상품부터 고른다. (번호는 이번 주 목록에서의 순번 1~10)"""
    ranked = sorted(
        enumerate(pool, 1),
        key=lambda t: (usage["product"].get(t[1]["keyword"], 0), random.random()),
    )
    return ranked[:k]


def _shorts(cfg, number, prod, fmt):
    prompt = SHORTS_PROMPT.format(
        keyword=prod["keyword"], name=prod.get("name", ""), price=prod.get("price", "미확인"),
        category=prod.get("category", ""), notes=prod.get("notes", "") or "없음",
        number=number, format_guide=FORMAT_GUIDE[fmt],
    )
    for _ in range(3):
        s = generate_json(prompt, cfg["llm"]["model"])
        text = " ".join(x["narration"] + " " + x["caption"] for x in s["scenes"]) + s["title"] + s["description"]
        if not compliance.problems(text, need_disclosure=False):
            return s
    raise RuntimeError(f"대본 점검 통과 실패: {prod['keyword']}")


def _threads_link(cfg, prod):
    prompt = THREADS_LINK_PROMPT.format(
        keyword=prod["keyword"], name=prod.get("name", ""), price=prod.get("price", "미확인"),
        notes=prod.get("notes", "") or "없음",
    )
    for _ in range(3):
        t = generate_json(prompt, cfg["llm"]["model"])["text"].strip()
        if not compliance.problems(t, need_disclosure=False):
            return t
    return None


def build_day(day: str | None = None) -> dict:
    cfg = load_config()
    day = day or today_str()
    pool = products.load_pool()
    if not pool:
        raise RuntimeError("영상·글로 만들 상품이 없습니다. data/manual_products.yaml 을 채웠는지 확인하세요.")
    usage = _usage()
    sched = cfg["schedule"]
    formats = cfg["shorts"]["formats"]

    shorts = []
    for number, prod in _pick(pool, sched["shorts_per_day"], usage):
        fmt = formats[usage["format_idx"] % len(formats)]
        usage["format_idx"] += 1
        s = _shorts(cfg, number, prod, fmt)
        shorts.append({"number": number, "format": fmt, "product": prod, "script": s, "done": False})
        usage["product"][prod["keyword"]] = usage["product"].get(prod["keyword"], 0) + 1

    link_posts = []
    for number, prod in _pick(pool, sched["threads_link_posts"], usage):
        t = _threads_link(cfg, prod)
        if t:
            link_posts.append({"kind": "link", "number": number, "product": prod, "text": t, "done": False})

    n_tips = sched["threads_per_day"] - len(link_posts)
    cats = sorted({p.get("category", "") for p in pool if p.get("category")}) or ["생활"]
    tips = generate_json(THREADS_TIP_PROMPT.format(n=n_tips, categories=", ".join(cats)), cfg["llm"]["model"])["posts"]
    tip_posts = [
        {"kind": "tip", "text": t.strip(), "done": False}
        for t in tips
        if not compliance.problems(t, need_disclosure=False)
    ][:n_tips]

    # 링크 글이 몰리지 않게 섞기: 팁, 팁, 링크 ...
    threads, li, ti = [], 0, 0
    for i in range(len(link_posts) + len(tip_posts)):
        if (i % 3 == 2 and li < len(link_posts)) or ti >= len(tip_posts):
            threads.append(link_posts[li]); li += 1
        else:
            threads.append(tip_posts[ti]); ti += 1

    q = {"day": day, "shorts": shorts, "threads": threads}
    write_json(queue_file(day), q)
    write_json(USAGE, usage)
    return q
