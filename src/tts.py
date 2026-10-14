"""edge-tts 로 장면별 나레이션 음성 생성 (무료)."""
import asyncio
import os
import subprocess
from pathlib import Path


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


async def _speak(text: str, voice: str, rate: str, path: Path):
    import edge_tts

    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


def speak(text: str, voice: str, rate: str, path: Path) -> float:
    """음성 파일을 만들고 길이(초)를 돌려준다.
    TTS_DRY=1 이면 글자 수에 비례한 무음을 만든다 (오프라인 테스트용)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get("TTS_DRY") == "1":
        secs = max(1.5, len(text) * 0.13)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", f"{secs:.2f}", "-q:a", "9", str(path)],
            check=True,
        )
        return secs
    for attempt in range(3):
        try:
            asyncio.run(_speak(text, voice, rate, path))
            return duration(path)
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"TTS 실패: {e}")
    return 0.0
