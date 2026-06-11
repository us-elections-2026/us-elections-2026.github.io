#!/usr/bin/env python3
"""FRED API로 전국 경제 지표를 받아 data/national_econ.json 으로 정규화.

산출 (national.qmd가 사용):
  rows    — 최신 스냅샷 (gt_national_econ() 정적 표)
  series  — SERIES_START 이후 월별 시계열 (assets/econ.js Chart.js 그래프)

대상 시리즈:
  CPIAUCSL  CPI → 전년 동월 대비 % (cpi_yoy)
  UNRATE    실업률 % (unrate)
  UMCSENT   미시간대 소비자심리지수 (umcsent)

사용법:
  export FRED_API_KEY=...   # https://fred.stlouisfed.org/docs/api/api_key.html (무료)
  python3 scripts/fetch_national_econ.py

원칙: 값을 못 받으면 null 유지 (추정으로 채우지 않음). 표준 라이브러리만 사용.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

API = "https://api.stlouisfed.org/fred/series/observations"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "national_econ.json")

SERIES_START = "2026-01"  # 그래프 시계열 시작 (YYYY-MM) — 필요 시 여기만 수정

SERIES = [
    # (series_id, 출력키, 지표명, 단위, yoy 계산 여부, 선거 함의 메모)
    ("CPIAUCSL", "cpi_yoy", "CPI (전년 대비)", "%", True,  "물가는 현 사이클 최대 악재"),
    ("UNRATE",   "unrate",  "실업률",          "%", False, "고용 악화 시 현직당 부담 가중"),
    ("UMCSENT",  "umcsent", "미시간대 소비자심리", "지수", False, "체감 경기 — 지지율 선행 지표 성격"),
]


def fetch(series_id: str, key: str, start: str):
    """start(YYYY-MM-DD) 이후 observations를 [(YYYY-MM, value), ...] 오름차순으로."""
    q = urllib.parse.urlencode({
        "series_id": series_id, "api_key": key, "file_type": "json",
        "sort_order": "asc", "observation_start": start,
    })
    try:
        with urllib.request.urlopen(f"{API}?{q}", timeout=30) as r:
            obs = json.load(r)["observations"]
        return [(o["date"][:7], float(o["value"])) for o in obs if o["value"] != "."]
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {series_id}: {e}", file=sys.stderr)
        return None


def main() -> int:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        print("FRED_API_KEY 환경변수가 필요합니다.", file=sys.stderr)
        return 1

    # YoY 계산을 위해 시계열 시작 1년 전부터 받는다.
    fetch_start = f"{int(SERIES_START[:4]) - 1}-01-01"

    rows, series = [], {}
    for sid, out_key, name, unit, yoy, note in SERIES:
        obs = fetch(sid, key, fetch_start)
        ts = None
        if obs:
            if yoy:
                lookup = dict(obs)
                ts = []
                for ym, v in obs:
                    if ym < SERIES_START:
                        continue
                    base = lookup.get(f"{int(ym[:4]) - 1}-{ym[5:]}")
                    if base:
                        ts.append([ym, round((v / base - 1) * 100, 1)])
            else:
                ts = [[ym, v] for ym, v in obs if ym >= SERIES_START]
        series[out_key] = ts  # 실패 시 null

        value = prev = period = None
        if ts:
            period, value = ts[-1]
            if len(ts) > 1:
                prev = ts[-2][1]
        rows.append({
            "indicator": name, "series_id": sid, "key": out_key, "unit": unit,
            "value": value, "prev": prev, "period": period,
            "election_note": note,
        })

    out = {
        "as_of": date.today().isoformat(),
        "series_start": SERIES_START,
        "source_label": "FRED (St. Louis Fed) — BLS·미시간대 원자료",
        "provenance_note": "빌드 시점 스냅샷. null은 수집 실패 — 추정으로 채우지 않음.",
        "rows": rows,
        "series": series,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    n = sum(1 for v in series.values() if v)
    print(f"wrote {os.path.normpath(OUT)} ({n}/{len(SERIES)} series, {SERIES_START}~)")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
