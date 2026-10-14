#!/usr/bin/env python3.11
"""한국 기업 미국 공장 → 2026 연방하원 지역구 배정.

입력  data/korea/us_plants.csv        (수기 정리본 — 행마다 출처 URL, 좌표는 출처·주소 지오코딩으로만)
출력  data/korea/us_plants_districts.json  (공장 id → 지역구, 배정 방법)
      data/korea/plant_districts.geojson   (공장이 있는 지역구 경계만, 단순화)

지역구 경계(2026 본선 기준):
  - 재획정 9개 주(TX·CA·FL·OH·NC·TN·LA·AL·UT): 새 지도. 경로는 redistricting-2026 저장소의
    data/geo_sources.json 을 따른다.
  - 그 밖의 주: Census 119대 의회 경계(cb_2024_us_cd119_500k). 미주리는 2025 신지도가
    연방대법원 정지로 본선에 쓰이지 않으므로 119대 경계가 맞다.
경계 원본은 저장소 밖(GEO_DIR, 기본 ~/code/_geo_dl)에 있다. 배정 결과만 커밋한다.

좌표가 비어 있고 street_address 가 있으면 Census 지오코더(onelineaddress)로 채운다.
좌표를 끝내 못 얻은 행은 지역구를 null 로 둔다(추정 금지).
"""
import csv, datetime, json, math, os, re, sys, urllib.parse, urllib.request
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

REPO = Path(__file__).resolve().parent.parent
GEO_DIR = Path(os.environ.get("GEO_DIR", "~/code/_geo_dl")).expanduser()
SRC_JSON = Path(os.environ.get("REDIST_GEO_SOURCES",
                               "~/code/redistricting-2026/data/geo_sources.json")).expanduser()
IN_CSV = REPO / "data/korea/us_plants.csv"
OUT_JSON = REPO / "data/korea/us_plants_districts.json"
OUT_GEO = REPO / "data/korea/plant_districts.geojson"

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
        "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
        "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
        "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
        "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
        "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
        "54": "WV", "55": "WI", "56": "WY"}


def load_districts():
    cd = gpd.read_file(GEO_DIR / "cd119/cb_2024_us_cd119_500k.shp").to_crs(4326)
    cd["st"] = cd["STATEFP"].map(FIPS)
    cd = cd[cd["st"].notna()]
    num = cd["CD119FP"].astype(int)
    cd["cd"] = cd["st"] + "-" + num.where(num > 0, 1).astype(str)  # 00(at-large) → -1 (Cook 표기)
    cd["map"] = "119대 의회 경계(Census)"
    src = json.loads(SRC_JSON.read_text())
    new_states = set(src)
    parts = [cd[~cd["st"].isin(new_states)][["st", "cd", "map", "geometry"]]]
    for st, v in src.items():
        g = gpd.read_file(Path(v["path"]).expanduser()).to_crs(4326)
        g["st"] = st
        g["cd"] = [f"{st}-{_cd_num(x)}" for x in g[v["col"]]]
        g["map"] = "2026 신지도 — " + v["label"]
        parts.append(g[["st", "cd", "map", "geometry"]])
    return gpd.GeoDataFrame(pd_concat(parts), crs=4326)


def _cd_num(x):
    """경계 파일의 지역구 번호 표기(1, "01", 1.0, "CD-01", "00")를 Cook 표기 숫자로. at-large(0)=1."""
    m = re.search(r"\d+(?:\.0+)?$", str(x).strip())
    if not m:
        raise ValueError(f"지역구 번호를 읽을 수 없음: {x!r}")
    n = int(float(m.group()))
    return n if n > 0 else 1


def census_cd120(lat, lon):
    """Census 지오코더의 120대 의회 지역구(2026 선거 경계) — 배정 결과 교차검증용."""
    q = urllib.parse.urlencode({"x": lon, "y": lat, "benchmark": "Public_AR_Current",
                                "vintage": "Current_Current", "format": "json"})
    url = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates?" + q
    with urllib.request.urlopen(url, timeout=30) as r:
        geo = json.load(r)["result"]["geographies"]
    c = geo["120th Congressional Districts"][0]
    return _cd_num(re.sub(r"\D", "", c.get("BASENAME", "")) or 0)


def pd_concat(parts):
    import pandas as pd
    return pd.concat(parts, ignore_index=True)


def census_geocode(addr):
    q = urllib.parse.urlencode({"address": addr, "benchmark": "Public_AR_Current", "format": "json"})
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + q
    with urllib.request.urlopen(url, timeout=30) as r:
        m = json.load(r)["result"]["addressMatches"]
    if not m:
        return None
    c = m[0]["coordinates"]
    return float(c["y"]), float(c["x"]), m[0]["matchedAddress"]


def main():
    rows = list(csv.DictReader(IN_CSV.open(encoding="utf-8")))
    dist = load_districts()
    out, used = [], set()
    for r in rows:
        lat, lon, method = r.get("lat"), r.get("lon"), r.get("coord_method") or ""
        if (not lat or not lon) and r.get("street_address"):
            addr = f'{r["street_address"]}, {r["city"]}, {r["state"]}'
            try:
                g = census_geocode(addr)
            except Exception as e:  # 네트워크 실패는 배정 보류로 남긴다
                print("geocode 실패:", r["id"], e, file=sys.stderr)
                g = None
            if g:
                lat, lon, method = g[0], g[1], f"Census 지오코더({g[2]})"
        rec = {"id": r["id"], "lat": None, "lon": None, "coord_method": method or None,
               "district": None, "district_map": None}
        if lat and lon:
            lat, lon = float(lat), float(lon)
            rec["lat"], rec["lon"] = round(lat, 5), round(lon, 5)
            hit = dist[dist.contains(Point(lon, lat))]
            hit = hit[hit["st"] == r["state"]] if len(hit) > 1 else hit
            if len(hit) and (method or "").startswith("city_centroid"):
                # 부지 좌표가 없으면 도시 중심 반경 8km 안의 지역구를 모두 모아 확실성을 표시한다.
                kx = 111.0 * max(0.2, abs(math.cos(math.radians(lat))))
                ring = [Point(lon + dx / kx, lat + dy / 111.0)
                        for dx in (-8, -4, 0, 4, 8) for dy in (-8, -4, 0, 4, 8) if dx * dx + dy * dy <= 64]
                near = sorted({c for pt in ring for c in dist[dist.contains(pt)]["cd"] if c.startswith(r["state"] + "-")})
                rec["district_candidates"] = near
                rec["district_certain"] = len(near) == 1
            else:
                rec["district_certain"] = bool(len(hit))
            if len(hit):
                rec["district"] = hit.iloc[0]["cd"]
                rec["district_map"] = hit.iloc[0]["map"]
                used.add(rec["district"])
            if len(hit) and hit.iloc[0]["st"] != r["state"]:
                print("주 불일치:", r["id"], r["state"], hit.iloc[0]["cd"], file=sys.stderr)
            try:  # 같은 좌표를 Census 120대 지역구와 대조해 결과를 남긴다(실패는 null)
                rec["census_cd120"] = f'{r["state"]}-{census_cd120(lat, lon)}'
            except Exception as e:
                print("Census 대조 실패:", r["id"], e, file=sys.stderr)
                rec["census_cd120"] = None
            rec["census_match"] = None if rec["census_cd120"] is None else rec["census_cd120"] == rec["district"]
        out.append(rec)
    OUT_JSON.write_text(json.dumps({"generated_by": "scripts/build_korea_plants.py",
                                    "generated_at": datetime.date.today().isoformat(),
                                    "census_check": "Census geocoder geographies/coordinates · 120th Congressional Districts",
                                    "plants": out}, ensure_ascii=False, indent=1))
    g = dist[dist["cd"].isin(used)].copy()
    g["geometry"] = g.geometry.simplify(0.004, preserve_topology=True)
    g[["cd", "map", "geometry"]].to_file(OUT_GEO, driver="GeoJSON", COORDINATE_PRECISION=4)
    miss = [o["id"] for o in out if not o["district"]]
    bad = [(o["id"], o["district"], o["census_cd120"]) for o in out if o.get("census_match") is False]
    print(f"{len(out)}개 공장, 지역구 배정 {len(out) - len(miss)}개, 미배정 {miss}, Census 120대 불일치 {bad}")


if __name__ == "__main__":
    main()
