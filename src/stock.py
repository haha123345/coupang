"""무료 스톡 사진 (Pixabay, 상업적 사용 가능·출처 표기 불필요). 키가 없으면 빈 목록."""
import os

import requests


def photos(query: str, n: int = 1) -> list[str]:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key or not query:
        return []
    try:
        r = requests.get("https://pixabay.com/api/", params={
            "key": key, "q": query, "image_type": "photo", "orientation": "vertical",
            "safesearch": "true", "per_page": 10, "order": "popular"}, timeout=20)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        return [h.get("largeImageURL") or h.get("webformatURL") for h in hits[:n]]
    except Exception as e:
        print("Pixabay 실패:", e)
        return []
