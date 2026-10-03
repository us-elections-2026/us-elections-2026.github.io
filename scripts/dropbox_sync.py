#!/usr/bin/env python3
"""GitHub Actions ↔ Dropbox 동기화 (일일 자동 발행용, 2026-10-03).

  pull  : _NIS senate_daily/ 의 원문(KR)·정리본(site/)·정리 프롬프트를 로컬 폴더로 내려받는다.
  push  : 정리본 파일을 Dropbox senate_daily/site/ 에 올린다(_NIS 보관본 유지).

인증(둘 중 하나):
  A) 환경변수 DROPBOX_APP_KEY · DROPBOX_APP_SECRET · DROPBOX_REFRESH_TOKEN  — scoped app, files.content.read/write
     (refresh 토큰은 scripts/dropbox_auth.py 로 한 번 발급)
  B) 환경변수 DROPBOX_SHARED_LINK — senate_daily 폴더의 공유 링크(dl=1 zip). pull 전용, push 불가.
표준 라이브러리만 사용.
사용:  python3 scripts/dropbox_sync.py pull --out <dir> [--since YYYY-MM-DD]
       python3 scripts/dropbox_sync.py push <local_file> [--dest site]
"""
from __future__ import annotations  # 호스트 python3(3.9)의 `X | None` 힌트 호환
import argparse
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

BASE = "/_NIS/2026_senate_election/2026_midterm_outlook"
DAILY = f"{BASE}/senate_daily"
PROMPT = f"{BASE}/pipeline_prompts/상원_일일_사이트정리_프롬프트.md"


def token() -> str:
    k, s, r = (os.environ.get(x) for x in ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN"))
    if not (k and s and r):
        raise SystemExit("DROPBOX_APP_KEY/APP_SECRET/REFRESH_TOKEN 없음")
    data = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": r, "client_id": k, "client_secret": s}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://api.dropboxapi.com/oauth2/token", data=data), timeout=60) as resp:
        return json.load(resp)["access_token"]


def rpc(tok: str, ep: str, arg: dict) -> dict:
    req = urllib.request.Request(f"https://api.dropboxapi.com/2/{ep}", data=json.dumps(arg).encode(),
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def list_folder(tok: str, path: str) -> list[dict]:
    out, r = [], rpc(tok, "files/list_folder", {"path": path, "recursive": False})
    out += r["entries"]
    while r.get("has_more"):
        r = rpc(tok, "files/list_folder/continue", {"cursor": r["cursor"]}); out += r["entries"]
    return [e for e in out if e[".tag"] == "file"]


def download(tok: str, path: str) -> bytes:
    req = urllib.request.Request("https://content.dropboxapi.com/2/files/download",
                                 headers={"Authorization": f"Bearer {tok}", "Dropbox-API-Arg": json.dumps({"path": path})})  # 헤더는 ASCII — 한글 경로는 \\u 이스케이프
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def upload(tok: str, path: str, data: bytes) -> dict:
    arg = {"path": path, "mode": "overwrite", "autorename": False, "mute": True}
    req = urllib.request.Request("https://content.dropboxapi.com/2/files/upload", data=data,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/octet-stream",
                                          "Dropbox-API-Arg": json.dumps(arg)})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def pull_api(out: Path, since: str | None) -> int:
    tok = token(); n = 0
    (out / "site").mkdir(parents=True, exist_ok=True)
    for e in list_folder(tok, DAILY):
        nm = e["name"]
        if not (nm.endswith("_일일브리핑_KR.md") and (not since or nm[:10] >= since)):
            continue
        (out / nm).write_bytes(download(tok, e["path_lower"])); n += 1
    for e in list_folder(tok, f"{DAILY}/site"):
        nm = e["name"]
        if nm.endswith("_site_KR.md") and (not since or nm[:10] >= since):
            (out / "site" / nm).write_bytes(download(tok, e["path_lower"])); n += 1
    (out / "_prompt.md").write_bytes(download(tok, PROMPT))
    return n


def pull_link(out: Path, since: str | None) -> int:
    link = os.environ["DROPBOX_SHARED_LINK"]
    link = link.replace("dl=0", "dl=1") if "dl=" in link else link + ("&" if "?" in link else "?") + "dl=1"
    with urllib.request.urlopen(urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"}), timeout=300) as resp:
        z = zipfile.ZipFile(io.BytesIO(resp.read()))
    n = 0
    (out / "site").mkdir(parents=True, exist_ok=True)
    for info in z.infolist():
        nm = Path(info.filename).name
        if nm.endswith("_일일브리핑_KR.md") and (not since or nm[:10] >= since):
            (out / nm).write_bytes(z.read(info)); n += 1
        elif nm.endswith("_site_KR.md") and "site" in info.filename and (not since or nm[:10] >= since):
            (out / "site" / nm).write_bytes(z.read(info)); n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pull", "push"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--out", default="senate_daily_sync")
    ap.add_argument("--since")
    ap.add_argument("--dest", default="site")
    a = ap.parse_args()
    if a.cmd == "pull":
        out = Path(a.out)
        if os.environ.get("DROPBOX_REFRESH_TOKEN"):
            n = pull_api(out, a.since); print(f"[dropbox] API pull: {n}개 파일 → {out} (+프롬프트)")
        elif os.environ.get("DROPBOX_SHARED_LINK"):
            n = pull_link(out, a.since); print(f"[dropbox] 공유링크 pull: {n}개 파일 → {out} (프롬프트는 저장소 사본 사용)")
        else:
            raise SystemExit("Dropbox 인증 정보 없음(DROPBOX_REFRESH_TOKEN 또는 DROPBOX_SHARED_LINK)")
        return 0
    if not a.file:
        raise SystemExit("push 할 파일 경로 필요")
    if not os.environ.get("DROPBOX_REFRESH_TOKEN"):
        print("[dropbox] refresh 토큰 없음 — push 건너뜀(정리본은 저장소에만 남음)"); return 0
    p = Path(a.file); r = upload(token(), f"{DAILY}/{a.dest}/{p.name}", p.read_bytes())
    print(f"[dropbox] push: {r.get('path_display')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
