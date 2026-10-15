"""쿠팡 상품 이미지 + 모션 편집으로 쇼츠(1080x1920) 렌더링.

디자인: 흰 바탕 '광고 컷' 스타일.
- 흰 배경 상품컷은 배경과 이어져 상품만 떠 보이고, 연출컷(방 사진 등)은 둥근 사진으로
- 상단: 스토리형 진행바 + 작은 광고 표시
- 상품 위: 실제 데이터 칩 (평점·리뷰 수, 네이버 인기 검색어, 할인율)
- 상품 아래: 형광펜 강조 헤드라인 + 자막
- 유튜브 쇼츠 하단 UI(설명·채널명)와 오른쪽 버튼에 가리지 않게 글자는 y<1520, x<940 안쪽
"""
import io
import subprocess
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

import tts

W, H, FPS = 1080, 1920, 30
CX = 510                     # 오른쪽 쇼츠 버튼을 피해 살짝 왼쪽 중심
SAFE_W = 860
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36"}

BG = (255, 255, 255)
INK = (17, 17, 20)
MUTED = (110, 110, 118)
ACCENTS = {
    "top3_points": (255, 72, 54),
    "before_after": (0, 168, 150),
    "dont_buy_instead": (255, 170, 0),
    "price_check": (54, 110, 255),
}

FONT_CANDIDATES = {
    "black": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"],
    "bold": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
             "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"],
    "medium": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
               "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
}
_font_cache: dict = {}


def font(size: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    key = (size, weight)
    if key in _font_cache:
        return _font_cache[key]
    for w in (weight, "bold", "black", "medium"):
        for p in FONT_CANDIDATES[w]:
            if Path(p).exists():
                f = ImageFont.truetype(p, size, index=1)  # KR
                _font_cache[key] = f
                return f
    raise RuntimeError("한글 폰트가 없습니다 (fonts-noto-cjk 설치 필요)")


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.replace("\n", " \n ").split(" "):
        if word == "\n":
            lines.append(cur); cur = ""; continue
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = ""
        for ch in word:
            if draw.textlength(cur + ch, font=fnt) > max_w and cur:
                lines.append(cur); cur = ch
            else:
                cur += ch
    if cur:
        lines.append(cur)
    return [l for l in lines if l.strip()]


def load_image(src: str) -> Image.Image:
    if src.startswith("//"):
        src = "https:" + src
    if src.startswith("http"):
        r = requests.get(src, headers=UA, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
    else:
        img = Image.open(src)
    return ImageOps.exif_transpose(img).convert("RGB")


def is_cutout(img: Image.Image) -> bool:
    """가장자리가 거의 흰색이면 '누끼(흰 배경) 상품컷'."""
    w, h = img.size
    px = img.load()
    pts = [(x, y) for x in range(0, w, max(1, w // 20)) for y in (0, h - 1)] + \
          [(x, y) for y in range(0, h, max(1, h // 20)) for x in (0, w - 1)]
    bright = sum(1 for p in pts if min(px[p]) > 238)
    return bright / len(pts) > 0.85


def product_layer(img: Image.Image, box: int = 900) -> Image.Image:
    """상품 이미지를 투명 배경 RGBA 레이어로. 누끼면 그대로, 연출컷이면 둥근 사진+그림자."""
    if is_cutout(img):
        inner = ImageOps.contain(img, (box, box), Image.LANCZOS).convert("RGBA")
        layer = Image.new("RGBA", (box, box), (0, 0, 0, 0))
        layer.paste(inner, ((box - inner.width) // 2, (box - inner.height) // 2))
        return layer
    pad = 40
    inner = ImageOps.fit(img, (box - pad * 2, box - pad * 2), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", inner.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, inner.width, inner.height], 44, fill=255)
    inner.putalpha(mask)
    layer = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([pad, pad + 18, box - pad, box - pad + 18], 44, fill=(0, 0, 0, 70))
    layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22)))
    layer.alpha_composite(inner, (pad, pad))
    return layer


def chip(d, x, y, text, fnt, fill, ink, pad=(26, 14), r=30):
    tw = d.textlength(text, font=fnt)
    bb = fnt.getbbox(text)
    h = bb[3] - bb[1]
    d.rounded_rectangle([x, y, x + tw + pad[0] * 2, y + h + pad[1] * 2], r, fill=fill)
    d.text((x + pad[0], y + pad[1] - bb[1]), text, font=fnt, fill=ink)
    return x + tw + pad[0] * 2


def headline_layer(text: str, highlight: str, accent) -> Image.Image:
    """형광펜 강조 헤드라인 (최대 2줄)."""
    layer = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    size = 96
    while size > 64:
        f = font(size, "black")
        lines = wrap(d, text, f, SAFE_W)
        if len(lines) <= 2:
            break
        size -= 6
    lh = size + 22
    y0 = (260 - lh * len(lines)) // 2
    mark = accent + (95,)
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=f)
        x = CX - tw / 2
        y = y0 + i * lh
        hl = highlight if highlight and highlight in line else (line if not highlight else "")
        if hl:
            pre = line[: line.index(hl)]
            hx = x + d.textlength(pre, font=f)
            hw = d.textlength(hl, font=f)
            d.rectangle([hx - 6, y + size * 0.52, hx + hw + 6, y + size * 1.08], fill=mark)
        d.text((x, y - f.getbbox(line)[1] + 6), line, font=f, fill=INK)
    return layer


def subtitle_layer(text: str) -> Image.Image:
    layer = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(44, "medium")
    lines = wrap(d, text, f, SAFE_W - 40)[:3]
    lh = 60
    y = (200 - lh * len(lines)) // 2
    for line in lines:
        tw = d.textlength(line, font=f)
        d.text((CX - tw / 2, y), line, font=f, fill=MUTED)
        y += lh
    return layer


def chrome_layer(n_scenes: int, idx: int, prog: float, accent, disclosure: str, big: bool) -> Image.Image:
    """진행바 + 광고 표시."""
    layer = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    gap, x0, x1, y = 10, 40, W - 40, 44
    seg = (x1 - x0 - gap * (n_scenes - 1)) / n_scenes
    for i in range(n_scenes):
        sx = x0 + i * (seg + gap)
        d.rounded_rectangle([sx, y, sx + seg, y + 8], 4, fill=(225, 225, 230))
        fillw = seg if i < idx else (seg * prog if i == idx else 0)
        if fillw > 1:
            d.rounded_rectangle([sx, y, sx + fillw, y + 8], 4, fill=accent)
    if big:
        f = font(36, "bold")
        lines = wrap(d, disclosure, f, W - 160)
        h = 40 + 50 * len(lines)
        d.rounded_rectangle([40, 76, W - 40, 76 + h], 26, fill=(17, 17, 20, 235))
        yy = 96
        for l in lines:
            tw = d.textlength(l, font=f)
            d.text(((W - tw) / 2, yy), l, font=f, fill=(255, 255, 255))
            yy += 50
    else:
        f = font(28, "medium")
        chip(d, 40, 76, "광고 · 쿠팡 파트너스 수수료 지급", f, (240, 240, 243), MUTED, pad=(20, 10), r=22)
    return layer


def fmt_count(n) -> str:
    try:
        n = int(str(n).replace(",", ""))
    except Exception:
        return str(n)
    if n >= 10000:
        v = int(n / 1000) / 10   # 내림 (16,629 → 1.6만)
        return f"{v:.1f}만".replace(".0만", "만")
    return f"{n:,}"


def facts_chips(prod: dict) -> list[str]:
    out = []
    if prod.get("rating") and prod.get("reviews"):
        out.append(f"★ {prod['rating']} · 리뷰 {fmt_count(prod['reviews'])}개")
    try:
        p, lp = int(prod.get("price") or 0), int(prod.get("list_price") or 0)
        if lp > p > 0 and (lp - p) / lp >= 0.1:
            out.append(f"{round((lp - p) / lp * 100)}% 할인 중")
    except Exception:
        pass
    if prod.get("trend"):
        out.append(prod["trend"])
    return out


def cta_layer(number: int, prod: dict, accent) -> Image.Image:
    layer = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(66, "black")
    msg = f"프로필 링크 ▶ {number}번"
    tw = d.textlength(msg, font=f)
    d.rounded_rectangle([CX - tw / 2 - 44, 20, CX + tw / 2 + 44, 136], 58, fill=accent)
    lum = 0.299 * accent[0] + 0.587 * accent[1] + 0.114 * accent[2]
    d.text((CX - tw / 2, 34), msg, font=f, fill=INK if lum > 170 else (255, 255, 255))
    price = str(prod.get("price") or "")
    if price.isdigit():
        fp, fs = font(48, "black"), font(36, "medium")
        p_txt = f"{int(price):,}원"
        lp = str(prod.get("list_price") or "")
        parts = [(p_txt, fp, INK)]
        if lp.isdigit() and int(lp) > int(price):
            parts.insert(0, (f"{int(lp):,}원", fs, MUTED))
        total = sum(d.textlength(t, font=ft) for t, ft, _ in parts) + 24 * (len(parts) - 1)
        x = CX - total / 2
        for t, ft, col in parts:
            yy = 180 if ft is fp else 190
            d.text((x, yy), t, font=ft, fill=col)
            w = d.textlength(t, font=ft)
            if ft is fs:
                d.line([x, yy + 24, x + w, yy + 24], fill=MUTED, width=3)
            x += w + 24
        fn = font(26, "medium")
        note = "작성 시점 기준 · 가격은 바뀔 수 있어요"
        d.text((CX - d.textlength(note, font=fn) / 2, 252), note, font=fn, fill=MUTED)
    return layer


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def render(item: dict, cfg: dict, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    prod, script, number = item["product"], item["script"], item["number"]
    accent = ACCENTS.get(item.get("format"), ACCENTS["top3_points"])
    imgs = [load_image(u) for u in prod["image_urls"][:6]]
    layers = [product_layer(im) for im in imgs]
    voice, rate = cfg["shorts"]["voice"], cfg["shorts"]["rate"]

    scenes = list(script["scenes"])
    if script.get("hook"):
        scenes[0] = {**scenes[0], "caption": script["hook"], "highlight": script.get("hook_highlight", "")}

    # 1) 장면별 음성 → 길이
    parts, durs = [], []
    for i, sc in enumerate(scenes):
        a = workdir / f"a{i}.mp3"
        durs.append(tts.speak(sc["narration"], voice, rate, a) + 0.2)
        parts.append(a)
    audio = workdir / "voice.m4a"
    inputs, filt = [], []
    for i, (a, d) in enumerate(zip(parts, durs)):
        inputs += ["-i", str(a)]
        filt.append(f"[{i}:a]aresample=44100,apad=whole_dur={d:.3f}[p{i}]")
    filt.append("".join(f"[p{i}]" for i in range(len(durs))) + f"concat=n={len(durs)}:v=0:a=1[out]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "[out]", "-c:a", "aac", "-b:a", "160k", str(audio)], check=True)

    # 2) 프레임
    out = workdir / "short.mp4"
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE,
    )
    disclosure = cfg["disclosure"]["short"]
    chips = facts_chips(prod)
    chip_font = font(34, "bold")
    n = len(scenes)
    cta = cta_layer(number, prod, accent)
    prev_last = None
    PROD_Y, BOX = 320, 830

    for si, (sc, dur) in enumerate(zip(scenes, durs)):
        layer = layers[si % len(layers)]
        head = headline_layer(sc["caption"], sc.get("highlight", ""), accent)
        sub = subtitle_layer(sc["narration"])
        last = si == n - 1
        # 장면별로 보여줄 칩: 첫 장면은 전부, 이후엔 하나씩 돌아가며
        rest = [chips[si % len(chips)]] if chips and not last and si > 0 else []
        scene_chips = [f"No.{number}"] + (chips[:2] if si == 0 else rest)
        frames = int(round(dur * FPS))
        z0, z1 = (1.0, 1.07) if si % 2 == 0 else (1.07, 1.0)
        for f in range(frames):
            t = f / FPS
            p = f / max(1, frames - 1)
            frame = Image.new("RGBA", (W, H), BG + (255,))
            # 상품 (켄번스 + 등장 시 살짝 커지며 페이드)
            intro = ease_out(t / 0.35)
            z = (z0 + (z1 - z0) * p) * (0.94 + 0.06 * intro)
            size = int(BOX * z)
            pl = layer.resize((size, size), Image.BILINEAR)
            if intro < 1:
                a = pl.getchannel("A").point(lambda v, k=intro: int(v * k))
                pl.putalpha(a)
            frame.alpha_composite(pl, (int(CX - size / 2), int(PROD_Y + (BOX - size) / 2)))
            d = ImageDraw.Draw(frame)
            # 사실 칩
            cy = 236
            cx = 40
            for ci, c in enumerate(scene_chips):
                appear = ease_out((t - 0.25 - ci * 0.12) / 0.3)
                if appear <= 0:
                    continue
                col = (17, 17, 20) if ci == 0 else (accent if ci == 1 else (60, 60, 68))
                nx = chip(d, cx, cy + int((1 - appear) * 20), c, chip_font,
                          col + (int(235 * appear),), (255, 255, 255))
                cx = nx + 12
                if cx > 700:
                    cx, cy = 40, cy + 72
            # 헤드라인 (아래에서 올라오며)
            hy = 1150 + int((1 - ease_out(t / 0.3)) * 50)
            if last and t > 0.25:
                frame.alpha_composite(cta, (0, 1150))
            else:
                frame.alpha_composite(head, (0, hy))
                frame.alpha_composite(sub, (0, 1400))
            frame.alpha_composite(chrome_layer(n, si, p, accent, disclosure, big=(si == 0 and t < 2.4)), (0, 0))
            rgb = frame.convert("RGB")
            # 장면 전환 크로스페이드
            if prev_last is not None and t < 0.2:
                rgb = Image.blend(prev_last, rgb, t / 0.2)
            proc.stdin.write(rgb.tobytes())
            if f == frames - 1:
                prev_last = rgb
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("영상 인코딩 실패")
    return out
