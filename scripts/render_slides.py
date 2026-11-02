"""posts/<폴더>/slides.html 을 슬라이드 이미지(1.png, 2.png …)로 렌더링한다.

slides.html 안의 <section class="slide"> 하나가 1080x1350 슬라이드 한 장이다.
이미 1.jpg 또는 1.png 가 있는 폴더는 건너뛴다(다시 그리려면 이미지를 지우면 된다).
게시가 끝났거나 실패한 게시물도 건너뛴다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import POSTS_DIR  # noqa: E402

W, H = 1080, 1350


def needs_render(folder: Path) -> bool:
    if not (folder / "slides.html").exists():
        return False
    if (folder / "1.jpg").exists() or (folder / "1.png").exists():
        return False
    meta = folder / "post.json"
    if meta.exists():
        status = json.loads(meta.read_text(encoding="utf-8")).get("status")
        if status in {"published", "failed"}:
            return False
    return True


def render(page, folder: Path) -> int:
    page.goto((folder / "slides.html").resolve().as_uri(), wait_until="networkidle", timeout=120_000)
    page.evaluate("document.fonts.ready")
    broken = page.evaluate(
        "Array.from(document.images).filter(i => !i.complete || i.naturalWidth === 0).map(i => i.src)"
    )
    if broken:
        raise RuntimeError("이미지를 불러오지 못함: " + ", ".join(broken))
    slides = page.query_selector_all("section.slide")
    if not slides:
        raise RuntimeError("section.slide 가 없음")
    for i, el in enumerate(slides, 1):
        el.screenshot(path=str(folder / f"{i}.png"))
    return len(slides)


def main() -> int:
    targets = [f for f in sorted(POSTS_DIR.iterdir()) if f.is_dir() and not f.name.startswith("_") and needs_render(f)] if POSTS_DIR.exists() else []
    if not targets:
        print("렌더링할 슬라이드 없음")
        return 0
    from playwright.sync_api import sync_playwright

    failed = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for folder in targets:
            try:
                n = render(page, folder)
                print(f"렌더링: {folder.name} {n}장")
            except Exception as exc:  # 한 게시물이 실패해도 나머지는 진행
                failed += 1
                print(f"렌더링 실패: {folder.name} — {exc}")
        browser.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
