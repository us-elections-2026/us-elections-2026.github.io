#!/usr/bin/env python3
"""상원 일일 브리핑(KR) → data/senate_daily_log.json 추출.

원천: _NIS 2026_midterm_outlook/senate_daily/YYYY-MM-DD_일일브리핑_KR.md
      (Cowork 예약 작업이 매일 ~07:00 KST에 생성)
산출: data/senate_daily_log.json — 날짜별로 다음을 담는다
      lead      : 제목 아래 이탤릭 도입 문단(수집 구간·오늘의 최대 변수)
      summary   : "## 오늘의 핵심 요약" 본문(마크다운 그대로)
      states    : "## 주별 뉴스"의 "### N. <주>" 소절을 주 약자로 매핑한 본문
      extras    : 주별 뉴스 안의 로스터 외 소절(사우스캐롤라이나 등) — 제목 보존
      polls     : "## 새로운 여론조사" 본문
      watch     : "## 주시 항목" 본문
      gaps      : "## 수집 결손" 본문(있으면)
      source_file, chars

설계 원칙
  - 본문은 마크다운 텍스트를 자르지 않고 그대로 싣는다. 요약·재서술을 하지 않는다
    (LLM이 하는 프로즈 작성은 이 스크립트 밖 — 원천 브리핑에서 끝난 상태로 가정).
  - 같은 날짜는 덮어쓴다(idempotent). 다른 날짜는 건드리지 않는다.
  - 소절 제목 변형("### 3. 메인 ⚠️", "### 5. 알래스카 — 예비선거 …")은 주 이름 포함 여부로 매핑.
  - 렌더는 R/helpers.R의 daily_log_md()가 한다. 여기서는 HTML을 만들지 않는다.

사용:
  python3 scripts/ingest_senate_daily.py                # 오늘(KST) 파일 1건
  python3 scripts/ingest_senate_daily.py --date 2026-09-17
  python3 scripts/ingest_senate_daily.py --since 2026-09-01   # 소급 적재
  python3 scripts/ingest_senate_daily.py --src <dir>    # 원천 폴더 덮어쓰기(기본: _NIS 경로)
종료코드: 0 정상 / 2 해당 날짜 파일 없음(발행 스크립트는 '오늘 브리핑 없음'으로 종료) / 1 오류
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import zoneinfo
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "senate_daily_log.json"
DEFAULT_SRC = Path(os.environ.get(
    "NIS_SENATE_DAILY",
    "~/Library/CloudStorage/Dropbox/_NIS/2026_senate_election/2026_midterm_outlook/senate_daily",
)).expanduser()

# 감시 9주 — 소절 제목에 주 이름이 들어 있으면 매핑. 순서는 판정 우선순위와 무관.
STATE_KR = {
    "조지아": "GA", "미시간": "MI", "뉴햄프셔": "NH", "메인": "ME",
    "노스캐롤라이나": "NC", "텍사스": "TX", "오하이오": "OH",
    "알래스카": "AK", "아이오와": "IA",
}
WATCH = ["GA", "MI", "NH", "ME", "NC", "TX", "OH", "AK", "IA"]

H2 = re.compile(r"^## +(.+?)\s*$")
H3 = re.compile(r"^### +(.+?)\s*$")


def split_h2(text: str) -> dict[str, str]:
    """'## ' 제목 기준으로 본문을 나눈다. 키는 제목 원문(공백 정리)."""
    out: dict[str, str] = {}
    cur = None
    buf: list[str] = []
    for line in text.splitlines():
        m = H2.match(line)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf).strip("\n")
            cur = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).strip("\n")
    return out


HR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
HEAD = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def sanitize(body: str) -> str:
    """페이지 안에 들어갈 본문의 블록 구조를 무해화한다.
    - 수평선(---/***/___)은 제거: 접힘 callout 안에서 pandoc이 `---` 줄을 YAML 메타데이터
      블록 시작으로 읽어 렌더가 깨진다(2026-09-17 dashboard 실측).
    - 제목(#…)은 굵은 한 줄로 낮춘다: 원천의 소제목이 사이트 목차·callout 제목과 충돌하지 않게.
    인라인 서식·링크·표·목록은 손대지 않는다."""
    out = []
    for line in body.splitlines():
        if HR.match(line):
            continue
        m = HEAD.match(line)
        if m:
            out.append(f"**{m.group(2)}**")
            continue
        out.append(line)
    return "\n".join(out).strip("\n")


def find_section(sections: dict[str, str], *needles: str) -> str | None:
    for k, v in sections.items():
        if all(n in k for n in needles):
            return v
    return None


def find_any(sections: dict[str, str], alternatives: list[str]) -> str | None:
    """제목이 회차마다 다른 절(주시 항목/주시 대상/내일 볼 것 …)을 후보 순서대로 찾는다."""
    for n in alternatives:
        v = find_section(sections, n)
        if v is not None:
            return v
    return None


def split_states(body: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    """'## 주별 뉴스' 본문을 '### ' 소절로 나눠 주 약자에 매핑한다."""
    states: dict[str, str] = {}
    extras: list[dict[str, str]] = []
    cur_title = None
    buf: list[str] = []

    def flush():
        if cur_title is None:
            return
        content = "\n".join(buf).strip("\n")
        code = next((c for kr, c in STATE_KR.items() if kr in cur_title), None)
        if code and code not in states:
            states[code] = content
        else:
            extras.append({"title": cur_title, "body": content})

    for line in body.splitlines():
        m = H3.match(line)
        if m:
            flush()
            cur_title = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    flush()
    return states, extras


def parse_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^# .*?(\d{4}-\d{2}-\d{2})\s*$", text, re.M)
    date = m.group(1) if m else path.name[:10]

    # 도입 문단: 제목 다음의 첫 비어 있지 않은 문단(보통 *…* 이탤릭)
    after_title = text.split("\n", 1)[1] if "\n" in text else ""
    lead = ""
    for para in re.split(r"\n\s*\n", after_title):
        p = para.strip()
        if not p:
            continue
        if p.startswith("#"):
            break
        # 원천은 도입 문단 전체를 *…* 이탤릭으로 감싼다 — 서체가 세리프라 통째로 기울면 읽기 어려워
        # 바깥 이탤릭 표식만 벗긴다(내부 굵게 등 서식은 그대로).
        if p.startswith("*") and p.endswith("*") and not p.startswith("**"):
            p = p[1:-1].strip()
        elif p.startswith("*") and p.endswith("***"):
            p = p[1:-1].strip()
        lead = p
        break

    sec = split_h2(text)
    news = find_section(sec, "주별 뉴스") or ""
    states, extras = split_states(news)
    # 로스터 외 관찰(사우스캐롤라이나 특별선거 등)이 H2로 따로 선 회차도 있다 — extras에 합친다
    for k, v in sec.items():
        if ("이벤트" in k or "로스터 외" in k or "명단 외" in k) and v.strip():
            extras.append({"title": k, "body": v})

    return {
        "date": date,
        "source_file": path.name,
        "chars": len(text),
        "lead": sanitize(lead),
        "summary": sanitize(find_section(sec, "오늘의 핵심 요약") or ""),
        "states": {c: sanitize(states[c]) for c in WATCH if c in states},
        "extras": [{"title": e["title"], "body": sanitize(e["body"])} for e in extras],
        "polls": sanitize(find_section(sec, "새로운 여론조사") or ""),
        # 제목 변형: 주시 항목 / 주시 대상 / 주목할 일정 / 내일 주목할 사항 / 내일 볼 것 / 이월 미결 항목
        "watch": sanitize(find_any(sec, ["주시", "주목", "내일", "이월"]) or ""),
        "gaps": sanitize(find_any(sec, ["수집 결손", "수집 공백"]) or ""),
    }


def load_log() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {
        "as_of": None,
        "source_label": "_NIS 상원 일일 브리핑(KR) — Cowork 예약 작업 산출물을 scripts/ingest_senate_daily.py가 그대로 추출",
        "provenance_note": (
            "본문은 원천 마크다운을 자르지 않고 전재한다(요약·재서술 없음). 종결체는 원천대로 다체. "
            "【수집 필요】 표기도 원천 그대로 남긴다 — 빈 칸을 추정으로 채우지 않는 규약과 같은 이유. "
            "같은 날짜 재실행은 덮어쓴다."
        ),
        "days": [],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘 KST)")
    ap.add_argument("--since", help="YYYY-MM-DD — 이 날짜부터 있는 파일 전부 적재")
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = Path(a.src).expanduser()
    if not src.is_dir():
        print(f"[ingest] ✗ 원천 폴더 없음: {src}", file=sys.stderr)
        return 1

    if a.since:
        files = sorted(p for p in src.glob("*_일일브리핑_KR.md") if p.name[:10] >= a.since)
        if not files:
            print(f"[ingest] ✗ {a.since} 이후 파일 없음", file=sys.stderr)
            return 2
    else:
        date = a.date or dt.datetime.now(zoneinfo.ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
        p = src / f"{date}_일일브리핑_KR.md"
        if not p.exists():
            print(f"[ingest] {date} 일일 브리핑 없음 — {p.name}", file=sys.stderr)
            return 2
        files = [p]

    log = load_log()
    by_date = {d["date"]: d for d in log["days"]}
    added, replaced = 0, 0
    for p in files:
        day = parse_file(p)
        missing = [c for c in WATCH if c not in day["states"]]
        if day["date"] in by_date:
            replaced += 1
        else:
            added += 1
        by_date[day["date"]] = day
        print(f"[ingest] {day['date']}  주 {len(day['states'])}/9"
              + (f"  (없음: {','.join(missing)})" if missing else "")
              + f"  extras {len(day['extras'])}  summary {len(day['summary'])}자"
              + ("  ! summary 비어 있음" if not day["summary"] else ""))

    log["days"] = sorted(by_date.values(), key=lambda d: d["date"], reverse=True)
    log["as_of"] = log["days"][0]["date"] if log["days"] else None

    if a.dry_run:
        print(f"[ingest] dry-run — 추가 {added} · 교체 {replaced} · 총 {len(log['days'])}일 (미저장)")
        return 0
    OUT.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[ingest] ✓ {OUT.relative_to(REPO)}  추가 {added} · 교체 {replaced} · 총 {len(log['days'])}일 · as_of {log['as_of']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
