"""하루치 콘텐츠 생성: 쇼츠 대본 N개 + 쓰레드 글 N개 → data/queue/YYYY-MM-DD.json"""
import random
import re

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

SHORTS_PROMPT = """너는 조회수와 구매 전환이 높은 한국 쇼핑 쇼츠 카피라이터야.
아래 상품으로 보는 사람이 '이거 사고 싶다'고 느끼게 만드는 25~35초 쇼츠 대본을 써.

[상품]
- 상품명: {name} (브랜드: {brand})
- 이 상품이 속한 검색 키워드: {keyword} / 카테고리: {category}
- 소개 번호: {number}번

[확인된 사실 — 숫자·순위·인기 표현은 반드시 여기 있는 것만 써]
{facts}

[구성] {format_guide}
{review_rule}
[잘 팔리는 대본 공식]
1) 첫 장면(훅): 위 사실 중 가장 센 것 하나로 2초 안에 멈추게 해.
   예) "리뷰 1만6천 개 달린 비데", "정가 29만 원이 지금 16만 원대", "요즘 네이버에서 제일 많이 찾는 비데"
2) 공감: 이 상품을 찾는 사람이 겪는 불편을 한 문장으로 콕 집기
3) 해결: 상품명·특징 정보에 근거한 장점 2~3개를 '그래서 뭐가 좋아지는지'로 말하기
4) 사회적 증거: 평점·리뷰 수·인기 검색어 같은 사실로 '다들 이걸 고르는 이유'를 보여주기
5) 가격 앵커: 정가 대비 할인이 있으면 강조, "가격은 바뀔 수 있어요" 붙이기 (할인율은 숫자 그대로. 50% 미만을 '반값'이라고 하지 마)
6) 마지막: "프로필 링크에서 {number}번 확인하세요"

[절대 금지 — 어기면 허위·기만 광고]
- 위 사실에 없는 순위·판매량·수상·'1등'·'완판' 표현을 지어내지 마.
  (인기 검색어 순위는 '{keyword}'라는 검색어의 순위지 이 상품의 판매 순위가 아님 → "요즘 많이 찾는 {keyword}" 처럼만 써)
- 연예인·유명인·인플루언서가 썼다는 말 금지 (메모에 '확인됨'으로 적힌 경우만 예외)
- 직접 써봤다, 샀다, 우리 집에서 등 사용 경험처럼 들리는 말 금지
- 효능·치료·건강 개선 같은 의학 표현, '무조건/100%/최저가' 금지
- 모르는 스펙은 지어내지 말고 "상세페이지에서 꼭 확인하세요"로

[말투] 친구한테 추천하듯 자연스러운 구어체, 문장은 짧고 리듬감 있게. 매 장면 다음이 궁금하게.

JSON으로만 답해:
{{
 "title": "유튜브 제목 (40자 이내, 사실 기반 후킹, 끝에 #shorts)",
 "hook": "첫 화면 큰 글자 (12자 이내)",
 "hook_highlight": "hook 안에서 형광펜 칠할 단어 (hook에 그대로 들어있는 부분 문자열)",
 "scenes": [
   {{"caption": "화면 큰 글자 (12자 이내)", "highlight": "caption 안의 강조 단어", "narration": "읽을 문장 1~2개", "type": "normal"}}
 ],
 "description": "영상 설명 2~3줄 (링크 넣지 마)",
 "hashtags": ["#태그", "..."]
}}
scenes 는 5~6개.
"""

THREADS_LINK_PROMPT = """너는 한국 스레드(Threads)에서 살림·생활 정보를 쓰는 계정이야.
아래 상품을 소개하는 글 1개를 써.

[상품] 키워드: {keyword} / 상품명: {name} / 메모: {notes}
[확인된 사실 — 숫자·인기 표현은 이것만]
{facts}

규칙:
- 직접 써봤다, 샀다 같은 사용 경험처럼 들리는 말 금지 (우리는 써보지 않았어).
- 정보에 없는 수치·후기·별점을 지어내지 마. 효능·의학 표현, 과장 금지.
- [실제 후기]가 있으면 그중 1개를 "구매자 후기 중" 이라고 밝히고 큰따옴표 안에 글자 그대로 인용해도 좋아 (고치기·지어내기 금지).
- 첫 줄은 사실(리뷰 수·할인·많이 찾는 검색어) 하나로 시선을 끌고, '고를 때 볼 기준'을 짧게 알려준 뒤
  이 상품이 그 기준에 맞는 예시라고 소개. 연예인 사용·판매 1위 같은 지어낸 말 금지.
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
- 각 글 300자 이내. 한두 문장마다 줄바꿈(\\n)을 넣고, 첫 줄은 짧은 한 줄 후킹으로. 이모지 0~2개, 해시태그 금지.
글마다 어울리는 사진을 찾을 영어 검색어(2~3단어, 예: "blackout curtain bedroom")도 같이 줘.
JSON으로만: {{"posts": [{{"text": "...", "photo": "english keywords"}}]}}
"""


REVIEW_RULE = """
[실제 구매자 후기 장면 — 꼭 1개 넣어]
- 3~4번째 장면 하나를 "type": "reviews" 로 표시해. 이 장면 화면에는 아래 [실제 후기] 문장이 카드로 그대로 뜬다.
- caption 예: "구매자 반응은?", "후기 보니까" (12자 이내)
- narration: [실제 후기] 중 1~2개를 큰따옴표 안에 글자 하나 바꾸지 말고 그대로 읽어. 예) 구매자 후기 보면 "편하고 수압 좋아요" 이런 말이 많아요.
- 후기를 고치거나, 없는 후기를 만들거나, '제가/저희가 샀다'처럼 말하지 마. 퍼센트는 '별 5개 비율'만 쓸 수 있어.
"""


def _norm(t: str) -> str:
    return re.sub(r"[\s.,!?~'\"‘’“”]", "", t)


def quotes_ok(script: dict, prod: dict) -> bool:
    """대본 속 따옴표 문장이 실제 후기에 있는 말인지 확인 (후기 조작 방지)."""
    real = [_norm(r["text"]) for r in prod.get("top_reviews") or []]
    text = " ".join(x.get("narration", "") + " " + x.get("caption", "") for x in script.get("scenes", []))
    for q in re.findall(r'["“]([^"”]{4,})["”]', text):
        if not any(_norm(q) and _norm(q) in r for r in real):
            return False
    # 후기 장면 내레이션에는 실제 후기 문장이 하나 이상 그대로 들어 있어야 함
    for x in script.get("scenes", []):
        if x.get("type") == "reviews" and real and not any(r and r in _norm(x.get("narration", "")) for r in real):
            return False
    return True


def strip_quotes(text: str) -> str:
    """점검할 때 실제 후기 인용 부분은 빼고 본다 ('구매했어요' 같은 후기 원문 때문에 막히지 않게)."""
    return re.sub(r'["“][^"”]*["”]', "", text)


def _won(v) -> str:
    return f"{int(v):,}원" if str(v).isdigit() else str(v)


def facts_text(prod: dict) -> str:
    f = []
    price, lp = str(prod.get("price") or ""), str(prod.get("list_price") or "")
    if price.isdigit():
        if lp.isdigit() and int(lp) > int(price):
            pct = int((int(lp) - int(price)) * 100 / int(lp))  # 쿠팡 표기처럼 내림
            f.append(f"- 가격(작성 시점): 정가 {_won(lp)} → 지금 {_won(price)} ({pct}% 할인)")
        else:
            f.append(f"- 가격(작성 시점): {_won(price)}")
    if prod.get("rating") and prod.get("reviews"):
        f.append(f"- 쿠팡 평점 {prod['rating']}점, 상품평 {int(str(prod['reviews']).replace(',', '')):,}개")
    if prod.get("buyers"):
        f.append(f"- 쿠팡 상품 페이지 표시: '{prod['buyers']}' (쿠팡이 보여주는 구매자 수)")
    if prod.get("trend_rank"):
        f.append(f"- '{prod['keyword']}'는 이번 주 네이버 쇼핑 '{prod.get('category', '')}' 분야 인기 검색어 {prod['trend_rank']}위 (검색어 순위)")
    else:
        f.append(f"- '{prod['keyword']}'는 이번 주 네이버 쇼핑 인기 검색어 상위권 (검색어 순위)")
    if prod.get("five_star_pct"):
        f.append(f"- 쿠팡 전체 상품평 중 별 5개 비율 {prod['five_star_pct']}%")
    for sv in prod.get("survey") or []:
        f.append(f"- 후기 설문(추천순 상위 후기 {sv['tot']}개 기준): '{sv['q']}' → '{sv['a']}' {sv['n']}개"
                 " (말할 땐 '후기 대부분이 ~래요' 정도로만, 퍼센트로 바꾸지 마)")
    for r in prod.get("top_reviews") or []:
        f.append(f"- [실제 후기] 별{r['rating']} \"{r['text']}\"")
    if prod.get("desc") and not str(prod["desc"]).startswith("현재 별점"):
        f.append(f"- 상품 설명(판매자 제공): {str(prod['desc'])[:300]}")
    if prod.get("notes"):
        f.append(f"- 메모: {prod['notes']}")
    return "\n".join(f)


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
        keyword=prod["keyword"], name=prod.get("name", ""), brand=prod.get("brand") or "미확인",
        category=prod.get("category", ""), facts=facts_text(prod),
        number=number, format_guide=FORMAT_GUIDE[fmt],
        review_rule=REVIEW_RULE if prod.get("top_reviews") else "",
    )
    for _ in range(4):
        s = generate_json(prompt, cfg["llm"]["model"])
        text = " ".join(x["narration"] + " " + x["caption"] for x in s["scenes"]) + s["title"] + s["description"]
        if compliance.problems(strip_quotes(text), need_disclosure=False) or not quotes_ok(s, prod):
            continue
        if prod.get("top_reviews"):
            rv = [x for x in s["scenes"] if x.get("type") == "reviews"]
            if not rv:  # 표시를 빠뜨렸으면 '후기'를 말하는 장면을 후기 장면으로
                cand = [x for x in s["scenes"][1:-1] if "후기" in x.get("narration", "")]
                if cand:
                    cand[0]["type"] = "reviews"
        return s
    raise RuntimeError(f"대본 점검 통과 실패: {prod['keyword']}")


def _threads_link(cfg, prod):
    prompt = THREADS_LINK_PROMPT.format(
        keyword=prod["keyword"], name=prod.get("name", ""),
        notes=prod.get("notes", "") or "없음", facts=facts_text(prod),
    )
    for _ in range(3):
        t = generate_json(prompt, cfg["llm"]["model"])["text"].strip()
        if not compliance.problems(strip_quotes(t), need_disclosure=False) and \
                quotes_ok({"scenes": [{"narration": t}]}, prod):
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
    tip_posts = []
    for t in tips:
        text = (t.get("text") if isinstance(t, dict) else str(t)).strip()
        query = t.get("photo", "") if isinstance(t, dict) else ""
        if compliance.problems(text, need_disclosure=False):
            continue
        tip_posts.append({"kind": "tip", "text": text, "photo_query": query, "done": False})
    tip_posts = tip_posts[:n_tips]

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
