#!/usr/bin/env python3
"""EIA 주간 소매 휘발유 가격(Regular, All Formulations)을 받아 data/gas_prices.json 으로 저장.

원자료: https://www.eia.gov/petroleum/gasdiesel/xls/pswrgvwall.xls (EIA, 매주 월요일 가격, 키 불필요)
 - 'Data 3' 시트 = Regular · All Formulations · 모든 지역(미국·PADD·주 9곳·도시).
 - EIA 주 단위 주간 시계열은 CA·CO·FL·MA·MN·NY·OH·TX·WA 아홉 주뿐이다. 감시 9주 중 OH·TX만 주 실측이 있고,
   나머지는 그 주가 속한 PADD 지역 평균을 **대리값**으로 쓴다(JSON에 proxy 로 표시, 그래프는 점선).
사용법: python3 scripts/fetch_gas_prices.py   (xlrd·pandas 필요 — 호스트 python3 확인됨)
"""
import io
import json
import os
import sys
import urllib.request
from datetime import date

URL = "https://www.eia.gov/petroleum/gasdiesel/xls/pswrgvwall.xls"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "gas_prices.json")
WEEKS = 53  # 지난 1년 + 비교 기준 1주

# 표시 순서. state: 사이트 지역 코드, area: EIA 지역 코드, proxy: 주 실측이 아니면 True
SERIES = [
    ("US", "NUS", "미국 전체", False),
    ("OH", "SOH", "오하이오", False),
    ("TX", "STX", "텍사스", False),
    ("MI·IA", "R20", "미시간·아이오와 (중서부 PADD 2 대리)", True),
    ("GA·NC", "R1Z", "조지아·노스캐롤라이나 (남부 대서양 PADD 1C 대리)", True),
    ("ME·NH", "R1X", "메인·뉴햄프셔 (뉴잉글랜드 PADD 1A 대리)", True),
    ("AK", "R50", "알래스카 (서부 PADD 5 대리)", True),
    ("NY", "SNY", "뉴욕 (NY-17 참고)", False),
    ("PA", "R1Y", "펜실베이니아 (중부 대서양 PADD 1B 대리, PA-01 참고)", True),
]


def main() -> int:
    import pandas as pd  # noqa: WPS433
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
        raw = r.read()
    x = pd.ExcelFile(io.BytesIO(raw), engine="xlrd")
    df = x.parse("Data 3", header=None)
    keys = [str(k) for k in df.iloc[1, :].tolist()]          # 행 1 = Sourcekey (EMM_EPMR_PTE_<AREA>_DPG)
    col = {k.split("_")[3]: i for i, k in enumerate(keys) if k.startswith("EMM_")}
    body = df.iloc[3:, :].copy()
    body = body[pd.to_datetime(body[0], errors="coerce").notna()]
    body[0] = pd.to_datetime(body[0]).dt.strftime("%Y-%m-%d")
    body = body.tail(WEEKS)
    weeks = body[0].tolist()
    out_series = []
    for code, area, label, proxy in SERIES:
        if area not in col:
            print(f"[warn] {area} 없음", file=sys.stderr); continue
        vals = [None if pd.isna(v) else round(float(v), 3) for v in body[col[area]].tolist()]
        first, last = next((v for v in vals if v is not None), None), next((v for v in reversed(vals) if v is not None), None)
        out_series.append({"code": code, "area": area, "label": label, "proxy": proxy, "values": vals,
                           "latest": last, "year_ago": first,
                           "yoy": round(last - first, 3) if (last is not None and first is not None) else None,
                           "max": max(v for v in vals if v is not None), "min": min(v for v in vals if v is not None)})
    out = {"as_of": date.today().isoformat(), "data_through": weeks[-1], "unit": "달러/갤런",
           "source_label": "EIA Weekly Retail Gasoline Prices — Regular, All Formulations (매주 월요일 가격)",
           "source_url": "https://www.eia.gov/petroleum/gasdiesel/",
           "provenance_note": "EIA 주 단위 주간 시계열은 CA·CO·FL·MA·MN·NY·OH·TX·WA 아홉 주에만 있다. 감시 9주 중 OH·TX만 주 실측이며 "
                              "나머지는 소속 PADD 지역 평균을 대리값으로 쓴다(proxy=true). 브리핑의 AAA 주별 일일가와 수준이 다를 수 있다.",
           "weeks": weeks, "series": out_series}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"wrote {os.path.normpath(OUT)} — {len(weeks)}주({weeks[0]}~{weeks[-1]}), 시리즈 {len(out_series)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
