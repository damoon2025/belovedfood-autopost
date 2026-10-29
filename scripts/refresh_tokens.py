"""인스타그램·Threads 장기 토큰(60일)을 연장하고 GitHub Secrets에 다시 저장한다.

매주 한 번 실행되므로 토큰이 만료될 일이 없다. 새 토큰 값은 화면에 출력하지 않고
gh CLI의 표준 입력으로만 넘긴다.

필요한 환경 변수: IG_ACCESS_TOKEN, THREADS_ACCESS_TOKEN, GH_TOKEN(Secrets 쓰기 권한 PAT), GITHUB_REPOSITORY
"""
from __future__ import annotations

import os
import subprocess
import sys

import requests

TARGETS = [
    ("IG_ACCESS_TOKEN", "https://graph.instagram.com/refresh_access_token", "ig_refresh_token"),
    ("THREADS_ACCESS_TOKEN", "https://graph.threads.net/refresh_access_token", "th_refresh_token"),
]


def refresh(name: str, url: str, grant: str) -> bool:
    token = os.environ.get(name)
    if not token:
        print(f"{name}: 설정되지 않아 건너뜀")
        return True
    resp = requests.get(url, params={"grant_type": grant, "access_token": token}, timeout=60)
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    new = body.get("access_token")
    if resp.status_code >= 400 or not new:
        msg = body.get("error", {}).get("message", resp.text[:200]) if isinstance(body.get("error"), dict) else resp.text[:200]
        print(f"{name}: 갱신 실패 ({resp.status_code}) {msg}")
        return False
    subprocess.run(
        ["gh", "secret", "set", name, "--repo", os.environ["GITHUB_REPOSITORY"]],
        input=new.encode(), check=True,
    )
    days = int(body.get("expires_in", 0)) // 86400
    print(f"{name}: 갱신 완료, 약 {days}일 유효")
    return True


def main() -> int:
    ok = all([refresh(*t) for t in TARGETS])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
