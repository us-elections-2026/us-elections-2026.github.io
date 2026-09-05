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

**--live를 기본으로 쓸 것.** 이 레포의 _site/는 Dropbox 안이라 신뢰할 수 없다 —
2026-09-05 실측: 지운 CSS 번들이 되살아나고, 새로 렌더한 HTML이 며칠 전 사본으로
되돌려졌으며, 106개 페이지가 참조하는 번들 파일이 사라져 있었다. 그 상태로 검사하면
"스타일이 아예 없는 페이지"를 재게 되어 거짓 문제가 무더기로 나온다.
CI는 git 클린 체크아웃에서 렌더하므로 배포본이 정본이다.

주의 — 이 레포의 _site/는 Dropbox 안에 있다. 렌더 중 충돌 사본이 생기고 파일 접근이
일시 실패하므로(2026-09-05 실측), 검사 전에 Dropbox 밖으로 복사해서 본다(--copy, 기본값).

사용:
  python3.11 scripts/check_tables.py --live          # 배포된 사이트 (권장·정본)
  python3.11 scripts/check_tables.py                 # 로컬 _site 전체
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
      selfOverflowX: getComputedStyle(t).overflowX,
      clientW: Math.round(t.clientWidth),
      right: Math.round(r.right),
      headingRight: heading ? Math.round(heading.getBoundingClientRect().right) : null,
      headingLeft: heading ? Math.round(heading.getBoundingClientRect().left) : null,
      headTextStart: (() => {
        if (!heading) return null;
        const n = [...heading.childNodes].find(x => x.nodeType === 3 && x.textContent.trim())
               || heading.firstElementChild;
        if (!n) return null;
        const rg = document.createRange(); rg.selectNodeContents(n);
        const r = rg.getBoundingClientRect();
        return r.width ? Math.round(r.left) : null;
      })(),
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
    # 레이아웃이 안정된 뒤에 재야 한다. 220ms만 기다렸을 때 이미지가 아직 배치되지 않아
    # "페이지 가로 스크롤" 거짓 양성이 대량 발생했다(2026-09-05: 21건 중 전부가 artifact).
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    page.evaluate("() => document.fonts ? document.fonts.ready : null")
    page.wait_for_timeout(400)
    d = page.evaluate(PROBE)
    problems = []
    # 페이지 자체가 가로로 밀리면 표 하나가 폭을 지배한 것이다
    if d["docW"] > d["winW"] + 2:
        problems.append(f"페이지 가로 스크롤 (문서 {d['docW']}px > 뷰포트 {d['winW']}px)")
    for t in d["tables"]:
        tag = f"표#{t['idx']}"
        # 넘치는 폭을 감당할 스크롤 상자가 없으면 잘린다.
        # 스크롤 주체는 부모일 수도(gt의 컨테이너 div) 표 자신일 수도 있다
        # (마크다운 표는 display:block + overflow-x:auto로 표가 직접 스크롤한다).
        scrolls = (t["boxOverflowX"] in ("auto", "scroll")
                   or t["selfOverflowX"] in ("auto", "scroll"))
        if t["tableW"] > t["boxW"] + 2 and not scrolls:
            problems.append(f"{tag} 컨테이너 초과·스크롤 없음 "
                            f"(표 {t['tableW']}px > 칸 {t['boxW']}px, "
                            f"부모 overflow-x:{t['boxOverflowX']}, 표 자신:{t['selfOverflowX']})")
        # 제목이 화면 밖에서 시작하는가 — 2026-09-05 회귀의 증상.
        # 재는 것은 제목 **칸**이 아니라 **글자 시작점**이다. gt 제목 칸은 colspan으로
        # 표 폭 전체를 차지하므로, 넓은 표에서는 칸의 오른쪽 끝이 뷰포트를 넘는 게 정상이다.
        # 문제는 글자가 화면 밖에서 시작할 때(가운데 정렬 + 넓은 표)뿐이다.
        hl, hr = t["headingLeft"], t["headingRight"]
        ts = t["headTextStart"]
        if ts is not None and (ts > w - 8 or ts < -2):
            problems.append(f"{tag} 제목 글자가 화면 밖에서 시작 (글자 시작 {ts}px, 뷰포트 {w}px)")
    return problems, d


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not SITE.exists():
        print(f"[check] {SITE} 없음 — 먼저 quarto render", file=sys.stderr); return 2
    live = "--live" in flags
    if live:
        import urllib.request, re as _re
        base = "https://us-elections-2026.github.io"
        with urllib.request.urlopen(base + "/sitemap.xml", timeout=30) as r:
            urls = _re.findall(r"<loc>([^<]+)</loc>", r.read().decode())
        pages = [u for u in urls if u.endswith(".html")] or urls
        print(f"[check] 배포 사이트 검사: {base} ({len(pages)}쪽)")
        return run(pages, flags, live=True)
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
    return run([f.as_uri() for f in pages], flags, live=False, site=site)


def run(targets, flags, live, site=None):
    from playwright.sync_api import sync_playwright
    SHOTS.mkdir(exist_ok=True)
    bad, checked, n_tables, skipped = {}, 0, 0, []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for label, w, h in VIEWPORTS:
            page = b.new_page(viewport={"width": w, "height": h})
            for f in targets:
                try:
                    probs, d = audit(page, f, label, w)
                    # 한 번 더 재서 양쪽에 다 나온 것만 남긴다. 스타일시트·이미지가
                    # 적용되기 전에 재면 "페이지 가로 스크롤"이 헛나온다(2026-09-05:
                    # 9건 전부가 그런 흔들림이었다). 게이트로 쓰려면 흔들림을 지워야 한다.
                    if probs:
                        page.wait_for_timeout(600)
                        again, _ = audit(page, f, label, w)
                        probs = [x for x in probs if x in again]
                except Exception as e:
                    skipped.append(f"{f.rsplit('/',1)[-1]} [{label}]: {type(e).__name__}: {e}")
                    continue
                if label == "desktop":
                    checked += 1; n_tables += len(d["tables"])
                if probs:
                    name = f.rsplit("/", 2)[-1] if live else str(pathlib.Path(f[7:]).relative_to(site))
                    key = f"{name} [{label}]"
                    bad[key] = probs
                    if "--shot" in flags or "--all-shots" in flags:
                        page.screenshot(path=str(SHOTS / f"{name.replace('/','_')}-{label}.png"), full_page=True)
                elif "--all-shots" in flags:
                    page.screenshot(path=str(SHOTS / f"{f.rsplit('/',1)[-1]}-{label}.png"), full_page=True)
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
