"""posts/<폴더>/slides.html 을 슬라이드 이미지(1.png, 2.png …)로 렌더링한다.

slides.html 안의 <section class="slide"> 하나가 1080x1350 슬라이드 한 장이다.
slides.html 내용이 바뀌면(.render_hash 와 다르면) 이전 슬라이드 이미지를 지우고 다시 그린다.
게시가 끝났거나 실패한 게시물은 건너뛴다.
렌더링 후 폴더에 README.md 미리보기(모든 장)를 만든다.

  python scripts/render_slides.py           렌더링
  python scripts/render_slides.py --check   렌더링할 게 있으면 종료 코드 10
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import POSTS_DIR  # noqa: E402

W, H = 1080, 1350
HASH_FILE = ".render_hash"


def html_hash(folder: Path) -> str:
    return hashlib.sha256((folder / "slides.html").read_bytes()).hexdigest()


def needs_render(folder: Path) -> bool:
    if not (folder / "slides.html").exists():
        return False
    meta = folder / "post.json"
    if meta.exists():
        status = json.loads(meta.read_text(encoding="utf-8")).get("status")
        if status in {"published", "failed"}:
            return False
    stored = (folder / HASH_FILE).read_text().strip() if (folder / HASH_FILE).exists() else ""
    has_images = any(p.stem.isdigit() for p in folder.glob("*.jpg")) or any(p.stem.isdigit() for p in folder.glob("*.png"))
    return stored != html_hash(folder) or not has_images


def targets() -> list[Path]:
    if not POSTS_DIR.exists():
        return []
    return [f for f in sorted(POSTS_DIR.iterdir()) if f.is_dir() and not f.name.startswith("_") and needs_render(f)]


def write_preview(folder: Path, n: int) -> None:
    title = folder.name
    meta = folder / "post.json"
    if meta.exists():
        title = json.loads(meta.read_text(encoding="utf-8")).get("title", title)
    lines = [f"# {title} — 미리보기 ({n}장)", ""]
    for i in range(1, n + 1):
        lines += [f"**{i} / {n}**", "", f'<img src="{i}.jpg" width="420">', ""]
    (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")


def render(page, folder: Path) -> int:
    for old in list(folder.glob("*.jpg")) + list(folder.glob("*.png")):
        if old.stem.isdigit():
            old.unlink()
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
    (folder / HASH_FILE).write_text(html_hash(folder) + "\n")
    write_preview(folder, len(slides))
    return len(slides)


def main() -> int:
    todo = targets()
    if "--check" in sys.argv:
        return 10 if todo else 0
    if not todo:
        print("렌더링할 슬라이드 없음")
        return 0
    from playwright.sync_api import sync_playwright

    failed = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for folder in todo:
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
