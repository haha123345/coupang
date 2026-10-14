"""이번 주 상품 10개 선정.

- 쿠팡파트너스 API 키가 있으면: 인기 검색어 → API 검색 → 상품·링크 자동 확정
- 없으면(최종 승인 전): data/manual_products.yaml 에 키워드 10개를 적어두고
  텔레그램으로 알림 → 사용자가 파트너스 링크·이미지 주소만 채움
"""
import re
import urllib.parse

import yaml

import coupang_api
import notify
import trends
from common import DATA, load_config, read_json, today_str, week_file, write_json
from llm import generate_json

MANUAL = DATA / "manual_products.yaml"
LAST = DATA / "products_last.json"

PICK_PROMPT = """너는 쿠팡 쇼핑 쇼츠 채널의 상품 기획자야.
아래는 이번 주 네이버 쇼핑 분야별 인기 검색어 목록(카테고리, 순위)이야.

{items}

여기서 쇼츠로 소개하기 좋은 상품 키워드 {n}개를 골라.
규칙:
- 특정 브랜드명·모델명·쇼핑몰명이 들어간 키워드는 제외 (예: '다이슨', '나이키' 제외)
- 의약품, 건강기능식품, 성인용품, 담배, 주류, 시즌이 끝난 상품 제외
- 사진만 봐도 무엇인지 알 수 있는 실물 상품 위주
- 서로 겹치지 않게, 순위가 높은 것 우선, 카테고리를 고르게
JSON으로만 답해: {{"picks": [{{"keyword": "...", "category": "...", "reason": "한 줄"}}]}}
"""


def pick_keywords(cfg: dict) -> list[dict]:
    raw = trends.interleave(trends.collect(cfg))
    if not raw:
        raise RuntimeError("인기 검색어를 하나도 가져오지 못했습니다.")
    listing = "\n".join(f"- [{r['category']}] {r['rank']}위 {r['keyword']}" for r in raw[:160])
    n = cfg["trends"]["top_n"]
    try:
        picks = generate_json(PICK_PROMPT.format(items=listing, n=n), cfg["llm"]["model"], 0.3)["picks"]
    except Exception as e:
        (DATA / "last_error.txt").write_text(f"{e}\n모델 후보: {__import__('llm').available_models()}", encoding="utf-8")
        notify.send(f"[쿠팡] ⚠️ 키워드 선별(Gemini) 실패 — 영문 브랜드만 거르고 순위대로 사용\n{e}")
        # 최소한의 거르기: 영문 포함(브랜드일 가능성 큼) 제외
        picks = [r for r in raw if not re.search(r"[A-Za-z]", r["keyword"])]
    return picks[:n]


def coupang_search_url(keyword: str) -> str:
    return "https://www.coupang.com/np/search?q=" + urllib.parse.quote(keyword)


def weekly(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    picks = pick_keywords(cfg)

    if coupang_api.available():
        products = []
        for p in picks:
            try:
                found = coupang_api.search(p["keyword"], limit=5)
            except Exception as e:
                print(f"쿠팡 검색 실패 {p['keyword']}: {e}")
                continue
            if not found:
                continue
            best = next((x for x in found if x["rocket"]), found[0])
            products.append({**best, "keyword": p["keyword"], "category": p.get("category", "")})
        write_json(week_file(), {"week_of": today_str(), "mode": "api", "products": products})
        notify.send(
            f"[쿠팡] 이번 주 상품 {len(products)}개 자동 선정 완료\n"
            + "\n".join(f"{i}. {x['keyword']} — {x['name'][:30]}" for i, x in enumerate(products, 1))
        )
        return

    # 수동 모드: 템플릿 작성
    items = [
        {
            "keyword": p["keyword"],
            "category": p.get("category", ""),
            "search_url": coupang_search_url(p["keyword"]),
            "name": "",
            "price": "",
            "partner_url": "",
            "image_urls": [],
            "notes": "",
        }
        for p in picks
    ]
    header = (
        "# 이번 주 상품 목록 — 각 상품의 name, price, partner_url, image_urls 를 채워주세요.\n"
        "# 1) search_url 을 열어 상품을 고른다\n"
        "# 2) 쿠팡파트너스 > 링크 생성 으로 만든 링크(link.coupang.com/a/...)를 partner_url 에 붙여넣기\n"
        "# 3) 상품 사진 위에서 우클릭 > 이미지 주소 복사 → image_urls 에 2~4개\n"
        "# 채운 상품만 영상·글로 만들어집니다. 비워둔 상품은 건너뜁니다.\n"
    )
    MANUAL.parent.mkdir(parents=True, exist_ok=True)
    with open(MANUAL, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump({"week_of": today_str(), "items": items}, f, allow_unicode=True, sort_keys=False)
    write_json(week_file(), {"week_of": today_str(), "mode": "manual", "products": []})
    repo = __import__("os").environ.get("GITHUB_REPOSITORY", "haha123345/coupang")
    notify.send(
        "[쿠팡] 이번 주 인기 상품 키워드 10개를 골랐어요.\n"
        + "\n".join(f"{i}. {x['keyword']} ({x['category']})" for i, x in enumerate(items, 1))
        + f"\n\n아래 파일에서 파트너스 링크와 이미지 주소를 채워주세요:\n"
        f"https://github.com/{repo}/edit/main/data/manual_products.yaml"
    )


def _manual_ready() -> list[dict]:
    if not MANUAL.exists():
        return []
    with open(MANUAL, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    out = []
    for it in doc.get("items", []):
        if it.get("partner_url") and it.get("image_urls") and it.get("name"):
            urls = it["image_urls"]
            if isinstance(urls, str):
                urls = [urls]
            out.append({**it, "image_urls": [u for u in urls if u]})
    return out


def load_pool() -> list[dict]:
    """영상·글을 만들 수 있는(정보가 다 채워진) 이번 주 상품들."""
    wk = read_json(week_file(), {}) or {}
    if wk.get("mode") == "api" and wk.get("products"):
        return wk["products"]
    ready = _manual_ready()
    if ready:
        write_json(LAST, ready)
        return ready
    # 새 주 목록을 아직 안 채웠으면 지난주 상품으로 계속 운영
    return read_json(LAST, []) or []
