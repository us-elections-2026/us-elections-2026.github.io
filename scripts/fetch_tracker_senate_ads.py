#!/usr/bin/env python3
"""선거운동 트래커(campaign-tracker-2026)의 FEC 독립지출 집계에서 상원 감시주 행만 가져온다 — 2026-10-24.

원천: 트래커 공개 사이트의 data/ads_fec.json (트래커 Actions가 매일 09:30 KST 갱신).
트래커 소스 저장소는 private이라 공개 배포본만 읽는다.
출력: data/tracker_senate_ads.json — 후보 카드 펀드레이징 행의 '우호 외부지출'과 광고 페이지 링크에 쓴다.
pro_D = 민주(NE는 무소속 Osborn) 지지 + 공화 반대, pro_R = 그 반대. 단위 달러.
실패하면 기존 파일을 그대로 두고 1로 끝난다(발행 스크립트는 건너뛰고 계속).
"""
import json
import sys
import urllib.request

BASE = "https://woochangkang.github.io/campaign-tracker-2026-site"
SRC = f"{BASE}/data/ads_fec.json"
OUT = "data/tracker_senate_ads.json"
KEYS = ("pro_D", "pro_R", "ads_D", "ads_R", "last_date", "independent_note")
TOP_KEYS = ("committee_id", "committee", "affiliate_of", "candidate", "so", "side", "total", "last_date")


def main() -> int:
    watch = sorted({c["state"] for c in json.load(open("data/candidates.json", encoding="utf-8"))["candidates"]})
    try:
        req = urllib.request.Request(SRC, headers={"User-Agent": "us-elections-2026-site"})
        src = json.load(urllib.request.urlopen(req, timeout=60))
    except Exception as e:
        print(f"[tracker] 취득 실패: {e}")
        return 1
    races = {}
    for st in watch:
        r = src.get("races", {}).get(f"senate-{st}")
        if r:
            races[st] = {k: r.get(k) for k in KEYS}
            races[st]["page"] = f"{BASE}/ads/senate-{st}.html"
            # 단체×후보 상위 행(트래커가 주마다 15행, 그 주 집행액의 약 9할) — 전국 환경 「독립지출」 표용
            races[st]["top"] = [{k: t.get(k) for k in TOP_KEYS} for t in r.get("top", [])]
    missing = [st for st in watch if st not in races]
    out = {
        "as_of": src.get("as_of"),
        "source_label": "선거운동 트래커 광고 페이지 — " + (src.get("source_label") or "FEC Schedule E 독립지출"),
        "source_url": SRC,
        "provenance_note": "pro_D = 민주(무소속 포함, independent_note=true) 지지 + 공화 반대, pro_R = 그 반대. 단위 달러. "
                           "후보 캠프 자금이 아니라 외부 단체의 신고 집행액이다.",
        "races": races,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"[tracker] {OUT} — as_of {out['as_of']}, {len(races)}주" + (f", 없음: {missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
