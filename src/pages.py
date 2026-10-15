"""유튜브·쓰레드 프로필에 걸 '이번 주 상품 모음' 페이지 (GitHub Pages: docs/index.html)."""
import html

import products
from common import ROOT, load_config, now_kst


def build() -> None:
    cfg = load_config()
    pool = products.load_pool()
    rows = []
    for i, p in enumerate(pool, 1):
        img = html.escape((p.get("image_urls") or [""])[0])
        if img.startswith("//"):
            img = "https:" + img
        price = p.get("price")
        price_txt = f"{int(price):,}원" if str(price).isdigit() else html.escape(str(price or ""))
        meta = []
        if p.get("rating") and p.get("reviews"):
            meta.append(f"★ {html.escape(str(p['rating']))} · 리뷰 {int(str(p['reviews']).replace(',', '')):,}개")
        lp = str(p.get("list_price") or "")
        if str(price).isdigit() and lp.isdigit() and int(lp) > int(price):
            meta.append(f"{int((int(lp) - int(price)) * 100 / int(lp))}% 할인")
        rv = (p.get("top_reviews") or [{}])[0].get("text")
        quote = f'<span class="q">“{html.escape(rv)}” <em>구매자 후기</em></span>' if rv else ""
        rows.append(
            f'<a class="item" id="n{i}" href="{html.escape(p["partner_url"])}" rel="sponsored noopener" target="_blank">'
            f'<span class="no">{i}</span><img src="{img}" alt="" loading="lazy">'
            f'<span class="txt"><b>{html.escape(p.get("name") or p["keyword"])}</b>'
            f'<span class="meta">{" · ".join(meta)}</span>{quote}'
            f'<small>{price_txt} · 작성 시점 기준, 가격 변동 가능</small>'
            f'<span class="go">쿠팡에서 보기 →</span></span></a>'
        )
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>이번 주 추천 상품</title>
<style>
:root{{--bg:#f6f6f4;--card:#fff;--ink:#16161a;--muted:#6b6b72;--acc:#ff5c35}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111114;--card:#1c1c21;--ink:#f2f2f2;--muted:#a0a0a8}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}}
main{{max-width:560px;margin:0 auto;padding:16px}}
.notice{{background:var(--card);border-left:4px solid var(--acc);padding:12px 14px;border-radius:10px;font-size:14px;line-height:1.5}}
h1{{font-size:22px;margin:20px 0 4px}} p.sub{{color:var(--muted);margin:0 0 14px;font-size:14px}}
.item{{display:flex;gap:12px;align-items:center;background:var(--card);border-radius:14px;padding:10px;margin:10px 0;color:inherit;text-decoration:none}}
.no{{flex:0 0 34px;height:34px;border-radius:50%;background:var(--acc);color:#fff;display:grid;place-items:center;font-weight:800}}
.item img{{width:72px;height:72px;object-fit:contain;background:#fff;border-radius:10px}}
.txt{{display:flex;flex-direction:column;gap:4px;min-width:0}} .txt b{{font-size:15px;line-height:1.35}}
.txt small{{color:var(--muted);font-size:12px}}
.meta{{font-size:13px;color:var(--acc);font-weight:700}}
.q{{font-size:13px;line-height:1.4}} .q em{{color:var(--muted);font-style:normal;font-size:11px}}
.go{{align-self:flex-start;margin-top:4px;background:var(--acc);color:#fff;font-weight:800;font-size:14px;padding:7px 14px;border-radius:999px}}
.item img{{width:96px;height:96px}}
</style></head><body><main>
<div class="notice">{html.escape(cfg["disclosure"]["short"])}</div>
<h1>영상 속 상품 번호로 찾으세요</h1>
<p class="sub">{now_kst():%Y.%m.%d} 업데이트</p>
{''.join(rows) or '<p>이번 주 상품을 준비 중이에요.</p>'}
</main></body></html>"""
    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
