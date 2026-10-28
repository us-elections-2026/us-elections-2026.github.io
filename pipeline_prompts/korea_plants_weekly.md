# 한국 기업 미국 공장 — 주간 언론 점검 지시서 v1.0 (2026-10-26)

클라우드 루틴이 매주 월요일 09:00 KST에 이 파일을 따른다. 결과는 **브랜치 + PR**로만 낸다. main에 직접 커밋하지 않는다.

## 0. 준비
- 오늘 날짜(KST)를 `RUN=YYYY-MM-DD`로 정한다. `git checkout -b korea-weekly/$RUN origin/main`.
- 읽을 파일: `data/korea/README.md`(규칙), `data/korea/us_plants.csv`(공장 정본), `data/korea/plant_news.csv`(보도 경과), `data/korea/pending_checks.csv`(확인 필요), `data/korea/top100_groups_2026.csv`(범위).
- 직전 점검일 = `data/korea/weekly/`의 가장 최근 파일 날짜(없으면 2026-10-26). 그 다음 날부터 오늘까지가 이번 구간이다.

## 1. 기존 공장 보도 점검 (전 공장)
공장마다 이번 구간의 보도를 찾는다(회사명·시설명·도시 영문, 한국어 그룹명 둘 다). 지역 언론·한국 언론·업계지·회사 보도자료·주정부 경제개발청.
- 기사를 **직접 열어**(WebFetch 또는 `curl -sL -A "Mozilla/5.0"`) 확인한 것만 반영한다. 검색 결과 요약만 본 것은 반영하지 않고 3절로 보낸다.
- 새 사건 → `plant_news.csv`에 행 추가: `plant_id,date,event,summary_kr,outlet,url,fetched`. date는 사건 날짜 YYYY-MM-DD(일자를 모르면 YYYY-MM, 연도만 알면 YYYY — **1일로 채우지 않는다**). event: announce / groundbreaking / construction / start / expansion / pause / closure / sale / incident / policy / other. summary_kr은 한국어 한 문장 80자 이내. fetched=Y.
- 같은 사건이 이미 있으면 추가하지 않는다(날짜·요약으로 판단).
- `us_plants.csv`에서 바꿔도 되는 열: `status`, `status_as_of`, `company`(소유 변경), `start`, `latest_news`, `latest_news_url`, `notes`(끝에 `[보도 YYYY-MM-DD] …`로 덧붙이기만). status는 operating / under_construction / announced / paused / closed.
- **바꾸지 않는 열**: `id`, `lat`, `lon`, `coord_method`, `state`, `city`, `county`, `group`, `group_rank`, `investment_usd_m`, `jobs`(발표치 정의 — 새 발표치는 notes에 적고 사람 판단), `source_url`, `verified`.
- `latest_news`는 이번에 연 가장 최근 기사 날짜, `latest_news_url`은 그 기사.

## 2. 새 공장 후보 (100대 그룹)
- `top100_groups_2026.csv` 그룹의 **미국 제조 공장 신규 발표·착공·인수**를 찾는다(포함 규칙은 README 「공장 목록 규칙」).
- 새 공장은 `us_plants.csv`에 **넣지 않는다**(지역구 배정은 로컬 스크립트만 할 수 있다). 대신 `data/korea/candidates/$RUN.csv`에 `us_plants.csv`와 같은 열로 한 행씩 쓴다. id는 `c$RUN-01`처럼. 좌표는 출처 주소를 Census 지오코더로(`https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address=…&benchmark=Public_AR_Current&format=json`), 없으면 비운다. Nominatim은 쓰지 않는다.
- 같은 공장의 보도는 `plant_news.csv`가 아니라 후보 파일의 notes에 날짜·링크로 적는다.

## 3. 확인 필요 목록
- `pending_checks.csv`의 각 행을 다시 확인한다. 기사를 열어 확인되면 1절 규칙대로 반영하고 그 행을 지운다. 여전히 확인 못 하면 남긴다.
- 이번 구간에 검색 요약으로만 본 변경 후보는 이 파일에 행을 더한다(`plant_id,field,proposed,as_of,evidence_url,note`).

## 4. 점검 보고서
`data/korea/weekly/$RUN.md`를 쓴다. 이 파일이 PR 본문이 된다.
```
# 한국 기업 미국 공장 주간 점검 — $RUN (구간 <시작>~$RUN)
## 반영한 변경 (기사 확인)
- p15 SK온 테네시: status under_construction → operating (2026-11-0X, 매체, URL)
## 새 보도 N건 (공장별 한 줄)
## 새 공장 후보 (candidates/$RUN.csv) — 지역구 배정 필요
## 확인 필요로 넘긴 것
## 보도를 못 찾은 공장 / 열지 못한 사이트(403 등)
## 통계: 점검 공장 수, 열어 본 기사 수, 검색 횟수
```
변경이 하나도 없으면 "변경 없음"이라고 쓰고, 그래도 보고서는 커밋한다(점검했다는 기록).

## 5. 검사와 push
- `python3 scripts/check_korea_weekly.py` — 실패하면 고치고 다시 돌린다. 실패를 남긴 채 push하지 않는다.
- `git add data/korea && git commit -m "주간 점검: 한국 기업 미국 공장 ($RUN)" && git push -u origin korea-weekly/$RUN`
- PR은 Actions(`korea-weekly-pr.yml`)가 연다. 루틴은 PR을 열거나 병합하지 않는다.

## 금지
- 숫자를 추정해 채우지 않는다. 열어 본 페이지에 없는 값은 비운다.
- 기존 보도 행·공장 행을 지우지 않는다(정정은 notes에 덧붙이고 사람이 판단).
- `R/`, `*.qmd`, `scripts/`, `_quarto.yml`, 다른 `data/` 파일을 고치지 않는다.
