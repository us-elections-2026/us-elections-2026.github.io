# data/korea — Korea Watch 보조 자료 (2026-10-14 신설)

`korea/fact-sheet.qmd`(한미 조인트 팩트시트)·`korea/plants.qmd`(한국 기업 미국 공장과 2026 선거) 페이지가 읽는 자료다.

| 파일 | 내용 | 갱신 |
|---|---|---|
| `sources/joint_fact_sheet_2025-11-13_en.md` | 백악관 영문 원문 사본(2026-10-14 수집) | 고정 |
| `sources/joint_fact_sheet_2025-11-14_ko.md` | 대통령실 배포 국문본 — **뉴시스 전재본**(정부 사이트 원문 미대조) | 고정 |
| `sources/joint_fact_sheet_related_docs.md` | USTR 성명·전략투자 MOU 등 관련 문서 목록(열람 여부 표기) | 고정 |
| `joint_fact_sheet.json` | 원문 41개 문단을 경제·안보로 묶은 것. `ko`·`en`은 원문 그대로, `label`·`sector`·`theme`는 사이트 편집 분류 | 수기 |
| `top30_groups_2026.csv` | 공정위 2026 공시대상기업집단 1~30위(2026-04-29 발표, 별첨2 원표) | 연 1회 |
| `us_plants.csv` | 30대 그룹 미국 공장 61곳. 행마다 출처 URL·`verified`(fetched/partial)·검증 메모(`notes`) | 수기 |
| `us_plants_districts.json` | 공장 → 2026 본선 하원 지역구(생성물) | 스크립트 |
| `plant_districts.geojson` | 공장이 있는 지역구 경계(단순화, 생성물) | 스크립트 |

## 공장 목록 규칙
- 범위: 공정위 2026 자산순위 30위 안 그룹. 새로 짓거나 증설한 공장, 공장 단위 인수. 미국 회사 통째 인수(슈완스·Kraton·밥캣)는 인수 뒤 새 투자가 발표된 공장만.
- 상태: `operating`/`under_construction`/`announced`/`paused`/`closed`, 기준일은 `status_as_of`.
- 투자(`investment_usd_m`, 백만 달러)·고용은 연 페이지에 적힌 발표치만. 못 읽은 값은 비운다.
- 좌표: 주소 지오코딩(Census) > OpenStreetMap 시설 > 도시 중심(`coord_method=city_centroid`). 도시 중심 행은 반경 8km 후보 지역구를 `us_plants_districts.json`에 남긴다.

## 지역구 재생성
```bash
python3.11 scripts/build_korea_plants.py   # geopandas 필요, 경계 원본은 GEO_DIR(기본 ~/code/_geo_dl)
```
경계: 재획정 9개 주는 `~/code/redistricting-2026/data/geo_sources.json`의 신지도, 나머지는 Census 119대(cb_2024_us_cd119_500k).
2026-10-14 배정 결과 61곳 전부 Census 지오코더 `120th Congressional Districts` 레이어와 일치 확인.

선거 상황(Cook 하원·상원·주지사 등급, Kalshi)은 이 폴더에 저장하지 않는다 — 렌더 때 사이트 데이터에서 읽는다(`R/helpers.R` 2.10~2.11).
