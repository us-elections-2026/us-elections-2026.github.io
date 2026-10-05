#!/usr/bin/env python3
"""원문(07:00 수집) 일일 브리핑이 수집 프롬프트 v2.8의 고정 요소를 갖췄는지 점검 — 경고 전용(발행을 막지 않음).

사용: python3 scripts/check_raw_briefing.py <YYYY-MM-DD_일일브리핑_KR.md>
짝이 되는 EN 파일(<날짜>_daily-briefing_EN.md)이 같은 폴더에 있으면 함께 본다.

점검 항목(프롬프트 §13 Run self-audit와 1:1):
  A 주 소절 11개가 고정 순서(10·11은 v2.8 전 원문이면 없을 수 있음 → 경고만)
  B 주 소절마다 [유세] 한 줄(EN은 [VISIT])
  C 주 소절마다 §5.1 로컬 매체 도메인 ≥1
  D 「새로운 여론조사」 불릿마다 기간(날짜)·격차 숫자
  E 파일 끝 「## Run self-audit」 블록 존재 + 자기보고 수치와 실측 비교
  F EN/KR 주 소절 수 일치
"""
from __future__ import annotations
import re, sys, pathlib

STATES = ["조지아", "미시간", "메인", "노스캐롤라이나", "알래스카", "오하이오", "텍사스", "아이오와", "뉴햄프셔"]
OPTIONAL = ["네브래스카", "캔자스"]
# v2.8 §5.1 로컬 매체(도메인). 한 주 소절에 이 중 하나라도 링크돼 있으면 C 통과.
LOCAL = {
 "조지아": ["ajc.com", "wsbtv.com", "capitol-beat.org", "georgiarecorder.com", "georgiastarnews.com"],
 "미시간": ["freep.com", "detroitnews.com", "bridgemi.com", "michiganadvance.com", "mirsnews.com", "michigancapitolconfidential.com"],
 "메인": ["pressherald.com", "bangordailynews.com", "mainepublic.org", "mainemorningstar.com", "themainewire.com"],
 "노스캐롤라이나": ["newsobserver.com", "wral.com", "ncnewsline.com", "carolinajournal.com", "charlotteobserver.com"],
 "알래스카": ["adn.com", "alaskapublic.org", "alaskabeacon.com", "mustreadalaska.com", "alaskalandmine.com"],
 "오하이오": ["cleveland.com", "dispatch.com", "statenews.org", "signalohio.org", "ohiocapitaljournal.com", "theohiostar.com"],
 "텍사스": ["houstonchronicle.com", "dallasnews.com", "texastribune.org", "quorumreport.com", "texasobserver.org", "texasscorecard.com"],
 "아이오와": ["desmoinesregister.com", "iowapublicradio.org", "iowacapitaldispatch.com", "thegazette.com", "theiowastandard.com"],
 "뉴햄프셔": ["unionleader.com", "wmur.com", "nhpr.org", "newhampshirebulletin.com", "nhjournal.com"],
 "네브래스카": ["omaha.com", "journalstar.com", "nebraskapublicmedia.org", "flatwaterfreepress.org", "nebraskaexaminer.com"],
 "캔자스": ["kansas.com", "kansascity.com", "cjonline.com", "kcur.org", "thebeacon.media", "kansasreflector.com", "sentinelksmo.org"],
}
EN_OF = dict(zip(STATES + OPTIONAL, ["Georgia", "Michigan", "Maine", "North Carolina", "Alaska", "Ohio", "Texas", "Iowa", "New Hampshire", "Nebraska", "Kansas"]))


def sections(text: str, names: list[str]) -> dict[str, str]:
    """'### n. 이름' 소절 → 본문. 다음 ### 또는 ## 까지."""
    out = {}
    for nm in names:
        m = re.search(rf"^### \d+\.\s*{re.escape(nm)}\s*$(.*?)(?=^###? |\Z)", text, re.M | re.S)
        if m: out[nm] = m.group(1)
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 2
    kr = pathlib.Path(sys.argv[1]); text = kr.read_text(encoding="utf-8")
    date = kr.name[:10]
    en = kr.with_name(f"{date}_daily-briefing_EN.md")
    warn: list[str] = []; ok: list[str] = []

    # A 순서
    heads = re.findall(r"^### (\d+)\.\s*(\S+)", text, re.M)
    names = [h[1] for h in heads]
    exp = STATES + OPTIONAL
    if names[:9] == STATES: ok.append("A 주 소절 1~9 순서")
    else: warn.append(f"A 주 소절 순서 불일치: {names[:11]}")
    missing_opt = [s for s in OPTIONAL if s not in names]
    if missing_opt: warn.append(f"A 선택 소절 없음(v2.8 전 원문이면 정상): {missing_opt}")
    secs = sections(text, exp)

    # B 유세 / C 로컬 매체
    nov = [s for s in secs if not re.search(r"^\s*-?\s*\[유세\]", secs[s], re.M)]
    if nov: warn.append(f"B [유세] 줄 없음({len(nov)}/{len(secs)}): {nov}")
    else: ok.append(f"B [유세] 줄 {len(secs)}/{len(secs)}")
    noloc = [s for s in secs if not any(d in secs[s] for d in LOCAL[s])]
    if noloc: warn.append(f"C §5.1 로컬 매체 링크 없음({len(noloc)}/{len(secs)}): {noloc}")
    else: ok.append(f"C 로컬 매체 링크 {len(secs)}/{len(secs)}")

    # D 여론조사
    m = re.search(r"^## 새로운 여론조사\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if m:
        body = m.group(1)
        # 불릿 또는 표(| 주 | 기관 | 기간 | 표본 | 결과 | 격차 |) 둘 다 받는다. 실제 원문은 표가 많다.
        bullets = [b for b in re.findall(r"^- (.+)$", body, re.M) if "없음" not in b[:12]]
        rows = [r for r in re.findall(r"^\|(.+)\|\s*$", body, re.M) if not re.match(r"^\s*(-{2,}\s*\|?\s*)+$", r) and "조사기관" not in r]
        bullets += [" · ".join(c.strip() for c in r.split("|")) for r in rows]
        bad = [b[:60] for b in bullets if not (re.search(r"\d{1,2}/\d{1,2}|\d{1,2}월\s*\d{1,2}일|미확인", b) and re.search(r"\d+\s*[-–~]\s*\d+|[+−-]\s?\d|\d+\s*%|동률", b))]
        if bad: warn.append(f"D 조사 불릿에 기간/격차 누락 {len(bad)}/{len(bullets)}: {bad[:3]}")
        else: ok.append(f"D 조사 불릿 {len(bullets)}개 기간·격차 확인")
    else: warn.append("D 「새로운 여론조사」 절 없음")

    # E self-audit
    a = re.search(r"^## Run self-audit\s*$(.*)\Z", text, re.M | re.S)
    if not a: warn.append("E 「## Run self-audit」 블록 없음(v2.8 §13)")
    else:
        claimed = dict(re.findall(r"^- ([A-F])\S*[^:：]*[:：]\s*(.+)$", a.group(1), re.M))
        ok.append(f"E self-audit 블록 있음(항목 {len(claimed)})")
        cb = re.search(r"(\d+)\s*/\s*(\d+)", claimed.get("B", ""))
        if cb and int(cb.group(1)) != len(secs) - len(nov):
            warn.append(f"E 자기보고 B {cb.group(0)} ≠ 실측 {len(secs)-len(nov)}/{len(secs)}")

    # F EN 대조
    if en.exists():
        et = en.read_text(encoding="utf-8")
        eh = re.findall(r"^### \d+\.\s*(.+?)\s*$", et, re.M)
        if len(eh) != len(names): warn.append(f"F EN 주 소절 {len(eh)}개 ≠ KR {len(names)}개")
        else: ok.append(f"F EN/KR 주 소절 {len(names)}개 일치")
        ev = len(re.findall(r"\[VISIT\]", et)); kv = len(re.findall(r"\[유세\]", text))
        if ev != kv: warn.append(f"F [VISIT] {ev} ≠ [유세] {kv}")
    else: warn.append(f"F EN 파일 없음: {en.name}")

    print(f"[raw-check] {kr.name}")
    for o in ok: print(f"  ✓ {o}")
    for w in warn: print(f"  ⚠ {w}")
    print(f"[raw-check] 통과 {len(ok)} · 경고 {len(warn)} (경고는 발행을 막지 않음 — 수집 프롬프트 준수 여부 참고용)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
