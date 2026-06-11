#!/usr/bin/env python3
"""FRED API로 전국 경제 지표를 받아 data/national_econ.json 으로 정규화.

대상 시리즈 (national.qmd 경제 표):
  CPIAUCSL  CPI (전년 동월 대비 % 계산)
  UNRATE    실업률 (%)
  UMCSENT   미시간대 소비자심리지수

사용법:
  export FRED_API_KEY=...   # https://fred.stlouisfed.org/docs/api/api_key.html (무료)
  python3 scripts/fetch_national_econ.py

cron(macmini, 주 1회 월요일 06:00) 예:
  0 6 * * 1 cd /path/to/repo && FRED_API_KEY=... python3 scripts/fetch_national_econ.py && git add data/national_econ.json && git commit -m "data: national_econ 갱신" && git push

원칙: 값을 못 받으면 해당 행을 null로 두고 종료 코드 0 (추정으로 채우지 않음).
표준 라이브러리만 사용 (의존성 없음).
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

API = "https://api.stlouisfed.org/fred/series/observations"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "national_econ.json")

SERIES = [
    # (series_id, 지표명, 단위, yoy 계산 여부, 선거 함의 메모)
    ("CPIAUCSL", "CPI (전년 대비)", "%", True,  "물가는 현 사이클 최대 악재"),
    ("UNRATE",   "실업률",          "%", False, "고용 악화 시 현직당 부담 가중"),
    ("UMCSENT",  "미시간대 소비자심리", "지수", False, "체감 경기 — 지지율 선행 지표 성격"),
]


def fetch(series_id: str, key: str, limit: int = 14):
    """최근 observations를 (date, value) 리스트로. 실패 시 None."""
    q = urllib.parse.urlencode({
        "series_id": series_id, "api_key": key, "file_type": "json",
        "sort_order": "desc", "limit": limit,
    })
    try:
        with urllib.request.urlopen(f"{API}?{q}", timeout=30) as r:
            obs = json.load(r)["observations"]
        return [(o["date"], float(o["value"])) for o in obs if o["value"] != "."]
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {series_id}: {e}", file=sys.stderr)
        return None


def main() -> int:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        print("FRED_API_KEY 환경변수가 필요합니다.", file=sys.stderr)
        return 1

    rows = []
    for sid, name, unit, yoy, note in SERIES:
        obs = fetch(sid, key)
        value = prev = period = None
        if obs:
            period, latest = obs[0]
            if yoy:
                # 전년 동월 값 탐색 (월차 시리즈 가정)
                target = f"{int(period[:4]) - 1}{period[4:7]}"
                base = next((v for d, v in obs if d.startswith(target)), None)
                if base is None:
                    more = fetch(sid, key, limit=26) or []
                    base = next((v for d, v in more if d.startswith(target)), None)
                value = round((latest / base - 1) * 100, 1) if base else None
                prev = None  # YoY 전월치는 별도 계산 필요 — null 유지
            else:
                value = latest
                prev = obs[1][1] if len(obs) > 1 else None
        rows.append({
            "indicator": name, "series_id": sid, "unit": unit,
            "value": value, "prev": prev, "period": period[:7] if period else None,
            "election_note": note,
        })

    out = {
        "as_of": date.today().isoformat(),
        "source_label": "FRED (St. Louis Fed) — BLS·미시간대 원자료",
        "provenance_note": "빌드 시점 스냅샷. null은 수집 실패 — 추정으로 채우지 않음.",
        "rows": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {os.path.normpath(OUT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
