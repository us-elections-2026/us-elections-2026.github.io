#!/usr/bin/env python3
"""주별 자금 누적 추이(후보 계좌 + 슈퍼팩 독립지출) → data/fec_timeline.json.

- 후보: 본선 지명자 2인(D·R)의 FEC 정기 보고(/reports/house-senate/)를 기간별로 더해 누적 모금액 계단선.
  분기 보고라 마지막 보고 마감일 이후는 평평하다(다음 갱신 10/15 3분기 보고).
- 슈퍼팩·위원회: Schedule E 독립지출(본선)을 지출일 기준 주별 누적 — 민주 우호(D 지지+R 반대) / 공화 우호.
  필터 규칙은 fetch_fec_independent_expenditures.py 와 같다.
- 주(week) 격자: 2026-01-05(월)부터 오늘 이전 마지막 월요일까지. 값은 그 주 일요일까지의 누적.
사용법: export FEC_API_KEY=... ; python3 scripts/fetch_fec_timeline.py
"""
from __future__ import annotations  # 호스트 python3(3.9)의 `X | None` 힌트 호환
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from fetch_fec_independent_expenditures import fetch_rows, STATES  # noqa: E402

API = "https://api.open.fec.gov/v1"
ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "fec_timeline.json")
FALLBACK_ID = {("ME", "D"): "S6ME00464"}  # Jackson — 7월 교체 후보라 fec_fundraising.json 에 없음
WEEK0 = date(2026, 1, 5)


def get(path, key, **p):
    p["api_key"] = key
    with urllib.request.urlopen(f"{API}{path}?{urllib.parse.urlencode(p, doseq=True)}", timeout=60) as r:
        return json.load(r)


def nominees():
    cands = json.load(open(os.path.join(ROOT, "data", "candidates.json"), encoding="utf-8"))["candidates"]
    fec = json.load(open(os.path.join(ROOT, "data", "fec_fundraising.json"), encoding="utf-8"))["states"]
    out = {}
    for c in cands:
        if c.get("status") != "nominee" or c["state"] not in STATES:
            continue
        sur = c["name"].split()[-1].upper()
        rows = [r for r in (fec.get(c["state"]) or []) if sur in (r.get("name") or "").upper()
                and (r.get("party") or "")[:1] == c["party"]]
        rows.sort(key=lambda r: -(r.get("receipts") or 0))
        cid = rows[0]["candidate_id"] if rows else FALLBACK_ID.get((c["state"], c["party"]))
        out[(c["state"], c["party"])] = {"name": c["name"], "name_kr": c.get("name_kr"), "candidate_id": cid}
    return out


def receipts_steps(cid, key):
    """[(coverage_end, cumulative_receipts_M)] — 정정본 제외, 마감일 순."""
    if not cid:
        return []
    d = get("/reports/house-senate/", key, candidate_id=cid, cycle=2026, is_amended="false", per_page=100, sort="coverage_end_date")
    steps, cum = [], 0.0
    for r in sorted(d["results"], key=lambda r: r.get("coverage_end_date") or ""):
        if not r.get("coverage_end_date"):
            continue
        cum += float(r.get("total_receipts_period") or 0)
        steps.append((r["coverage_end_date"][:10], round(cum / 1e6, 3)))
    return steps


def ie_daily(rows):
    """{side: {date: amount}} — 본선·최신본·비메모, 통지는 마지막 정기 보고 이후분만."""
    keep = [x for x in rows if x.get("most_recent") is not False and x.get("memo_code") != "X"
            and (not (x.get("election_type") or "") or x["election_type"].startswith("G"))
            and x.get("expenditure_amount") and x.get("expenditure_date")]
    last_rep = defaultdict(str)
    for x in keep:
        if not x.get("is_notice"):
            last_rep[x["committee_id"]] = max(last_rep[x["committee_id"]], x["expenditure_date"][:10])
    out = {"D": defaultdict(float), "R": defaultdict(float)}
    for x in keep:
        ed = x["expenditure_date"][:10]
        if x.get("is_notice") and ed <= last_rep[x["committee_id"]]:
            continue
        p, so = (x.get("candidate_party") or "")[:3], x.get("support_oppose_indicator")
        side = None
        if p == "DEM": side = "D" if so == "S" else "R"
        elif p == "REP": side = "R" if so == "S" else "D"
        if side:
            out[side][ed] += float(x["expenditure_amount"])
    return out


def main() -> int:
    key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    today = date.today()
    weeks = []
    w = WEEK0
    while w <= today:
        weeks.append(w); w += timedelta(days=7)
    week_ends = [(w + timedelta(days=6)).isoformat() for w in weeks]
    noms = nominees()
    out = {"as_of": today.isoformat(), "unit": "$M",
           "source_label": "FEC — 후보 정기 보고(누적 모금, 분기) + Schedule E 독립지출(본선, 주별 누적)",
           "provenance_note": "후보 계단선은 2025-01-01 이후 정기 보고 합계라 현직 상원의원의 2021~24년 모금은 빠진다(펀드레이징 탭의 사이클 누적과 다름). 보고 마감일에만 오르며 마지막 보고 이후는 평평하다(3분기 보고 10/15). "
                              "독립지출은 신고된 집행만(광고 예약 아님). 민주 측 합계 = D 후보 누적 모금 + 민주 우호 독립지출.",
           "weeks": [w.isoformat() for w in weeks], "states": {}}
    for st in STATES:
        rows = fetch_rows(st, key)
        if rows is None:
            out["states"][st] = None; continue
        ie = ie_daily(rows)
        rec = {}
        for side in ("D", "R"):
            n = noms.get((st, side)) or {}
            rec[side] = {"name": n.get("name"), "name_kr": n.get("name_kr"), "candidate_id": n.get("candidate_id"),
                         "steps": receipts_steps(n.get("candidate_id"), key)}
        series = {}
        for side in ("D", "R"):
            cand, iec = [], []
            steps = rec[side]["steps"]
            ie_days = sorted(ie[side].items())
            for we in week_ends:
                cand.append(next((v for d_, v in reversed(steps) if d_ <= we), 0.0))
                iec.append(round(sum(v for d_, v in ie_days if d_ <= we) / 1e6, 3))
            series[f"cand_{side}"] = cand; series[f"ie_{side}"] = iec
            series[f"total_{side}"] = [round(a + b, 3) for a, b in zip(cand, iec)]
        out["states"][st] = {"D": {k: rec["D"][k] for k in ("name", "name_kr", "candidate_id")},
                             "R": {k: rec["R"][k] for k in ("name", "name_kr", "candidate_id")},
                             "cand_last_report": {s: (rec[s]["steps"][-1][0] if rec[s]["steps"] else None) for s in ("D", "R")},
                             **series}
        print(f"[timeline] {st}: D {series['total_D'][-1]}M (후보 {series['cand_D'][-1]} + IE {series['ie_D'][-1]}) · "
              f"R {series['total_R'][-1]}M (후보 {series['cand_R'][-1]} + IE {series['ie_R'][-1]})")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"wrote {os.path.normpath(OUT)} — {len(weeks)}주")
    return 0


if __name__ == "__main__":
    sys.exit(main())
