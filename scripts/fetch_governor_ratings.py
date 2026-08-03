#!/usr/bin/env python3
"""2026 주지사 선거 등급 자동 취득 (270towin 재게시 피드).

상·하원 스크립트와 동일 구조. 주지사 map_string은 50자(주 약자순 1주 1칸):
  - 9 = 이번 사이클 미선거 · 코드: 0=Toss-up 1=Solid D 2=Solid R 3=Likely D 4=Likely R 5=Lean D 6=Lean R
검증(2026-08-03): 9로 표시된 14개 주가 2026 주지사 선거 미실시 주
  (DE·IN·KY·LA·MO·MS·MT·NC·ND·NJ·UT·VA·WA·WV)와 정확히 일치 → 36개 선거.

일부 기관(RaceToTheWH·Kalshi·Inside Elections)의 'a','b' 코드는 의미 미확인 → null 유지(추정 금지).
산출물: data/governor_ratings.json
"""
import argparse, json, os, re, sys, urllib.request

URL = "https://www.270towin.com/2026-governor-election/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = {"0": "Toss-up", "1": "Solid D", "2": "Solid R", "3": "Likely D",
        "4": "Likely R", "5": "Lean D", "6": "Lean R"}
ABBR = sorted(["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME",
               "MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA",
               "RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"])
KR = {"AL":"앨라배마","AK":"알래스카","AZ":"애리조나","AR":"아칸소","CA":"캘리포니아","CO":"콜로라도","CT":"코네티컷",
 "FL":"플로리다","GA":"조지아","HI":"하와이","ID":"아이다호","IL":"일리노이","IA":"아이오와","KS":"캔자스","ME":"메인",
 "MD":"메릴랜드","MA":"매사추세츠","MI":"미시간","MN":"미네소타","NE":"네브래스카","NV":"네바다","NH":"뉴햄프셔",
 "NM":"뉴멕시코","NY":"뉴욕","OH":"오하이오","OK":"오클라호마","OR":"오리건","PA":"펜실베이니아","RI":"로드아일랜드",
 "SC":"사우스캐롤라이나","SD":"사우스다코타","TN":"테네시","TX":"텍사스","VT":"버몬트","WI":"위스콘신","WY":"와이오밍"}
SOURCES = [
    ("cook-political-report-2026-governor", "Cook Political Report"),
    ("sabatos-crystal-ball-2026-governor", "Sabato's Crystal Ball"),
    ("inside-elections-governor-2026", "Inside Elections"),
    ("almanac-american-politics-2026-governor-handicapping", "Almanac of American Politics"),
    ("fox-news-2026-governor-power-rankings", "Fox News Power Rankings"),
    ("racetothewh-2026-governor-forecast", "Race to the WH"),
    ("kalshi-2026-governor-prediction-market-prices", "Kalshi (예측시장 가격)"),
    ("consensus-2026-governor-forecast", "270toWin Consensus"),
]
# 2026 주지사 선거 미실시 14주 (검증용 고정값)
NO_RACE = {"DE","IN","KY","LA","MO","MS","MT","NC","ND","NJ","UT","VA","WA","WV"}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        html = r.read().decode("utf-8", "ignore").replace("\\/", "/").replace('\\"', '"')

    out = {"generated_from": URL, "n_races": 50 - len(NO_RACE), "sources": [], "state_names_kr": KR}
    for slug, label in SOURCES:
        objs = re.findall(r'\{[^{}]*"url_title":"' + re.escape(slug) + r'"[^{}]*\}', html)
        if not objs:
            print(f"[gov] ! {label}: 피드 없음", file=sys.stderr); continue
        ms = re.search(r'"map_string":"([0-9a-z]+)"', objs[0])
        dm = re.search(r'"date_created":"(\d{4}-\d{2}-\d{2})', objs[0])
        if not ms or not dm or len(ms.group(1)) != 50:
            print(f"[gov] ! {label}: map_string/날짜 이상", file=sys.stderr); continue
        s, as_of = ms.group(1), dm.group(1)
        got_no_race = {ABBR[i] for i, c in enumerate(s) if c == "9"}
        if got_no_race != NO_RACE:
            print(f"[gov] ! {label}: 미선거 주 불일치 {sorted(got_no_race ^ NO_RACE)} — 정렬 의심, 건너뜀", file=sys.stderr)
            continue
        ratings, unknown = {}, 0
        for i, ab in enumerate(ABBR):
            if s[i] == "9":
                continue
            if s[i] in CODE:
                ratings[ab] = CODE[s[i]]
            else:
                ratings[ab] = None; unknown += 1
        comp = {ab: v for ab, v in ratings.items() if v and ("Toss" in v or "Lean" in v)}
        out["sources"].append({"key": slug, "label": label, "as_of": as_of,
                               "ratings": ratings, "unknown_codes": unknown, "competitive": comp})
        print(f"[gov] {label:30} {as_of}  경합 {len(comp)}개: " +
              ", ".join(f"{a}:{v}" for a, v in sorted(comp.items())))
    if not out["sources"]:
        print("[gov] 취득 실패", file=sys.stderr); return 1
    if args.dry_run:
        print("[gov] --dry-run: 파일 미변경."); return 0
    p = os.path.join(ROOT, "data", "governor_ratings.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1); f.write("\n")
    print(f"[gov] wrote data/governor_ratings.json ({len(out['sources'])} sources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
