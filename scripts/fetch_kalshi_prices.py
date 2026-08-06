#!/usr/bin/env python3
"""Kalshi 예측시장 '실제 가격' 취득 (공개 API).

270towin은 Kalshi 가격을 Cook과 같은 7단계 등급으로 **환산**해 재게시한다.
환산값은 등급과 뒤섞여 오독되기 쉬우므로(가격 91¢가 'Solid D'로 보이는 문제),
이 스크립트는 Kalshi 공개 API에서 **원가격(센트=확률 근사)**을 직접 받아온다.

취득 대상
  - 상원 다수: CONTROLS-2026-{D,R}  ("Will {party} win the U.S. Senate in 2026?")
  - 하원 다수: CONTROLH-2026-{D,R}   ("Will {party} win the House in 2026?")
  - 상원 개별 레이스: SENATE{ST} → 없으면 SENATE{ST}S(특별선거) → KXSENATE{ST}
  - 주지사 개별 레이스: GOVPARTY{ST} → 없으면 KXGOVPARTY{ST}

주의 — Kalshi의 티커는 신뢰할 수 없다(2026-08-06 확인)
  1) 사이클 접미사가 주마다 제각각이다: 조지아 주지사는 `-26`, 캔자스는 `-27`, 뉴햄프셔는 `-28`.
  2) 티커의 주 약자가 틀린 경우가 있다: `SENATELA-26-*`의 제목·규칙은 **켄터키** 경선이다.
  그래서 티커를 믿지 않고 — 주는 **규칙 원문(rules_primary)**의 주 이름으로,
  사이클은 **만기일(expected_expiration)**로 각각 따로 판정한다.
  어느 선거를 가격화한 것인지 확정되지 않는 계약은 **버린다**(추정으로 채우지 않는다).

원칙
  - 마지막 체결가가 없으면 null(추정 금지). D+R이 100이 안 되는 것은 정상이다 —
    서로 다른 계약의 '마지막 체결가'라 호가 스프레드만큼 어긋난다. 정규화하지 않는다.

산출물: data/kalshi_prices.json
사용:   python3 scripts/fetch_kalshi_prices.py [--dry-run]
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.elections.kalshi.com/trade-api/v2/markets"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATE_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
# 2026 주지사 선거 36개 주 (미선거 14주 제외 — fetch_governor_ratings.py와 같은 기준)
NO_GOV = {"DE", "IN", "KY", "LA", "MO", "MS", "MT", "NC", "ND", "NJ", "UT", "VA", "WA", "WV"}


FAILED = []


def api_markets(series):
    """시리즈 조회. 일시적 실패(요청 제한 등)는 재시도하고, 끝내 실패하면 기록한다.
    조용히 빈 목록을 돌려주면 '시장 없음'과 구분되지 않아 결측을 못 알아챈다."""
    url = f"{API}?series_ticker={series}&limit=40"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r).get("markets", [])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []                      # 존재하지 않는 시리즈 — 정상
            time.sleep(1.5 * (attempt + 1))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            time.sleep(1.5 * (attempt + 1))
    FAILED.append(series)
    return []


def cents(v):
    """'0.9110' → 91.1 (백분율). 값이 없거나 0이면 None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f * 100, 1) if f > 0 else None


# 긴 이름 먼저 — "West Virginia"가 "Virginia"로, "North Carolina"가 "Carolina"로 잘못 잡히는 것을 막는다
BY_LEN = sorted(STATE_NAME.items(), key=lambda kv: -len(kv[1]))


def state_of(market):
    """계약 규칙 원문에서 주를 읽는다(티커를 믿지 않는다)."""
    txt = ((market.get("rules_primary") or "") + " " + (market.get("title") or "")).lower()
    for ab, name in BY_LEN:
        if name.lower() in txt:
            return ab
    return None


def cycle_ok(market):
    """2026 선거를 가격화한 계약인지 — **만기일**로 판정한다.

    규칙 원문의 연도 표기는 직군마다 달라 기준으로 쓸 수 없다:
      주지사 "pursuant to the 2026 election" / 상원 "for the term beginning in 2027".
    반면 만기(취임·선서일)는 사이클마다 명확히 갈린다 — 2026년 본선의 당선자는
    2027년 초에 취임하고, 2028년 본선분은 2029년 초다. 그래서 만기 하나로 본다.
    (규칙은 2026이라면서 만기가 2029인 뉴햄프셔 주지사 계약처럼 자체 모순인 건은
     어느 선거인지 확정할 수 없으므로 이 기준에서 자동 탈락한다.)
    """
    exp = str(market.get("expected_expiration_time") or "")[:10]
    return "2026-11-01" <= exp <= "2027-12-31"


def series_for(kind, st):
    if kind == "senate":
        return [f"SENATE{st}", f"SENATE{st}S", f"KXSENATE{st}"]
    return [f"GOVPARTY{st}", f"KXGOVPARTY{st}"]


def collect(kind, states):
    """후보 시리즈를 모두 조회해 하나의 풀로 모은 뒤, 규칙 원문 기준으로 주에 배정한다."""
    names = []
    for st in states:
        names.extend(series_for(kind, st))
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        fetched = list(zip(names, ex.map(api_markets, names)))

    pool, seen = [], set()
    for series, markets in fetched:
        for m in markets:
            if m.get("ticker") in seen:
                continue
            seen.add(m["ticker"])
            m["_series"] = series
            pool.append(m)

    out, dropped = {}, []
    for m in pool:
        side = m["ticker"].rsplit("-", 1)[-1]
        if side not in ("D", "R"):
            continue                      # 무소속·제3후보 계약 — 양당 가격만 싣는다
        st = state_of(m)
        if st is None or st not in states:
            continue
        if not cycle_ok(m):
            if "2026" in (m.get("rules_primary") or ""):
                dropped.append(f"{m['ticker']}({st})")
            continue
        row = out.setdefault(st, {"dem": None, "rep": None, "dem_label": None, "rep_label": None,
                                  "volume": 0.0, "open_interest": 0.0,
                                  "series": m["_series"], "tickers": []})
        k = "dem" if side == "D" else "rep"
        row[k] = cents(m.get("last_price_dollars"))
        row[k + "_label"] = m.get("yes_sub_title") or None
        row["volume"] += float(m.get("volume_fp") or 0)
        row["open_interest"] += float(m.get("open_interest_fp") or 0)
        row["tickers"].append(m["ticker"])
    for st, row in out.items():
        row["volume"] = round(row["volume"])
        row["open_interest"] = round(row["open_interest"])
        row["url"] = f"https://kalshi.com/markets/{row['series'].lower()}"
    if dropped:
        print(f"[kalshi] · {kind}: 규칙은 2026이나 만기가 어긋나 제외 — {', '.join(sorted(dropped))}",
              file=sys.stderr)
    for st in states:
        if st not in out:
            print(f"[kalshi] · {kind} {st}: 2026 시장 없음", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # 상원 선거 대상 주는 등급 피드에서 가져온다(단일 정본)
    feed = os.path.join(ROOT, "data", "senate_ratings_feed.json")
    with open(feed, encoding="utf-8") as f:
        sen_states = sorted(json.load(f).get("state_names", {}))
    if not sen_states:
        print("[kalshi] 상원 대상 주 목록을 얻지 못함", file=sys.stderr)
        return 1
    gov_states = sorted(set(STATE_NAME) - NO_GOV)

    def chamber_control(series, url):
        ctl = {m.get("ticker"): m for m in api_markets(series)}
        d = ctl.get(f"{series}-2026-D")
        if not d:
            print(f"[kalshi] ! 다수 시장({series}-2026) 없음", file=sys.stderr)
            return None
        return {"dem": cents(d.get("last_price_dollars")),
                "rep": cents((ctl.get(f"{series}-2026-R") or {}).get("last_price_dollars")),
                "question": d.get("title"),
                "rules": d.get("rules_primary"),
                "volume": round(float(d.get("volume_fp") or 0)),
                "open_interest": round(float(d.get("open_interest_fp") or 0)),
                "url": url}

    control = chamber_control("CONTROLS", "https://kalshi.com/markets/controls/senate-winner")
    house_control = chamber_control("CONTROLH", "https://kalshi.com/markets/controlh")

    out = {
        "as_of": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "fetched_at_utc": datetime.datetime.now(datetime.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "market",
        "source_label": "Kalshi (예측시장 가격)",
        "source_url": "https://kalshi.com/",
        "note": ("가격(센트)은 확률의 근사일 뿐이며 확률 자체가 아니다 — 유동성·수수료·거래자 편향이 섞인다. "
                 "민주/공화 값은 서로 다른 계약의 마지막 체결가라 합이 100이 안 될 수 있으며, "
                 "정규화하지 않고 원값 그대로 싣는다. Cook·Sabato의 등급과 같은 잣대로 비교하지 말 것."),
        "senate_control": control,
        "house_control": house_control,
        "senate": collect("senate", sen_states),
        "governor": collect("governor", gov_states),
    }
    if house_control:
        print(f"[kalshi] 하원 다수: 민주 {house_control['dem']}% / 공화 {house_control.get('rep')}%")
    if control:
        print(f"[kalshi] 상원 다수: 민주 {control['dem']}% / 공화 {control.get('rep')}% "
              f"(거래액 {control['volume']:,} · 미결제 {control['open_interest']:,})")
    print(f"[kalshi] 상원 {len(out['senate'])}/{len(sen_states)}개 · "
          f"주지사 {len(out['governor'])}/{len(gov_states)}개 취득")
    if FAILED:
        print(f"[kalshi] ! 조회 실패 시리즈 {len(FAILED)}개: {', '.join(sorted(set(FAILED)))} "
              f"— 결측이 아니라 '못 받은 것'이므로 재실행 필요", file=sys.stderr)
    if args.dry_run:
        print("[kalshi] --dry-run: 파일 미변경.")
        return 0
    p = os.path.join(ROOT, "data", "kalshi_prices.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"[kalshi] wrote data/kalshi_prices.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
