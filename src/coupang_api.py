"""쿠팡파트너스 Open API (최종 승인 후 사용 가능).

COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY 가 없으면 available() 이 False.
"""
import hashlib
import hmac
import os
import time
import urllib.parse

import requests

DOMAIN = "https://api-gateway.coupang.com"
SEARCH_PATH = "/v2/providers/affiliate_open_api/apis/openapi/products/search"


def available() -> bool:
    return bool(os.environ.get("COUPANG_ACCESS_KEY") and os.environ.get("COUPANG_SECRET_KEY"))


def _auth(method: str, path: str, query: str) -> str:
    access = os.environ["COUPANG_ACCESS_KEY"]
    secret = os.environ["COUPANG_SECRET_KEY"]
    signed_date = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
    message = signed_date + method + path + query
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={access}, "
        f"signed-date={signed_date}, signature={signature}"
    )


def search(keyword: str, limit: int = 5) -> list[dict]:
    """키워드로 상품 검색. 파트너스 링크(productUrl)가 함께 온다."""
    query = urllib.parse.urlencode({"keyword": keyword, "limit": limit})
    resp = requests.get(
        f"{DOMAIN}{SEARCH_PATH}?{query}",
        headers={"Authorization": _auth("GET", SEARCH_PATH, query), "Content-Type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {}) or {}
    items = data.get("productData", []) or []
    return [
        {
            "name": p.get("productName"),
            "price": p.get("productPrice"),
            "image_urls": [p.get("productImage")] if p.get("productImage") else [],
            "partner_url": p.get("productUrl"),
            "rocket": bool(p.get("isRocket")),
            "product_id": p.get("productId"),
        }
        for p in items
    ]
