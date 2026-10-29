"""실제 API 없이 게시 흐름 전체를 검증한다: python -m pytest tests -q"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import common  # noqa: E402
import prepare_images  # noqa: E402
import publish  # noqa: E402


@pytest.fixture
def posts_dir(tmp_path, monkeypatch):
    d = tmp_path / "posts"
    d.mkdir()
    for mod in (common, prepare_images):
        monkeypatch.setattr(mod, "POSTS_DIR", d)
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(publish, "ROOT", tmp_path)
    monkeypatch.setattr(publish.time, "sleep", lambda s: None)
    monkeypatch.setenv("NOW_OVERRIDE", "2026-11-02T19:31:00+09:00")
    monkeypatch.setenv("IMAGE_BASE_URL", "https://raw.example/sha")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "ig-test")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "th-test")
    return d


def make_post(posts_dir, name, n=7, status="approved", publish_at="2026-11-02T19:30:00+09:00", ext="png", **extra):
    folder = posts_dir / name
    folder.mkdir()
    for i in range(1, n + 1):
        Image.new("RGBA", (1600, 2000), (200, 220, 200, 255)).save(folder / f"{i}.{ext}")
    data = {
        "title": name, "publish_at": publish_at, "status": status,
        "instagram_caption": "훅\n\n#그리운밥상 #동치미", "threads_text": "훅 #동치미",
    }
    data.update(extra)
    (folder / "post.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return folder


class FakeAPI:
    """인스타그램·Threads 응답을 흉내 낸다. 호출 기록을 남긴다."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.n = 0
        self.fail_on = fail_on

    def _resp(self, body, code=200):
        r = mock.Mock(status_code=code)
        r.json.return_value = body
        return r

    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, dict(params or {})))
        if url.endswith("/me"):
            return self._resp({"id": "TH1", "user_id": "IG1"})
        if params and params.get("fields") == "status_code":
            return self._resp({"status_code": "FINISHED"})
        if params and params.get("fields") == "status":
            return self._resp({"status": "FINISHED"})
        return self._resp({})

    def post(self, url, data=None, timeout=None):
        self.calls.append(("POST", url, dict(data or {})))
        if self.fail_on and self.fail_on in url:
            return self._resp({"error": {"message": "테스트 실패"}}, 400)
        self.n += 1
        return self._resp({"id": f"C{self.n}"})


def run_with(api):
    with mock.patch.object(publish.requests, "get", api.get), mock.patch.object(publish.requests, "post", api.post):
        return publish.run()


def test_prepare_converts_png_to_4x5_jpeg(posts_dir):
    folder = make_post(posts_dir, "a")
    prepare_images.main()
    jpgs = sorted(folder.glob("*.jpg"))
    assert len(jpgs) == 7 and not list(folder.glob("*.png"))
    with Image.open(jpgs[0]) as im:
        assert im.size == (1080, 1350) and im.mode == "RGB"


def test_full_publish_instagram_then_threads(posts_dir):
    folder = make_post(posts_dir, "a")
    prepare_images.main()
    api = FakeAPI()
    assert run_with(api) == 0
    data = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    assert data["status"] == "published"
    assert data["instagram_media_id"] and data["threads_media_id"]
    posts = [c for c in api.calls if c[0] == "POST"]
    ig_children = [c for c in posts if "graph.instagram.com" in c[1] and c[2].get("is_carousel_item") == "true"]
    th_children = [c for c in posts if "threads" in c[1] and c[2].get("is_carousel_item") == "true"]
    assert len(ig_children) == 7 and len(th_children) == 7
    assert ig_children[0][2]["image_url"] == "https://raw.example/sha/posts/a/1.jpg"
    parent = next(c for c in posts if c[2].get("media_type") == "CAROUSEL" and "instagram" in c[1])
    assert parent[2]["is_ai_generated"] == "true"
    # 인스타그램이 Threads보다 먼저
    first_th = next(i for i, c in enumerate(api.calls) if "threads" in c[1])
    last_ig = max(i for i, c in enumerate(api.calls) if "graph.instagram.com" in c[1])
    assert last_ig < first_th


def test_instagram_failure_skips_threads(posts_dir):
    folder = make_post(posts_dir, "a")
    prepare_images.main()
    api = FakeAPI(fail_on="media_publish")
    assert run_with(api) == 1
    data = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    assert data["status"] == "failed" and "테스트 실패" in data["error"]
    assert not any("threads" in c[1] for c in api.calls)


def test_retry_skips_finished_channel(posts_dir):
    folder = make_post(posts_dir, "a", instagram_media_id="IGDONE")
    prepare_images.main()
    api = FakeAPI()
    assert run_with(api) == 0
    assert not any("graph.instagram.com" in c[1] for c in api.calls)
    assert json.loads((folder / "post.json").read_text(encoding="utf-8"))["status"] == "published"


def test_not_due_and_not_approved_are_skipped(posts_dir):
    make_post(posts_dir, "later", publish_at="2026-11-04T19:30:00+09:00")
    make_post(posts_dir, "draft", status="draft")
    api = FakeAPI()
    assert run_with(api) == 0
    assert api.calls == []


def test_validation_blocks_bad_post(posts_dir):
    folder = make_post(posts_dir, "a", n=1, threads_text="가" * 501)
    prepare_images.main()
    api = FakeAPI()
    assert run_with(api) == 1
    data = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    assert data["status"] == "failed" and "슬라이드 수" in data["error"] and "Threads 문구" in data["error"]
    assert api.calls == []


def test_threads_disabled(posts_dir):
    make_post(posts_dir, "a", threads=False, threads_text="")
    prepare_images.main()
    api = FakeAPI()
    assert run_with(api) == 0
    assert not any("threads" in c[1] for c in api.calls)
