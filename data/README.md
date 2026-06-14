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

### `forecast.json` — 예보 종합
- 최상위: `as_of`, `next_update`, **`rows`**(배열).
- `rows[]`: `source`, `type`, `house_dem`, `senate_dem`, `house_delta`, `senate_delta`, `note`.
  - `house_dem`/`senate_dem`/`*_delta`는 nullable(【수집】 슬롯).
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

---

## `data/history/<YYYY-MM-DD>/` — 주간 스냅샷
- `scripts/snapshot_and_publish.sh`가 주 1회 `data/*`를 복사(delta 추적용). 스키마는 위와 동일.
