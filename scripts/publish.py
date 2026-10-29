"""승인된 캐러셀을 예약 시각에 인스타그램과 Threads에 게시한다.

규칙
- post.json의 status가 "approved"이고 publish_at이 지난 게시물만 올린다.
- 인스타그램을 먼저 올리고, 성공했을 때만 Threads에 같은 이미지로 올린다.
- 단계마다 결과를 post.json에 기록하므로, 중간에 실패해도 다음 실행이
  이미 끝난 채널은 건너뛰고 남은 채널만 다시 시도한다.
- 한 장이라도 실패하면 장수를 줄여 올리지 않고 그 게시물 전체를 실패로 둔다.

환경 변수
  IG_ACCESS_TOKEN       인스타그램 장기 토큰 (Instagram 로그인 방식)
  THREADS_ACCESS_TOKEN  Threads 장기 토큰
  IMAGE_BASE_URL        이미지가 공개되는 주소의 앞부분.
                        예: https://raw.githubusercontent.com/OWNER/REPO/<커밋SHA>
  DRY_RUN=1             실제 호출 없이 무엇을 할지만 출력
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, Post, load_posts, now_kst, validate  # noqa: E402

IG_HOST = os.environ.get("IG_API_HOST", "https://graph.instagram.com")
IG_VERSION = os.environ.get("IG_API_VERSION", "v24.0")
TH_HOST = os.environ.get("THREADS_API_HOST", "https://graph.threads.net")
TH_VERSION = os.environ.get("THREADS_API_VERSION", "v1.0")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
TIMEOUT = 60


class PublishError(RuntimeError):
    pass


def _call(method: str, url: str, token: str, **params) -> dict:
    params["access_token"] = token
    if method == "GET":
        resp = requests.get(url, params=params, timeout=TIMEOUT)
    else:
        resp = requests.post(url, data=params, timeout=TIMEOUT)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text[:500]}
    if resp.status_code >= 400 or "error" in body:
        err = body.get("error", body)
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise PublishError(f"{method} {url.split('?')[0]} → {resp.status_code}: {msg}")
    return body


def _wait_ready(url: str, token: str, field: str, label: str) -> None:
    """컨테이너가 FINISHED가 될 때까지 최대 5분, 20초 간격으로 확인."""
    for _ in range(15):
        body = _call("GET", url, token, fields=field)
        state = body.get(field)
        if state == "FINISHED":
            return
        if state in {"ERROR", "EXPIRED"}:
            raise PublishError(f"{label} 컨테이너 상태 {state}: {body.get('error_message', '')}")
        time.sleep(20)
    raise PublishError(f"{label} 컨테이너가 5분 안에 준비되지 않음")


def image_urls(post: Post) -> list[str]:
    base = os.environ.get("IMAGE_BASE_URL", "").rstrip("/")
    if not base:
        raise PublishError("IMAGE_BASE_URL이 설정되지 않음")
    return [f"{base}/{p.relative_to(ROOT).as_posix()}" for p in post.slide_files()]


# ---------- Instagram ----------
def publish_instagram(post: Post, urls: list[str], token: str) -> str:
    api = f"{IG_HOST}/{IG_VERSION}"
    me = _call("GET", f"{api}/me", token, fields="user_id,username")
    uid = me.get("user_id") or me["id"]
    children = []
    for i, url in enumerate(urls, 1):
        body = _call("POST", f"{api}/{uid}/media", token, image_url=url, is_carousel_item="true")
        children.append(body["id"])
        print(f"  IG {i}/{len(urls)}장 컨테이너 생성")
    params = dict(media_type="CAROUSEL", children=",".join(children), caption=post.data["instagram_caption"])
    if post.data.get("ai_generated", True):
        params["is_ai_generated"] = "true"  # 부모 컨테이너에만 표시
    parent = _call("POST", f"{api}/{uid}/media", token, **params)["id"]
    _wait_ready(f"{api}/{parent}", token, "status_code", "인스타그램")
    media_id = _call("POST", f"{api}/{uid}/media_publish", token, creation_id=parent)["id"]
    return media_id


# ---------- Threads ----------
def publish_threads(post: Post, urls: list[str], token: str) -> str:
    api = f"{TH_HOST}/{TH_VERSION}"
    uid = _call("GET", f"{api}/me", token, fields="id,username")["id"]
    children = []
    for i, url in enumerate(urls, 1):
        body = _call("POST", f"{api}/{uid}/threads", token, media_type="IMAGE", image_url=url, is_carousel_item="true")
        children.append(body["id"])
        print(f"  Threads {i}/{len(urls)}장 컨테이너 생성")
    parent = _call(
        "POST", f"{api}/{uid}/threads", token,
        media_type="CAROUSEL", children=",".join(children), text=post.data["threads_text"],
    )["id"]
    _wait_ready(f"{api}/{parent}", token, "status", "Threads")
    return _call("POST", f"{api}/{uid}/threads_publish", token, creation_id=parent)["id"]


# ---------- 실행 ----------
def due_posts() -> list[Post]:
    now = now_kst()
    out = []
    for post in load_posts():
        if post.status != "approved":
            continue
        if post.publish_at and post.publish_at > now:
            continue
        out.append(post)
    return out


def run() -> int:
    posts = due_posts()
    if not posts:
        print("지금 게시할 승인된 게시물 없음")
        return 0

    failures = 0
    for post in posts:
        print(f"[{post.slug}] {post.data.get('title', '')}")
        problems = validate(post)
        if problems:
            failures += 1
            print("  검증 실패:\n   - " + "\n   - ".join(problems))
            if not DRY_RUN:
                post.data.update(status="failed", error="; ".join(problems))
                post.save()
            continue

        if DRY_RUN:
            print(f"  (드라이런) 인스타그램 {len(post.slide_files())}장 게시 예정")
            if post.data.get("threads", True):
                print(f"  (드라이런) Threads {len(post.slide_files())}장 게시 예정")
            continue

        try:
            urls = image_urls(post)
            if not post.data.get("instagram_media_id"):
                media_id = publish_instagram(post, urls, os.environ["IG_ACCESS_TOKEN"])
                post.data["instagram_media_id"] = media_id
                post.save()
                print(f"  인스타그램 게시 완료: {media_id}")
            if post.data.get("threads", True) and not post.data.get("threads_media_id"):
                th_id = publish_threads(post, urls, os.environ["THREADS_ACCESS_TOKEN"])
                post.data["threads_media_id"] = th_id
                post.save()
                print(f"  Threads 게시 완료: {th_id}")
            post.data.update(status="published", published_at=now_kst().isoformat(timespec="seconds"))
            post.data.pop("error", None)
            post.save()
        except (PublishError, KeyError, requests.RequestException) as exc:
            failures += 1
            post.data.update(status="failed", error=str(exc))
            post.save()
            print(f"  실패: {exc}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
