#!/usr/bin/env python3
"""VoteHub 공개 API(https://api.votehub.com/polls, 인증 불필요)의 2026 상원 본선 조사를
감시주 11곳에 대해 받아 extract_daily_polls.py 의 JSON 입력 형식으로 저장한다 (2026-10-13).

왜 — 일일 브리핑의 조사 표는 집계 사이트(RCP·270toWin) 목록에서 옮겨 와 실사 기간·원출처가 비는
일이 잦고(10/6~10/13 조지아 0건 append), 그러면 추출기가 pending 으로 두어 조사 표·추이 차트가 멈춘다.
VoteHub 레코드에는 실사 시작·종료일·표본·모집단·원출처 URL(언론·조사기관)이 있어 '준비 완료' 조건을 채운다.
한계 — 피드 신선도: 실시간이 아니다(취득일 기준 2~3일 지연). 일일 브리핑 추출과 병행하며, 같은 조사는
추출기의 중복 규칙((주,기관,종료일) 또는 (주,종료일,D%,R%))으로 한 번만 실린다.
규약 — 본선 D 대 R 지명자 대진만(subject 에 'Democratic'/'Republican'이 붙은 예비 조사 제외),
internal=true(캠프 내부) 제외, 지명자 성(姓)이 answers 에 둘 다 있어야 함. 추정으로 채우지 않는다.
사용: python3 scripts/fetch_votehub_senate_polls.py [--since YYYY-MM-DD] [--out PATH]
 이어서: python3 scripts/extract_daily_polls.py --from-json PATH --apply
"""
from __future__ import annotations
import argparse, json, os, re, sys, urllib.request
from datetime import date, timedelta

API = "https://api.votehub.com/polls"
SUBJECT = {"2026 Georgia": "GA", "2026 Michigan": "MI", "2026 New Hampshire": "NH", "2026 Maine": "ME",
           "2026 North Carolina": "NC", "2026 Texas": "TX", "2026 Ohio": "OH", "2026 Alaska": "AK",
           "2026 Iowa": "IA", "2026 Nebraska": "NE", "2026 Kansas": "KS"}
NOMINEE = {"GA": ("Ossoff", "Collins"), "MI": ("El-Sayed", "Rogers"), "NH": ("Pappas", "Sununu"),
           "ME": ("Jackson", "Collins"), "NC": ("Cooper", "Whatley"), "TX": ("Talarico", "Paxton"),
           "OH": ("Brown", "Husted"), "AK": ("Peltola", "Sullivan"), "IA": ("Turek", "Hinson"),
           "NE": ("Osborn", "Ricketts"), "KS": ("Hamilton", "Marshall")}
# 알래스카는 현직 Dan Sullivan 과 동명이인 Daniel J. Sullivan 이 같은 용지에 있다 — 'Daniel J'는 제외
EXCLUDE_CHOICE = {"AK": ("daniel j",)}


PARTY_COMMITTEE = re.compile(r"(republican|democratic) .*committee|\b(nrsc|dscc|dccc|nrcc)\b|campaign", re.I)


def partisan_of(p: dict) -> tuple[str, str, str]:
    """(sponsor, partisan, note) — 사이트 규약: partisan 열은 **후원자(의뢰) 당파만** D/R.
    VoteHub의 partisan 필드는 후원자가 없을 때 조사기관 자체 성향(예: Trafalgar=REP)을 담으므로
    후원자가 없으면 partisan을 비우고 upstream 표기를 note에 보존한다(Codex 검토 2026-10-13).
    예외: 후원자가 없고 '조사기관' 자리에 당 위원회·캠프가 적힌 경우(NRSC 등)는 그 이름을 후원자로 본다."""
    up = (p.get("partisan") or "").upper()
    code = {"DEM": "D", "REP": "R"}.get(up, "")
    sponsor = ", ".join(p.get("sponsors") or [])
    pollster = p.get("pollster") or ""
    if not sponsor and code and PARTY_COMMITTEE.search(pollster):
        sponsor = pollster
    if sponsor and code:
        return sponsor, code, ""
    if code and not sponsor:
        return "", "", f"VoteHub partisan 표기 {up}(후원자 없음 → 하우스 성향, partisan 열은 의뢰 당파만)"
    return sponsor, "", ""


def selftest() -> int:
    cases = [
        ({"pollster": "Trafalgar Group", "sponsors": [], "partisan": "REP"}, ("", "", True)),
        ({"pollster": "co/efficient", "sponsors": [], "partisan": "REP"}, ("", "", True)),
        ({"pollster": "Pulse Decision Science", "sponsors": ["Lone Star Liberty PAC"], "partisan": "REP"}, ("Lone Star Liberty PAC", "R", False)),
        ({"pollster": "Public Policy Polling", "sponsors": ["Senate Majority PAC"], "partisan": "DEM"}, ("Senate Majority PAC", "D", False)),
        ({"pollster": "Emerson College", "sponsors": ["Nexstar"], "partisan": None}, ("Nexstar", "", False)),
        ({"pollster": "National Republican Senatorial Committee", "sponsors": [], "partisan": "REP"}, ("National Republican Senatorial Committee", "R", False)),
    ]
    bad = 0
    for p, (es, ec, has_note) in cases:
        s, c, note = partisan_of(p)
        ok = (s == es and c == ec and bool(note) == has_note)
        bad += (not ok)
        print(("ok  " if ok else "FAIL"), p["pollster"], p["sponsors"], p.get("partisan"), "→", (s, c, note[:40]))
    print(f"[selftest] {len(cases) - bad}/{len(cases)} passed")
    return 1 if bad else 0


def pick(answers: list[dict], surname: str, st: str) -> float | None:
    hits = [a for a in answers if surname.lower() in (a.get("choice") or "").lower()
            and not any(x in (a.get("choice") or "").lower() for x in EXCLUDE_CHOICE.get(st, ()))]
    if len(hits) != 1:
        return None
    return hits[0].get("pct")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=(date.today() - timedelta(days=120)).isoformat())
    ap.add_argument("--selftest", action="store_true", help="partisan 매핑 회귀 시험만")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "votehub_senate_polls.json"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    try:
        with urllib.request.urlopen(urllib.request.Request(API, headers={"User-Agent": "us-elections-2026 site"}), timeout=60) as r:
            data = json.load(r)
    except Exception as e:
        print(f"[votehub] ✗ 취득 실패: {e}", file=sys.stderr); return 1
    out, skipped = [], {"primary": 0, "internal": 0, "nominee": 0, "old": 0}
    newest = ""
    for p in data:
        if p.get("poll_type") != "us-senator":
            continue
        st = SUBJECT.get(p.get("subject") or "")
        if not st:
            if (p.get("subject") or "").startswith("2026 ") and (p.get("subject") or "").split(" ", 1)[1].rsplit(" ", 1)[0] in {k.split(" ", 1)[1] for k in SUBJECT}:
                skipped["primary"] += 1
            continue
        if p.get("internal"):
            skipped["internal"] += 1; continue
        if (p.get("end_date") or "") < a.since:
            skipped["old"] += 1; continue
        d_s, r_s = NOMINEE[st]
        dp, rp = pick(p.get("answers") or [], d_s, st), pick(p.get("answers") or [], r_s, st)
        if dp is None or rp is None:
            skipped["nominee"] += 1; continue
        newest = max(newest, p.get("end_date") or "")
        sponsor, partisan, pnote = partisan_of(p)
        out.append({
            "state": st, "pollster": p.get("pollster") or "", "sponsor": sponsor,
            "partisan": partisan,
            "population": (p.get("population") or "").upper(), "n": p.get("sample_size"),
            "start_date": p.get("start_date"), "end_date": p.get("end_date"),
            "dem_candidate": d_s, "rep_candidate": r_s, "dem_pct": dp, "rep_pct": rp,
            "notes": "VoteHub 경유(원출처 URL)" + (" · " + pnote if pnote else ""), "source_url": p.get("url") or "",
        })
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    by = {}
    for o in out:
        by[o["state"]] = by.get(o["state"], 0) + 1
    print(f"[votehub] {len(out)}건(since {a.since}, 최신 종료일 {newest or '—'}) {by} · 제외 {skipped} → {os.path.normpath(a.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
