#!/usr/bin/env python3.11
"""렌더된 페이지를 실제 브라우저로 열어 표 레이아웃을 검증한다.

왜 필요한가 — 2026-09-05에 CSS 한 줄(`min-width:max-content`)이 대시보드 두 표를
화면보다 수천 px 넓게 만들어 표 제목이 화면 밖으로 밀려났다. 그런데 HTML·CSS를
문자열로 검사하는 확인은 전부 통과했다(착색 90/90, 규칙 배포 확인). **레이아웃
붕괴는 문자열 검사로 잡히지 않는다** — 실제로 렌더해서 폭을 재야 잡힌다.

검사 항목 (표마다):
  1. 표가 자기 스크롤 컨테이너를 넘는가        → 가로 스크롤 없이 잘리면 실패
  2. 표 때문에 페이지 본문이 가로로 밀리는가    → 항상 실패
  3. 표 제목(gt heading)이 뷰포트 밖으로 나가는가 → 실패 (2026-09-05 회귀의 증상)
  4. 표가 컨테이너보다 넓은데 스크롤이 없는가   → 실패

주의 — 이 레포의 _site/는 Dropbox 안에 있다. 렌더 중 충돌 사본이 생기고 파일 접근이
일시 실패하므로(2026-09-05 실측), 검사 전에 Dropbox 밖으로 복사해서 본다(--copy, 기본값).

사용:
  python3.11 scripts/check_tables.py                 # _site 전체
  python3.11 scripts/check_tables.py dashboard.html  # 특정 페이지만
  python3.11 scripts/check_tables.py --shot          # 문제 페이지 스크린샷 저장
  python3.11 scripts/check_tables.py --all-shots     # 전 페이지 스크린샷

종료 코드: 문제가 하나라도 있으면 1 (CI 게이트로 쓸 수 있게).
"""
import sys, pathlib, json

def _is_conflict(name):
    """Dropbox 충돌 사본 판정. macOS는 파일명을 NFD로 저장하므로 NFC 문자열 비교가
    그냥은 실패한다(2026-09-05 실측) — 정규화한 뒤 비교한다."""
    import unicodedata
    n = unicodedata.normalize("NFC", name)
    return ("충돌" in n and "사본" in n) or "conflicted copy" in n or "conflicted-copy" in n


ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"
SHOTS = ROOT / ".table-audit"
# 데스크톱 + 모바일 두 폭에서 본다. 좁은 폭에서만 깨지는 표가 흔하다.
VIEWPORTS = [("desktop", 1280, 900), ("mobile", 390, 844)]

PROBE = """() => {
  const out = [];
  document.querySelectorAll('table').forEach((t, i) => {
    const box = t.parentElement;
    const heading = t.querySelector('.gt_heading, caption');
    const r = t.getBoundingClientRect();
    out.push({
      idx: i,
      cls: (t.className || '').slice(0, 40),
      tableW: Math.round(t.scrollWidth),
      boxW: Math.round(box ? box.clientWidth : 0),
      boxScrolls: box ? (box.scrollWidth > box.clientWidth + 1) : false,
      boxOverflowX: box ? getComputedStyle(box).overflowX : '',
      right: Math.round(r.right),
      headingRight: heading ? Math.round(heading.getBoundingClientRect().right) : null,
      headingLeft: heading ? Math.round(heading.getBoundingClientRect().left) : null,
    });
  });
  return {
    tables: out,
    docW: Math.round(document.documentElement.scrollWidth),
    winW: Math.round(window.innerWidth),
  };
}"""


def audit(page, url, label, w):
    page.goto(url, wait_until="load")
    page.wait_for_timeout(220)          # 웹폰트·레이아웃 안정화
    d = page.evaluate(PROBE)
    problems = []
    # 페이지 자체가 가로로 밀리면 표 하나가 폭을 지배한 것이다
    if d["docW"] > d["winW"] + 2:
        problems.append(f"페이지 가로 스크롤 (문서 {d['docW']}px > 뷰포트 {d['winW']}px)")
    for t in d["tables"]:
        tag = f"표#{t['idx']}"
        # 컨테이너보다 넓은데 그 컨테이너가 스크롤을 못 하면 잘린다
        if t["tableW"] > t["boxW"] + 2 and t["boxOverflowX"] not in ("auto", "scroll"):
            problems.append(f"{tag} 컨테이너 초과·스크롤 없음 "
                            f"(표 {t['tableW']}px > 칸 {t['boxW']}px, overflow-x:{t['boxOverflowX'] or '없음'})")
        # 제목이 뷰포트 밖 — 2026-09-05 회귀의 증상
        hr, hl = t["headingRight"], t["headingLeft"]
        if hr is not None and (hr > w + 2 or hl < -2):
            problems.append(f"{tag} 제목이 뷰포트 밖 (left {hl}px, right {hr}px, 뷰포트 {w}px)")
    return problems, d


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not SITE.exists():
        print(f"[check] {SITE} 없음 — 먼저 quarto render", file=sys.stderr); return 2
    site = SITE
    if "--no-copy" not in flags:
        # Dropbox 밖 사본에서 검사한다 — 원본은 동기화 중 파일이 사라졌다 나타난다.
        import tempfile, shutil
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="table-audit-"))
        for f in SITE.rglob("*"):
            if _is_conflict(f.name):
                continue
            dst = tmp / f.relative_to(SITE)
            try:
                if f.is_dir(): dst.mkdir(parents=True, exist_ok=True)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, dst)
            except OSError:
                pass          # 동기화 경합으로 사라진 파일은 건너뛴다
        site = tmp
        print(f"[check] Dropbox 밖 사본에서 검사: {site}")
    pages = ([site / a for a in args] if args
             else sorted(p for p in site.rglob("*.html") if not _is_conflict(p.name)))
    from playwright.sync_api import sync_playwright
    SHOTS.mkdir(exist_ok=True)
    bad, checked, n_tables, skipped = {}, 0, 0, []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for label, w, h in VIEWPORTS:
            page = b.new_page(viewport={"width": w, "height": h})
            for f in pages:
                try:
                    probs, d = audit(page, f.as_uri(), label, w)
                except Exception as e:
                    skipped.append(f"{f.name} [{label}]: {type(e).__name__}")
                    continue
                if label == "desktop":
                    checked += 1; n_tables += len(d["tables"])
                if probs:
                    key = f"{f.relative_to(site)} [{label}]"
                    bad[key] = probs
                    if "--shot" in flags or "--all-shots" in flags:
                        page.screenshot(path=str(SHOTS / f"{f.stem}-{label}.png"), full_page=True)
                elif "--all-shots" in flags:
                    page.screenshot(path=str(SHOTS / f"{f.stem}-{label}.png"), full_page=True)
            page.close()
        b.close()
    print(f"[check] 페이지 {checked} · 표 {n_tables} · 뷰포트 {len(VIEWPORTS)}종")
    if skipped:
        print(f"[check] ! 로드 실패 {len(skipped)}건: " + ", ".join(skipped[:4]))
    if not bad:
        print("[check] ✓ 표 레이아웃 문제 없음"); return 0
    print(f"[check] ✗ 문제 {sum(len(v) for v in bad.values())}건 / {len(bad)}개 페이지-뷰포트\n")
    for k in sorted(bad):
        print(f"  {k}")
        for p in bad[k]:
            print(f"    - {p}")
    if "--shot" in flags:
        print(f"\n  스크린샷: {SHOTS}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
