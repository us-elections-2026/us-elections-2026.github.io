# CLAUDE.md

이 파일은 Claude Code가 이 레포에서 작업할 때 따르는 프로젝트 지침이다.

## 프로젝트

한국 독자를 위한 **2026 미국 중간선거 주간 브리핑** 사이트. Quarto + GitHub Pages.
독자층은 **약간의 전문성을 갖춘 층**(NYT·538·Silver Bulletin을 직접 볼 수 있는 사람들).
따라서 속보 중계가 아니라 **해석·여론조사 리터러시·한국 정책 함의**로 차별화한다.
구성은 **데이터 약 50% / 분석 약 50%**.

## 아키텍처 (한 줄)

```
Mac mini (수집 + 정규화 → data/ 에 JSON/CSV 커밋) → git push
  → GitHub Actions (Quarto render + R 실행) → gh-pages → Pages
```

요청 시점에 서버가 DB를 때리지 않는다. 모든 표는 **빌드 시점에 미리 계산**되어 정적 HTML로 굳는다.
데이터 표는 `data/`의 정규화 파일에서 렌더링되고, 분석은 마크다운(`.qmd` 프로즈)으로 쓴다.

## 디렉터리

- `_quarto.yml` — 사이트 설정. `execute-dir: project`(작업경로=루트 고정), `freeze: false`(데이터 변경 시 매 빌드 재계산).
- `R/helpers.R` — `data/` 로딩·정규화·`gt` 표 렌더링 헬퍼. `gt_forecast()` `gt_generic()` `gt_generic_spread()` `gt_approval()` `gt_senate()` `gt_senate_primaries()` `gt_state_detail()` `gt_polls_log()` `gt_model_states()` `gt_model_scenarios()` `model_kpi()` `gt_house_races()` `gt_korea_watch()`.
- `index.qmd` — 홈(상원 전망 요약 KPI + 환경 스냅샷 + 이슈 listing). `trackers.qmd` — 최신 표 모음. `senate.qmd` — 경합주 표. `dashboard.qmd` — ★ 자체 모델 대시보드. `about.qmd` — evergreen 소개.
- `dashboard.qmd` + `assets/dashboard.{js,css}` — 인터랙티브 대시보드(Chart.js). `data/model_dashboard.json`을 런타임 `fetch`로 읽어 KPI·확률차트·시나리오·주별카드·타임라인 렌더. JS 비활성 환경 대비 `gt_model_states()`/`gt_model_scenarios()` 정적 표도 함께 렌더. **데이터 갱신 = `data/model_dashboard.json` 한 파일만 편집 → push → 자동 재빌드.** `fetch` 대상이라 `_quarto.yml`의 `project.resources`에 등록돼 있어야 `_site/`로 복사됨.
- `states/{ga,mi,nh,me,nc,tx,oh,ak}.qmd` — 경합주 8곳 State Focus 페이지(`gt_state_detail()` 카드 + 프로즈). 민주 수성 3(GA·MI·NH) + 공화 표적 5(ME·NC·TX·OH·AK). 주 추가/제외는 사람이 결정한다.
- `issues/YYYY-MM-DD.qmd` — 주간 호. 데이터(PART 1)는 함수 렌더링, 분석(PART 2)은 프로즈. 사이드바에는 `archive.qmd`(listing 페이지)만 노출 — 개별 호 자동 등재(auto)는 사이드바 비대화 문제로 제거(2026-06-11). 홈 listing은 유지.
- `house.qmd` — ★ 하원 경합구 트래커(`gt_house_races()`, `data/house_races.json`). Cook 토스업 상시 + Lean 주간 관리의 2단 구조.
- `national.qmd` — ★ 전국 환경(지지율·제너릭 밸럿·경제·외교). `scenarios.qmd` — ★ 상원 시나리오(소수/50:50/다수, tipping-point, 한국 함의). `methodology.qmd` — ★ 방법론(수치 3종 구분·모델 개요·여론조사 리터러시). `korea-watch.qmd` — ★ Korea Watch(`gt_korea_watch()`, `data/korea_watch.csv`).
- `data/` — ★ 정규화 데이터. Mac mini가 여기에 커밋한다. `forecast.json` `generic_ballot.json` `approval.json` `senate_races.json` `senate_primaries.json` `model_dashboard.json` `polls_log.csv` `house_races.json` `korea_watch.csv`(스키마 고정: date,type,actor,affiliation,state_or_district,event,detail,race_link,significance,source_url). `data/history/<YYYY-MM-DD>/` — 주간 스냅샷(delta 추적).
- `scripts/snapshot_and_publish.sh` + `com.us-elections.snapshot.plist` — 주 1회 `data/*` 스냅샷을 `history/`에 남기고 변경 시 commit+push(launchd). 데이터 수치 갱신 자체는 수동 편집이 주도.
- `scripts/fetch_national_econ.py` — FRED API(`FRED_API_KEY` env — 키는 `~/.claude/settings.json`의 `env`에 저장됨, 2026-06-11 유효성 확인. **키를 레포에 커밋 금지**) → `data/national_econ.json`(CPI YoY·실업률·미시간 심리). `gt_national_econ()`이 렌더, 파일 없으면 안내문 렌더(빌드 안전). `scripts/fetch_fec_fundraising.py` — FEC API(`FEC_API_KEY` env — 키는 `~/.claude/settings.json`의 `env`에 저장됨, 2026-06-11 유효성 확인. **키를 레포에 커밋 금지**) → `data/fec_fundraising.json` 스테이징(단위 $M). senate_races.json 반영은 수동 병합(편집 통제).
- `theme/custom.scss` — 테마. `.github/workflows/publish.yml` — 배포(R 패키지 + apt 빌드 의존성).

## 명령

```bash
quarto preview        # 로컬 미리보기(자동 새로고침)
quarto render         # 전체 빌드
Rscript -e 'install.packages(c("jsonlite","dplyr","gt","readr"))'   # 최초 1회
```

배포: `main`에 push → Actions가 `gh-pages` 생성·배포. (Pages Source=`gh-pages`는 GitHub 웹 UI에서 1회 수동 설정.)

## 편집 3원칙 (불변)

1. **정규화(comparability)** — 기관마다 다른 등급·표본을 한 기준으로. 마진은 항상 "양수=민주 우위"(`D+` / `R+`).
2. **변화추적(delta)** — 모든 표에 "지난 주 대비" 자리를 둔다. 자동화하려면 직전 스냅샷을 `data/history/YYYY-MM-DD/`에 보관하고 (이번 값 − 지난 값)을 `*_delta`에 기록.
3. **출처라벨(provenance)** — `type`(market/model/rating/aggregate), `population`(A/RV/LV), 기준일(`*_as_of`)을 항상 보존.

## 금지·주의 (중요)

- **추정치로 빈 칸을 채우지 말 것.** 모르는 값은 `null`로 두고 표에서는 `—` 또는 `【수집】` 슬롯으로 렌더링한다. 전문 독자에게 staleness·오류가 가장 큰 평판 리스크다.
- **예측시장 가격은 확률의 근사일 뿐**이며 확률 자체가 아니다(유동성·편향 섞임).
- **등급(Toss Up/Lean)은 확률이 아니다.** 모델·시장과 같은 잣대로 비교하지 말 것(표에서 `종류` 열로 구분).
- 모든 데이터 표에 **기준 시각 스탬프**를 노출한다. 단일 조사보다 **집계 평균·추세**를 우선한다.
- 새 데이터 칼럼을 추가·변경할 땐 **스키마 일관성**을 유지해 시계열 비교가 깨지지 않게 한다(열 정의를 함부로 바꾸지 말 것).
- 작업은 항상 **로컬 `quarto render`로 검증한 뒤** 커밋한다.

## 작성 톤

한국어. 미국 정치 배경지식을 전제하지 않되, 전문 독자를 지루하게 만들지 않는 깊이. 영문 고유명사는 그대로(예: Ossoff, Cook Political). 과장·단정 회피, 불확실성은 정직하게 표시.

## 현재 미완 (TODO)

### 긴급 (날짜 임박)
- ~~`actions/checkout@v4` Node 24 대응~~ — ✅ 완료(2026-06-11): checkout@v5 업그레이드 + workflow env `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`. 단, **다음 push 시 Actions 정상 통과 확인 필요**.
- **GA 결선(6/16) 후 데이터 갱신**: `data/senate_races.json`·`data/senate_primaries.json`·`data/model_dashboard.json`·`states/ga.qmd`

### 콘텐츠
- `issues/2026-06-14.qmd` 작성 — ME 6/9 Platner 77.7% 압승·GA 6/16 결선 직전 동향 반영
- ~~`states/me.qmd` Platner 77.7% 업데이트~~ — ✅ 이미 반영됨(확인 2026-06-11)
- **신규 페이지 콘텐츠 채우기**(2026-06-11 골격 생성): `house.qmd` 주목 레이스 카드·재획정 표, `national.qmd` 경제 지표(→ `data/national_econ.json` 정규화), `korea-watch.qmd` 인물 명단, `data/house_races.json`의 `margin_2024`·`rating_sabato`·`rating_delta` 【수집】 채우기
- `states/nc.qmd`·`states/ak.qmd`·`states/oh.qmd` — 【수집】 슬롯 채우기
- `about.qmd` — evergreen 소개 실제 콘텐츠 채우기
- `data/model_dashboard.json` — 경선 결과 반영 후 확률 재검토. **NH `prob`는 null(산정 전) — 모델 확률은 사람이 입력** (헬퍼·dashboard.js는 null을 "산정 전"으로 렌더)
- `states/nh.qmd` — 무당파 등록 비율(NH SOS 통계)·Pappas 하원 의정 기록(Voteview) 【수집】
- `data/trends.json` — 일반투표 결측 8개 주 RealClearPolling 소급 보강

### 자동화
- **launchd 주간 스냅샷 활성화** (Mac mini): `cp scripts/com.us-elections.snapshot.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.us-elections.snapshot.plist` (TCC 이슈 시 `~/.local` 래퍼 패턴 적용)
- `data/*`의 `*_delta` 자동화 — `scripts/snapshot_and_publish.sh`가 스냅샷을 쌓으면 delta 계산 스크립트 추가

### 선택
- 예보 종합표 일부 모델 수치(RacetotheWH·Silver Bulletin 본선 확률) — 슬롯 상태
- 뉴스레터 배포 채널 분리(Pages는 이메일 발송 불가 → Buttondown/Substack 등)
