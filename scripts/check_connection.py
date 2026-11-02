"""게시 없이 토큰과 계정 연결만 확인한다. 토큰 값은 출력하지 않는다."""
from __future__ import annotations

import os
import sys

import requests

IG = "https://graph.facebook.com/v24.0"
TH = "https://graph.threads.net/v1.0"


def get(url: str, token: str, **params) -> tuple[int, dict]:
    params["access_token"] = token
    r = requests.get(url, params=params, timeout=60)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"raw": r.text[:300]}


def err(body: dict) -> str:
    e = body.get("error", body)
    return e.get("message", str(e)) if isinstance(e, dict) else str(e)


def main() -> int:
    ok = True

    ig_token = os.environ.get("IG_ACCESS_TOKEN", "")
    ig_id = os.environ.get("IG_USER_ID", "")
    if not ig_token:
        print("인스타그램: IG_ACCESS_TOKEN 시크릿이 없음")
        ok = False
    else:
        code, body = get(f"{IG}/{ig_id}", ig_token, fields="username,name")
        if code == 200 and "username" in body:
            print(f"인스타그램: 연결 성공 → @{body['username']}")
            code, lim = get(f"{IG}/{ig_id}/content_publishing_limit", ig_token, fields="quota_usage,config")
            if code == 200:
                data = (lim.get("data") or [{}])[0]
                total = data.get("config", {}).get("quota_total", "?")
                print(f"인스타그램: 게시 권한 확인 → 24시간 사용 {data.get('quota_usage', 0)}/{total}")
            else:
                print(f"인스타그램: 게시 권한 확인 실패 ({code}) {err(lim)}")
                ok = False
        else:
            print(f"인스타그램: 연결 실패 ({code}) {err(body)}")
            ok = False

    th_token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not th_token:
        print("Threads: THREADS_ACCESS_TOKEN 시크릿이 없음")
        ok = False
    else:
        code, body = get(f"{TH}/me", th_token, fields="id,username")
        if code == 200 and "username" in body:
            print(f"Threads: 연결 성공 → @{body['username']}")
        else:
            print(f"Threads: 연결 실패 ({code}) {err(body)}")
            ok = False

    print("결과:", "모두 정상" if ok else "확인 필요")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
