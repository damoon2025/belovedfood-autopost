"""posts/ 안의 PNG·WebP·큰 JPEG를 인스타그램 규격 JPEG(1080x1350, 4:5)로 맞춘다.

인스타그램 API는 JPEG만 받는다. 캠버스에서 PNG로 내보낸 슬라이드를
그대로 올려 두면 이 스크립트가 같은 번호의 .jpg로 바꾸고 원본은 지운다.
바뀐 파일이 있으면 종료 코드 0과 함께 바뀐 경로를 출력한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import POSTS_DIR  # noqa: E402

TARGET = (1080, 1350)
SOURCE_EXT = {".png", ".webp", ".jpeg", ".jpg"}


def fit_4x5(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("RGB")
    return ImageOps.fit(img, TARGET, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def process(path: Path) -> Path | None:
    if not path.stem.isdigit() or path.suffix.lower() not in SOURCE_EXT:
        return None
    out = path.with_suffix(".jpg")
    with Image.open(path) as img:
        already_ok = path.suffix == ".jpg" and img.size == TARGET and img.mode == "RGB"
        if already_ok:
            return None
        fitted = fit_4x5(img)
    fitted.save(out, "JPEG", quality=90, optimize=True, progressive=True)
    if path != out:
        path.unlink()
    return out


def main() -> int:
    changed = []
    if POSTS_DIR.exists():
        for folder in sorted(POSTS_DIR.iterdir()):
            if folder.is_dir() and not folder.name.startswith("_"):
                for f in sorted(folder.iterdir()):
                    result = process(f)
                    if result:
                        changed.append(result)
    for c in changed:
        print(f"변환: {c.relative_to(POSTS_DIR.parent)}")
    if not changed:
        print("변환할 이미지 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
