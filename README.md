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
├── _quarto.yml            # 사이트 설정 (execute-dir: project 로 작업경로=루트 고정)
├── index.qmd              # 홈: 환경 스냅샷 + 이슈 목록(listing)
├── trackers.qmd           # 트래커: 최신 데이터 표 모음
├── about.qmd              # 소개(evergreen) 해설
├── issues/
│   └── 2026-06-07.qmd     # 주간 호 (데이터=함수 렌더링, 분석=프로즈)
├── data/                  # ★ 정규화 데이터 — Mac mini가 여기에 커밋
│   ├── forecast.json
│   ├── generic_ballot.json
│   ├── approval.json
│   ├── senate_races.json
│   └── polls_log.csv
├── R/helpers.R            # 로딩·정규화·gt 표 렌더링 헬퍼
├── theme/custom.scss      # 테마
└── .github/workflows/publish.yml
```

## 로컬에서 보기

요구사항: [Quarto CLI](https://quarto.org), R, 그리고 R 패키지 `jsonlite dplyr gt readr`.

```bash
# R 패키지 (최초 1회)
Rscript -e 'install.packages(c("jsonlite","dplyr","gt","readr"))'

# 미리보기 (자동 새로고침)
quarto preview

# 전체 빌드
quarto render
```

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
