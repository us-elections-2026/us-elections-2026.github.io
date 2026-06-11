#!/usr/bin/env python3
"""FEC API로 2026 상원 경합주 후보 모금 현황을 받아 data/fec_fundraising.json 으로 저장.

senate_races.json의 cash_on_hand 필드에 수동 병합하기 위한 스테이징 파일을 만든다
(편집 통제를 위해 자동 덮어쓰기 하지 않음 — 표 반영은 사람이 결정).

사용법:
  export FEC_API_KEY=...   # https://api.open.fec.gov/developers/ (무료; DEMO_KEY는 시간당 제한 큼)
  python3 scripts/fetch_fec_fundraising.py

조회 방식: 주(state)+상원(office=S)+2026 사이클 후보 전체를 검색해
총모금(receipts)·총지출(disbursements)·현금(last_cash_on_hand_end_period)을 기록.
FEC 수치는 분기 보고 기준 — 보고 마감일(coverage_end_date)을 반드시 함께 표기.
표준 라이브러리만 사용.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

STATES = ["GA", "MI", "NH", "ME", "NC", "TX", "OH", "AK"]  # 경합주 8곳
API = "https://api.open.fec.gov/v1/candidates/totals/"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "fec_fundraising.json")


def fetch_state(state: str, key: str):
    q = urllib.parse.urlencode({
        "api_key": key, "office": "S", "state": state,
        "cycle": 2026, "election_year": 2026,
        "sort": "-receipts", "per_page": 20, "is_active_candidate": "true",
    })
    try:
        with urllib.request.urlopen(f"{API}?{q}", timeout=30) as r:
            res = json.load(r)["results"]
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {state}: {e}", file=sys.stderr)
        return None
    rows = []
    for c in res:
        if not c.get("receipts"):
            continue
        rows.append({
            "name": c.get("name"),
            "party": (c.get("party") or "")[:3],
            "candidate_id": c.get("candidate_id"),
            "receipts": round(c.get("receipts", 0) / 1e6, 2),          # $M
            "disbursements": round(c.get("disbursements", 0) / 1e6, 2),
            "cash_on_hand": (round(c["last_cash_on_hand_end_period"] / 1e6, 2)
                             if c.get("last_cash_on_hand_end_period") is not None else None),
            "coverage_end": c.get("coverage_end_date", "")[:10] or None,
        })
    return rows


def main() -> int:
    key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    out = {
        "as_of": date.today().isoformat(),
        "source_label": "FEC (api.open.fec.gov) — 분기 보고 기준, 단위 $M",
        "provenance_note": "coverage_end가 분기 마감일. 슈퍼팩 외부지출은 별도(independent expenditures) — 이 파일에 미포함.",
        "states": {},
    }
    ok = 0
    for st in STATES:
        rows = fetch_state(st, key)
        out["states"][st] = rows  # 실패 시 null 그대로 — 추정 금지
        ok += rows is not None
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {os.path.normpath(OUT)} ({ok}/{len(STATES)} states)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
