#!/usr/bin/env python3.11
"""STYLE.md의 문체 규약을 수치로 확인한다 (이 레포 전용).

"유창함"을 취향 논쟁이 아니라 재는 대상으로 바꾸는 것이 목적이다. 규약과 기준은
STYLE.md가 정본이며, 이 스크립트는 그중 기계로 잴 수 있는 넷만 본다:
  ① 종결체 혼용 (상시=습니다체 / issues=다체)
  ② 100자 초과 문장 비율 (≤10%)
  ③ 굵게 밀도 (≤4 / 1,000자)
  ④ 문장당 괄호·줄표 (≤1)

사용:  python3.11 scripts/check_prose.py [파일…]
종료코드: 위반이 있으면 1.
"""
import re, sys, glob, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LONG, BOLD_PER_K, LONG_SHARE = 100, 4.0, 0.10


def strip_md(s):
    s = re.sub(r"```.*?```", "", s, flags=re.S)          # 코드 청크
    s = re.sub(r"^---.*?^---", "", s, flags=re.S | re.M)  # frontmatter
    s = re.sub(r"^\s*\|.*$", "", s, flags=re.M)           # 표
    s = re.sub(r"`[^`]*`", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)        # 링크 → 텍스트
    return s


def sentences(body):
    out = []
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith(("#", ">", ":::", "!", "|")):
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        for m in re.split(r"(?<=다\.)\s+|(?<=요\.)\s+", line):
            m = m.strip()
            if len(m) > 10 and re.search(r"[가-힣]", m):
                out.append(m)
    return out


def check(path):
    raw = pathlib.Path(path).read_text(encoding="utf-8")
    body = strip_md(raw)
    sents = sentences(body)
    if not sents:
        return []
    n, chars = len(sents), max(len(body), 1)
    issues_page = str(path).replace("\\", "/").startswith("issues/")

    hab = len(re.findall(r"(니다|습니다)[.\s]", body))
    # ⚠️ "습니다."도 '다.'로 끝난다 — 그냥 [가-힣]다\. 로 세면 습니다체 문장이
    # 전부 다체로 잡혀 "혼용" 오진이 난다(2026-09-06 실측: 21개 중 진짜 다체는 1개).
    da = len(re.findall(r"(?<!니)다\.", body))
    longs = [s for s in sents if len(s) > LONG]
    # 불릿 머리의 **라벨**(`- **경제**: …`, `- **Roy Cooper (D)** — …`)은 강조가 아니라
    # 정의목록의 항목명이다. 이걸 강조로 세면 카드형 페이지가 전부 위반으로 잡히고,
    # 지우면 구조가 무너진다(2026-09-06: NC 페이지 21개 중 12개가 라벨이었다).
    body_wo_labels = re.sub(r"^\s*[-*]\s*\*\*[^*]+\*\*(?=\s*[:—-])", "", body, flags=re.M)
    bold = len(re.findall(r"\*\*[^*]+\*\*", body_wo_labels))
    inline = sum(len(re.findall(r"\([^)]{6,}\)", s)) + s.count(" — ") for s in sents)

    p = []
    want = "다체" if issues_page else "습니다체"
    if want == "습니다체" and da > hab * 0.5:
        p.append(f"종결체 혼용 — 습니다 {hab} / 다 {da} (이 지면은 습니다체)")
    if want == "다체" and hab > da * 0.5:
        p.append(f"종결체 혼용 — 습니다 {hab} / 다 {da} (이 지면은 다체)")
    if len(longs) / n > LONG_SHARE:
        p.append(f"긴 문장 {len(longs)}/{n} ({len(longs)/n*100:.0f}%, 기준 {LONG_SHARE*100:.0f}%) "
                 f"· 최장 {max(len(s) for s in longs)}자")
    if bold / (chars / 1000) > BOLD_PER_K:
        p.append(f"굵게 {bold/(chars/1000):.1f}/1,000자 (기준 {BOLD_PER_K})")
    if inline / n > 1:
        p.append(f"괄호·줄표 문장당 {inline/n:.1f}개 (기준 1)")
    return p


def main():
    args = sys.argv[1:]
    files = args or sorted(
        glob.glob("*.qmd") + glob.glob("states/*.qmd") + glob.glob("governors/*.qmd"))
    files = [f for f in files if pathlib.Path(f).name != "archive.qmd"]
    bad = {f: p for f in files if (p := check(f))}
    print(f"[prose] {len(files)}개 파일 검사 (기준: STYLE.md)")
    if not bad:
        print("[prose] ✓ 규약 위반 없음")
        return 0
    print(f"[prose] ✗ {sum(len(v) for v in bad.values())}건 / {len(bad)}개 파일\n")
    for f in sorted(bad, key=lambda x: -len(bad[x])):
        print(f"  {f}")
        for x in bad[f]:
            print(f"    - {x}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
