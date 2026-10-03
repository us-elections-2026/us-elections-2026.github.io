#!/usr/bin/env python3
"""FEC API로 하원 District Focus 지역구의 후보 모금(분기 보고)과 독립지출(Schedule E, 본선)을 받아
data/fec_house.json 으로 저장. 상원용 fetch_fec_fundraising.py + fetch_fec_independent_expenditures.py 의 하원 판.

사용법:  export FEC_API_KEY=... ; python3 scripts/fetch_fec_house.py
지역구는 아래 DISTRICTS 에 추가한다(사이트 house/<st><dd>.qmd 와 짝).
"""
from __future__ import annotations  # 호스트 python3(3.9)의 `X | None` 힌트 호환
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from fetch_fec_independent_expenditures import aggregate  # noqa: E402  (같은 집계 규칙)

DISTRICTS = [("NY", "17"), ("PA", "01")]
API = "https://api.open.fec.gov/v1"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "fec_house.json")


def get(path, key, **p):
    p["api_key"] = key
    with urllib.request.urlopen(f"{API}{path}?{urllib.parse.urlencode(p)}", timeout=60) as r:
        return json.load(r)


def totals(st, dist, key):
    d = get("/candidates/totals/", key, office="H", state=st, district=dist, cycle=2026, election_year=2026,
            sort="-receipts", per_page=20, is_active_candidate="true")
    rows = []
    for c in d["results"]:
        if not c.get("receipts"):
            continue
        coh = c.get("cash_on_hand_end_period")
        rows.append({"name": c.get("name"), "party": (c.get("party") or "")[:3], "candidate_id": c.get("candidate_id"),
                     "receipts": round(float(c.get("receipts") or 0) / 1e6, 2),
                     "disbursements": round(float(c.get("disbursements") or 0) / 1e6, 2),
                     "cash_on_hand": round(float(coh) / 1e6, 2) if coh is not None else None,
                     "coverage_end": (c.get("coverage_end_date") or "")[:10] or None})
    return rows


def sched_e(st, dist, key):
    rows, last = [], {}
    for _ in range(30):
        d = get("/schedules/schedule_e/", key, cycle=2026, candidate_office="H", candidate_office_state=st,
                candidate_office_district=dist, per_page=100, sort="-expenditure_date", **last)
        rows += d["results"]
        li = d.get("pagination", {}).get("last_indexes") or {}
        if not d["results"] or not li.get("last_index"):
            break
        last = {"last_index": li["last_index"], "last_expenditure_date": li.get("last_expenditure_date")}
    return aggregate(rows)


def main() -> int:
    key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    out = {"as_of": date.today().isoformat(),
           "source_label": "FEC (api.open.fec.gov) — 후보 분기 보고 + Schedule E 독립지출(본선), 단위 $M",
           "provenance_note": "candidates 는 사이클 누적 모금·현금(coverage_end 기준). ie 는 상원 독립지출 파일과 같은 규칙(정기 보고 + 이후 통지, 예비선거 제외).",
           "districts": {}}
    ok = 0
    for st, dist in DISTRICTS:
        k = f"{st}-{dist}"
        try:
            out["districts"][k] = {"candidates": totals(st, dist, key), "ie": sched_e(st, dist, key)}
            ok += 1
            ie = out["districts"][k]["ie"]
            print(f"[house] {k}: 후보 {len(out['districts'][k]['candidates'])} · IE 민주 우호 {ie['pro_D']}M · 공화 우호 {ie['pro_R']}M · 최근 {ie['last_date']}")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {k}: {e}", file=sys.stderr)
            out["districts"][k] = None
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {os.path.normpath(OUT)} ({ok}/{len(DISTRICTS)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
