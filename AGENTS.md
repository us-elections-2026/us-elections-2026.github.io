# AGENTS.md

이 파일은 Codex가 이 레포에서 작업할 때 따르는 프로젝트 지침이다.

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
- `scripts/fetch_national_econ.py` — FRED API(`FRED_API_KEY` env — 키는 `~/.Codex/settings.json`의 `env`에 저장됨, 2026-06-11 유효성 확인. **키를 레포에 커밋 금지**) → `data/national_econ.json`(CPI YoY·실업률·미시간 심리). `gt_national_econ()`이 렌더, 파일 없으면 안내문 렌더(빌드 안전). `scripts/fetch_fec_fundraising.py` — FEC API(`FEC_API_KEY` env — 키는 `~/.Codex/settings.json`의 `env`에 저장됨, 2026-06-11 유효성 확인. **키를 레포에 커밋 금지**) → `data/fec_fundraising.json` 스테이징(단위 $M). senate_races.json 반영은 수동 병합(편집 통제).
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

## 수집 규약 (중복 방지) — `data/_collection_ledger.json`

여러 에이전트가 같은 자료를 각자 수집하는 것을 막기 위한 규칙이다. 대장이 어떤 자료를 **누가·어떻게** 수집하며 지금 **무슨 상태**인지의 단일 기록이다.

1. **수집 전에 대장을 먼저 읽는다.** 해당 항목이 `확보`이거나 다른 담당에게 배정돼 있으면 중복 수집하지 않는다.
2. **사이트 제작 세션은 1차 자료를 직접 수집하지 않는다.** `data/`를 소비하고, 없는 값은 대장의 `gaps`에 요청으로 기록한다. 수집은 담당(`mac-mini`/`cowork`)이 한다 — 접근 능력이 서로 다르므로 아무나 긁으면 실패하거나 중복된다.
3. **`blocked_sources`의 출처는 재시도하지 않는다.** 새로 차단을 확인하면 거기에 **추가한다.** 이 절의 목적은 다음 세션이 같은 벽에 부딪히지 않게 하는 것 하나뿐이다.
4. **수집을 마치면 `last_updated`·`status`를 갱신한다.** 값만 커밋하고 대장을 두면 다음 세션이 다시 수집한다.
5. **데이터 값을 바꾸는 PR은 근거 기록을 동반한다.** 리뷰어(사람·Codex)는 diff의 모든 수치가 그 기록에 등장하는지 대조한다. 실물 예시는 `data/trends_verification.md`(20주 전량 원자료 대조).

## 변경 반영 경로 (PR 운용)

- **데이터·콘텐츠 변경은 브랜치 + PR로 낸다.** `main` 직커밋은 검토 없이 곧바로 배포된다(`main` push → Actions → `gh-pages`). 사람·에이전트가 손으로 수치를 고치는 변경이 여기 해당하며, 지금까지 발견된 수치 사고는 전부 이 경로에서 나왔다.
- **예외 — 자동 경로는 직커밋을 유지한다**: `scripts/publish_weekly.sh`의 주간 자동 발행, Mac mini 자동 수집. **이 스크립트들은 PR 강제를 위해 고치지 않는다.** 대신 `publish.yml`이 `scripts/validate_data.R`을 하드 게이트로 돌려 스키마·규약 위반을 막는다.

## 검수자(Reviewer) 역할 — Codex용 지침

너의 역할은 이 리포에 들어오는 데이터·콘텐츠 변경의 **독립 검수자**다. 작성자는 별도의 에이전트(Claude)이므로, 작성자의 판단을 신뢰하지 말고 아래 기준으로 교차 검증하라.

CI가 통과했더라도 아래 항목은 사람 수준의 판단이 필요하다 — **현재 CI는 `publish.yml`이 `scripts/validate_data.R`을 실행하는 것이 전부이고, 스키마·파싱·필수 필드·범위만 본다.** 아래 A-1·A-3·B-9·B-10은 **스키마상 완벽히 정상인 값**에서 실제로 발생한 사고 유형이므로 CI가 잡지 못한다.

### A. 데이터 변경 (data/**) 검수

1. **출처 정합**: 새 수치에 원출처(기관·기준일)가 붙어 있는가. `source_url`이 비었으면 note에 `【수집】` 태그가 있는가. 이차보도(뉴스위크·야후 등)만 근거인 수치는 지적하라.
   **파생값 금지** — 여러 출처의 범위에서 중간값·대표치를 만들어 넣은 값은 어느 출처에도 존재하지 않는 수치다. 계열 라벨이 특정 기관(예: "Silver Bulletin 평균")이면 값도 그 기관의 실제 기재값이어야 한다. *(실사고: `trends.json` 4/13 −16.8 — 그 주 기재값은 RCP −15.2·SB −16.3이었고 −16.8은 어디에도 없었다.)*
2. **델타의 서사**: 지난 스냅샷(`data/history/`) 대비 큰 변동(등급 2단계 이동, 가격 ±15¢, 마진 ±5p)에 커밋 메시지나 브리핑에 이유가 적혀 있는가. 이유 없는 급변은 질문하라.
   단 **Kalshi 가격 급변은 먼저 티커를 의심하라** — 접미사·주 약자 오매핑이 잦아(`SENATELA-26`의 실제 대상이 켄터키) 다른 계약을 본 것일 수 있다. 예측시장은 원래 빨리 움직이므로 급변 자체는 오류가 아니다. 차단이 아니라 질문으로 다뤄라.
3. **층위 혼동**: 이 리포는 같은 지표를 두 층으로 보관한다 — **집계기관 평균**(`approval.json`·`generic_ballot.json`·`trends.json`)과 **개별 조사 원자료**(`approval_polls.csv`·`generic_polls.csv`·`pollster_series.json`). 산출 방식이 달라 값이 다른 것이 정상이다. 한 계열 안에 두 층이 섞이면 그 구간의 오르내림은 여론 변화가 아니라 **출처 층위 변화**다. *(실사고: `trends.json` 5/25·6/1의 D+8은 집계 평균이 아니라 Verasight 단일 조사였다.)* 개별 조사의 단순 평균으로 집계 결측을 메우는 변경은 반드시 지적하라.
4. **시간 필드의 방향**: **미래 날짜는 이 리포에서 정상이다** — 경선 일정, 투표·등록·우편 마감일(10~11월)이 전부 미래다. 과거여야 하는 것은 `as_of`·`*_as_of`·`row_as_of`뿐이다. 반대로 **오래된 `as_of`가 곧 오류도 아니다** — 의도적으로 갱신을 보류한 행이 있다(`approval.json`의 USPollingData `row_as_of: 2026-06-12`, note에 "신규 반영 대기"). 신선도·미래날짜를 근거로 지적하기 전에 그 필드가 어느 쪽인지 먼저 확인하라.
5. **알려진 함정** (CLAUDE.md 금지·주의 절과 동일):
   - Kalshi 티커 접미사 오매핑(주 판정은 `rules_primary`, 사이클은 `expected_expiration`) / 270toWin '다수 확률' 위젯은 시장가지 모델이 아님 / 등급 ≠ 확률 / 예측시장 가격 ≠ 확률
   - 2025년 조사와 2026년 조사 혼용(예: Emerson OH 2025-08) — 조사 기간을 반드시 확인
   - `dem`/`rep`가 `null`이고 `margin`만 있는 행이 **정상적으로** 존재한다(`generic_ballot.json`의 USPollingData·Silver Bulletin). 마진을 재계산해 대조할 때 `null`을 0으로 읽지 말 것.
6. **정정 이력 대조**: 확인된 기존 오류의 재발 여부 — 2022 투표율은 VEP 46.1%(45.1% 아님), 재획정 순효과 "R+10" 무출처(Cook R+12 또는 Morris ~R+8로 병기), GA-14 특별선거 마진 축소는 기준 병기(그린 대비 ~18p/트럼프 대비 ~25p), 1938년 하원은 APP 기준 −72.
7. **수집 대장 대조**(`data/_collection_ledger.json`): 변경된 파일의 담당이 맞는가 — 사이트 제작 세션이 1차 자료를 수집한 흔적은 지적하라. `blocked_sources`의 출처를 다시 시도한 흔적이 있으면 지적하라. 수집·정정 PR인데 대장의 `last_updated`·`status`가 그대로면 지적하라.

### B. 브리핑·프로즈 (issues/, *.qmd) 검수

8. 수치가 `data/` 파일과 일치하는가(파일 인용 표기 `(data/…, as_of)` 확인). 브리핑에만 있고 환류 append가 없는 정형 수치(신규 조사)는 지적하라 — "환류: +N행" 대사 확인.
   **데이터 값을 바꾸는 PR은 근거 기록을 동반해야 한다**(위 「수집 규약」 5). diff의 모든 수치가 그 기록에 등장하는지 대조하라. 실물 예시는 `data/trends_verification.md`.
9. **표 내부 산술 정합**: 한 행의 헤드라인 값과 그 행의 구성 수치가 서로 맞는가. 지지−반대=순지지, D−R=마진을 직접 계산해 보라. *(실사고: `issues/2026-06-29.qmd`가 `D+6.1 | 7/3 (SB 평균, D 49.1 / R 43.5)`로 적었는데 49.1−43.5=5.6이었다.)*
10. **비교 기준값 혼입**: 브리핑은 당해 값 옆에 과거 사이클 벤치마크를 반복 인용한다("2018 동기 D+6.6과 동일 페이스", "바이든 동기 −19.2", "1기 동기 −11.3"). **그 벤치마크가 당해 계열값 자리로 옮겨 들어가는 사고가 실제로 있었다** — `trends.json` 6/15의 D+6.6은 2026년 값이 아니라 2018년 벤치마크였고 그 주 브리핑의 실제 값은 D+7이었다. **데이터 파일의 값이 브리핑에 반복 등장하는 벤치마크 수치와 일치하면 의심하라.**
11. 마진 표기 규약(양수=민주 우위 `D+`), 기준일 스탬프, 미확인 값의 `【수집】` 처리 여부.
12. 단정 어조 검사: 등급·시장·모델을 같은 잣대로 비교하거나, 단일 조사를 추세로 승격한 문장. **결측 구간을 보간한 선·표를 실측처럼 서술한 문장.**

### C. 코드 변경 (scripts/, R/, assets/) 검수

13. fetch 스크립트 수정 시: 스키마 하위호환(기존 열 정의 불변), `as_of` 스탬프 유지, 실패 시 `null` 처리(추정으로 채우지 않음) 관례 준수.
14. `helpers.R`·`assets/*.js` 수정 시: 등급 9단계 팔레트·타일 좌표 등 시각 규약 변경이 의도된 것인지 확인. **결측을 실측처럼 그리는 변경은 지적하라** — 시계열 차트는 실측과 보간을 시각적으로 구분해야 한다(`assets/trends.js`가 기준 구현).
15. **검증 규칙을 추가하는 변경**: 오탐으로 정상 발행을 막지 않는지 보라. A-4·A-5의 세 가지가 실제 함정이다 — 의도적으로 오래된 `as_of`, 정상적인 미래 날짜, `null` 구성값. 새 규칙이 차단(fail)인지 경고(warn)인지 명시돼 있어야 한다.

### 검수 결과 형식

- PR 리뷰: 위 번호를 인용해 지적 (예: "A-2: kalshi 컨트롤 45→28¢ 사유 미기재").
- 야간 감사 모드(CLI): `worklogs/audit_YYYY-MM-DD.md`에 ✅/⚠️/❌ 목록 + 요약 3줄.
- 지적할 것이 없으면 "검수 통과 — 특이사항 없음" 1줄로 끝낸다. 과잉 지적 금지.

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
