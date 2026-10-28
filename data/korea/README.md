# data/korea — Korea Watch 보조 자료 (2026-10-14 신설)

`korea/fact-sheet.qmd`(한미 조인트 팩트시트)·`korea/plants.qmd`(한국 기업 미국 공장과 2026 선거) 페이지가 읽는 자료다.

| 파일 | 내용 | 갱신 |
|---|---|---|
| `sources/joint_fact_sheet_2025-11-13_en.md` | 백악관 영문 원문 사본(2026-10-14 수집) | 고정 |
| `sources/joint_fact_sheet_2025-11-14_ko.md` | 대통령실 배포 국문본 — **뉴시스 전재본**(정부 사이트 원문 미대조) | 고정 |
| `sources/joint_fact_sheet_related_docs.md` | USTR 성명·전략투자 MOU 등 관련 문서 목록(열람 여부 표기) | 고정 |
| `joint_fact_sheet.json` | 원문 41개 문단을 경제·안보로 묶은 것. `ko`·`en`은 원문 그대로, `label`·`sector`·`theme`는 사이트 편집 분류 | 수기 |
| `top100_groups_2026.csv` | 공정위 2026 공시대상기업집단 1~100위(2026-04-29 발표, 별첨2 원표에서 직접 추출) | 연 1회 |
| `us_plants.csv` | 100대 그룹 미국 공장 73곳. 행마다 출처 URL·`verified`(fetched/partial)·검증 메모(`notes`)·최근 보도(`latest_news`·`latest_news_url`) | 수기·주간 점검 PR |
| `plant_news.csv` | 공장별 보도 경과(plant_id·date·event·summary_kr·outlet·url·fetched). date는 YYYY / YYYY-MM / YYYY-MM-DD — 일자를 모르면 줄여 쓴다 | 수기·주간 점검 PR |
| `pending_checks.csv` | 검색 요약에만 근거한 변경 후보·미검증 신규 후보. 반영하지 않고 다음 점검에서 확인 | 주간 점검 |
| `sources/aggregate_lists_2026-10-26.md` | 언론·연구기관 공개 목록 11건과의 대조 기록 | 고정 |
| `us_plants_districts.json` | 공장 → 2026 본선 하원 지역구(생성물) | 스크립트 |
| `plant_districts.geojson` | 공장이 있는 지역구 경계(단순화, 생성물) | 스크립트 |

## 공장 목록 규칙
- 범위: 공정위 2026 자산순위 100위 안 그룹(2026-10-26 30위에서 확대). 외국 회사 지배 그룹사(한국지엠)·미국령(사모아)은 제외. 새로 짓거나 증설한 공장, 공장 단위 인수. 미국 회사 통째 인수(슈완스·Kraton·밥캣)는 인수 뒤 새 투자가 발표된 공장만.
- 상태: `operating`/`under_construction`/`announced`/`paused`/`closed`, 기준일은 `status_as_of`.
- 투자(`investment_usd_m`, 백만 달러)·고용은 연 페이지에 적힌 발표치만. 못 읽은 값은 비운다.
- 좌표: 주소 지오코딩(Census) > OpenStreetMap 시설 > 도시 중심(`coord_method=city_centroid`). 도시 중심 행은 반경 8km 후보 지역구를 `us_plants_districts.json`에 남긴다.

## 지역구 재생성
```bash
python3.11 scripts/build_korea_plants.py   # geopandas 필요, 경계 원본은 GEO_DIR(기본 ~/code/_geo_dl)
```
경계: 재획정 9개 주는 `~/code/redistricting-2026/data/geo_sources.json`의 신지도, 나머지는 Census 119대(cb_2024_us_cd119_500k).
배정 결과는 생성물의 `census_match`에 기록된다(2026-10-26: 73곳 전부 일치).

선거 상황(Cook 하원·상원·주지사 등급, Kalshi)은 이 폴더에 저장하지 않는다 — 렌더 때 사이트 데이터에서 읽는다(`R/helpers.R` 2.10~2.11).
