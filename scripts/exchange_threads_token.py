"""Threads 단기 토큰(1시간)을 장기 토큰(60일)으로 바꿔 THREADS_ACCESS_TOKEN에 저장한다.

필요한 환경 변수: THREADS_SHORT_TOKEN, THREADS_APP_SECRET, GH_TOKEN, GITHUB_REPOSITORY
토큰 값은 출력하지 않는다.
"""
from __future__ import annotations

import os
import subprocess
import sys

import requests


def main() -> int:
    resp = requests.get(
        "https://graph.threads.net/access_token",
        params={
            "grant_type": "th_exchange_token",
            "client_secret": os.environ["THREADS_APP_SECRET"],
            "access_token": os.environ["THREADS_SHORT_TOKEN"],
        },
        timeout=60,
    )
    body = resp.json()
    token = body.get("access_token")
    if resp.status_code >= 400 or not token:
        print(f"전환 실패 ({resp.status_code}): {body.get('error', {}).get('message', body)}")
        return 1
    subprocess.run(
        ["gh", "secret", "set", "THREADS_ACCESS_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
        input=token.encode(), check=True,
    )
    print(f"THREADS_ACCESS_TOKEN 저장 완료, 약 {int(body.get('expires_in', 0)) // 86400}일 유효")
    print("이제 THREADS_SHORT_TOKEN 시크릿은 지워도 됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
