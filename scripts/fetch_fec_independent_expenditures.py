#!/usr/bin/env python3
"""FEC Schedule E(독립지출)로 2026 상원 감시 9주의 슈퍼팩·위원회 외부지출을 받아
data/fec_independent_expenditures.json 으로 저장.

fetch_fec_fundraising.py(후보 계좌)의 짝. 기사가 전하는 '예약'과 달리 이것은 FEC에 신고된 '집행'이다.

사용법:
  export FEC_API_KEY=...
  python3 scripts/fetch_fec_independent_expenditures.py

방법:
  - /schedules/schedule_e/ 를 주별로 전부 받는다(cycle 2026 · 상원 · 본선 election_type G*).
  - 정기 보고(F3X 등, is_notice=false)와 24/48시간 통지(is_notice=true)는 같은 지출이 두 번 실리므로,
    통지는 그 위원회의 마지막 정기 보고 지출일 이후 것만 더한다(근사 — FEC도 같은 원칙으로 안내).
  - 정정 전 원본(most_recent=false)·메모 항목(memo_code=X)은 뺀다.
  - 집계: 위원회×후보×지지/반대. 주 요약은 '민주 우호'(민주 지지+공화 반대) 대 '공화 우호'.
표준 라이브러리만 사용. 실패한 주는 null — 추정으로 채우지 않는다.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date

STATES = ["GA", "MI", "NH", "ME", "NC", "TX", "OH", "AK", "IA"]
API = "https://api.open.fec.gov/v1/schedules/schedule_e/"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "fec_independent_expenditures.json")


def fetch_rows(state: str, key: str) -> list[dict] | None:
    rows, last = [], {}
    for _ in range(60):  # 100행 × 60쪽 상한
        q = {"api_key": key, "cycle": 2026, "candidate_office": "S", "candidate_office_state": state,
             "per_page": 100, "sort": "-expenditure_date", **last}
        try:
            with urllib.request.urlopen(f"{API}?{urllib.parse.urlencode(q)}", timeout=60) as r:
                d = json.load(r)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {state}: {e}", file=sys.stderr)
            return None
        rows += d["results"]
        li = d.get("pagination", {}).get("last_indexes") or {}
        if not d["results"] or not li.get("last_index"):
            break
        last = {"last_index": li["last_index"], "last_expenditure_date": li.get("last_expenditure_date")}
    return rows


def aggregate(rows: list[dict]) -> dict:
    keep = []
    for x in rows:
        if x.get("most_recent") is False or x.get("memo_code") == "X":
            continue
        et = x.get("election_type") or ""
        if et and not et.startswith("G"):
            continue  # 예비선거 지출 제외 — 본선만
        if not x.get("expenditure_amount") or not x.get("expenditure_date"):
            continue
        keep.append(x)
    # 통지 중복 제거: 위원회별 마지막 정기 보고 지출일 이후의 통지만 산입
    last_rep = defaultdict(str)
    for x in keep:
        if not x.get("is_notice"):
            last_rep[x["committee_id"]] = max(last_rep[x["committee_id"]], x["expenditure_date"][:10])
    agg = {}
    for x in keep:
        cid = x["committee_id"]; ed = x["expenditure_date"][:10]
        notice = bool(x.get("is_notice"))
        if notice and ed <= last_rep[cid]:
            continue
        k = (cid, x.get("candidate_id"), x.get("support_oppose_indicator"))
        a = agg.setdefault(k, {
            "committee_id": cid, "committee": (x.get("committee") or {}).get("name") or cid,
            "candidate_id": x.get("candidate_id"), "candidate": x.get("candidate_name"),
            "party": (x.get("candidate_party") or "")[:3], "so": x.get("support_oppose_indicator"),
            "reported": 0.0, "notice_recent": 0.0, "last_date": ""})
        a["notice_recent" if notice else "reported"] += float(x["expenditure_amount"])
        a["last_date"] = max(a["last_date"], ed)
    out = []
    pro = {"D": 0.0, "R": 0.0}
    for a in agg.values():
        a["total"] = a["reported"] + a["notice_recent"]
        side = None
        if a["party"] == "DEM": side = "D" if a["so"] == "S" else "R"
        elif a["party"] == "REP": side = "R" if a["so"] == "S" else "D"
        a["side"] = side
        if side: pro[side] += a["total"]
        for f in ("reported", "notice_recent", "total"):
            a[f] = round(a[f] / 1e6, 2)
        out.append(a)
    out.sort(key=lambda a: -a["total"])
    return {"pro_D": round(pro["D"] / 1e6, 2), "pro_R": round(pro["R"] / 1e6, 2),
            "n_rows": len(keep), "last_date": max((a["last_date"] for a in out), default=None),
            "rows": out}


def main() -> int:
    key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    out = {
        "as_of": date.today().isoformat(),
        "source_label": "FEC Schedule E 독립지출 (api.open.fec.gov) — 본선(G2026) 신고분, 단위 $M",
        "provenance_note": ("정기 보고 + 마지막 정기 보고 이후의 24/48시간 통지. 위원회×후보×지지(S)/반대(O) 집계. "
                            "pro_D = 민주 지지+공화 반대, pro_R = 그 반대. 예비선거·메모·정정 전 행 제외. "
                            "광고 '예약'(AdImpact 등)이 아니라 신고된 '집행'이며, 단체가 신고를 늦추면 실제보다 작다."),
        "states": {}, "committees": [],
    }
    by_comm = defaultdict(lambda: {"total": 0.0, "by_state": {}})
    ok = 0
    for st in STATES:
        rows = fetch_rows(st, key)
        if rows is None:
            out["states"][st] = None
            continue
        agg = aggregate(rows)
        out["states"][st] = agg
        ok += 1
        for a in agg["rows"]:
            c = by_comm[a["committee_id"]]
            c["name"] = a["committee"]; c["total"] += a["total"]
            s = c["by_state"].setdefault(st, {"D": 0.0, "R": 0.0})
            if a["side"]: s[a["side"]] = round(s[a["side"]] + a["total"], 2)
        print(f"[ie] {st}: 행 {agg['n_rows']} · 민주 우호 {agg['pro_D']}M · 공화 우호 {agg['pro_R']}M · 최근 {agg['last_date']}")
    out["committees"] = sorted(
        ({"committee_id": k, "name": v["name"], "total": round(v["total"], 2), "by_state": v["by_state"]} for k, v in by_comm.items()),
        key=lambda c: -c["total"])[:40]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {os.path.normpath(OUT)} ({ok}/{len(STATES)} states)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
