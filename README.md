# 미국 중간선거 한국어 브리핑 (Quarto + GitHub Pages)

한국 독자를 위한 2026 미국 중간선거 주간 브리핑. **데이터 약 50% / 분석 약 50%**.
데이터 표는 `data/`의 정규화 파일에서 빌드 시점에 렌더링되고, 분석은 마크다운으로 작성합니다.

## 설계 한 줄

```
Mac mini (수집 + 정규화 → data/ 에 JSON/CSV 커밋)
  → git push
  → GitHub Actions (Quarto render + R 실행)
  → gh-pages 브랜치 → GitHub Pages 배포
```

요청 시점에 서버가 DB를 때리지 않습니다. 모든 표는 **빌드 때 미리 계산**되어 정적 HTML로 굳습니다.

## 디렉터리

```
.
├── _quarto.yml            # 사이트 설정 (execute-dir: project, freeze: false)
├── index.qmd              # 홈: 상원 전망 KPI + 환경 스냅샷 + 추이 차트 + 이슈 listing + 데이터 유의사항
├── dashboard.qmd          # ★ 자체 모델 대시보드 (Chart.js, model_dashboard.json 런타임 fetch)
├── house.qmd              # ★ 하원 경합구 트래커 (house_races.json)
├── national.qmd           # ★ 전국 환경 (지지율·제너릭·경제·외교)
├── korea-watch.qmd        # ★ Korea Watch (korea_watch.csv + 인물·법안 표)
├── methodology.qmd        # ★ 방법론 (수치 3종 구분·모델 개요·여론조사 리터러시)
├── scenarios.qmd          # ★ 상원 시나리오 (소수/50:50/다수, tipping-point, 한국 함의)
├── senate.qmd             # 상원 경합주 표
├── trackers.qmd           # 최신 데이터 표 모음
├── archive.qmd            # 주간 호 아카이브 listing
├── about.qmd              # 소개(evergreen)
├── issues/                # 주간 호 (데이터=함수 렌더링, 분석=프로즈). 홈·archive listing.
├── states/                # 경합 8주 State Focus (6섹션 표준 + gt_state_detail 카드)
│   └── {ga,mi,nh,me,nc,tx,oh,ak}.qmd
├── data/                  # ★ 정규화 데이터 — Mac mini가 여기에 커밋. 스키마는 data/README.md
│   ├── forecast.json  generic_ballot.json  approval.json  trends.json  national_econ.json
│   ├── senate_races.json  senate_primaries.json  candidates.json  fec_fundraising.json
│   ├── model_dashboard.json  house_races.json
│   ├── korea_watch.csv  polls_log.csv
│   ├── README.md          # 데이터 스키마 문서 (필드·nullable·부호 규약·소비처)
│   └── history/<YYYY-MM-DD>/   # 주간 스냅샷 (delta 추적)
├── assets/                # dashboard.{js,css}, trends.js, econ.js, candidates/ (후보 사진 PD·CC)
├── R/helpers.R            # 로딩·정규화·gt 표·카드 렌더링 헬퍼
├── scripts/
│   ├── validate_data.R    # ★ data/ 스키마·파싱 검증 (CI publish 전 실행)
│   ├── fetch_national_econ.py   # FRED → national_econ.json
│   ├── fetch_fec_fundraising.py # FEC → fec_fundraising.json (스테이징)
│   └── snapshot_and_publish.sh  # 주간 스냅샷 + launchd
├── theme/custom.scss      # 테마
└── .github/workflows/publish.yml   # 검증 → Quarto render → gh-pages 배포
```

## 로컬에서 보기

요구사항: [Quarto CLI](https://quarto.org), R, 그리고 R 패키지 `jsonlite dplyr gt readr`.

```bash
# R 패키지 (최초 1회)
Rscript -e 'install.packages(c("jsonlite","dplyr","gt","readr"))'

# 데이터 검증 (파싱·필수 필드·부호/범위 규약) — 커밋·렌더 전 권장
Rscript scripts/validate_data.R

# 미리보기 (자동 새로고침)
quarto preview

# 전체 빌드
quarto render
```

> `scripts/validate_data.R`는 CI(`publish.yml`)에서도 Quarto render 직전에 실행되어,
> 깨진 JSON/CSV·필수 필드 누락·부호 규약 위반이 공개 페이지로 나가기 전에 빌드를 멈춥니다.
> 데이터 파일별 필드·nullable·부호 규약은 **[`data/README.md`](data/README.md)** 참조.

## 배포 (GitHub Pages)

1. 레포를 GitHub에 push (`main` 브랜치).
2. `_quarto.yml`의 `site-url`과 navbar의 GitHub 링크에서 `USERNAME`을 본인 계정/레포명으로 수정.
3. 첫 push 시 Actions가 돌며 `gh-pages` 브랜치를 생성·배포.
4. 레포 **Settings → Pages → Source: Deploy from a branch → `gh-pages` / root** 로 설정.

## 데이터 갱신 (핵심)

`data/`의 파일만 바꿔 커밋하면 사이트가 다시 빌드되어 표가 갱신됩니다.
Mac mini의 launchd/cron 작업 끝에 다음을 붙이면 됩니다:

```bash
cd /path/to/midterm-kr
# (수집 스크립트가 data/*.json 을 갱신)
git add data/ && git commit -m "data: $(date +%F) 갱신" && git push
```

> **delta(주간 변화) 채우기**: 현재 시드 데이터의 `*_delta` 값은 `null`입니다.
> 변화 추적을 자동화하려면 매주 직전 스냅샷을 보관(예: `data/history/2026-06-07/`)하고,
> 수집 스크립트에서 이번 값 − 지난 값을 계산해 `*_delta`에 기록하세요.

## 정규화 스키마 메모 (편집 3원칙)

- **정규화**: 기관마다 다른 등급·표본을 한 기준으로(예: 마진은 항상 "양수=민주 우위").
- **delta**: 모든 표에 "지난 주 대비"를 둘 자리를 마련(현재 슬롯만 존재).
- **provenance**: `type`(market/model/rating/aggregate), `population`(A/RV/LV), 기준일(`*_as_of`)을 항상 보존.

## 면책

예측시장 가격은 확률의 근사일 뿐이며, 등급(Toss Up/Lean)은 확률이 아닙니다.
모든 수치는 표 상단 기준 시각의 스냅샷이며, 단일 조사보다 집계 평균·추세를 우선합니다.
`〔...〕` / `【...】` 슬롯은 발행 시 채워집니다.
