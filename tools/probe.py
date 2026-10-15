"""진단용: 쿠팡 위젯/상품 페이지를 GitHub 서버에서 열어 보고 data/debug/ 에 저장."""
import re, sys, pathlib, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
out = pathlib.Path("data/debug"); out.mkdir(parents=True, exist_ok=True)
for i, url in enumerate(sys.argv[1:]):
    try:
        r = requests.get(url, headers=UA, timeout=30, allow_redirects=True)
        hist = " -> ".join([h.url for h in r.history] + [r.url])
        (out / f"p{i}.html").write_text(r.text[:200000], encoding="utf-8")
        (out / f"p{i}.txt").write_text(f"{r.status_code}\n{hist}\n", encoding="utf-8")
        # 위젯 안 상품 링크를 한 단계 더 따라가 본다
        m = re.search(r'href="(https?://[^"]*coupang[^"]*)"', r.text)
        if m:
            r2 = requests.get(m.group(1).replace("&amp;", "&"), headers=UA, timeout=30, allow_redirects=True)
            (out / f"p{i}_2.html").write_text(r2.text[:300000], encoding="utf-8")
            (out / f"p{i}_2.txt").write_text(f"{r2.status_code}\n" + " -> ".join([h.url for h in r2.history] + [r2.url]), encoding="utf-8")
    except Exception as e:
        (out / f"p{i}.txt").write_text(f"ERR {e}", encoding="utf-8")
