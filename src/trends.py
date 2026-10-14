"""네이버 데이터랩 쇼핑인사이트 '분야별 인기 검색어'에서 상위 키워드를 가져온다.

데이터랩 웹 화면이 쓰는 공개 엔드포인트를 그대로 호출한다(공식 API 아님).
화면 구조가 바뀌면 이 파일만 고치면 된다.
"""
import time
from datetime import timedelta

import requests

from common import now_kst

URL = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


def category_ranks(cid: str, days: int, count: int) -> list[str]:
    end = now_kst().date() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    keywords: list[str] = []
    page = 1
    while len(keywords) < count:
        resp = requests.post(
            URL,
            headers=HEADERS,
            data={
                "cid": cid,
                "timeUnit": "date",
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "age": "",
                "gender": "",
                "device": "",
                "page": page,
                "count": 20,
            },
            timeout=20,
        )
        resp.raise_for_status()
        ranks = resp.json().get("ranks", [])
        if not ranks:
            break
        keywords += [r["keyword"] for r in ranks]
        page += 1
        time.sleep(0.5)
    return keywords[:count]


def collect(cfg: dict) -> list[dict]:
    """카테고리별 순위를 모아 (키워드, 카테고리, 순위) 목록으로 돌려준다."""
    t = cfg["trends"]
    exclude = t.get("exclude_words", [])
    out = []
    for cid, name in t["categories"].items():
        try:
            kws = category_ranks(str(cid), t["lookback_days"], t["per_category"])
        except Exception as e:
            print(f"[{name}] 순위 수집 실패: {e}")
            continue
        for i, kw in enumerate(kws, 1):
            if any(w in kw for w in exclude):
                continue
            out.append({"keyword": kw, "category": name, "rank": i})
    return out


def interleave(items: list[dict]) -> list[dict]:
    """카테고리를 번갈아가며 순위 순으로 섞는다 (한 카테고리 쏠림 방지)."""
    by_cat: dict[str, list[dict]] = {}
    for it in items:
        by_cat.setdefault(it["category"], []).append(it)
    for v in by_cat.values():
        v.sort(key=lambda x: x["rank"])
    merged, seen = [], set()
    while any(by_cat.values()):
        for cat in list(by_cat):
            if by_cat[cat]:
                it = by_cat[cat].pop(0)
                if it["keyword"] not in seen:
                    seen.add(it["keyword"])
                    merged.append(it)
    return merged
