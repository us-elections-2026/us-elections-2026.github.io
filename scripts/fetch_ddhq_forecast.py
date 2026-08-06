#!/usr/bin/env python3
"""Decision Desk HQ 2026 상원 예측 취득 (공개 예측 페이지의 구조화 데이터).

왜 필요한가 — '50–50'은 확률이 아니라 **평균 의석 수**다.
DDHQ 페이지는 두 수치를 나란히 싣는다:
    seats = 50 / 50           ← 시뮬레이션 평균 의석 (50-50이면 부통령 캐스팅보트로 공화 유지)
    winProbability = .43/.57  ← 실제 다수당 확률
언론 보도가 "Senate set for a 50-50 split"이라고 요약하면서 이 사이트도 한때
'DDHQ 50%'로 옮겨 적었는데, 그건 의석 수를 확률로 오독한 것이다(2026-08-06 정정).
이 스크립트는 둘을 분리해 그대로 싣는다.

수치는 Next.js 페이로드에 JSON으로 박혀 있어 정적 요청으로 취득된다.
(같은 이유로 RaceToTheWH는 자동화 불가 — 그쪽은 구글 시트 연동 인포그램이다.)

산출물: data/ddhq_forecast.json
사용:   python3 scripts/fetch_ddhq_forecast.py [--dry-run]
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.request

URL = "https://votes.decisiondeskhq.com/forecast/2026/senate"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        html = r.read().decode("utf-8", "ignore").replace('\\"', '"')

    m = re.search(r'"overviews":\[\{"toplineId":\d+,"officeId":\d+,'
                  r'"forecast":(\{.*?"updatedAt":"[^"]+"\})', html)
    if not m:
        print("[ddhq] 예측 데이터를 찾지 못함 — 페이지 구조 변경 의심", file=sys.stderr)
        return 1
    try:
        fc = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print(f"[ddhq] 파싱 실패: {e}", file=sys.stderr)
        return 1

    parties = {p["shortAbbrev"]: p for p in fc.get("parties", [])}
    if "D" not in parties or "R" not in parties:
        print("[ddhq] 정당 항목 없음", file=sys.stderr)
        return 1

    def pct(p):
        v = p.get("winProbability")
        return None if v is None else round(float(v) * 100, 1)

    out = {
        "as_of": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "fetched_at_utc": datetime.datetime.now(datetime.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "model",
        "source_label": "Decision Desk HQ",
        "source_url": URL,
        "model_updated_at": fc.get("updatedAt"),
        "rating": fc.get("rating"),
        # 확률과 의석은 서로 다른 값이다 — 절대 섞어 쓰지 말 것
        "dem_majority_prob": pct(parties["D"]),
        "rep_majority_prob": pct(parties["R"]),
        "dem_seats_mean": parties["D"].get("seats"),
        "rep_seats_mean": parties["R"].get("seats"),
        "note": ("seats는 시뮬레이션 **평균 의석**, dem_majority_prob는 **다수당 확률**로 서로 다른 값이다. "
                 "50–50 의석은 부통령 캐스팅보트로 공화 다수를 뜻하므로 '민주 50% 확률'이 아니다."),
    }
    print(f"[ddhq] 민주 다수 확률 {out['dem_majority_prob']}% / 공화 {out['rep_majority_prob']}% · "
          f"평균 의석 D {out['dem_seats_mean']} – R {out['rep_seats_mean']} · "
          f"모델 갱신 {out['model_updated_at']}")
    if args.dry_run:
        print("[ddhq] --dry-run: 파일 미변경.")
        return 0
    p = os.path.join(ROOT, "data", "ddhq_forecast.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("[ddhq] wrote data/ddhq_forecast.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
