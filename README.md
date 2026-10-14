# 쿠팡파트너스 쇼핑 쇼츠·쓰레드 자동화

매주 인기 상품 10개를 고르고, 매일 **유튜브 쇼츠 2개 + 쓰레드 글 9개**를 자동으로 만들어 올립니다.
결과와 오류는 텔레그램으로 알려줍니다.

| 시간(한국) | 하는 일 | 워크플로 |
| --- | --- | --- |
| 월 06:10 | 네이버 데이터랩 인기 검색어 → 상품 10개 선정, 상품 모음 페이지 갱신 | `1 매주 인기 상품 선정` |
| 매일 06:40 | 오늘 쇼츠 대본 2개·쓰레드 글 9개 생성 (Gemini) | `2 매일 콘텐츠 준비` |
| 11:52, 18:52 | 쇼츠 1편씩 렌더링(상품 이미지+모션+AI 음성) → 업로드 | `3 쇼츠 제작·업로드` |
| 08:05~22:05, 9회 | 쓰레드 글 1개씩 게시 (링크 글 3개는 첫 답글에 파트너스 링크) | `4 쓰레드 게시` |
| 매월 1·20일 | 쓰레드 토큰 연장 | `5 쓰레드 토큰 연장` |

GitHub Actions 예약 실행은 몇 분~수십 분 늦게 시작될 수 있어요.

---

## 처음 한 번만 설정

모든 키는 **저장소 > Settings > Secrets and variables > Actions > New repository secret** 에 등록합니다. 코드에는 절대 넣지 마세요.

### 1. 쇼핑 채널용 구글 계정·유튜브 채널
기존 채널과 **다른 구글 계정**으로 새 채널을 만드세요. 저작권 경고는 같은 계정에 묶인 채널 전체에 영향을 줍니다.

### 2. Gemini API 키 (대본·글 생성, 무료)
1. https://aistudio.google.com/apikey 에서 키 만들기
2. Secret 등록: `GEMINI_API_KEY`

### 3. 텔레그램 알림
기존에 쓰던 봇을 그대로 써도 됩니다.
- `TELEGRAM_BOT_TOKEN` : BotFather 가 준 토큰
- `TELEGRAM_CHAT_ID` : 내 채팅 ID

### 4. 유튜브 업로드 (무료, YouTube Data API)
1. https://console.cloud.google.com 에서 새 프로젝트 → **YouTube Data API v3** 사용 설정
2. **OAuth 동의 화면**: 외부 → 앱 이름 입력 → 테스트 사용자에 쇼핑 채널 구글 계정 추가
   → 다 만든 뒤 **게시 상태를 '프로덕션 단계로 푸시'** (테스트 상태로 두면 토큰이 7일 만에 만료됩니다)
3. **사용자 인증 정보 > OAuth 클라이언트 ID > 데스크톱 앱** → JSON 다운로드 → `tools/client_secret.json` 으로 저장
4. 내 컴퓨터에서:
   ```
   pip install google-auth-oauthlib
   cd tools
   python get_youtube_token.py
   ```
   브라우저에서 **쇼핑 채널 계정**으로 로그인 → 출력된 값 3개를 Secret 등록:
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`

> ⚠️ **중요: 비공개 잠금**
> 구글 감사를 받지 않은 API 프로젝트로 올린 영상은 **비공개로 잠겨서 공개로 바꿀 수 없습니다.**
> - 무료로 풀려면: [YouTube API 감사 신청](https://support.google.com/youtube/contact/yt_api_form) (본인 채널 업로드용으로 신청, 승인까지 수 주)
> - 바로 공개하려면: Upload-Post Basic 결제 후 `config.yaml` 의 `shorts.backend` 를 `upload_post` 로 바꾸고
>   `UPLOAD_POST_API_KEY`, `UPLOAD_POST_USER`(프로필 이름) 등록
> - 감사 전까지 직접 올리려면: `backend: "telegram_only"` → 완성 영상이 텔레그램으로 옵니다

### 5. 쓰레드 게시 (무료, Threads API)
1. https://developers.facebook.com → **앱 만들기** → 사용 사례 **"Threads API 액세스"** 선택
2. 권한: `threads_basic`, `threads_content_publish` 추가
3. **앱 역할 > Threads 테스터** 에 쓰레드 계정 추가 → 쓰레드 앱 **설정 > 계정 > 웹사이트 권한 > 초대** 수락
4. **사용자 토큰 생성기**에서 토큰 발급(단기 토큰) → 브라우저 주소창에서 장기 토큰(60일)으로 교환:
   ```
   https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=앱시크릿&access_token=단기토큰
   ```
5. 나온 `access_token` 을 Secret `THREADS_ACCESS_TOKEN` 으로 등록
6. (선택) 토큰 자동 연장: GitHub > Settings > Developer settings > **Fine-grained token** (이 저장소, Secrets 읽기·쓰기) 를 만들어 `GH_PAT` 로 등록. 없으면 60일마다 직접 갱신하세요.

### 6. 상품 모음 페이지 (프로필 링크용)
쇼츠 설명란·댓글 링크는 클릭이 안 되므로, 영상에서는 "프로필 링크에서 N번"으로 안내합니다.
1. 저장소 **Settings > Pages > Deploy from a branch > `main` / `/docs`** 저장
2. 생긴 주소 `https://haha123345.github.io/coupang/` 를 **유튜브 채널 링크**와 **쓰레드 프로필 링크**에 등록

### 7. (나중에) 쿠팡파트너스 최종 승인 후
누적 판매 15만 원으로 최종 승인이 나면 파트너스 사이트에서 API 키를 발급받아
`COUPANG_ACCESS_KEY`, `COUPANG_SECRET_KEY` 를 등록하세요. 그 다음 주부터 상품·링크·이미지가 **완전 자동**이 됩니다.

### 8. 첫 실행
**Actions 탭** → 워크플로 사용 허용 → `1 매주 인기 상품 선정` → **Run workflow**.
그다음 아래 "매주 할 일"을 하고 `2` → `3` → `4` 순서로 한 번씩 수동 실행해 확인하세요.

---

## 매주 할 일 (API 키 등록 전까지, 약 10분)
월요일 아침 텔레그램으로 이번 주 키워드 10개와 편집 링크가 옵니다.
`data/manual_products.yaml` 을 열어 상품마다 **html 과 price 두 칸만** 채우고 **Commit changes**:

1. `search_url` 을 열어 상품을 고르고 주소를 복사
2. 쿠팡파트너스 > **링크 생성** > 상품 주소 붙여넣기 > **HTML** 복사
3. `html` 칸에 작은따옴표로 감싸서 붙여넣기

```yaml
  - keyword: 비데
    html: '<a href="https://link.coupang.com/a/xxxx" ...><img src="https://...coupangcdn.com/..." alt="상품명" ...></a>'
    price: "189000"                       # 가격(숫자만)
    notes: "온풍 건조, 노즐 자동 세척"      # (선택) 상세페이지에서 본 특징
```

상품명·파트너스 링크·사진은 `html` 에서 자동으로 뽑습니다.
사진을 더 넣고 싶으면 `image_urls` 에 추가하세요. 쿠팡 사진은 우클릭이 막혀 있으니
**사진을 브라우저 새 탭으로 끌어다 놓은 뒤 주소창 주소를 복사**하면 됩니다.

채우지 않은 상품은 건너뛰고, 아직 하나도 안 채웠으면 지난주 상품으로 계속 운영합니다.
`notes` 에 상세페이지의 실제 특징을 적으면 대본이 훨씬 구체적이고 정확해집니다.

---

## 자동으로 지키는 규칙
- **대가성 문구**: 쇼츠 첫 화면(크게)·전 구간(작게)·설명란 첫 줄, 쓰레드 본문 첫 줄·링크 답글, 상품 페이지 상단
- **가짜 사용 경험 금지**: "써보니", "내돈내산" 같은 표현이 들어가면 다시 생성 (실제로 써보지 않았으므로 기만 광고 위험)
- **지어낸 수치·의학적 효능·과장 표현 금지**, 가격은 "작성 시점·변동 가능" 표기
- **유튜브 표시**: 유료 광고 포함, AI 음성(합성 미디어) 사용 표시
- **쇼츠 형식 4가지 순환** (포인트 3가지 / 전후 비교 / 사지 말 것 / 가격·기준) — 같은 틀 반복 방지
- 쿠팡 로고·엠블럼 사용 안 함, 남의 영상 사용 안 함 (상품 이미지만 사용)

## 설정 바꾸기
`config.yaml` 에서 카테고리, 하루 개수, 링크 글 비율, 음성(남/여), 말 빠르기, 업로드 방식을 바꿀 수 있습니다.

## 폴더 구조
```
config.yaml              설정
src/main.py              명령 진입점 (weekly / prep / shorts / threads)
src/trends.py            네이버 데이터랩 인기 검색어
src/products.py          상품 선정 (API 자동 / 수동 목록)
src/coupang_api.py       쿠팡파트너스 API
src/content.py           대본·쓰레드 글 생성 (Gemini)
src/compliance.py        게시 전 점검
src/render.py, tts.py    영상 렌더링, 음성
src/youtube_upload.py    유튜브 업로드
src/threads_post.py      쓰레드 게시
src/pages.py             상품 모음 페이지 (docs/index.html)
data/                    주간 상품, 일일 대기열, 사용 기록 (자동 저장)
```
