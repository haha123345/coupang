"""게시 전 자동 점검: 대가성 문구 누락, 가짜 사용 경험 표현, 과장 표현."""
import re

# 실제로 써보지 않았는데 써본 것처럼 말하면 표시광고법상 기만 광고가 될 수 있음
FAKE_EXPERIENCE = [
    "써보니", "써봤", "써 봤", "직접 써", "제가 써", "내돈내산", "사용해보니", "사용해봤",
    "사용해 봤", "구매해보니", "구매해봤", "샀는데", "사봤", "써본 결과", "우리 집에서",
]
OVERCLAIM = ["100%", "무조건", "최저가 보장", "부작용 없", "효과 보장", "완치", "치료"]


def problems(text: str, need_disclosure: bool, disclosure_markers=("쿠팡 파트너스", "쿠팡파트너스")) -> list[str]:
    found = []
    if need_disclosure and not any(m in text for m in disclosure_markers):
        found.append("대가성 문구 없음")
    for w in FAKE_EXPERIENCE:
        if w in text:
            found.append(f"사용 경험처럼 보이는 표현: '{w}'")
    for w in OVERCLAIM:
        if w in text:
            found.append(f"과장 표현: '{w}'")
    if re.search(r"(?:https?://|www\.)", text) and "link.coupang.com" not in text and "github.io" not in text:
        found.append("허용되지 않은 링크")
    return found
