"""쿠팡 상품 이미지 + 모션 편집으로 쇼츠(1080x1920) 렌더링.

장면마다: 흐린 배경 + 상품 카드(천천히 확대·이동) + 큰 자막 + 나레이션 자막.
첫 화면 상단에 대가성 문구를 크게, 이후에도 작게 계속 표시한다.
"""
import io
import random
import subprocess
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

import tts

W, H, FPS = 1080, 1920, 30
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36"}

THEMES = {
    "top3_points": {"accent": (255, 92, 53), "bg_tint": (20, 20, 28)},
    "before_after": {"accent": (46, 196, 182), "bg_tint": (14, 26, 30)},
    "dont_buy_instead": {"accent": (255, 196, 0), "bg_tint": (30, 22, 10)},
    "price_check": {"accent": (88, 140, 255), "bg_tint": (14, 18, 34)},
}

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size, index=1 if p.endswith(".ttc") else 0)
            except Exception:
                return ImageFont.truetype(p, size)
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
        for ch in word:  # 한 단어가 너무 길면 글자 단위로 자름
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


def make_bg(img: Image.Image, tint) -> Image.Image:
    bg = ImageOps.fit(img, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    return Image.blend(bg, Image.new("RGB", (W, H), tint), 0.62)


def make_card(img: Image.Image, size=860) -> Image.Image:
    card = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    inner = ImageOps.contain(img, (size - 60, size - 60), Image.LANCZOS)
    card.paste(inner, ((size - inner.width) // 2, (size - inner.height) // 2))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], 48, fill=255)
    card.putalpha(mask)
    return card


def text_layer(lines, fnt, y, fill, stroke=(0, 0, 0), stroke_w=8, box=None, line_gap=14):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    heights = [fnt.getbbox(l)[3] - fnt.getbbox(l)[1] for l in lines]
    total = sum(heights) + line_gap * (len(lines) - 1)
    if box:
        widest = max(d.textlength(l, font=fnt) for l in lines)
        pad = 28
        d.rounded_rectangle(
            [(W - widest) / 2 - pad, y - pad, (W + widest) / 2 + pad, y + total + pad + 10], 26, fill=box
        )
    cy = y
    for l, h in zip(lines, heights):
        tw = d.textlength(l, font=fnt)
        d.text(((W - tw) / 2, cy - fnt.getbbox(l)[1]), l, font=fnt, fill=fill,
               stroke_width=stroke_w, stroke_fill=stroke)
        cy += h + line_gap
    return layer


def overlay_static(disclosure: str, number: int, accent, big: bool) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if big:
        f = font(40)
        lines = wrap(d, disclosure, f, W - 120)
        h = 60 + 54 * len(lines)
        d.rectangle([0, 0, W, h + 40], fill=(0, 0, 0, 200))
        y = 60
        for l in lines:
            tw = d.textlength(l, font=f)
            d.text(((W - tw) / 2, y), l, font=f, fill=(255, 255, 255))
            y += 54
    else:
        f = font(30)
        msg = "광고 · 쿠팡 파트너스 활동으로 수수료를 받습니다"
        tw = d.textlength(msg, font=f)
        d.rounded_rectangle([(W - tw) / 2 - 20, 70, (W + tw) / 2 + 20, 122], 20, fill=(0, 0, 0, 150))
        d.text(((W - tw) / 2, 78), msg, font=f, fill=(255, 255, 255, 230))
    fb = font(46)
    badge = f"No.{number}"
    bw = d.textlength(badge, font=fb)
    d.rounded_rectangle([60, 250, 60 + bw + 44, 322], 22, fill=accent + (255,))
    d.text((82, 254), badge, font=fb, fill=(255, 255, 255))
    return layer


def cta_layer(number: int, price, accent) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(64)
    msg = f"프로필 링크 ▶ {number}번"
    tw = d.textlength(msg, font=f)
    d.rounded_rectangle([(W - tw) / 2 - 40, 1150, (W + tw) / 2 + 40, 1260], 40, fill=accent + (255,))
    lum = 0.299 * accent[0] + 0.587 * accent[1] + 0.114 * accent[2]
    d.text(((W - tw) / 2, 1162), msg, font=f, fill=(20, 20, 24) if lum > 160 else (255, 255, 255))
    if price:
        fp = font(36)
        p = f"{int(price):,}원 (작성 시점 · 가격 변동 가능)" if str(price).isdigit() else f"{price} (가격 변동 가능)"
        pw = d.textlength(p, font=fp)
        d.text(((W - pw) / 2, 1280), p, font=fp, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    return layer


def render(item: dict, cfg: dict, workdir: Path) -> Path:
    """queue의 쇼츠 항목 하나를 mp4로 만든다."""
    workdir.mkdir(parents=True, exist_ok=True)
    prod, script, number = item["product"], item["script"], item["number"]
    theme = THEMES.get(item.get("format"), THEMES["top3_points"])
    accent = theme["accent"]
    imgs = [load_image(u) for u in prod["image_urls"][:4]]
    voice, rate = cfg["shorts"]["voice"], cfg["shorts"]["rate"]

    scenes = list(script["scenes"])
    scenes[0] = {**scenes[0], "caption": script.get("hook") or scenes[0]["caption"]}

    # 1) 장면별 음성 → 길이 결정
    audio_parts, durs = [], []
    for i, sc in enumerate(scenes):
        a = workdir / f"a{i}.mp3"
        d = tts.speak(sc["narration"], voice, rate, a)
        audio_parts.append(a)
        durs.append(d + 0.25)

    # 2) 음성 합치기 (장면 길이에 맞춰 무음 패딩)
    audio = workdir / "voice.m4a"
    inputs, filt = [], []
    for i, (a, d) in enumerate(zip(audio_parts, durs)):
        inputs += ["-i", str(a)]
        filt.append(f"[{i}:a]aresample=44100,apad=whole_dur={d:.3f}[p{i}]")
    filt.append("".join(f"[p{i}]" for i in range(len(durs))) + f"concat=n={len(durs)}:v=0:a=1[out]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "[out]", "-c:a", "aac", "-b:a", "160k", str(audio)], check=True)

    # 3) 프레임 생성 → ffmpeg 로 바로 인코딩
    out = workdir / "short.mp4"
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE,
    )
    cap_font, sub_font = font(92), font(48)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    disclosure = cfg["disclosure"]["short"]
    small_overlay = overlay_static(disclosure, number, accent, big=False)
    big_overlay = overlay_static(disclosure, number, accent, big=True)
    last_cta = cta_layer(number, prod.get("price"), accent)

    for si, (sc, dur) in enumerate(zip(scenes, durs)):
        src = imgs[si % len(imgs)]
        bg = make_bg(src, theme["bg_tint"])
        card = make_card(src)
        lum = 0.299 * accent[0] + 0.587 * accent[1] + 0.114 * accent[2]
        cap_ink = (20, 20, 24) if lum > 160 else (255, 255, 255)  # 밝은 강조색엔 검은 글자
        cap = text_layer(wrap(probe, sc["caption"], cap_font, W - 140), cap_font, 1360,
                         fill=cap_ink, box=accent + (235,), stroke_w=0)
        sub = text_layer(wrap(probe, sc["narration"], sub_font, W - 160), sub_font, 1640,
                         fill=(255, 255, 255), stroke_w=6)
        direction = random.choice([-1, 1])
        zoom_from, zoom_to = (1.0, 1.10) if si % 2 == 0 else (1.10, 1.0)
        frames = int(round(dur * FPS))
        for f in range(frames):
            t = f / FPS
            p = f / max(1, frames - 1)
            frame = bg.copy()
            z = zoom_from + (zoom_to - zoom_from) * p
            size = int(card.width * z * 0.92)
            c = card.resize((size, size), Image.BILINEAR)
            slide = int(140 * (1 - min(1, t / 0.22)) ** 2) * direction
            drift = int(24 * (p - 0.5)) * direction
            frame.paste(c, ((W - size) // 2 + slide + drift, 330 + (860 - size) // 2), c)
            cap_off = int(60 * (1 - min(1, t / 0.18)) ** 2)
            frame.paste(cap, (0, cap_off), cap)
            frame.paste(sub, (0, 0), sub)
            ov = big_overlay if (si == 0 and t < 2.5) else small_overlay
            frame.paste(ov, (0, 0), ov)
            if si == len(scenes) - 1 and t > 0.3:
                frame.paste(last_cta, (0, 0), last_cta)
            proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("영상 인코딩 실패")
    return out
