#!/usr/bin/env python3
"""상원 일일 브리핑 → data/senate_polls.csv 후보 추출·중복 제거·append.

두 입력 경로를 같은 정규화·중복 제거·append 로직으로 처리한다.

  (A) 매일 — 일일 브리핑 KR의 「새로운 여론조사」 고정 형식 표(프롬프트 v2.8부터)
      python3 scripts/extract_daily_polls.py --date 2026-09-18 [--apply]
  (B) 소급 — LLM 추출 JSON(스키마는 아래 FIELDS)들을 병합
      python3 scripts/extract_daily_polls.py --from-json out/chunk*.json [--apply]

공통 옵션
  --apply    'ready' 행을 data/senate_polls.csv 에 append (없으면 후보 파일만 씀)
  --verify   ready 행의 source_url 을 열어 dem/rep 수치가 본문에 있는지 자동 대조(느림)
  --candidates PATH  후보 전량(ready/pending/dup)을 CSV로 저장(기본 data/senate_polls_candidates.csv)

규약 (CLAUDE.md·STEP6-8 (8)단계와 동일)
  - 본선(general) D 대 R 지명자 대진만. 집계 평균·시장가·예비·가상대결·하위집단 조사는 넣지 않는다.
  - ready = 실사 시작·종료일 + 양측 % + 출처 URL 전부 있음. 하나라도 없으면 pending(후보 파일에만).
  - 같은 조사는 몇 번 언급됐든 한 행: (주, 조사기관 정규화, 종료일) 또는 (주, 종료일, D%, R%)가 같으면 동일.
  - 같은 주·같은 기관·종료일 ±3일 안에 다른 수치가 있으면 'near' 로 표시하고 append 하지 않는다(사람 판단).
  - margin = dem_pct − rep_pct (양수 = 민주 우위).
  - CSV 스키마 고정: state,pollster,sponsor,partisan,population,n,start_date,end_date,
    dem_candidate,rep_candidate,dem_pct,rep_pct,margin,note,source_url
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import io
import json
import os
import re
import sys
import zoneinfo
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSV = REPO / "data" / "senate_polls.csv"
def _resolve_default_src() -> Path:
    """원천 폴더 경로 결정 순서:
    1) NIS_SENATE_DAILY 환경변수
    2) 실제 Dropbox 경로(맥에서 직접 실행할 때)
    3) Cowork 샌드박스(device_bash)의 마운트 경로 — Dropbox 폴더가
       $HOME/mnt/<폴더명>/ 아래에 마운트되는 경우의 흔한 형태들을 시도
    """
    env = os.environ.get("NIS_SENATE_DAILY")
    if env:
        return Path(env).expanduser()
    primary = Path(
        "~/Library/CloudStorage/Dropbox/_NIS/2026_senate_election/2026_midterm_outlook/senate_daily"
    ).expanduser()
    if primary.is_dir():
        return primary
    for alt in (
        Path.home() / "mnt" / "2026_midterm_outlook" / "senate_daily",
        Path.home() / "mnt" / "_NIS" / "2026_senate_election" / "2026_midterm_outlook" / "senate_daily",
    ):
        if alt.is_dir():
            return alt
    return primary


DEFAULT_SRC = _resolve_default_src()
COLS = ["state", "pollster", "sponsor", "partisan", "population", "n", "start_date", "end_date",
        "dem_candidate", "rep_candidate", "dem_pct", "rep_pct", "margin", "note", "source_url"]
WATCH = ["GA", "MI", "NH", "ME", "NC", "TX", "OH", "AK", "IA"]
STATE_KR = {"조지아": "GA", "미시간": "MI", "뉴햄프셔": "NH", "메인": "ME", "노스캐롤라이나": "NC",
            "텍사스": "TX", "오하이오": "OH", "알래스카": "AK", "아이오와": "IA"}
NOMINEE = {  # 주별 지명자 성(姓) — 대진 검증용
    "GA": ("Ossoff", "Collins"), "MI": ("El-Sayed", "Rogers"), "NH": ("Pappas", "Sununu"),
    "ME": ("Jackson", "Collins"), "NC": ("Cooper", "Whatley"), "TX": ("Talarico", "Paxton"),
    "OH": ("Brown", "Husted"), "AK": ("Peltola", "Sullivan"), "IA": ("Turek", "Hinson"),
}
CAND_KR = {  # 한글 표기 → 영문 성
    "오소프": "Ossoff", "콜린스": "Collins", "엘사예드": "El-Sayed", "엘사이드": "El-Sayed", "로저스": "Rogers",
    "파파스": "Pappas", "수누누": "Sununu", "서누누": "Sununu", "잭슨": "Jackson", "쿠퍼": "Cooper",
    "왯틀리": "Whatley", "와틀리": "Whatley", "워틀리": "Whatley", "탈라리코": "Talarico", "탤라리코": "Talarico",
    "팩스턴": "Paxton", "브라운": "Brown", "허스테드": "Husted", "허스티드": "Husted", "펠톨라": "Peltola",
    "설리번": "Sullivan", "튜렉": "Turek", "투렉": "Turek", "힌슨": "Hinson",
}

# 조사기관 정규화 — 기존 CSV 표기(왼쪽 정본)에 일일의 변형을 맞춘다. 키는 소문자·기호 제거 후 비교.
POLLSTER_ALIAS = {
    "rasmussen": "Rasmussen Reports", "라스무센": "Rasmussen Reports",
    "emerson": "Emerson College/Nexstar", "에머슨": "Emerson College/Nexstar", "emerson college": "Emerson College/Nexstar",
    "emerson college nexstar": "Emerson College/Nexstar", "emerson nexstar": "Emerson College/Nexstar",
    "fox news": "Fox News/Beacon·Shaw", "fox news beacon shaw": "Fox News/Beacon·Shaw", "fox": "Fox News/Beacon·Shaw", "폭스": "Fox News/Beacon·Shaw",
    "insideradvantage": "InsiderAdvantage", "인사이더어드밴티지": "InsiderAdvantage",
    "trafalgar": "Trafalgar Group", "trafalgar group": "Trafalgar Group", "트라팔가": "Trafalgar Group",
    "cnn": "CNN/SSRS", "cnn ssrs": "CNN/SSRS",
    "unh": "UNH Survey Center", "unh survey center": "UNH Survey Center", "unh survey center granite state poll": "UNH Survey Center",
    "saint anselm": "Saint Anselm College Survey Center", "saint anselm college": "Saint Anselm College Survey Center", "세인트 안셀름": "Saint Anselm College Survey Center",
    "aarp": "AARP/Fabrizio Ward·Impact Research", "aarp fabrizio impact": "AARP/Fabrizio Ward·Impact Research",
    "aarp fabrizio ward impact research": "AARP/Fabrizio Ward·Impact Research", "aarp fabrizio ward impact": "AARP/Fabrizio Ward·Impact Research",
    "quantus": "Quantus Insights", "quantus insights": "Quantus Insights", "퀀터스": "Quantus Insights",
    "wick": "Wick Insights", "wick insights": "Wick Insights",
    "elon": "Elon University", "elon university": "Elon University", "일론대": "Elon University",
    "ecu": "East Carolina University", "east carolina": "East Carolina University", "east carolina university": "East Carolina University",
    "bgsu": "BGSU/YouGov", "bgsu yougov": "BGSU/YouGov", "bowling green": "BGSU/YouGov",
    "telemundo mason dixon": "Telemundo/Mason-Dixon", "mason dixon": "Telemundo/Mason-Dixon",
    "suffolk": "Suffolk University", "suffolk university": "Suffolk University",
    "glengariff": "Glengariff", "glengariff wdiv detroit news": "Glengariff",
    "epic mra": "EPIC-MRA", "epicmra": "EPIC-MRA",
    "susquehanna": "Susquehanna Polling & Research", "susquehanna polling research": "Susquehanna Polling & Research",
    "tipp": "TIPP/TechnoMetrica", "tipp technometrica": "TIPP/TechnoMetrica",
    "abacus": "Abacus Data", "abacus data": "Abacus Data",
    "alaska survey research": "Alaska Survey Research", "asr": "Alaska Survey Research",
    "data for progress": "Data for Progress", "dfp": "Data for Progress",
    "hart": "Hart Research", "hart research": "Hart Research", "hart smp": "Hart Research",
    "public policy polling": "Public Policy Polling", "ppp": "Public Policy Polling",
    "nyt siena": "NYT/Siena", "new york times siena": "NYT/Siena", "siena": "NYT/Siena",
    "yougov": "YouGov", "msu ippsr yougov": "MSU/IPPSR·YouGov",
    "catawba yougov": "Catawba College/YouGov", "catawba college yougov": "Catawba College/YouGov",
    "harper": "Harper Polling", "harper polling": "Harper Polling", "carolina journal harper": "Harper Polling",
    "wedgewood": "Wedgewood Polls", "wedgewood polls": "Wedgewood Polls",
    "change research": "Change Research", "high point": "High Point University", "high point university": "High Point University",
    "texas politics project": "UT Austin/Texas Politics Project", "ut texas politics project": "UT Austin/Texas Politics Project",
    "ut austin texas politics project": "UT Austin/Texas Politics Project",
    "tpor": "Texas Public Opinion Research", "texas public opinion research": "Texas Public Opinion Research",
    "univision yougov": "Univision/YouGov", "overton": "Overton Insights", "overton insights": "Overton Insights",
    "nyt siena college": "NYT/Siena", "new york times siena college": "NYT/Siena",
    "university of new hampshire survey center": "UNH Survey Center", "unh granite state poll": "UNH Survey Center",
    "ut austin": "UT Austin/Texas Politics Project", "university of texas texas politics project": "UT Austin/Texas Politics Project",
    "wedgwood polls": "Wedgewood Polls", "wedgwood": "Wedgewood Polls",
    "texas pulse": "Bush School/Recon MR Pulse", "texas a m university reconmr": "Bush School/Recon MR Pulse",
    "texas a m reconmr": "Bush School/Recon MR Pulse", "bush school reconmr": "Bush School/Recon MR Pulse",
    "carolina journal poll": "Carolina Journal", "texas southern university yougov": "Texas Southern Univ./Jordan Research Center",
    "epic mra": "EPIC-MRA", "saint anselm college survey center": "Saint Anselm College Survey Center",
    "peak insights": "NRSC/Peak Insights", "nrsc peak insights": "NRSC/Peak Insights",
    "gbao": "GBAO", "global strategy group": "Global Strategy Group", "gsg": "Global Strategy Group",
}
# 집계 사이트·백과 페이지는 조사 원문이 아니다 — 여기가 출처면 '출처 불확실'로 pending
AGGREGATOR_DOMAINS = ("realclearpolling.com", "realclearpolitics.com", "pollsmax.com", "wikipedia.org",
                      "270towin.com", "fiftyplusone", "racetothewh.com", "electionbettingodds.com")
# 지명 확정일 — 이보다 앞선 실사는 "지명 전 가상 대진"으로 표시(기존 CSV 관행: "본선 가상(8/4 예비 전)")
NOMINATED = {"GA": "2026-06-16", "MI": "2026-08-04", "NH": "2026-09-08", "ME": "2026-07-25", "AK": "2026-08-18", "IA": "2026-06-02"}
# 조사기관이 아닌 것(캠프 내부 플래시폴·기관 미상)은 출처 불확실로 제외
UNNAMED = ("internal", "내부", "campaign", "캠프", "미상", "불명", "미공개", "unknown")


def norm_key(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = s.replace("&", " ").replace("/", " ").replace("·", " ").replace("-", " ").replace("–", " ").replace("—", " ")
    s = re.sub(r"[^\w\s가-힣]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def canon_pollster(name: str) -> str:
    k = norm_key(name)
    if k in POLLSTER_ALIAS:
        return POLLSTER_ALIAS[k]
    # 접두 일치(예: "rasmussen reports" → "rasmussen")
    for a, v in POLLSTER_ALIAS.items():
        if k.startswith(a + " ") or k == a:
            return v
    return name.strip()


def canon_cand(name: str | None, state: str, side: str) -> str:
    if not name:
        return NOMINEE[state][0 if side == "D" else 1]
    n = name.strip()
    for kr, en in CAND_KR.items():
        if kr in n:
            return en
    return n


def num(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return x
    s = str(x).strip().replace(",", "").replace("%", "")
    if s in ("", "?", "—", "-", "null", "None"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return int(v) if v.is_integer() else v


def fmt_num(v):
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def parse_date(s):
    if not s:
        return None
    s = str(s).strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:
        dt.date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None
    return s


# ---- (A) 일일 브리핑의 고정 형식 표 ----------------------------------------
# 프롬프트 v2.8 표 헤더(순서 고정):
# | 주 | 조사기관 | 후원 | 성향 | 모집단 | n | 조사시작 | 조사종료 | D후보 | D% | R후보 | R% | 출처URL |
FIXED_HEADER = ["주", "조사기관", "후원", "성향", "모집단", "n", "조사시작", "조사종료", "D후보", "D%", "R후보", "R%", "출처URL"]


def parse_fixed_table(text: str, day: str) -> list[dict]:
    rows = []
    sec = None
    for line in text.splitlines():
        if line.startswith("## "):
            sec = line[3:].strip()
            continue
        if sec is None or "새로운 여론조사" not in sec:
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[:2] == FIXED_HEADER[:2] and "조사시작" in cells:
            hdr = cells
            continue
        if set(c.replace("-", "").replace(":", "") for c in cells) == {""}:
            continue
        if len(cells) < 13:
            continue
        c = dict(zip(FIXED_HEADER, cells[:13]))
        st = c["주"].strip()
        st = STATE_KR.get(st, st.upper())
        if st not in WATCH:
            continue
        url = c["출처URL"].strip()
        m = re.search(r"\((https?://[^)]+)\)", url) or re.search(r"(https?://\S+)", url)
        url = m.group(1) if m else ""
        rows.append({
            "state": st, "pollster": c["조사기관"], "sponsor": c["후원"] if c["후원"] not in ("?", "-", "—") else "",
            "partisan": c["성향"] if c["성향"] in ("D", "R") else "none",
            "population": c["모집단"] if c["모집단"] in ("LV", "RV", "A") else "",
            "n": num(c["n"]), "start_date": parse_date(c["조사시작"]), "end_date": parse_date(c["조사종료"]),
            "dem_candidate": c["D후보"], "rep_candidate": c["R후보"],
            "dem_pct": num(c["D%"]), "rep_pct": num(c["R%"]), "source_url": url,
            "first_seen": day, "mentions": [day], "moe": None, "notes": None,
        })
    return rows


# ---- (B) LLM 추출 JSON ------------------------------------------------------
def load_json_polls(paths: list[str]) -> list[dict]:
    out = []
    for p in paths:
        for f in sorted(glob.glob(p)):
            data = json.loads(Path(f).read_text(encoding="utf-8"))
            for o in data:
                if not isinstance(o, dict) or "_summary" in o:
                    continue
                o["_src"] = Path(f).name
                out.append(o)
    return out


# ---- 공통: 정규화 → 중복 제거 → 기존 CSV 대조 ------------------------------
def normalize(o: dict) -> dict | None:
    st = (o.get("state") or "").strip().upper()
    if st not in WATCH:
        return None
    r = {
        "state": st,
        "pollster": canon_pollster(o.get("pollster") or ""),
        "sponsor": (o.get("sponsor") or "").strip(),
        "partisan": o.get("partisan") if o.get("partisan") in ("D", "R") else "none",
        "population": o.get("population") if o.get("population") in ("LV", "RV", "A") else "",
        "n": num(o.get("n")),
        "start_date": parse_date(o.get("start_date")),
        "end_date": parse_date(o.get("end_date")),
        "dem_candidate": canon_cand(o.get("dem_candidate"), st, "D"),
        "rep_candidate": canon_cand(o.get("rep_candidate"), st, "R"),
        "dem_pct": num(o.get("dem_pct")),
        "rep_pct": num(o.get("rep_pct")),
        "source_url": (o.get("source_url") or "").strip(),
        "moe": num(o.get("moe")),
        "release_date": parse_date(o.get("release_date")),
        "first_seen": o.get("first_seen") or "",
        "mentions": sorted(set(o.get("mentions") or ([o.get("first_seen")] if o.get("first_seen") else []))),
        "notes": (o.get("notes") or "").strip(),
        "confidence": o.get("confidence") or "",
    }
    # 대진 검증 — 지명자 성이 아니면 제외(가상대결·경선 혼입 방지)
    if r["dem_candidate"] != NOMINEE[st][0] or r["rep_candidate"] != NOMINEE[st][1]:
        r["_reject"] = f"대진 불일치 {r['dem_candidate']}–{r['rep_candidate']}"
    if not r["pollster"]:
        r["_reject"] = "조사기관 없음"
    elif any(u in r["pollster"].lower() for u in UNNAMED):
        r["_reject"] = f"조사기관 미상/내부조사({r['pollster'][:30]})"
    if r["end_date"] and st in NOMINATED and r["end_date"] < NOMINATED[st]:
        tag = f"지명 전 가상 대진({NOMINATED[st][5:].replace('-', '/')} 확정 전)"
        r["notes"] = (tag + (" · " + r["notes"] if r["notes"] else ""))
    return r


def key_a(r):  # 같은 조사 판정 1
    return (r["state"], norm_key(r["pollster"]), r["end_date"])


def key_b(r):  # 같은 조사 판정 2
    return (r["state"], r["end_date"], r["dem_pct"], r["rep_pct"])


def key_c(r):  # 같은 조사 판정 3 — 기관·수치가 같으면 날짜 표기(발표일/실사일)가 달라도 같은 조사로 본다
    return (r["state"], norm_key(r["pollster"]), r["dem_pct"], r["rep_pct"])


def dedup(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        hit = None
        for o in out:
            if r["state"] != o["state"]:
                continue
            if r["end_date"] and o["end_date"]:
                if key_a(r) == key_a(o) or key_b(r) == key_b(o) or (
                        r["dem_pct"] is not None and key_c(r) == key_c(o)):
                    hit = o
                    break
            else:
                # 종료일이 한쪽이라도 없으면 기관+수치 일치로만 같은 조사로 본다
                if norm_key(r["pollster"]) == norm_key(o["pollster"]) and r["dem_pct"] == o["dem_pct"] and r["rep_pct"] == o["rep_pct"]:
                    hit = o
                    break
        if hit is None:
            out.append(r)
            continue
        # 병합: 비어 있는 필드는 채우고, 언급일은 합친다
        for k in ("sponsor", "population", "n", "start_date", "end_date", "source_url", "moe", "release_date", "dem_pct", "rep_pct"):
            if (hit.get(k) in (None, "")) and r.get(k) not in (None, ""):
                hit[k] = r[k]
        hit["mentions"] = sorted(set(hit["mentions"]) | set(r["mentions"]))
        if r["notes"] and r["notes"] not in hit["notes"]:
            hit["notes"] = (hit["notes"] + " · " + r["notes"]).strip(" ·")
    return out


def load_csv() -> list[dict]:
    with open(CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def classify(rows: list[dict], existing: list[dict]) -> None:
    # 기존 행의 기관명도 같은 별칭표로 정규화해 비교한다(예: "Catawba/YouGov" ↔ "Catawba College/YouGov")
    ek = lambda e: norm_key(canon_pollster(e["pollster"]))
    ex_a = {(e["state"], ek(e), e["end_date"]) for e in existing}
    ex_b = {(e["state"], e["end_date"], num(e["dem_pct"]), num(e["rep_pct"])) for e in existing}
    ex_c = {(e["state"], ek(e), num(e["dem_pct"]), num(e["rep_pct"])) for e in existing}
    ex_near = [(e["state"], ek(e), e["end_date"]) for e in existing if e["end_date"]]
    for r in rows:
        if r.get("_reject"):
            r["status"] = "reject"; r["why"] = r["_reject"]; continue
        if r["end_date"] and (key_a(r) in ex_a or key_b(r) in ex_b):
            r["status"] = "dup"; r["why"] = "기존 CSV에 있음"; continue
        if r["dem_pct"] is not None and key_c(r) in ex_c:
            r["status"] = "dup"; r["why"] = "기존 CSV에 있음(기관·수치 일치, 날짜 표기만 다름)"; continue
        missing = [k for k in ("start_date", "end_date", "dem_pct", "rep_pct", "source_url") if r.get(k) in (None, "")]
        if missing:
            r["status"] = "pending"; r["why"] = "누락: " + ",".join(missing); continue
        if any(d in r["source_url"].lower() for d in AGGREGATOR_DOMAINS):
            r["status"] = "pending"; r["why"] = "출처가 집계 사이트 — 조사 원문/보도 URL 필요"; continue
        # 같은 주·기관·종료일 ±3일에 다른 조사가 있으면 사람 판단
        d = dt.date.fromisoformat(r["end_date"])
        near = [e for e in ex_near if e[0] == r["state"] and e[1] == norm_key(r["pollster"])
                and abs((dt.date.fromisoformat(e[2]) - d).days) <= 3]
        if near:
            r["status"] = "near"; r["why"] = f"기존 행과 종료일 근접({near[0][2]}) — 같은 조사인지 확인"; continue
        r["status"] = "ready"; r["why"] = ""


def verify_url(r: dict, timeout=12) -> str:
    """원문 페이지에 D%·R% 문자열이 모두 있으면 '일치', 접속 불가면 '차단/오류', 없으면 '미확인'."""
    import urllib.request
    try:
        req = urllib.request.Request(r["source_url"], headers={"User-Agent": "Mozilla/5.0 (Macintosh) us-elections-2026 poll-check"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(1_500_000).decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        return f"차단/오류({type(e).__name__})"
    text = re.sub(r"<[^>]+>", " ", body)
    d, rp = fmt_num(r["dem_pct"]), fmt_num(r["rep_pct"])
    ok = re.search(rf"(?<!\d){re.escape(d)}(\.0)?\s*%?", text) and re.search(rf"(?<!\d){re.escape(rp)}(\.0)?\s*%?", text)
    return "일치" if ok else "미확인"


def to_csv_row(r: dict, verify: str | None) -> dict:
    note_bits = []
    if r.get("moe") is not None:
        note_bits.append(f"±{fmt_num(r['moe'])}")
    src_days = r.get("mentions") or []
    note_bits.append(f"일일 브리핑 {src_days[0][5:].replace('-', '/') if src_days else '?'} 추출" + (f"(언급 {len(src_days)}회)" if len(src_days) > 1 else ""))
    if verify:
        note_bits.append(f"원문 대조 {verify}")
    if r.get("notes"):
        note_bits.append(r["notes"])
    margin = None
    if r["dem_pct"] is not None and r["rep_pct"] is not None:
        margin = round(float(r["dem_pct"]) - float(r["rep_pct"]), 1)
    return {
        "state": r["state"], "pollster": r["pollster"], "sponsor": r["sponsor"], "partisan": r["partisan"],
        "population": r["population"], "n": fmt_num(r["n"]), "start_date": r["start_date"] or "", "end_date": r["end_date"] or "",
        "dem_candidate": r["dem_candidate"], "rep_candidate": r["rep_candidate"],
        "dem_pct": fmt_num(r["dem_pct"]), "rep_pct": fmt_num(r["rep_pct"]), "margin": fmt_num(margin),
        "note": "·".join(note_bits), "source_url": r["source_url"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--from-json", nargs="*")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--candidates", default=str(REPO / "data" / "senate_polls_candidates.csv"))
    a = ap.parse_args()

    if a.from_json:
        raw = load_json_polls(a.from_json)
    else:
        date = a.date or dt.datetime.now(zoneinfo.ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
        p = Path(a.src).expanduser() / f"{date}_일일브리핑_KR.md"
        if not p.exists():
            print(f"[polls] {date} 일일 브리핑 없음", file=sys.stderr)
            return 2
        raw = parse_fixed_table(p.read_text(encoding="utf-8"), date)
        if not raw:
            print(f"[polls] {date}: 고정 형식 조사 표 없음(프롬프트 v2.8 이전 형식이거나 신규 조사 0건) — 추가 없음")
            return 0

    rows = [x for x in (normalize(o) for o in raw) if x]
    rows = dedup(rows)
    existing = load_csv()
    classify(rows, existing)

    ready = [r for r in rows if r["status"] == "ready"]
    if a.verify:
        for r in ready:
            r["verify"] = verify_url(r)
            if r["verify"] == "미확인":
                r["status"] = "pending"; r["why"] = "원문 페이지를 열었으나 D%·R% 수치가 본문에 없음"
        ready = [r for r in rows if r["status"] == "ready"]
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"[polls] 후보 {len(rows)}건 → " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if a.verify and ready:
        vc = {}
        for r in ready:
            vc[r["verify"]] = vc.get(r["verify"], 0) + 1
        print("[polls] 원문 대조: " + " · ".join(f"{k} {v}" for k, v in sorted(vc.items())))

    # 후보 전량 저장(검토용)
    Path(a.candidates).parent.mkdir(parents=True, exist_ok=True)
    with open(a.candidates, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["status", "why", "verify"] + COLS + ["mentions", "confidence"])
        for r in sorted(rows, key=lambda r: (r["state"], r["end_date"] or "", r["pollster"])):
            c = to_csv_row(r, r.get("verify"))
            w.writerow([r["status"], r["why"], r.get("verify", "")] + [c[k] for k in COLS] + [";".join(r["mentions"]), r.get("confidence", "")])
    print(f"[polls] 후보 파일 → {a.candidates}")

    if not a.apply:
        return 0
    if not ready:
        print("[polls] append 할 ready 행 없음")
        return 0
    with open(CSV, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        for r in sorted(ready, key=lambda r: (r["state"], r["end_date"])):
            w.writerow(to_csv_row(r, r.get("verify")))
    print(f"[polls] ✓ senate_polls.csv 에 {len(ready)}행 append")
    return 0


if __name__ == "__main__":
    sys.exit(main())
