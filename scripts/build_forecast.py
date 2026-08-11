#!/usr/bin/env python3
"""예보 종합표 생성 — data/forecast.json 을 이미 취득된 원천에서 조립한다.

종전에는 수동 편집이라 6/7 상태로 두 달 넘게 낡아 있었다(다른 표는 자동 갱신되는데
이 표만 멈춰 있어 오히려 눈에 띄었다). 이제 아래 네 원천에서 매 발행 시 다시 만든다.

  data/kalshi_prices.json   senate_control / house_control  → 시장(market)
  data/ddhq_forecast.json   senate / house 다수당 확률        → 모델(model)
  data/rtwh_forecast.json   상원 다수당 확률(상원 전용)         → 모델(model)
  data/model_v0.json        자체 모델 v0 상원 확률(상원 전용)    → 모델(model)

원칙(사이트 편집 3원칙 준수):
- **수치를 만들지 않는다.** 원천 파일에 없는 값은 null로 두고 표에서 `—`로 렌더된다.
- **delta는 직전 forecast.json 대비**로 계산한다. 직전 값이 없으면 null(첫 관측).
- `house_dem`/`senate_dem`/`*_delta`는 **0~1 분수**로 저장한다(`gt_forecast()`가 ×100).
- 원천이 하나라도 없거나 깨져도 나머지로 표를 만든다(부분 갱신 허용).

사용:
    python3 scripts/build_forecast.py            # data/forecast.json 갱신
    python3 scripts/build_forecast.py --dry-run  # 결과만 출력(파일 미변경)
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "forecast.json")


def load(name):
    """data/<name> 을 읽는다. 없거나 깨졌으면 None(부분 갱신 허용)."""
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f"[forecast] ! {name} 읽기 실패({e}) — 해당 행 건너뜀", file=sys.stderr)
        return None


def pct(x):
    """퍼센트/센트 값을 0~1 분수로. None은 그대로 None."""
    return None if x is None else round(float(x) / 100.0, 4)


def build_rows():
    rows = []

    kal = load("kalshi_prices.json")
    if kal:
        sc = (kal.get("senate_control") or {}).get("dem")
        hc = (kal.get("house_control") or {}).get("dem")
        vol_s = (kal.get("senate_control") or {}).get("volume")
        vol_h = (kal.get("house_control") or {}).get("volume")
        rows.append({
            "source": "Kalshi (예측시장)", "type": "market",
            "house_dem": pct(hc), "senate_dem": pct(sc),
            "note": ("민주 승리 계약의 마지막 체결가 — 확률의 근사일 뿐 확률이 아니다"
                     + (f". 누적 거래액 상원 ${vol_s:,.0f}·하원 ${vol_h:,.0f}"
                        if vol_s and vol_h else "")),
        })

    ddhq = load("ddhq_forecast.json")
    if ddhq:
        s, h = ddhq.get("senate") or {}, ddhq.get("house") or {}
        rows.append({
            "source": "Decision Desk HQ", "type": "model",
            "house_dem": pct(h.get("dem_majority_prob")),
            "senate_dem": pct(s.get("dem_majority_prob")),
            "note": ("다수당 확률. 평균 의석은 상원 "
                     f"{s.get('dem_seats_mean', '—')}·하원 {h.get('dem_seats_mean', '—')}석 — "
                     "상원 50–50은 부통령 캐스팅보트로 공화 다수를 뜻한다"),
        })

    rtwh = load("rtwh_forecast.json")
    if rtwh and rtwh.get("chamber") == "senate":
        sp = (rtwh.get("seats_projected") or {}).get("dem")
        rows.append({
            "source": "Race to the WH", "type": "model",
            "house_dem": None,  # 상원 전용 피드 — 하원은 취득처 없음
            "senate_dem": pct(rtwh.get("dem_majority_prob")),
            "note": (f"상원 전용(하원 미취득). 예상 의석 민주 {sp}석. "
                     f"Infogram 라이브 시계열의 마지막 관측치({rtwh.get('last_point_label', '—')})"),
        })

    v0 = load("model_v0.json")
    if v0:
        seats = v0.get("seats") or {}
        rows.append({
            "source": "자체 모델 v0", "type": "model",
            "house_dem": None,  # 상원만 모델링한다
            "senate_dem": pct(v0.get("dem_majority_prob")),
            "note": (f"이 사이트의 재현 가능한 모델(고정 시드). 의석 중앙값 {seats.get('median', '—')}"
                     f"·90% 구간 {seats.get('p05', '—')}–{seats.get('p95', '—')}. "
                     "감시주만 시뮬레이션하므로 감시 목록을 바꾸면 확률도 바뀐다(방법론 참조)"),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    prev = load("forecast.json") or {}
    prev_by_src = {r.get("source"): r for r in prev.get("rows", [])}

    rows = build_rows()
    if not rows:
        print("[forecast] 원천을 하나도 읽지 못함 — 기존 파일 유지", file=sys.stderr)
        return 1

    # delta = 이번 값 − 직전 값 (직전이 없으면 null)
    for r in rows:
        old = prev_by_src.get(r["source"], {})
        for ch in ("house", "senate"):
            new_v, old_v = r.get(f"{ch}_dem"), old.get(f"{ch}_dem")
            r[f"{ch}_delta"] = (round(new_v - old_v, 4)
                                if new_v is not None and old_v is not None else None)
        # 열 순서를 README 문서와 맞춘다
        r_ordered = {k: r[k] for k in ("source", "type", "house_dem", "senate_dem",
                                       "house_delta", "senate_delta", "note")}
        r.clear(); r.update(r_ordered)

    as_of = max([d.get("as_of", "") for d in
                 (load("kalshi_prices.json"), load("ddhq_forecast.json"),
                  load("rtwh_forecast.json")) if d] or [""])
    out = {
        "as_of": as_of or prev.get("as_of"),
        "generated_by": "scripts/build_forecast.py",
        "provenance_note": (
            "이 표는 이미 취득된 원천 파일에서 자동 조립됩니다 — Kalshi 공개 API(시장가), "
            "Decision Desk HQ·Race to the WH(외부 모델), 자체 모델 v0. "
            "빈 칸은 해당 원천이 그 원(院)을 예측하지 않는다는 뜻이며 추정으로 채우지 않습니다. "
            "Δ는 직전 발행분 대비입니다. 등급(Cook·Sabato)은 확률이 아니라 이 표에 넣지 않습니다 — "
            "등급 비교는 상원·주지사 페이지의 기관별 표를 보세요."),
        "rows": rows,
    }
    if args.dry_run:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"[forecast] wrote data/forecast.json ({len(rows)} rows, as_of {out['as_of']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
