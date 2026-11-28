#!/usr/bin/env python3
"""상원 경합 주 스냅샷 — 여론조사 격차 추이 + Cook·Sabato 등급 변화를 주마다 한 장으로 — 2026-10-31.

입력: data/senate_polls.csv · data/candidates.json · data/rating_history.json · data/senate_ratings_feed.json
출력: assets/snapshots/<st>.svg (그림) · data/race_snapshots.json (요점·결론·수치)
쓰는 곳: State Focus 「최신 여론조사」 탭(race_snapshot_html), 강연 덱 부록(midterm-mba-presentation/render),
        덱 부록 장을 찍은 PNG.

규칙(사이트 R 헬퍼 .poll_series와 같음):
- 현 민주 지명자 대진의 조사만 쓴다(성으로 거름). 무소속 Osborn(NE)은 민주 쪽 자리에 둔다.
- note에 '후보 방향 미확인' 류가 있는 조사는 뺀다.
- 주목 기관(siena·fox news·marist·aarp)은 큰 점, 당파 후원 조사는 속 빈 점.
- 평균 = 실사 종료일 기준 직전 30일 조사의 단순 평균(2건 이상일 때만). 최근 30일에 2건 미만이면 최근 3건 평균.
- 결론의 '접전'은 |평균| < 4%p로 판정한다(강연 덱 S28의 경합 주 격차 D+2~4 기준과 맞춤).
- 등급 칸은 rating_history.json(월말 기준)을 기간 띠로 펼치고, 그 뒤는 senate_ratings_feed.json 현재값으로 잇는다.
  rating_history에 없는 주(KS·NE)는 현재값만 표시한다(추정으로 채우지 않음, 2026-10-31 사용자 지시).
"""
import csv
import json
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_SVG = ROOT / "assets/snapshots"
OUT_JSON = DATA / "race_snapshots.json"

PRIORITY_RE = re.compile(r"siena|fox news|marist|aarp")
D, R, INK, LAB, GRID, GRAY = "#2a5db0", "#8a1538", "#222222", "#6a6a6a", "#ebebeb", "#9a9a9a"
X0, X1 = date(2026, 3, 1), date(2026, 11, 3)          # 3월 ~ 선거일
CLOSE = 4.0
RATING_FILL = {"Solid D": "#1f4a8f", "Likely D": "#2a5db0", "Lean D": "#6f95d2", "Tilt D": "#a9c0e6",
               "Toss-up": "#c9c9c9",
               "Tilt R": "#e2a9b9", "Lean R": "#c4607d", "Likely R": "#8a1538", "Solid R": "#6b0f2a"}
RATING_KR = {"Toss-up": "경합"}
# rating_history 칸(월말 기준)의 기간
PERIODS = {"3월": ("03-01", "03-31"), "4월": ("04-01", "04-30"), "5월": ("05-01", "05-31"), "6월": ("06-01", "06-30"),
           "7월": ("07-01", "07-31"), "8월 초": ("08-01", "08-15"), "8월 하순": ("08-16", "08-31"),
           "9월 초": ("09-01", "09-10"), "9월 중순": ("09-11", "09-20"), "9월 하순": ("09-21", "09-30"),
           "10월 초": ("10-01", "10-10"), "10월 중순": ("10-11", "10-20"), "10월 하순": ("10-21", "10-31")}
FEED_KEY = {"cook": "cook-political-report-2026-senate", "sabato": "sabatos-crystal-ball-senate-2026"}
AG_NAME = {"cook": "Cook", "sabato": "Sabato"}


def d(s):
    return date.fromisoformat(s)


def md(dt):
    return f"{dt.month}/{dt.day}"


def fmt(m, left="D"):
    if m is None:
        return "—"
    if abs(m) < 0.05:
        return "동률"
    return f"{left}+{abs(m):.1f}" if m > 0 else f"R+{abs(m):.1f}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def polls_for(st, cands, rows):
    dem = [c for c in cands if c["state"] == st and c["party"] == "D" and c["status"] == "nominee"]
    last = dem[0]["name"].split()[-1] if dem else None
    out = []
    for p in rows:
        if p["state"] != st or (last and last not in p["dem_candidate"]):
            continue
        if re.search("후보 방향 미확인|방향 원문 확인 필요", p.get("note") or ""):
            continue
        dt = p["end_date"] or p["start_date"]
        try:
            m = float(p["margin"])
        except ValueError:
            continue
        if not dt:
            continue
        out.append(dict(date=d(dt), m=m, pollster=p["pollster"], sponsor=p["sponsor"] or "",
                        partisan=(p["partisan"] or "none") != "none",
                        priority=bool(PRIORITY_RE.search((p["pollster"] + " " + (p["sponsor"] or "")).lower()))))
    return sorted(out, key=lambda x: x["date"])


def window_avg(ps, end, days=30):
    w = [p["m"] for p in ps if end - timedelta(days=days) < p["date"] <= end]
    return (sum(w) / len(w), len(w)) if len(w) >= 2 else (None, len(w))


def rating_segments(hist, feed, ag, st, today):
    """[(from, to, rating)] — 같은 등급이 이어지는 칸은 합친다."""
    segs = []
    row = next((r for r in hist.get(ag, []) if r["state"] == st), None)
    if row:
        for mon, cell in zip(hist["_months"], row["cells"]):
            if cell.get("status") == "unknown" or not cell.get("r"):
                continue
            a, b = PERIODS[mon]
            segs.append([d(f"2026-{a}"), d(f"2026-{b}"), cell["r"]])
    cur = feed.get(ag, {}).get("ratings", {}).get(st)
    asof = d(feed[ag]["as_of"]) if ag in feed else today
    if cur:
        start = segs[-1][1] + timedelta(days=1) if segs else asof
        segs.append([start, max(today, start), cur])
    merged = []
    for s in segs:
        if merged and merged[-1][2] == s[2]:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return merged, bool(row)


def changes_text(segs, ag, has_hist):
    name = AG_NAME[ag]
    if not segs:
        return f"{name} 등급 없음"
    cur = segs[-1][2]
    if not has_hist:
        return f"{name} 현재 {cur} (변화 기록 없음)"
    if len(segs) == 1:
        return f"{name} {cur} 유지"
    moves = " → ".join(s[2] for s in segs)
    return f"{name} {moves} (마지막 이동 {segs[-1][0].month}월)"


def svg(st, ps, avg_line, segs_by_ag, left):
    w, h = 760, 430
    L, Rr = 58, 744
    pt, pb = 26, 268                                      # 조사 패널 위·아래
    x = lambda dt: L + (dt - X0).days / (X1 - X0).days * (Rr - L)
    span = max([abs(p["m"]) for p in ps] + [6])
    lim = 5 * int(span // 5 + 1)
    y = lambda m: pt + (lim - m) / (2 * lim) * (pb - pt)
    g = []
    for v in range(-lim, lim + 1, 5):
        lab = "0" if v == 0 else (f"{left}+{v}" if v > 0 else f"R+{-v}")
        g.append(f'<line x1="{L}" y1="{y(v):.1f}" x2="{Rr}" y2="{y(v):.1f}" stroke="{GRAY if v == 0 else GRID}" stroke-width="{1.5 if v == 0 else 1}"/>'
                 f'<text x="{L - 8}" y="{y(v) + 4:.1f}" font-size="12" fill="{LAB}" text-anchor="end">{lab}</text>')
    for mth in range(3, 11):
        xx = x(date(2026, mth, 1))
        g.append(f'<line x1="{xx:.1f}" y1="{pt}" x2="{xx:.1f}" y2="{pb}" stroke="{GRID}"/>'
                 f'<text x="{xx + 3:.1f}" y="{pb + 16}" font-size="12" fill="{LAB}">{mth}월</text>')
    xe = x(X1)
    g.append(f'<line x1="{xe:.1f}" y1="{pt}" x2="{xe:.1f}" y2="{pb}" stroke="{INK}" stroke-dasharray="4 3"/>'
             f'<text x="{xe - 4:.1f}" y="{pt + 12}" font-size="12" fill="{INK}" text-anchor="end">선거일</text>')
    for p in ps:
        col = D if p["m"] > 0 else R if p["m"] < 0 else GRAY
        r = 7 if p["priority"] else 4.5
        fill = "#fff" if p["partisan"] else col
        g.append(f'<circle cx="{x(p["date"]):.1f}" cy="{y(p["m"]):.1f}" r="{r}" fill="{fill}" fill-opacity="{1 if p["partisan"] else .75}" stroke="{col}" stroke-width="1.5"/>')
    if len(avg_line) >= 2:
        path = " ".join(f'{"M" if i == 0 else "L"}{x(dt):.1f},{y(m):.1f}' for i, (dt, m) in enumerate(avg_line))
        g.append(f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="2.5"/>')
        dt, m = avg_line[-1]
        g.append(f'<text x="{x(dt) - 4:.1f}" y="{y(m) - 10:.1f}" font-size="15" font-weight="800" fill="{INK}" text-anchor="end" '
                 f'stroke="#fff" stroke-width="4" paint-order="stroke">{fmt(m, left)}</text>')
    if not ps:
        g.append(f'<text x="{(L + Rr) / 2}" y="{(pt + pb) / 2}" font-size="15" fill="{LAB}" text-anchor="middle">본선 조사 없음</text>')
    # 등급 띠
    for i, ag in enumerate(("cook", "sabato")):
        yy = 306 + i * 52
        segs, has_hist = segs_by_ag[ag]
        g.append(f'<text x="{L - 8}" y="{yy + 21}" font-size="13" font-weight="700" fill="{INK}" text-anchor="end">{AG_NAME[ag]}</text>')
        g.append(f'<rect x="{L}" y="{yy}" width="{Rr - L}" height="32" fill="#f6f6f6"/>')
        for a, b, rt in segs:
            xa, xb = x(max(a, X0)), x(min(b + timedelta(days=1), X1))
            fc = RATING_FILL.get(rt, GRAY)
            dark = rt in ("Solid D", "Likely D", "Likely R", "Solid R", "Lean R")
            g.append(f'<rect x="{xa:.1f}" y="{yy}" width="{max(xb - xa, 1):.1f}" height="32" fill="{fc}" stroke="#fff" stroke-width="1.5"/>')
            if xb - xa > len(RATING_KR.get(rt, rt)) * 8 + 14:
                g.append(f'<text x="{xa + 6:.1f}" y="{yy + 21}" font-size="13" font-weight="700" fill="{"#fff" if dark else INK}">{RATING_KR.get(rt, rt)}</text>')
        if not has_hist:
            now = RATING_KR.get(segs[-1][2], segs[-1][2]) if segs else "없음"
            g.append(f'<text x="{x(date(2026, 3, 8)):.1f}" y="{yy + 21}" font-size="13" fill="{LAB}">변화 기록 없음 — 현재 <tspan font-weight="800" fill="{INK}">{now}</tspan></text>')
    lg = [(f'<circle cx="{L + 6}" cy="415" r="4.5" fill="{GRAY}"/>', "조사"),
          (f'<circle cx="{L + 66}" cy="415" r="7" fill="{GRAY}"/>', "주목 기관(NYT/Siena·Fox·Marist·AARP)"),
          (f'<circle cx="{L + 346}" cy="415" r="4.5" fill="#fff" stroke="{GRAY}" stroke-width="1.5"/>', "당파 후원"),
          (f'<line x1="{L + 426}" y1="415" x2="{L + 450}" y2="415" stroke="{INK}" stroke-width="2.5"/>', "직전 30일 평균")]
    offs = [14, 78, 356, 456]
    for (mark, lab), o in zip(lg, offs):
        g.append(mark + f'<text x="{L + o}" y="{419}" font-size="12" fill="{LAB}">{lab}</text>')
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Pretendard, sans-serif" role="img" aria-label="{st} 여론조사·등급 추이">{"".join(g)}</svg>'


def main():
    today = date.today()
    rows = list(csv.DictReader(open(DATA / "senate_polls.csv", encoding="utf-8")))
    cands = json.load(open(DATA / "candidates.json", encoding="utf-8"))["candidates"]
    rh = json.load(open(DATA / "rating_history.json", encoding="utf-8"))
    hist = {a["key"]: a["rows"] for a in rh["agencies"]}
    hist["_months"] = rh["months"]
    fd = json.load(open(DATA / "senate_ratings_feed.json", encoding="utf-8"))
    feed = {k: next(s for s in fd["sources"] if s["key"] == v) for k, v in FEED_KEY.items()}
    states = sorted({c["state"] for c in cands})
    OUT_SVG.mkdir(parents=True, exist_ok=True)
    out = {"as_of": today.isoformat(),
           "source_label": "data/senate_polls.csv · rating_history.json · senate_ratings_feed.json(270toWin 재게시)",
           "rule_note": "평균 = 직전 30일 조사 단순 평균(2건 미만이면 최근 3건). 접전 = |평균| < 4%p. 등급 띠는 월말 기준 칸을 기간으로 펼친 것이라 이동 시점은 그 기간 안의 어느 날이다. "
                        "큰 점 = 주목 기관(NYT/Siena·Fox·Marist·AARP), 속 빈 점 = 당파 후원 조사.",
           "states": {}}
    for st in states:
        ps = polls_for(st, cands, rows)
        left = "I" if st == "NE" else "D"
        nom = {c["party"]: c for c in cands if c["state"] == st and c["status"] == "nominee"}
        dn = (nom.get("D") or nom.get("I"))["name"].split()[-1]
        rn = nom["R"]["name"].split()[-1]
        avg_line = [(p["date"], a) for p in ps for a, _ in [window_avg(ps, p["date"])] if a is not None]
        avg, n = window_avg(ps, today)
        if avg is not None and avg_line and avg_line[-1][0] < today:
            avg_line.append((min(today, X1), avg))      # 그림 끝 라벨 = 요점의 현재 평균
        label = "최근 30일 평균"
        if avg is None and ps:
            last3 = ps[-3:]
            avg, n, label = sum(p["m"] for p in last3) / len(last3), len(last3), f"최근 {len(last3)}건 평균"
        prev, _ = window_avg(ps, today - timedelta(days=30))
        segs = {ag: rating_segments(hist, feed, ag, st, today) for ag in ("cook", "sabato")}
        bullets = []
        if avg is not None:
            b = f"{label} {fmt(avg, left)} (조사 {n}건)"
            if prev is not None and label.startswith("최근 30일"):
                diff = avg - prev
                b += f"<br><span class='dim'>그 전 30일 {fmt(prev, left)} → {abs(diff):.1f}%p {'민주' if diff > 0 else '공화'} 쪽 이동</span>" \
                    if abs(diff) >= 0.5 else f"<br><span class='dim'>그 전 30일 {fmt(prev, left)} — 거의 같음</span>"
            bullets.append(b)
            lp = ps[-1]
            bullets.append(f"최신 조사 {'★ ' if lp['priority'] else ''}{esc(lp['pollster'])} {md(lp['date'])} {fmt(lp['m'], left)}")
        else:
            bullets.append("본선 조사 없음")
        bullets.append(changes_text(segs["cook"][0], "cook", segs["cook"][1]) + "<br><span class='dim'>"
                       + changes_text(segs["sabato"][0], "sabato", segs["sabato"][1]) + "</span>")
        cook_now = segs["cook"][0][-1][2] if segs["cook"][0] else "—"
        if avg is None:
            take = f"조사 없음 · Cook {cook_now}"
        elif abs(avg) < CLOSE:
            take = f"조사 평균 {fmt(avg, left)} — 오차 범위 안의 접전 · Cook {cook_now}"
        else:
            side = {"D": "민주", "I": "무소속"}[left] if avg > 0 else "공화"
            take = f"조사 평균 {fmt(avg, left)} — {side} 우세 · Cook {cook_now}"
        (OUT_SVG / f"{st.lower()}.svg").write_text(svg(st, ps, avg_line, segs, left), encoding="utf-8")
        out["states"][st] = {
            "name_kr": None, "matchup": f"{dn}({left}) 대 {rn}(R)", "avg": None if avg is None else round(avg, 1),
            "avg_label": label, "n_avg": n, "n_polls": len(ps),
            "latest": None if not ps else {"pollster": ps[-1]["pollster"], "date": ps[-1]["date"].isoformat(), "margin": ps[-1]["m"]},
            "ratings": {ag: [[a.isoformat(), b.isoformat(), r] for a, b, r in segs[ag][0]] for ag in segs},
            "bullets": bullets, "takeaway": take, "svg": f"assets/snapshots/{st.lower()}.svg"}
    kr = {"AK": "알래스카", "GA": "조지아", "IA": "아이오와", "KS": "캔자스", "ME": "메인", "MI": "미시간",
          "NC": "노스캐롤라이나", "NE": "네브래스카", "NH": "뉴햄프셔", "OH": "오하이오", "TX": "텍사스"}
    for st in out["states"]:
        out["states"][st]["name_kr"] = kr.get(st, st)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"[snapshots] {len(out['states'])}주 → {OUT_JSON.name}, assets/snapshots/*.svg")


if __name__ == "__main__":
    main()
