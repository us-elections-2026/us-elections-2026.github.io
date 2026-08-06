#!/usr/bin/env python3
"""RaceToTheWH 2026 상원 예측 취득 (Infogram 라이브 데이터).

배경 — 왜 이렇게까지 하나
  RtWH 예측 페이지의 수치는 HTML에 없다. Infogram 임베드가 렌더 시점에 구글 시트
  연동 데이터를 가져와 그린다. 그래서 정적 요청으로는 페이지의 **설명문에 박힌 과거
  수치**(예: "4월 업데이트: 71.8% → 73.4%")만 긁히는데, 이 사이트는 한때 그 값을
  현재 예측으로 오인해 실었다(2026-08-06 발견·삭제).

  Infogram 뷰어 번들이 쓰는 실제 데이터 주소를 따라가면 원 시계열을 JSON으로 받을 수
  있다:  https://live-data.jifo.co/{key}   (key = 임베드 페이지의 live.key)
  이 스크립트는 페이지 → 임베드 → key → 시계열 순으로 따라가 **마지막 관측치**를 싣는다.

  하원은 같은 방식이 통하지 않는다(해당 페이지의 임베드에 라이브 데이터가 없음) —
  따라서 하원 RtWH 확률은 취득하지 않는다(사이트에서 【확인 필요】로 남긴다).

산출물: data/rtwh_forecast.json
사용:   python3 scripts/fetch_rtwh_forecast.py [--dry-run]
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.request

PAGE = "https://www.racetothewh.com/senate/26"
LIVE = "https://live-data.jifo.co/{}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WANT_SHEET = "Chance to Win the Majority"


def get(url, referer=None):
    h = {"User-Agent": UA}
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "ignore")


def find_key(embed_html):
    """sheetNames에 '다수 확률' 시트를 가진 요소의 live.key를 찾는다."""
    # live 블록의 필드 순서: chartId … enabled … fileId … key … provider … sheetNames
    for m in re.finditer(r'"chartId":"[^"]+".{0,200}?"key":"([0-9a-f-]{36})"'
                         r'.{0,400}?"sheetNames":\[([^\]]*)\]', embed_html, re.S):
        if WANT_SHEET in m.group(2):
            return m.group(1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        page = get(PAGE)
    except Exception as e:                                  # noqa: BLE001
        print(f"[rtwh] 페이지 접근 실패: {e}", file=sys.stderr)
        return 1
    ids = sorted(set(re.findall(r"infogram\.com/_/([A-Za-z0-9]+)", page)))
    if not ids:
        print("[rtwh] 임베드를 찾지 못함 — 페이지 구조 변경 의심", file=sys.stderr)
        return 1

    key = None
    for eid in ids:
        try:
            emb = get(f"https://e.infogram.com/_/{eid}?src=embed", referer=PAGE)
        except Exception:                                    # noqa: BLE001
            continue
        key = find_key(emb.replace('\\"', '"'))
        if key:
            break
    if not key:
        print(f"[rtwh] '{WANT_SHEET}' 시트를 가진 차트를 찾지 못함", file=sys.stderr)
        return 1

    try:
        d = json.loads(get(LIVE.format(key), referer="https://e.infogram.com/"))
    except Exception as e:                                   # noqa: BLE001
        print(f"[rtwh] 라이브 데이터 취득 실패: {e}", file=sys.stderr)
        return 1

    sheets = d.get("sheetNames") or []
    if WANT_SHEET not in sheets:
        print(f"[rtwh] 시트 구성이 다름: {sheets}", file=sys.stderr)
        return 1
    rows = d["data"][sheets.index(WANT_SHEET)]
    hdr, body = rows[0], [r for r in rows[1:] if len(r) >= 3 and str(r[1]).endswith("%")]
    if not body:
        print("[rtwh] 확률 행이 비어 있음", file=sys.stderr)
        return 1
    last = body[-1]
    dem = float(str(last[1]).rstrip("%"))
    rep = float(str(last[2]).rstrip("%"))
    if not (95 <= dem + rep <= 105):
        print(f"[rtwh] 합이 100%에서 벗어남({dem}+{rep}) — 시트 오독 의심, 중단", file=sys.stderr)
        return 1

    seats = None
    if "Projected Seats Won" in sheets:
        srows = d["data"][sheets.index("Projected Seats Won")]
        sbody = [r for r in srows[1:] if len(r) >= 3]
        if sbody:
            try:
                seats = {"dem": float(sbody[-1][1]), "rep": float(sbody[-1][2])}
            except (TypeError, ValueError):
                seats = None

    out = {
        "as_of": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "fetched_at_utc": datetime.datetime.now(datetime.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "model",
        "source_label": "Race to the WH",
        "source_url": PAGE,
        "chamber": "senate",
        "series_refreshed": d.get("refreshed"),
        "last_point_label": last[0],
        "dem_majority_prob": dem,
        "rep_majority_prob": rep,
        "seats_projected": seats,
        "n_points": len(body),
        "note": ("Infogram 라이브 시계열의 마지막 관측치. 페이지 본문에 보이는 71.8%·73.4% 같은 "
                 "수치는 과거 모델 업데이트를 설명하는 서술문이므로 현재 예측이 아니다."),
    }
    print(f"[rtwh] 상원 다수 민주 {dem}% / 공화 {rep}% · {last[0]} 기준 "
          f"(시계열 {len(body)}점, 갱신 {d.get('refreshed')})"
          + (f" · 예상 의석 D {seats['dem']} – R {seats['rep']}" if seats else ""))
    if args.dry_run:
        print("[rtwh] --dry-run: 파일 미변경.")
        return 0
    p = os.path.join(ROOT, "data", "rtwh_forecast.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("[rtwh] wrote data/rtwh_forecast.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
