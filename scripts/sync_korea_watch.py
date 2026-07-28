#!/usr/bin/env python3
"""Korea Watch 동기화 — _NIS korea_watch_db.csv 의 신규 행을 사이트 data/korea_watch.csv 로 append.

두 파일은 스키마가 동일하다(date,type,actor,affiliation,state_or_district,event,detail,race_link,significance,source_url).
- idempotent: (date, event) 키로 중복 방지 → 여러 번 실행해도 안전.
- 예시행·log-once 슈퍼시드(6/22류 D-1 트래커)는 제외.
- detail 안의 내부 수집메모(back-fill / log-once / 1회 등재 등)는 제거하고 사실만 보존.
- 수치·문장을 생성하지 않는다. DB에 있는 값만 옮긴다.

사용:
    python3 scripts/sync_korea_watch.py            # 실제 append
    python3 scripts/sync_korea_watch.py --dry-run  # 추가될 행만 출력(파일 미변경)
    python3 scripts/sync_korea_watch.py --db <경로> --site <경로>
"""
import argparse
import csv
import os
import sys

DEFAULT_DB = os.path.expanduser(
    "~/Library/CloudStorage/Dropbox/_NIS/2026_senate_election/"
    "2026_midterm_outlook/KoreaWatch/korea_watch_db.csv"
)
DEFAULT_SITE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "korea_watch.csv"
)

COLS = ["date", "type", "actor", "affiliation", "state_or_district",
        "event", "detail", "race_link", "significance", "source_url"]

# detail 세그먼트에서 이 조각이 들어간 부분은 내부 수집메모 → 제거(사실 세그먼트는 유지)
DROP_FRAGMENTS = ["back-fill", "log-once", "1회 등재", "수거분",
                  "수집 누락", "수집서 누락", "윈도우 경계", "추적 행 결말", "기등재"]


def clean_detail(detail: str) -> str:
    kept = [seg for seg in detail.split(";")
            if not any(fr in seg for fr in DROP_FRAGMENTS)]
    return ";".join(kept).strip().rstrip(";").strip()


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--site", default=DEFAULT_SITE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"[kw-sync] DB 없음: {args.db}", file=sys.stderr)
        return 1
    if not os.path.exists(args.site):
        print(f"[kw-sync] 사이트 csv 없음: {args.site}", file=sys.stderr)
        return 1

    site_rows = load_rows(args.site)
    # 사이트 최신 날짜 이후만 동기화한다(그 이전 이력은 이미 수작업/과거 sync로 반영됨 —
    # DB와 event 문구가 미세하게 달라 (date,event) 매칭이 불안정하므로 날짜 바닥으로 차단).
    site_max = max((r["date"] for r in site_rows), default="0000")
    existing_urls = {r["source_url"] for r in site_rows if r.get("source_url")}
    existing_de = {(r["date"], r["event"]) for r in site_rows}

    new_rows = []
    for r in load_rows(args.db):
        if r.get("type") == "예시행":
            continue
        d, ev, url = r["date"], r["event"], r.get("source_url", "")
        if d < site_max:                       # 사이트 최신일 이전 → 건드리지 않음
            continue
        if d == "2026-06-22" and "D-1" in ev:   # log-once: 6/24 결과행이 대체
            continue
        if url and url in existing_urls:        # 동일 기사 URL → idempotent skip(1차 키)
            continue
        if (d, ev) in existing_de:              # 보조 키(URL 없는 행)
            continue
        row = {c: r.get(c, "") for c in COLS}
        row["detail"] = clean_detail(row.get("detail", ""))
        new_rows.append(row)
        if url:
            existing_urls.add(url)
        existing_de.add((d, ev))

    new_rows.sort(key=lambda r: r["date"])

    if not new_rows:
        print("[kw-sync] 추가할 신규 행 없음 (최신 상태).")
        return 0

    print(f"[kw-sync] 신규 {len(new_rows)}행:")
    for r in new_rows:
        print(f"  {r['date']}  {r['type']:6}  {r['event'][:46]}")

    if args.dry_run:
        print("[kw-sync] --dry-run: 파일 미변경.")
        return 0

    with open(args.site, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in new_rows:
            w.writerow([r[c] for c in COLS])
    total = sum(1 for _ in open(args.site, encoding="utf-8")) - 1
    print(f"[kw-sync] append 완료 → 사이트 csv 총 {total}행.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
