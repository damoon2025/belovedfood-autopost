# 그리운밥상 캐러셀 자동 게시

승인한 캐러셀을 예약 시각에 **인스타그램(@belovedfood.kr)과 Threads에 동시에** 올리는 저장소예요.
GitHub Actions가 15분마다 확인하고, 게시 결과는 각 게시물의 `post.json`에 기록돼요.

## 매주 쓰는 법

1. `posts/` 안에 날짜-주제 폴더를 만들어요. 예: `posts/2026-11-02-history/`
2. 슬라이드를 `1.png` ~ `7.png`로 넣어요. PNG·WebP·JPEG 모두 되고, 자동으로 1080×1350 JPEG로 바뀌어요.
3. `posts/_template/post.json`을 복사해 내용을 채워요.
4. 검수가 끝나면 `"status": "draft"`를 **`"approved"`**로 바꿔 커밋해요. 이게 승인이에요.
5. `publish_at` 시각이 지나면 다음 확인 때(15분 안) 게시돼요.

### post.json 항목

| 항목 | 설명 |
| --- | --- |
| `publish_at` | 게시 시각, 한국 시간. 예: `2026-11-02T19:30:00+09:00` |
| `status` | `draft` → `approved`(승인) → `published`(완료) / `failed`(실패) |
| `instagram_caption` | 인스타그램 캡션 (2,200자, 해시태그 30개 이내) |
| `threads` | Threads에도 올릴지 (`true`/`false`) |
| `threads_text` | Threads 문구 (500자 이내) |
| `ai_generated` | AI 이미지가 들어가면 `true` → 인스타그램에 AI 표시 |

### 실패했을 때

`post.json`의 `error`에 이유가 적혀요. 고친 뒤 `status`를 다시 `approved`로 바꾸면 돼요.
인스타그램은 성공하고 Threads만 실패했다면 다음 실행에서 **Threads만** 다시 시도해요.
실패하면 GitHub가 저장소 주인에게 이메일로 알려 줘요.

## 처음 한 번 설정

### 1. 저장소는 Public으로

이미지를 Meta 서버가 직접 내려받아야 해서 공개 주소가 필요해요. 그리고 15분마다 도는 작업이 Public 저장소에서는 무료예요.
토큰은 Secrets에 들어가서 공개되지 않아요. 단, 승인 전 게시물 이미지와 문구는 저장소에서 보일 수 있어요.

### 2. Secrets 등록

저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 넣어요.

| 이름 | 값 |
| --- | --- |
| `IG_ACCESS_TOKEN` | 인스타그램 장기 토큰 (Meta 앱의 Instagram 로그인 API 설정에서 생성) |
| `THREADS_SHORT_TOKEN` | Threads 이용 사례에서 생성한 토큰 (처음 한 번만) |
| `THREADS_APP_SECRET` | Meta 앱의 Threads 앱 시크릿 (처음 한 번만) |
| `GH_PAT` | 토큰 자동 연장용 GitHub 토큰 (아래 3번) |

그다음 **Actions → "Threads 토큰 장기 전환 (처음 한 번)" → Run workflow**를 누르면 `THREADS_ACCESS_TOKEN`이 자동으로 만들어져요.

### 3. GH_PAT 만들기

GitHub **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
- Repository access: 이 저장소만
- Permissions → Repository → **Secrets: Read and write**
- Expiration: 1년 (만료 전에 새로 만들어 `GH_PAT`만 바꿔 주면 돼요)

인스타그램·Threads 토큰은 60일마다 만료되지만, "토큰 자동 연장" 작업이 이 GH_PAT으로 매주 월요일 새벽에 연장해 줘요.

### 4. 테스트

**Actions → "캐러셀 자동 게시" → Run workflow**에서 `dry_run`을 `1`로 두고 실행하면 실제로 올리지 않고 무엇을 올릴지만 보여 줘요.

## 개발자용

```bash
pip install -r requirements.txt pytest
python -m pytest tests -q        # API 없이 전체 흐름 검증
DRY_RUN=1 python scripts/publish.py
```
