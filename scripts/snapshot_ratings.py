#!/usr/bin/env python3
"""등급 스냅샷 축적 — 주지사·상원 피드의 '변동'만 이력으로 쌓는다.

fetch_governor_ratings.py / fetch_senate_ratings.py 가 만든 현재 상태 파일을 읽어,
직전 스냅샷과 **달라진 경우에만** 새 항목을 추가한다(같으면 아무것도 하지 않음 → idempotent).
이렇게 쌓인 이력이 나중에 주지사판 '등급 변동 매트릭스'의 원천이 된다.

산출물:
  data/history/governor_rating_snapshots.json
  data/history/senate_rating_snapshots.json
형식: {"snapshots": [{"captured": "YYYY-MM-DD", "sources": {기관명: {"as_of": ..., "ratings": {...}}}}]}

사용: python3 scripts/snapshot_ratings.py [--date YYYY-MM-DD]
  --date 미지정 시 오늘 날짜(로컬)로 기록한다.
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "data", "history")
JOBS = [
    ("governor_ratings.json", "governor_rating_snapshots.json", "주지사"),
    ("senate_ratings_feed.json", "senate_rating_snapshots.json", "상원"),
]


def load(p):
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def compact(cur):
    """기관별 as_of + ratings만 남긴 비교 가능한 형태로 축약."""
    return {s["label"]: {"as_of": s.get("as_of"), "ratings": s.get("ratings", {})}
            for s in cur.get("sources", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    day = args.date or datetime.date.today().isoformat()
    os.makedirs(HIST, exist_ok=True)

    rc = 0
    for src_name, hist_name, label in JOBS:
        cur = load(os.path.join(ROOT, "data", src_name))
        if cur is None:
            print(f"[snap] ! {label}: {src_name} 없음 — 건너뜀", file=sys.stderr)
            continue
        now = compact(cur)
        hp = os.path.join(HIST, hist_name)
        hist = load(hp) or {"note": "등급이 바뀐 시점만 기록(동일하면 미기록). 원천은 270towin 재게시 피드.",
                            "snapshots": []}
        prev = hist["snapshots"][-1]["sources"] if hist["snapshots"] else None
        if prev == now:
            print(f"[snap] {label}: 변동 없음 — 기록 생략 (누적 {len(hist['snapshots'])}건)")
            continue
        # 무엇이 바뀌었는지 요약(사람이 읽는 용도)
        changes = []
        if prev:
            for lab, cs in now.items():
                ps = prev.get(lab)
                if not ps:
                    changes.append(f"{lab}: 신규 기관"); continue
                for st, v in cs["ratings"].items():
                    pv = ps["ratings"].get(st)
                    if pv != v:
                        changes.append(f"{lab} {st}: {pv} → {v}")
        hist["snapshots"].append({"captured": day, "sources": now,
                                  "changes": changes if prev else ["최초 스냅샷"]})
        with open(hp, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=1); f.write("\n")
        head = "최초 스냅샷" if not prev else f"변동 {len(changes)}건"
        print(f"[snap] {label}: {head} 기록 → data/history/{hist_name} (누적 {len(hist['snapshots'])}건)")
        for c in changes[:6]:
            print(f"        · {c}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
