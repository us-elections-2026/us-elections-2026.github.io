#!/usr/bin/env python3
"""사이트 정리본(site digest) ↔ 원문 일일 브리핑 대조 — 발행 전 하드 게이트.

정리본은 LLM(Cowork 10:15 작업)이 원문을 재배열·압축한 것이다. 그 과정에서 원문에 없는
숫자가 섞이는 것이 이 프로젝트의 최대 리스크이므로, 정리본의 모든 숫자가 원문에 존재하는지
기계적으로 확인한다. 구조(9주 소절·네 요소·조사 표 헤더)와 분량 상한도 함께 본다.

사용: python3 scripts/check_site_digest.py <원문.md> <정리본.md>
종료코드: 0 통과 / 1 위반(사유 출력) / 2 파일 없음
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

STATES = ["조지아", "미시간", "메인", "노스캐롤라이나", "알래스카", "오하이오", "텍사스", "아이오와", "뉴햄프셔"]
ELEMENTS = ["판세", "이월", "주 함의"]
TABLE_HEADER = "| 주 | 조사기관 | 후원 | 성향 | 모집단 | n | 조사시작 | 조사종료 | D후보 | D% | R후보 | R% | 출처URL |"
CAPS = {"state_section": 1500, "digest_total": 25000, "lead": 500}

URL_RE = re.compile(r"https?://\S+")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def numbers(text: str) -> set[str]:
    text = URL_RE.sub(" ", text)
    out = set()
    for m in NUM_RE.findall(text):
        n = m.replace(",", "").rstrip(".")
        if not n:
            continue
        # 소절 번호·월·일 같은 작은 정수는 구조어라 대조에서 뺀다
        if n.isdigit() and int(n) <= 31:
            continue
        out.add(n)
    return out


def split_h2(text: str) -> dict[str, str]:
    out, cur, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^## +(.+?)\s*$", line)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def split_h3(text: str) -> dict[str, str]:
    out, cur, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^### +(.+?)\s*$", line)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__); return 2
    raw_p, site_p = Path(sys.argv[1]), Path(sys.argv[2])
    if not raw_p.exists() or not site_p.exists():
        print(f"[digest] 파일 없음: {raw_p if not raw_p.exists() else site_p}"); return 2
    raw, site = raw_p.read_text(encoding="utf-8"), site_p.read_text(encoding="utf-8")
    errs: list[str] = []

    # 1) 숫자 부분집합 — 정리본의 숫자는 전부 원문에 있어야 한다(제목 줄·'원문:' 줄 제외)
    body = "\n".join(l for l in site.splitlines() if not l.startswith("# ") and not l.startswith("원문:"))
    extra = sorted(numbers(body) - numbers(raw), key=lambda x: (len(x), x))
    if extra:
        errs.append("원문에 없는 숫자 " + str(len(extra)) + "개: " + ", ".join(extra[:30]) + (" …" if len(extra) > 30 else ""))

    # 2) 구조
    sec = split_h2(site)
    for need in ("오늘의 핵심 요약", "주별 뉴스", "새로운 여론조사"):
        if not any(need in k for k in sec):
            errs.append(f"절 누락: ## {need}")
    news = next((v for k, v in sec.items() if "주별 뉴스" in k), "")
    sub = split_h3(news)
    for i, st in enumerate(STATES, 1):
        key = next((k for k in sub if k.startswith(f"{i}. ") and st in k), None)
        if key is None:
            errs.append(f"주 소절 누락 또는 순서 오류: ### {i}. {st}"); continue
        body_st = sub[key]
        for el in ELEMENTS:
            if not re.search(rf"^- \*\*{re.escape(el)}\*\*", body_st, re.M):
                errs.append(f"{st}: 요소 누락 — **{el}**")
        if len(body_st) > CAPS["state_section"]:
            errs.append(f"{st}: {len(body_st)}자 > 상한 {CAPS['state_section']}자")
    polls = next((v for k, v in sec.items() if "새로운 여론조사" in k), "")
    if TABLE_HEADER not in polls and "신규 본선 조사 없음" not in polls:
        errs.append("새로운 여론조사: 고정 표 헤더도 '신규 본선 조사 없음' 문구도 없음")

    # 3) 분량
    if len(site) > CAPS["digest_total"]:
        errs.append(f"정리본 전체 {len(site)}자 > 상한 {CAPS['digest_total']}자")
    lead = ""
    after = site.split("\n", 1)[1] if "\n" in site else ""
    for para in re.split(r"\n\s*\n", after):
        q = para.strip()
        if q and not q.startswith("#") and not q.startswith("원문:"):
            lead = q; break
    if len(lead) > CAPS["lead"]:
        errs.append(f"도입 문단 {len(lead)}자 > 상한 {CAPS['lead']}자")

    if errs:
        print(f"[digest] ✗ 정리본 대조 실패 ({len(errs)}건) — {site_p.name}")
        for e in errs:
            print("  -", e)
        return 1
    print(f"[digest] ✓ 정리본 대조 통과 — 원문 {len(raw):,}자 → 정리본 {len(site):,}자, 숫자 {len(numbers(body))}종 전부 원문 확인")
    return 0


if __name__ == "__main__":
    sys.exit(main())
