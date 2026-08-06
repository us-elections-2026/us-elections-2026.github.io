#!/usr/bin/env python3
"""상원 등급 다중 기관 자동 취득 (270towin 재게시 피드).

하원(fetch_cook_house.py)과 동일 구조. 상원 map_string은 101자:
  - 주 약자(abbr) 알파벳순 50개 주 × 2석 = 100자 + 말미 1자(용도 미상 — 사용하지 않음)
  - 인덱스 = 주순번*2 + (seat_number-1),  9 = 이번 사이클 미선거
  - 코드: 0=Toss-up 1=Solid D 2=Solid R 3=Likely D 4=Likely R 5=Leans D 6=Leans R
검증(2026-08-03): 페이지 JSON의 seat_status='T' 35석과 非9 위치가 35/35 일치, 오탐 0.

2026-08-06: 미확인이던 'a','b' 코드를 270towin 자체 지도 스크립트
https://www.270towin.com/js/maps/map.class.js 의 `mapCodeRatings` 표에서 확정 —
a=D1(Tilt D)·b=R1(Tilt R). 추정이 아니라 출처 원본의 정의를 그대로 옮긴 것이다.
Inside Elections·RaceToTheWH·Kalshi가 쓰는 'Tilt'(Lean보다 좁은 등급)가 이에 해당한다.

산출물: data/senate_ratings_feed.json (기관별 × 주별 등급 + 갱신일)
사용: python3 scripts/fetch_senate_ratings.py [--dry-run]
"""
import argparse
import json
import os
import re
import sys
import urllib.request

URL = "https://www.270towin.com/2026-senate-election/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# map.class.js `mapCodeRatings` 전사 (0~6·a·b만 등급. 7=I·8=split·9=미선거,
# c~f=당선/결선은 개표 후 코드라 본선 전에는 나오지 않는다 → 나오면 unknown으로 남는다)
CODE = {"0": "Toss-up", "1": "Solid D", "2": "Solid R", "3": "Likely D",
        "4": "Likely R", "5": "Lean D", "6": "Lean R",
        "a": "Tilt D", "b": "Tilt R"}
SOURCES = [
    ("cook-political-report-2026-senate", "Cook Political Report"),
    ("sabatos-crystal-ball-senate-2026", "Sabato's Crystal Ball"),
    ("inside-elections-2026-senate-ratings", "Inside Elections"),
    ("split-ticket-2026-senate-ratings", "Split Ticket"),
    ("almanac-american-politics-2026-senate-handicapping", "Almanac of American Politics"),
    ("fox-news-2026-senate-power-rankings", "Fox News Power Rankings"),
    ("decision-desk-hq-2026-senate-forecast", "Decision Desk HQ"),
    ("racetothewh-2026-senate-forecast", "Race to the WH"),
    ("kalshi-2026-senate-prediction-market-prices", "Kalshi (예측시장 가격)"),
    ("consensus-2026-senate-forecast", "270toWin Consensus"),
]
WATCH = ["GA", "NC", "NH", "MI", "ME", "AK", "OH", "TX"]   # 사이트 감시 8주


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        html = r.read().decode("utf-8", "ignore").replace("\\/", "/").replace('\\"', '"')

    # 어느 주·어느 의석에 2026 선거가 있는지 (페이지 자체 메타)
    recs = re.findall(r'\{"state_abbr":"([A-Z]{2})","state_name":"([^"]+)","seat_status":"T",'
                      r'"state_fips_code":"(\d+)","seat_number":(\d+)', html)
    if not recs:
        print("[senate] 선거 메타(seat_status)를 찾지 못함", file=sys.stderr); return 1
    race = {ab: int(sn) for ab, nm, fp, sn in recs}
    names = {ab: nm for ab, nm, fp, sn in recs}
    # 50개 주 약자 고정(준주·DC 제외) — map_string은 이 순서 × 2석으로 인덱싱된다
    abbrs = sorted(["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA",
                    "ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
                    "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"])
    unknown_states = sorted(set(race) - set(abbrs))
    if unknown_states:
        print(f"[senate] 목록 밖 주: {unknown_states}", file=sys.stderr); return 1

    out = {"generated_from": URL, "n_races": len(race), "sources": []}
    for slug, label in SOURCES:
        objs = re.findall(r'\{[^{}]*"url_title":"' + re.escape(slug) + r'"[^{}]*\}', html)
        if not objs:
            print(f"[senate] ! {label}: 피드 없음(건너뜀)", file=sys.stderr); continue
        ms = re.search(r'"map_string":"([0-9a-z]+)"', objs[0])
        dm = re.search(r'"date_created":"(\d{4}-\d{2}-\d{2})', objs[0])
        if not ms or not dm or len(ms.group(1)) != 101:
            print(f"[senate] ! {label}: map_string/날짜 이상(건너뜀)", file=sys.stderr); continue
        s, as_of = ms.group(1), dm.group(1)

        # 정렬 검증(양방향) — 선거석은 9가 아니어야 하고, 비선거석은 9여야 한다.
        # 한쪽만 보면 다른 종류의 지도(예: 100석 전체를 칠한 맵)를 그대로 삼켜 오독한다.
        race_idx = {abbrs.index(ab) * 2 + (seat - 1) for ab, seat in race.items()}
        nine = {i for i, c in enumerate(s[:100]) if c == "9"}
        miss = len(race_idx & nine)
        extra = len((set(range(100)) - race_idx) - nine)
        if miss or extra:
            print(f"[senate] ! {label}: 정렬 불일치(선거석이 9: {miss}석 · 비선거석에 값: {extra}석) "
                  f"— 다른 종류의 지도로 보임, 건너뜀", file=sys.stderr)
            continue
        ratings, unknown = {}, 0
        for ab, seat in race.items():
            c = s[abbrs.index(ab) * 2 + (seat - 1)]
            if c in CODE:
                ratings[ab] = CODE[c]
            else:
                ratings[ab] = None   # 미확인 코드 — 추정하지 않음
                unknown += 1
        out["sources"].append({
            "key": slug, "label": label, "as_of": as_of,
            "ratings": ratings,
            "unknown_codes": unknown,
            "watch": {ab: ratings.get(ab) for ab in WATCH},
        })
        w = " ".join(f"{ab}:{(ratings.get(ab) or '?')}" for ab in WATCH)
        print(f"[senate] {label:30} {as_of}  {w}" + (f"  (미확인코드 {unknown})" if unknown else ""))

    if not out["sources"]:
        print("[senate] 취득 실패", file=sys.stderr); return 1
    out["state_names"] = names
    if args.dry_run:
        print("[senate] --dry-run: 파일 미변경."); return 0
    p = os.path.join(ROOT, "data", "senate_ratings_feed.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1); f.write("\n")
    print(f"[senate] wrote data/senate_ratings_feed.json ({len(out['sources'])} sources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
