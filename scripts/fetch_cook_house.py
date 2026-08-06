#!/usr/bin/env python3
"""Cook Political Report 하원 등급 자동 취득 (270towin 경유).

cookpolitical.com은 직접 접근이 403으로 막혀 있다. 270towin이 Cook 등급을 재게시하며,
페이지에 435개 지역구 등급을 담은 map_string과 갱신 일자가 JSON으로 박혀 있다.
이 스크립트는 그 문자열을 해독해 카테고리 집계 + 지역구별 등급을 생성한다.

해독 키(2026-08-03 검증): 0=Toss-up · 1=Solid D · 2=Solid R · 3=Likely D · 4=Likely R · 5=Leans D · 6=Leans R
  - 지역구 순서 = 주 약자(abbr) 알파벳순, 각 주 안에서 지역구 번호순 (435개)
  - 검증 방법: 표 페이지의 카테고리별 지역구 명단과 대조해 전 건 일치 확인
    (토스업 18구 전부 '0', Leans D 10구 전부 '5', 안전구 표본 일치)

산출물:
  data/house_cook_ratings.json    — 7개 카테고리 의석수 (기존 스키마 유지)
  data/house_cook_districts.json  — 435개구 등급 전체 (토스업 명단·시계열 축적용)

사용: python3 scripts/fetch_cook_house.py [--dry-run]
실패 시 파일을 건드리지 않고 비정상 종료한다(주간 발행 스크립트가 경고 후 계속).
"""
import argparse
import json
import os
import re
import sys
import urllib.request

URL = "https://www.270towin.com/2026-house-election/"
TABLE_URL = ("https://www.270towin.com/2026-house-election/index_show_table.php"
             "?map_title=cook-political-report-2026-house-ratings")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2026 사이클 주별 하원 의석수 (2020 인구총조사 배분) — 합계 435
SEATS = {"AL":7,"AK":1,"AZ":9,"AR":4,"CA":52,"CO":8,"CT":5,"DE":1,"FL":28,"GA":14,"HI":2,"ID":2,
         "IL":17,"IN":9,"IA":4,"KS":4,"KY":6,"LA":6,"ME":2,"MD":8,"MA":9,"MI":13,"MN":8,"MS":4,
         "MO":8,"MT":2,"NE":3,"NV":4,"NH":2,"NJ":12,"NM":3,"NY":26,"NC":14,"ND":1,"OH":15,"OK":5,
         "OR":6,"PA":17,"RI":2,"SC":7,"SD":1,"TN":9,"TX":38,"UT":4,"VT":1,"VA":11,"WA":10,"WV":2,
         "WI":8,"WY":1}
CODE = {"0": ("tossup", "Toss-up", "T"), "1": ("solid_d", "Solid D", "D"), "2": ("solid_r", "Solid R", "R"),
        "3": ("likely_d", "Likely D", "D"), "4": ("likely_r", "Likely R", "R"),
        "5": ("lean_d", "Lean D", "D"), "6": ("lean_r", "Lean R", "R")}
ORDER = ["solid_d", "likely_d", "lean_d", "tossup", "lean_r", "likely_r", "solid_r"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "ignore")


def districts_in_order():
    out = []
    for ab in sorted(SEATS):
        for n in range(1, SEATS[ab] + 1):
            out.append(f"{ab}-{n}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if sum(SEATS.values()) != 435:
        print("[cook] 의석 배분표 합계 오류", file=sys.stderr); return 1

    html = get(URL).replace("\\/", "/").replace('\\"', '"')
    # 한 페이지에 여러 기관 피드가 들어 있으므로 반드시 JSON 객체 단위로 묶어 읽는다
    # (인접 객체의 날짜/문자열을 섞어 읽으면 잘못된 as_of가 나온다).
    objs = re.findall(r'\{[^{}]*"url_title":"cook-political-report-2026-house-ratings"[^{}]*\}', html)
    if not objs:
        print("[cook] Cook 피드 객체를 찾지 못함 — 페이지 구조 변경 가능", file=sys.stderr); return 1
    obj = objs[0]
    mm_ = re.search(r'"map_string":"([0-9]+)"', obj)
    dm = re.search(r'"date_created":"(\d{4}-\d{2}-\d{2})', obj)
    if not mm_ or not dm:
        print("[cook] map_string/date_created 누락", file=sys.stderr); return 1
    ms, as_of = mm_.group(1), dm.group(1)
    if len(ms) != 435:
        print(f"[cook] map_string 길이 이상: {len(ms)} (435 기대)", file=sys.stderr); return 1

    dl = districts_in_order()
    rows, counts = [], {k: 0 for k in ORDER}
    for d, c in zip(dl, ms):
        if c not in CODE:
            print(f"[cook] 미지의 등급 코드 '{c}' ({d})", file=sys.stderr); return 1
        key, label, party = CODE[c]
        counts[key] += 1
        rows.append({"district": d, "rating": label, "key": key, "party": party})

    # 표 페이지에서 현역/공석 라벨 보강 (실패해도 계속 — 등급이 본체)
    names = {}
    try:
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", get(TABLE_URL)))
        # "AZ-6 Ciscomani" 처럼 지역구 코드 뒤 이름이 오고, 다음 지역구 코드 직전에서 끊는다.
        pat = re.compile(r"\b([A-Z]{2}-(?:\d{1,2}|AL))\s+(OPEN(?:\s+\([^)]{1,30}\))?|[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,2})"
                         r"(?=\s+[A-Z]{2}-\d|\s+[A-Z]{2}-AL|\s*$|\s+(?:Solid|Likely|Leans|Toss))")
        for mm in pat.finditer(t):
            key = mm.group(1).replace("-AL", "-1")
            names.setdefault(key, mm.group(2).strip())
    except Exception as e:  # noqa: BLE001
        print(f"[cook] 현역 라벨 보강 실패(등급은 정상): {e}", file=sys.stderr)
    # 재획정으로 번호가 재배치된 구는 원 피드의 현역 라벨이 옛 지도 기준으로 남아 있다.
    # 자동 취득분을 그대로 실으면 페이지에 틀린 이름이 뜨므로, 확인된 건만 교정한다.
    #   FL-25: 신지도(델레이비치~마이애미비치)의 현역은 Jared Moskowitz다. Wasserman
    #          Schultz는 구지도 기준 — 2026-08-06 복수 매체(WLRN·CBS Miami·Florida
    #          Politics)가 Moskowitz를 FL-25 현역으로 보도(8/18 경선 상대 Oliver Larkin).
    INCUMBENT_FIX = {"FL-25": "Moskowitz"}
    for r in rows:
        if r["district"] in names:
            r["incumbent"] = names[r["district"]]
        if r["district"] in INCUMBENT_FIX:
            r["incumbent"] = INCUMBENT_FIX[r["district"]]

    ratings = {
        "as_of": as_of,
        "source_label": "Cook Political Report (270towin 재게시 · 자동 취득)",
        "source_url": TABLE_URL,
        "majority": 218,
        "note": ("scripts/fetch_cook_house.py가 270towin에 게시된 Cook 등급 문자열(435개구)을 해독해 자동 생성한다. "
                 "Solid는 역산이 아니라 지역구별 등급의 직접 집계다. 등급은 확률이 아니다."),
        "categories": [
            {"key": k, "label": CODE[[c for c in CODE if CODE[c][0] == k][0]][1],
             "party": CODE[[c for c in CODE if CODE[c][0] == k][0]][2], "seats": counts[k]}
            for k in ORDER
        ],
    }
    total = sum(counts.values())
    if total != 435:
        print(f"[cook] 합계 불일치: {total}", file=sys.stderr); return 1

    districts = {
        "as_of": as_of,
        "source_label": ratings["source_label"],
        "source_url": TABLE_URL,
        "decode_note": "0=Toss-up 1=Solid D 2=Solid R 3=Likely D 4=Likely R 5=Leans D 6=Leans R · 주 약자순×지역구번호순",
        "counts": counts,
        "districts": rows,
    }

    tossups = [r["district"] for r in rows if r["key"] == "tossup"]
    print(f"[cook] as_of {as_of} · " + " · ".join(f"{k} {counts[k]}" for k in ORDER))
    print(f"[cook] 토스업 {len(tossups)}구: {', '.join(tossups)}")
    if args.dry_run:
        print("[cook] --dry-run: 파일 미변경."); return 0

    with open(os.path.join(ROOT, "data", "house_cook_ratings.json"), "w", encoding="utf-8") as f:
        json.dump(ratings, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(ROOT, "data", "house_cook_districts.json"), "w", encoding="utf-8") as f:
        json.dump(districts, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("[cook] wrote data/house_cook_ratings.json · data/house_cook_districts.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
