#!/usr/bin/env python3
"""조사기관(pollster)별 개별 여론조사 취득 — 트럼프 순지지도·일반투표 마진.

왜 필요한가 — 이 사이트가 지금까지 실은 것은 **집계기관의 평균값**뿐이다
(Silver Bulletin -20.6, FiftyPlusOne -23.0 …). 그런데 같은 날 같은 나라를 두고
집계값이 2.4p 벌어지는 이유는 집계 알고리즘이 아니라 **원자료를 만든 조사기관이
서로 다르게 나오기 때문**이다. 그 차이를 보려면 평균이 아니라 개별 조사가 필요하다.

출처: VoteHub 공개 API (인증 불필요, https://api.votehub.com/polls).
  - subject="Donald Trump" & poll_type="approval"      → 순지지도(approve − disapprove)
  - subject="2026"        & poll_type="generic-ballot" → 일반투표 마진(dem − rep, 양수=민주 우위)

**알려진 한계 — 피드 신선도**: 이 API는 페이지네이션 없이 전량을 주지만, 피드 자체가
실시간이 아니다. 취득 시점의 최신 조사 종료일을 `data_through`에 그대로 적어
페이지에 노출한다(추정으로 메우지 않는다). 최신 주간 수치는 기존 집계표가 담당한다.

산출물:
  data/approval_polls.csv   개별 조사 원자료(정규화, 전 기간)
  data/generic_polls.csv    개별 조사 원자료(정규화, 전 기간)
  data/pollster_series.json 차트용 — 개별 조사 + 이동평균 추세 + 하우스 이펙트

사용: python3 scripts/fetch_pollster_polls.py [--dry-run] [--since 2026-01-01]
"""
import argparse
import csv
import datetime
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request

API = "https://api.votehub.com/polls"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 추세선: 단순 중심 이동평균. 창이 좁으면 표본 구성이 바뀔 때마다 튀고,
# 넓으면 실제 변동을 지운다. 21일은 월 단위 조사(Gallup 등)도 최소 1건 걸리는 폭.
TREND_WINDOW_DAYS = 21
# 하우스 이펙트를 산출할 최소 조사 수 — 3건 이하면 우연과 구분되지 않는다.
MIN_POLLS_FOR_HOUSE_EFFECT = 5
# 시계열 선을 그릴 조사기관 수 (나머지는 회색 점으로만 배경에 남는다)
TOP_N_POLLSTERS = 8


def fetch(subject, poll_type):
    q = urllib.parse.urlencode({"subject": subject, "poll_type": poll_type})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def pick(answers, a, b):
    """answers 배열에서 두 선택지의 % 를 꺼낸다. 하나라도 없으면 None."""
    m = {x.get("choice"): x.get("pct") for x in answers or []}
    if m.get(a) is None or m.get(b) is None:
        return None, None
    return float(m[a]), float(m[b])


def normalize(raw, hi, lo):
    """VoteHub 레코드 → 한 행. hi−lo 가 우리가 쓰는 부호(양수=민주/지지 우위)."""
    rows, skipped = [], 0
    for p in raw:
        v_hi, v_lo = pick(p.get("answers"), hi, lo)
        end = p.get("end_date")
        if v_hi is None or not end:
            skipped += 1          # 선택지 구성이 다른 레코드(피드 혼입) — 버리고 센다
            continue
        rows.append({
            "date_end": end,
            "date_start": p.get("start_date") or "",
            "pollster": p.get("pollster") or "",
            "sponsor": "; ".join(p.get("sponsors") or []),
            "population": (p.get("population") or "").upper(),
            "n": p.get("sample_size") or "",
            "hi": v_hi,
            "lo": v_lo,
            "value": round(v_hi - v_lo, 1),
            "partisan": p.get("partisan") or "",
            "internal": "Y" if p.get("internal") else "",
            "poll_id": p.get("id") or "",
            "source_url": p.get("url") or "",
        })
    rows.sort(key=lambda r: (r["date_end"], r["pollster"]))
    return rows, skipped


def to_day(s):
    return datetime.date.fromisoformat(s)


# 모집단 우선순위 — 같은 조사가 여러 모집단으로 실릴 때 무엇 하나만 남길지.
# 선거 예측에 가까운 순서(유력투표층 > 등록유권자 > 성인 전체).
POP_RANK = {"LV": 0, "RV": 1, "A": 2, "V": 3, "": 4}


def drop_exact_dupes(rows):
    """피드 중복 제거 — 기관·기간·모집단·값·표본이 전부 같은데 id만 다른 행.

    2026-08-06 원본 대조에서 확인: VoteHub 피드가 같은 조사를 두 id로 싣는 경우가 있다
    (Reuters 기사 URL과 Ipsos 토플라인 PDF URL처럼 출처만 다른 경우 포함).
    """
    seen, out, n = set(), [], 0
    for r in rows:
        k = (r["pollster"], r["date_start"], r["date_end"], r["population"],
             r["hi"], r["lo"], str(r["n"]))
        if k in seen:
            n += 1
            continue
        seen.add(k)
        out.append(r)
    return out, n


def one_per_survey(rows):
    """추세·하우스 이펙트용 — 한 조사(기관+현장기간)당 한 행만.

    왜 필요한가 — 한 조사가 성인/등록유권자/유력투표층으로 2~3행이 되면 단순 평균에서
    **같은 현장조사가 2~3번 가중**된다. 2026년 기준 순지지도 행의 20%, 일반투표의 24%가
    이 중복 가중이었고, 두 모집단을 늘 함께 싣는 YouGov가 가장 크게 부풀려졌다.
    게다가 순지지도는 RV/LV가 A보다 체계적으로 높게 나와, 어느 기관이 어느 모집단을
    싣느냐가 평균 수준까지 흔든다. 조사 단위로 하나만 남겨 이를 끊는다.
    (그래프의 점은 실제 발표된 값이므로 전부 그대로 찍는다 — 이 축약은 계산에만 쓴다.)
    """
    best = {}
    for r in rows:
        k = (r["pollster"], r["date_start"], r["date_end"])
        cur = best.get(k)
        if cur is None or POP_RANK.get(r["population"], 9) < POP_RANK.get(cur["population"], 9):
            best[k] = r
    return sorted(best.values(), key=lambda r: (r["date_end"], r["pollster"]))


def rolling_trend(rows, window, since):
    """비당파 조사만으로 중심 이동평균.

    **양끝을 잘라낸다** — 창의 절반이 자료 밖으로 나가는 날은 중심평균이 아니라
    편측평균이 되어 다른 추정량이 된다. 특히 오른쪽 끝(피드 최신일 부근)을 그대로
    두면 마지막 점만 성격이 달라 '최근 급변'처럼 보인다. 전 기간으로 계산한 뒤
    창이 온전한 구간만 내보내고, 표시는 since 이후만 한다.
    """
    pts = [(to_day(r["date_end"]), r["value"]) for r in rows if not r["partisan"]]
    if not pts:
        return []
    half = datetime.timedelta(days=window // 2)
    d0, d1 = pts[0][0], pts[-1][0]
    lo, hi = d0 + half, d1 - half
    out, day = [], to_day(since)
    while day <= hi:
        if day >= lo:
            vals = [v for d, v in pts if day - half <= d <= day + half]
            if vals:
                out.append({"d": day.isoformat(), "v": round(statistics.fmean(vals), 2),
                            "n": len(vals)})
        day += datetime.timedelta(days=7)   # 주 단위로만 찍는다 (JSON 경량화)
    return out


def house_effects(rows, trend):
    """조사기관별 평균 잔차 = (그 기관의 조사) − (같은 시점 이동평균).

    집계기관들이 쓰는 하우스 이펙트 보정과 같은 개념이지만, 여기 추세선은
    보정 이전의 단순 평균이므로 값은 근사다. 부호와 순서를 읽는 용도.
    """
    if not trend:
        return []
    tp = [(to_day(t["d"]), t["v"]) for t in trend]

    def at(day):                      # 가장 가까운 추세점 (주 단위 격자)
        return min(tp, key=lambda x: abs((x[0] - day).days))[1]

    by = {}
    for r in rows:
        if r["partisan"]:
            continue
        by.setdefault(r["pollster"], []).append(r["value"] - at(to_day(r["date_end"])))
    out = [{"pollster": k, "n": len(v), "effect": round(statistics.fmean(v), 1)}
           for k, v in by.items() if len(v) >= MIN_POLLS_FOR_HOUSE_EFFECT]
    out.sort(key=lambda x: x["effect"], reverse=True)
    return out


def write_csv(path, rows, hi_col, lo_col):
    cols = ["date_end", "date_start", "pollster", "sponsor", "population", "n",
            hi_col, lo_col, "value", "partisan", "internal", "poll_id", "source_url"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r["date_end"], r["date_start"], r["pollster"], r["sponsor"],
                        r["population"], r["n"], r["hi"], r["lo"], r["value"],
                        r["partisan"], r["internal"], r["poll_id"], r["source_url"]])


def block(rows, since, label):
    """차트용 블록 — since 이후만. 원자료 CSV는 전 기간을 따로 보관한다."""
    win = [r for r in rows if r["date_end"] >= since]
    # 계산용 표본: 조사 단위로 1행. 그래프의 점(win)은 발표된 값 전부를 그대로 쓴다.
    calc_all = one_per_survey(rows)
    calc = [r for r in calc_all if r["date_end"] >= since]
    # 추세는 전 기간(2025~)으로 계산해야 창 왼쪽 끝이 잘리지 않는다. 표시만 since 이후.
    trend = rolling_trend(calc_all, TREND_WINDOW_DAYS, since)
    eff = house_effects(calc, trend)
    counts = {}
    for r in win:
        counts[r["pollster"]] = counts.get(r["pollster"], 0) + 1
    top = [p for p, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:TOP_N_POLLSTERS]]
    print(f"[polls] {label}: {len(win)}건 / 조사기관 {len(counts)}곳 / "
          f"{win[0]['date_end']}~{win[-1]['date_end']} · 상위: {', '.join(top[:4])} …")
    print(f"[polls]   └ 계산용(조사 단위 1행): {len(calc)}건 — "
          f"모집단 중복 {len(win) - len(calc)}행 제외")
    return {
        "polls": [{"d": r["date_end"], "v": r["value"], "p": r["pollster"],
                   "pop": r["population"], "n": r["n"] or None,
                   "party": r["partisan"] or None, "url": r["source_url"]}
                  for r in win],
        "trend": trend,
        "top_pollsters": top,
        "house_effects": eff,
        "data_through": win[-1]["date_end"],
        "trend_through": trend[-1]["d"] if trend else None,
        "n_polls": len(win),
        "n_pollsters": len(counts),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--since", default="2026-01-01",
                    help="차트 표시 시작일 (CSV 원자료는 항상 전 기간)")
    args = ap.parse_args()

    try:
        appr_raw = fetch("Donald Trump", "approval")
        gen_raw = fetch("2026", "generic-ballot")
    except Exception as e:                       # noqa: BLE001 — 취득 실패는 그대로 보고
        print(f"[polls] API 취득 실패: {e}", file=sys.stderr)
        return 1

    appr, s1 = normalize(appr_raw, "Approve", "Disapprove")
    gen, s2 = normalize(gen_raw, "Dem", "Rep")
    if s1 or s2:
        print(f"[polls] 선택지 불일치로 제외: 지지율 {s1}건 · 일반투표 {s2}건", file=sys.stderr)
    appr, d1 = drop_exact_dupes(appr)
    gen, d2 = drop_exact_dupes(gen)
    if d1 or d2:
        print(f"[polls] 피드 중복 제거: 지지율 {d1}행 · 일반투표 {d2}행")
    if not appr or not gen:
        print("[polls] 정규화 결과가 비었다 — API 스키마 변경 의심", file=sys.stderr)
        return 1

    out = {
        "as_of": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "fetched_at_utc": datetime.datetime.now(datetime.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "poll",          # aggregate/model/market 이 아니라 개별 조사 원자료
        "source_label": "VoteHub (개별 조사 취합)",
        "source_url": "https://votehub.com/polls/",
        "window_start": args.since,
        "trend_window_days": TREND_WINDOW_DAYS,
        "note": ("점 하나가 개별 조사다. 굵은 선은 비당파 조사의 "
                 f"{TREND_WINDOW_DAYS}일 중심 이동평균이며 하우스 이펙트를 보정하지 않는다 — "
                 "위 표의 집계기관 평균(Silver Bulletin 등)과 산출 방식이 다르므로 "
                 "같은 잣대로 비교하지 말 것. 당파(내부) 조사는 추세·하우스 이펙트 산출에서 제외."),
        "approval": block(appr, args.since, "순지지도"),
        "generic": block(gen, args.since, "일반투표"),
    }

    if args.dry_run:
        print("[polls] --dry-run: 파일 미변경.")
        return 0

    write_csv(os.path.join(ROOT, "data", "approval_polls.csv"), appr,
              "approve", "disapprove")
    write_csv(os.path.join(ROOT, "data", "generic_polls.csv"), gen, "dem", "rep")
    with open(os.path.join(ROOT, "data", "pollster_series.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"[polls] wrote data/approval_polls.csv ({len(appr)}행) · "
          f"data/generic_polls.csv ({len(gen)}행) · data/pollster_series.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
