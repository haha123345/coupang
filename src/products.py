"""이번 주 상품 10개 선정.

- 쿠팡파트너스 API 키가 있으면: 인기 검색어 → API 검색 → 상품·링크 자동 확정
- 없으면(최종 승인 전): data/manual_products.yaml 에 키워드 10개를 적어두고
  텔레그램으로 알림 → 사용자가 파트너스 링크·이미지 주소만 채움
"""
import html as html_lib
import json
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
- 특정 브랜드명·모델명·쇼핑몰명·캐릭터명이 들어간 키워드는 제외. 한글로 쓴 브랜드도 제외 (예: 다이슨, 나이키, 크록스, 포켓몬, 아이폰)
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
        (DATA / "last_error.txt").unlink(missing_ok=True)
    except Exception as e:
        (DATA / "last_error.txt").write_text(f"{e}\n모델 후보: {__import__('llm').available_models()}", encoding="utf-8")
        notify.send(f"[쿠팡] ⚠️ 키워드 선별(Gemini) 실패 — 영문 브랜드만 거르고 순위대로 사용\n{e}")
        # 최소한의 거르기: 영문 포함(브랜드일 가능성 큼) 제외
        picks = [r for r in raw if not re.search(r"[A-Za-z]", r["keyword"])]
    rank_of = {(r["keyword"]): r["rank"] for r in raw}
    for pk in picks:
        pk["trend_rank"] = rank_of.get(pk["keyword"], "")
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
            "trend_rank": p.get("trend_rank", ""),
            "search_url": coupang_search_url(p["keyword"]),
            "info": "",
            "partner_url": "",
            "notes": "",
            "price": "",
            "name": "",
            "image_urls": [],
        }
        for p in picks
    ]
    header = (
        "# 이번 주 상품 목록 — 상품마다 info 와 partner_url 두 칸만 채우면 됩니다.\n"
        "# 1) search_url 을 열어 상품을 고르고 상품 페이지로 들어가기\n"
        "# 2) 즐겨찾기의 '쿠팡수집' 을 누르기 → 상품명·가격·사진 6장이 복사됨\n"
        "#    info 칸 작은따옴표 안에 붙여넣기:  info: '{...}'\n"
        "# 3) 쿠팡파트너스 > 링크 생성 > 상품 주소 붙여넣기 > '단축 URL' 복사\n"
        "#    partner_url 칸에 붙여넣기:  partner_url: 'https://link.coupang.com/a/...'\n"
        "# notes 는 선택: 상세페이지에서 본 특징을 적으면 대본이 더 정확해집니다.\n"
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
        + f"\n\n아래 파일에서 상품마다 파트너스 'HTML' 코드와 가격을 채워주세요:\n"
        f"https://github.com/{repo}/edit/main/data/manual_products.yaml"
    )


def _bigger(url: str) -> str:
    """쿠팡 썸네일 주소면 큰 사이즈(640)로 바꾼다 (예: /remote/212x212ex/ → /remote/640x640ex/)."""
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url

    def up(m):
        return "/remote/640x640ex/" if int(m.group(1)) < 640 else m.group(0)
    return re.sub(r"/remote/(\d+)x\d+ex/", up, url)


def parse_partner_html(code: str) -> dict:
    """쿠팡파트너스 'HTML' 코드에서 링크·사진·상품명을 뽑는다."""
    code = html_lib.unescape(code or "")
    href = re.search(r"""href\s*=\s*["']([^"']+)["']""", code)
    imgs = re.findall(r"""<img[^>]+src\s*=\s*["']([^"']+)["']""", code, re.I)
    alt = re.search(r"""alt\s*=\s*["']([^"']*)["']""", code)
    text = re.sub(r"<[^>]+>", " ", code)
    text = re.sub(r"\s+", " ", text).strip()
    return {
        "partner_url": href.group(1).strip() if href else "",
        "image_urls": [_bigger(u) for u in imgs],
        "name": (alt.group(1).strip() if alt and alt.group(1).strip() else text)[:80],
    }


def parse_info(raw) -> dict:
    """'쿠팡수집' 북마크가 복사해 준 JSON(상품명·가격·사진들)을 읽는다."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        d = raw
    else:
        try:
            d = json.loads(str(raw).replace("’", "'"))
        except Exception:
            print("info 칸을 읽지 못했습니다:", str(raw)[:80])
            return {}
    num = lambda v: re.sub(r"[^0-9.]", "", str(v or ""))
    return {
        "name": (d.get("name") or "").strip(),
        "brand": (d.get("brand") or "").strip(),
        "price": num(d.get("price")).split(".")[0],
        "list_price": num(d.get("list_price")).split(".")[0],
        "rating": num(d.get("rating")),
        "reviews": num(d.get("reviews")).split(".")[0],
        "desc": (d.get("desc") or "").strip()[:400],
        "image_urls": [_bigger(u) for u in d.get("images", []) if u],
        "product_url": d.get("url", ""),
    }


def _manual_ready() -> list[dict]:
    if not MANUAL.exists():
        return []
    with open(MANUAL, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    out = []
    for it in doc.get("items", []):
        got = parse_partner_html(it.get("html", "")) if it.get("html") else {}
        info = parse_info(it.get("info"))
        urls = it.get("image_urls") or []
        if isinstance(urls, str):
            urls = [urls]
        images = []
        for u in [_bigger(u) for u in urls if u] + info.get("image_urls", []) + got.get("image_urls", []):
            if u not in images:
                images.append(u)
        partner = (it.get("partner_url") or got.get("partner_url") or "").strip()
        if "coupa.ng" in partner and "link.coupang.com" not in partner:
            partner = ""  # 위젯(iframe) 주소는 상품으로 바로 안 가므로 쓰지 않음
        merged = {
            **it,
            "partner_url": partner,
            "name": (it.get("name") or info.get("name") or got.get("name") or "").strip(),
            "image_urls": images[:6],
            "price": str(it.get("price") or info.get("price") or "").replace(",", "").replace("원", "").strip(),
            "product_url": info.get("product_url", ""),
        }
        for k in ("brand", "list_price", "rating", "reviews", "desc"):
            if info.get(k) and not merged.get(k):
                merged[k] = info[k]
        rank = it.get("trend_rank")
        merged["trend"] = (f"'{it['keyword']}' 인기 검색어 {rank}위" if rank
                           else f"요즘 많이 찾는 '{it['keyword']}'")
        merged.pop("html", None)
        merged.pop("info", None)
        if merged["partner_url"] and merged["image_urls"]:
            if not merged["name"]:
                merged["name"] = it["keyword"]
            out.append(merged)
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
