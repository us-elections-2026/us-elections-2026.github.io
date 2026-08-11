# `data/` — 정규화 데이터 스키마

이 폴더의 JSON/CSV는 빌드 시점에 `R/helpers.R`가 읽어 정적 표·카드로 렌더링한다.
요청 시 서버가 DB를 때리지 않으므로, **여기 파일의 정확성이 곧 사이트의 정확성**이다.

검증: `Rscript scripts/validate_data.R` (파싱·필수 필드·규약 점검, CI publish 전 실행).

## 공통 규약 (모든 파일)

- **부호: 양수 = 민주 우위.** 마진은 `D+`(양수) / `R+`(음수)로 정규화한다. 절대 뒤집지 않는다.
- **모르는 값은 `null`**(JSON) / 빈칸(CSV)로 둔다. 표에서는 `—` 또는 `【수집】`으로 렌더된다.
  **추정치로 빈 칸을 채우지 않는다.**
- **provenance 보존**: `type`(market/model/rating/aggregate), `population`(A/RV/LV),
  기준일(`as_of`·`*_as_of`), `source_label`, `provenance_note` 필드가 있으면 유지한다.
- 대부분의 파일은 최상위에 **`as_of`**(기준일, `YYYY-MM-DD`)를 둔다.
- 등급(Toss Up/Lean)은 확률이 아니다. 모델·시장 수치와 같은 잣대로 비교하지 않는다.

---

## 전국 환경

### `forecast.json` — 예보 종합 (**자동 생성 — 직접 편집하지 말 것**)
- 최상위: `as_of`, `generated_by`, `provenance_note`, **`rows`**(배열).
- `rows[]`: `source`, `type`, `house_dem`, `senate_dem`, `house_delta`, `senate_delta`, `note`.
  - `house_dem`/`senate_dem`/`*_delta`는 **0~1 분수**(`gt_forecast()`가 ×100해 렌더). nullable.
- **생성**: `scripts/build_forecast.py`가 `kalshi_prices.json`(시장) · `ddhq_forecast.json` ·
  `rtwh_forecast.json` · `model_v0.json`(모델)에서 조립. `publish_weekly.sh` 2.7단계에서 실행되며,
  **모델 재실행(2.5) 뒤에 와야** 자체 모델 행이 최신값이 된다.
- `*_delta`는 **직전 `forecast.json` 대비**로 계산되므로, 파일을 손으로 되돌리면 다음 delta가 틀어진다.
- 빈 칸은 해당 원천이 그 원(院)을 예측하지 않는다는 뜻(RtWH·자체 모델은 상원 전용) — 추정으로 채우지 않는다.
- 등급(Cook·Sabato)은 확률이 아니므로 이 표에 넣지 않는다. 등급 비교는 `senate_ratings_feed.json`·`governor_ratings.json` 쪽 표.
- 소비: `gt_forecast()` → `trackers.qmd`.

### `generic_ballot.json` — 제너릭 밸럿
- 최상위: `as_of`, **`aggregators`**(배열), `spread_examples`(배열).
- `aggregators[]`: `source`, `dem`, `rep`, `margin`, `agg_as_of`, `population`(A/RV/LV).
- `spread_examples[]`: `pollster`, `dem`, `rep`, `margin`, `population`, `note`.
- `margin` 부호: 양수=민주 우위.
- 소비: `gt_generic()`·`gt_generic_spread()` → `index.qmd`, `trackers.qmd`, `national.qmd`.

### `approval.json` — 트럼프 지지율
- 최상위: `as_of`, **`rows`**.
- `rows[]`: `source`, `approve`, `disapprove`, `net`, `row_as_of`, `note`.
  - `net` = approve − disapprove(순지지, 음수 정상).
- 소비: `gt_approval()` → `index.qmd`, `trackers.qmd`, `national.qmd`.

### `trends.json` — 추이(홈 차트)
- 최상위: `as_of`, `source`, **`weeks`**.
- `weeks[]`: `date`, `label`, `trump_net`, `generic`.
  - `trump_net`(순지지)·`generic`(일반투표 D 마진, 양수=민주)은 보고된 주만 값, 나머지 nullable.
- 소비: 런타임 `assets/trends.js`가 `fetch` → `index.qmd`. (`_quarto.yml`의 `project.resources` 등록 필요.)

### `pollster_series.json` — 조사기관별 시계열 (차트용, **선택 파일**)
- `scripts/fetch_pollster_polls.py`가 `approval_polls.csv`·`generic_polls.csv`와 함께 생성.
  부재 시 `assets/pollsters.js`가 안내문 렌더(빌드 안전).
- 최상위: `as_of`, `fetched_at_utc`, `type`(=`poll`), `source_label`, `source_url`,
  `window_start`, `trend_window_days`, `note`, **`approval`**, **`generic`**.
- 각 블록: `polls[]`, `trend[]`, `top_pollsters[]`, `house_effects[]`,
  `data_through`, `trend_through`, `n_polls`, `n_pollsters`.
  - `polls[]`: `d`(종료일), `v`(값), `p`(조사기관), `pop`(A/RV/LV), `n`, `party`(당파 조사 표기), `url`.
  - `trend[]`: `d`, `v`, `n`(창 안 조사 수) — 비당파 조사의 21일 **중심** 이동평균.
    창의 절반이 자료 밖으로 나가는 양끝은 잘라내므로 **`trend_through` < `data_through`가 정상**
    (역전 시 검증 실패). 집계기관 평균과 **산출 방식이 다르므로 섞어 쓰지 말 것**.
  - `house_effects[]`: `pollster`, `n`, `effect`(이동평균 대비 평균 잔차, 5건 이상 기관만).
    부호의 뜻이 지표마다 반대 — 순지지도는 +가 트럼프에 후함, 일반투표는 +가 민주 우위.
- **집계 단위 주의**: `polls[]`는 발표된 값 전부지만, `trend`·`house_effects`는
  **조사(기관+현장기간) 단위로 1행만** 남겨 계산한다(우선순위 LV › RV › A). 한 조사가
  모집단별로 2~3행이 되면 같은 현장조사가 그만큼 중복 가중되기 때문(2026년 기준 순지지도
  행의 20%·일반투표 24%). 따라서 `house_effects[].n`은 `polls[]`의 기관별 행 수보다 작다.
- **피드 중복**: 같은 조사가 서로 다른 `poll_id`로 두 번 실리는 경우가 있어
  (기관·기간·모집단·값·표본이 모두 같으면) 수집 단계에서 제거한다.
- `v` 부호: 순지지도 = `approve − disapprove`, 일반투표 = `dem − rep`(양수=민주 우위).
- 소비: 런타임 `assets/pollsters.js`가 `fetch` → `national.qmd`. (`project.resources` 등록 필요.)
- **신선도 주의**: 원천 피드가 실시간이 아니어서 `data_through`가 사이트의 집계표보다
  수 주 이를 수 있다. 최신값 인용에 쓰지 말고 기관 간 분산을 읽는 데만 쓴다.

### `national_econ.json` — 경제 지표 (FRED, **선택 파일**)
- `scripts/fetch_national_econ.py`가 생성. fetch 실패 시 부재 가능 → `gt_national_econ()`이 안내문 렌더(빌드 안전).
- 최상위: `as_of`, `series_start`, `source_label`, `provenance_note`, **`rows`**, **`series`**.
- `rows[]`: `indicator`, `series_id`, `key`, `unit`, `value`, `prev`, `period`, `election_note`. `value`/`prev` nullable(수집 실패).
- `series`: `{ key: [[period, value], ...] }` 시계열(차트용).
- 소비: `gt_national_econ()` → `national.qmd` + `assets/econ.js` fetch.
- 검증은 **선택**(파일 없으면 통과).

---

## 상원

### `senate_races.json` — 경합 8주 카드
- 최상위: `as_of`, `dem_needed_net`(민주 다수까지 순증), `current_balance`, **`races`**.
- `races[]`: `state`, **`defense`**(`D`/`R` — 현 보유 정당), `incumbent`, `rating`,
  `latest_poll`, `poll_source`, `cash_on_hand`, `kr_relevance`.
  - `latest_poll`/`poll_source`/`cash_on_hand` nullable(`null`→`—`/`【수집】`).
  - `rating`은 문자열(예: "Toss Up", "Lean D (Cook 6/11)") — 확률 아님.
- 소비: `gt_state_detail()` → `states/*.qmd`; `gt_senate()` → `senate.qmd`, `trackers.qmd`.

### `senate_primaries.json` — 경선 일정/결과
- 최상위: `as_of`, **`rows`**.
- `rows[]`: `state`, `event`, `date`, `status`, `detail`. `date`/`detail` nullable.
- 소비: `gt_senate_primaries()` → `senate.qmd`; `gt_state_detail()`가 해당 주 행 병합; 카드 헬퍼가 참조.

### `candidates.json` — 후보 프로필 카드
- 최상위: `as_of`, `note`, **`candidates`**.
- `candidates[]`: `state`, `party`, `name`, `name_kr`, `incumbent`, `photo`, `photo_credit`,
  `born`, `occupation`, `education`, `family`, `past_elections`, `fundraising`,
  `strengths`, `weaknesses`, `policy`, `kr_note`, `sources`, `status`.
  - 다수 필드 nullable(`null`=공개 출처 미확인). 사진은 PD/CC만.
- 소비: `candidate_cards_html()`·`primary_cards_html()` → `states/*.qmd`.

### `governor_candidates.json` — 주지사 후보 프로필 카드
- 스키마는 `candidates.json`과 동일하며 **`office`**(="governor") 한 필드만 더 있다.
- 경합 8주(AZ·GA·IA·KS·MI·NV·OH·WI) 16명. `status`는 `nominee` 외에
  `presumptive (8/11)`처럼 경선 전 상태를 표기하며, 이 경우 카드 위에 "지명 확정 전" 주석이 붙는다.
- `photo`가 `null`이면 `_placeholder.svg`로 렌더된다(`.c_photo()`) — 저작권 미확인 캠페인 사진은 쓰지 않는다.
- 소비: `governor_cards_html()` → `governors.qmd#candidates`. **수동 갱신**(경선 확정·자금 신고 시).

### `fec_fundraising.json` — FEC 모금 스테이징 (직접 렌더 안 함)
- `scripts/fetch_fec_fundraising.py`가 생성(단위 $M). 최상위: `as_of`, `source_label`, `provenance_note`, `states`(`{ST: [후보…]}`).
- `senate_races.json`의 `cash_on_hand` 반영은 **수동 병합**(편집 통제). 슈퍼팩 외부지출 미포함.
- 현재 어떤 헬퍼도 직접 로드하지 않음 → `validate_data.R` 검증 대상 아님(파싱만 필요 시 수동).

---

## 자체 모델 대시보드

### `model_dashboard.json`
- 최상위: `as_of`, `facts_updated`, `source_label`, `provenance_note`, `current_balance`,
  `dem_needed_net`, `dem_majority_prob`, `net_expected_seats`, **`states`**, **`scenarios`**, **`timeline`**.
- `states[]`: `id`, `name`, `nameEn`, `defense`(D/R), `rating`, **`prob`**, `matchup`, `key_var`, `note`.
  - `prob`(민주 승리확률 %, 0–100)는 **nullable** = "산정 전"(예: NH). 모델 확률은 사람이 입력.
- `scenarios[]`: `id`, `name`, `subname`, `prob`, `seats`, `majority`, `desc`.
- `timeline[]`: `date`, `event`, `detail`, `party`, `status`.
- 소비: `gt_model_states()`/`gt_model_scenarios()`/`model_kpi()` → `dashboard.qmd`, `scenarios.qmd`, `index.qmd`
  + 런타임 `assets/dashboard.js` fetch. **갱신 = 이 한 파일만 편집.**

---

## 하원

### `house_races.json` — 토스업 트래커
- 최상위: `as_of`, `source_label`, `cook_outlook`, `provenance_note`, **`races`**.
- `races[]`: `district`, `incumbent`, `party`(D/R, 현 보유), `rating_cook`, `rating_sabato`,
  `rating_delta`, **`margin_2024`**, `map_status`, `status`, `korea_clue`, `note`.
  - `margin_2024`: **숫자(양수=민주 우위) 또는 `null`**(신지도 미공표 등 【수집】). 재획정 구는 신지도 기준.
  - `rating_sabato`/`rating_delta`/`korea_clue`/`note` nullable.
- 소비: `gt_house_races()` → `house.qmd`.

### `redistricting_states.json` — 2026 중간 재획정 주별 현황
- 최상위: `as_of`, `net_enacted_label`, `note`, **`states`**.
- `states[]`: `state`, `name`, `drawer`(작성 주체), `party`, `category`, `status`, **`net_d`**, `intended_d`, `enacted`, `source`, `source_url`.
  - `category`: enacted / blocked / failed.
  - **`net_d`**: 의석 순효과 추정, **양수=민주 순증(D+)** / 음수=공화 순증. `intended_d`=의도한 순효과(차단 시 net과 다름).
- 소비: `gt_redistricting_states()` + `svg_redistricting_bar()`(다이버징 바) → `redistricting.qmd`.

### `redistricting_pres.json` — 지역구별 신·구 대선 마진(2024 재집계)
- 최상위: `as_of`, `note`, **`districts`**.
- `districts[]`: `district`, `name`, `incumbent`, **`old_margin`**, **`new_margin`**, `source`, `source_url`, `memo`.
  - 마진: **숫자(양수=민주 우위) 또는 `null`**(신·구 정밀 마진 미공표 시 【수집】). 같은 2024 표를 새 경계로 재집계한 값.
  - 전체 데이터셋 소스: The Downballot (the-db.co/presbycd) — 수집 후 보강.
- 소비: `gt_redistricting_pres()` → `redistricting.qmd`. `house_races.json`의 `margin_2024` 단일 소스 역할.

---

## CSV (스키마 고정 — 열 정의 변경 금지)

### `korea_watch.csv` — Korea Watch DB
- 열(고정 10): `date`, `type`, `actor`, `affiliation`, `state_or_district`,
  `event`, `detail`, `race_link`, `significance`, `source_url`.
  - `type`: 안보/통상/산업/북한/법안표결/인사/선거연계.
  - `significance`: **정수 1–3**(3=정책변경·법안통과·고위인사 / 2=유력발언·법안발의·공식보고서 / 1=동향).
  - `detail` 내 쉼표는 세미콜론으로, 따옴표로 감쌈. `race_link` 빈칸 허용.
- 소비: `gt_korea_watch()` → `korea-watch.qmd`.

### `polls_log.csv` — 여론조사 로그
- 열: `date`, `pollster`, `sponsor`, `race`, `population`(A/RV/LV), `n`, `result`, `rating`.
- 소비: `gt_polls_log()` → `trackers.qmd`.

### `approval_polls.csv` · `generic_polls.csv` — 개별 조사 원자료 (**선택 파일**)
- `scripts/fetch_pollster_polls.py`가 생성(VoteHub 공개 API). **차트 구간(2026~)이 아니라
  전 기간(2025년 1월~)을 그대로 보관** — 차트용 축약본은 `pollster_series.json`.
- **`*_supplement.csv` (수동 보충분)**: 피드가 멈춘 구간(2026-07~)을 상위 기관 원본
  (YouGov 탭 PDF·Ipsos 토플라인·Napolitan 토플라인·ARG 발표)에서 직접 채운 행.
  스키마는 main과 동일 13열, `poll_id`가 `supp-` 접두. fetch 스크립트가 병합하되
  **같은 조사(기관+기간+모집단)가 피드에 생기면 피드가 정본**(보충 행 자동 후퇴).
  보충 행은 차트의 점·기관별 선에만 쓰이고 **이동평균·하우스 이펙트 계산에서는 제외**
  — 몇 곳뿐인 부분 표본이 추세를 표본 구성 변화로 왜곡하는 것을 막기 위함.
- 열(고정 13): `date_end`, `date_start`, `pollster`, `sponsor`, `population`(A/RV/LV), `n`,
  `approve`/`dem`, `disapprove`/`rep`, `value`, `partisan`(DEM/REP), `internal`, `poll_id`, `source_url`.
  - `value` = 7번째 열 − 8번째 열. 순지지도는 `approve − disapprove`,
    일반투표는 `dem − rep`(양수=민주 우위). 검증이 이 항등식을 확인한다.
  - `partisan`이 채워진 행은 당파(내부) 조사 — 추세·하우스 이펙트 산출에서 제외된다.
- 소비: 직접 렌더하지 않음(원자료 보관·재현용). 페이지는 `pollster_series.json`만 읽는다.

---

## `data/history/<YYYY-MM-DD>/` — 주간 스냅샷
- `scripts/snapshot_and_publish.sh`가 주 1회 `data/*`를 복사(delta 추적용). 스키마는 위와 동일.
