"""공통 유틸: 게시물 폴더 읽기, 검증, 시간 처리."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"

IG_CAPTION_MAX = 2200
IG_HASHTAG_MAX = 30
THREADS_TEXT_MAX = 500
SLIDES_MIN = 2
SLIDES_MAX = 10  # 운영 기준 7장, 안전 상한 10장 (API 상한은 20장)


@dataclass
class Post:
    folder: Path
    data: dict
    problems: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.folder.name

    @property
    def status(self) -> str:
        return self.data.get("status", "draft")

    @property
    def publish_at(self) -> datetime | None:
        raw = self.data.get("publish_at")
        if not raw:
            return None
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt

    def slide_files(self) -> list[Path]:
        """1.jpg, 2.jpg … 순서대로. 숫자 파일명만 인정."""
        files = [p for p in self.folder.glob("*.jpg") if p.stem.isdigit()]
        return sorted(files, key=lambda p: int(p.stem))

    def save(self) -> None:
        path = self.folder / "post.json"
        path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_posts() -> list[Post]:
    posts = []
    for folder in sorted(POSTS_DIR.iterdir()) if POSTS_DIR.exists() else []:
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        meta = folder / "post.json"
        if not meta.exists():
            continue
        posts.append(Post(folder=folder, data=json.loads(meta.read_text(encoding="utf-8"))))
    return posts


def validate(post: Post) -> list[str]:
    """게시 전에 막아야 할 문제를 모두 찾아 돌려준다."""
    problems = []
    slides = post.slide_files()
    if not (SLIDES_MIN <= len(slides) <= SLIDES_MAX):
        problems.append(f"슬라이드 수 {len(slides)}장 (허용 {SLIDES_MIN}~{SLIDES_MAX}장, 파일명 1.jpg부터 숫자로)")
    expected = [str(i) for i in range(1, len(slides) + 1)]
    if [p.stem for p in slides] != expected:
        problems.append("슬라이드 파일 번호가 1부터 빠짐없이 이어지지 않음")

    caption = post.data.get("instagram_caption", "")
    if not caption.strip():
        problems.append("instagram_caption이 비어 있음")
    if len(caption) > IG_CAPTION_MAX:
        problems.append(f"인스타 캡션 {len(caption)}자 (최대 {IG_CAPTION_MAX}자)")
    if caption.count("#") > IG_HASHTAG_MAX:
        problems.append(f"해시태그 {caption.count('#')}개 (최대 {IG_HASHTAG_MAX}개)")

    if post.data.get("threads", True):
        text = post.data.get("threads_text", "")
        if not text.strip():
            problems.append("threads_text가 비어 있음 (Threads에 안 올리려면 \"threads\": false)")
        if len(text) > THREADS_TEXT_MAX:
            problems.append(f"Threads 문구 {len(text)}자 (최대 {THREADS_TEXT_MAX}자)")

    if post.publish_at is None:
        problems.append("publish_at이 없음 (예: 2026-11-02T19:30:00+09:00)")
    return problems


def now_kst() -> datetime:
    override = os.environ.get("NOW_OVERRIDE")  # 테스트용
    if override:
        return datetime.fromisoformat(override)
    return datetime.now(KST)
