# CLAUDE.md

이 파일은 Claude Code가 이 레포에서 작업할 때 따르는 프로젝트 지침이다.

## 프로젝트

한국 독자를 위한 **2026 미국 중간선거 주간 브리핑** 사이트. Quarto + GitHub Pages.
독자층은 **약간의 전문성을 갖춘 층**(NYT·538·Silver Bulletin을 직접 볼 수 있는 사람들).
따라서 속보 중계가 아니라 **해석·여론조사 리터러시·한국 정책 함의**로 차별화한다.
구성은 **데이터 약 50% / 분석 약 50%**.

## 아키텍처 (한 줄)

**발행 담당 머신은 Mac Studio(mini)로 고정한다** — 두 로컬 머신이 Dropbox로 같은 작업 사본을 공유하므로(아래 「금지·주의」①), `publish_weekly.sh`·launchd·API 키는 이 한 대에서만 돌린다. 다른 머신은 편집만 한다. 클라우드(Claude Code) 세션은 GitHub에서 별도 클론을 받아 쓰므로 Dropbox 사본과 무관하고, 결과는 git으로만 되돌린다.

```
Mac mini (수집 + 정규화 → data/ 에 JSON/CSV 커밋) → git push
  → GitHub Actions (Quarto render + R 실행) → gh-pages → Pages
```

요청 시점에 서버가 DB를 때리지 않는다. 모든 표는 **빌드 시점에 미리 계산**되어 정적 HTML로 굳는다.
데이터 표는 `data/`의 정규화 파일에서 렌더링되고, 분석은 마크다운(`.qmd` 프로즈)으로 쓴다.

## 디렉터리

- `_quarto.yml` — 사이트 설정. `execute-dir: project`(작업경로=루트 고정), `freeze: false`(데이터 변경 시 매 빌드 재계산).
- `R/helpers.R` — `data/` 로딩·정규화·`gt` 표 렌더링 헬퍼. `gt_forecast()` `gt_generic()` `gt_generic_spread()` `gt_approval()` `gt_senate()` `gt_senate_primaries()` `gt_state_detail()` `gt_polls_log()` `gt_model_states()` `gt_model_scenarios()` `model_kpi()` `house_cook_bar_html()` `gt_house_races()` `gt_korea_watch()` `candidate_cards_html()` `governor_cards_html()` `gt_state_fec()` `gt_governor_detail()` `gt_governor_polls()` `governor_money_html()`.
- `index.qmd` — 홈(상원 전망 요약 KPI + 환경 스냅샷 + 이슈 listing). `trackers.qmd` — 최신 표 모음. `senate.qmd` — 경합주 표. `dashboard.qmd` — ★ 자체 모델 대시보드. `about.qmd` — evergreen 소개.
- `dashboard.qmd` + `assets/dashboard.{js,css}` — 인터랙티브 대시보드(Chart.js). `data/model_dashboard.json`을 런타임 `fetch`로 읽어 KPI·확률차트·시나리오·주별카드·타임라인 렌더. ⚠️ **JS 비활성 환경 폴백은 현재 끊겨 있다(2026-08-29 확인)** — `gt_model_scenarios()`는 `scenarios.qmd`에서 쓰이지만 `gt_model_states()`는 어느 `.qmd`에서도 호출되지 않아, `dashboard.html`은 `#dash-kpis`·`#dash-scenarios`·`#dash-states`·`#dash-timeline`·`#dash-stamp`·`#dash-note` 여섯 컨테이너를 **빈 채로 출고**한다(JS가 채운다). 복구는 아래 TODO 참조. 산문 수치는 2026-08-29부터 인라인 R로 `data/`에서 읽는다 — **손으로 박지 말 것**(8/6자 값이 5주간 남아 같은 페이지 표와 어긋난 전력). **데이터 갱신 = `data/model_dashboard.json` 한 파일만 편집 → push → 자동 재빌드.** `fetch` 대상이라 `_quarto.yml`의 `project.resources`에 등록돼 있어야 `_site/`로 복사됨.
- `states/{ga,mi,nh,me,nc,tx,oh,ak,ia}.qmd` — 경합주 9곳 State Focus 페이지(`gt_state_detail()` 카드 + 프로즈). 민주 수성 3(GA·MI·NH) + 공화 표적 6(ME·NC·TX·OH·AK·IA). 주 추가/제외는 사람이 결정한다 — **IA는 2026-08-08 편입**(Inside Elections 하향 + Fox 조사 튜렉 우위 + Q2 모금 역전).
- `issues/YYYY-MM-DD.qmd` — 주간 호. 데이터(PART 1)는 함수 렌더링, 분석(PART 2)은 프로즈. 사이드바에는 `archive.qmd`(listing 페이지)만 노출 — 개별 호 자동 등재(auto)는 사이드바 비대화 문제로 제거(2026-06-11). 홈 listing은 유지.
- `house.qmd` — ★ 하원. 맨 위 **Cook 등급 가로 누적 막대**(`house_cook_bar_html()`, `data/house_cook_ratings.json` — 7개 카테고리 의석수, 색은 270towin 원본 팔레트, 218 과반선·범례 포함. **자동 취득**(2026-08-03 전환): `scripts/fetch_cook_house.py`가 270towin에서 파싱해 이 파일을 쓰고, `publish_weekly.sh` §1.5가 호출한다 — 손으로 옮기지 말 것. Solid는 토플라인−Likely−Lean 역산, 합계 435 검증) + 경합구 트래커(`gt_house_races()`, `data/house_races.json`, Cook 토스업 상시 + Lean 주간 관리 2단 구조).
- `governors.qmd` — ★ 주지사(36개 주). 등급 표·기관 비교·Kalshi 원가격·경선 캘린더·주목 레이스 + **후보 프로필 카드**(`governor_cards_html()`, `data/governor_candidates.json`, 경합 8주 16명). 사진은 Wikimedia PD·CC만, 없으면 `_placeholder.svg`.
- `governors/{az,ga,oh,mi,wi,nv,ia,ks}.qmd` — ★ **주지사 State Focus 8주**(2026-08-12 신설, 상원 구조 이식): 카드 + `gt_governor_detail()` + 6절(개요·제도·관전점·조사·자금·한국 함의). 데이터는 `governor_races.json`(수동)·`governor_polls.csv`(수동, 전 행 원문 URL)·`governor_primaries.json`. 자금은 주(州) 선관위 신고 기준 — FEC 자동 취득 없음.
- `redistricting.qmd` — ★ 재획정 설명 페이지(한국 독자용 evergreen). ①제도·②배경·③17주 현황·④지도비교·⑤지역구Δ. `data/redistricting_states.json`(17주)·`data/redistricting_pres.json`(지역구 신·구 마진). 헬퍼: `gt_redistricting_states()`·`gt_redistricting_pres()`·`svg_redistricting_bar()`.
- `national.qmd` — ★ 전국 환경(지지율·제너릭 밸럿·경제·외교). `scenarios.qmd` — ★ 상원 시나리오(소수/50:50/다수, tipping-point, 한국 함의). `methodology.qmd` — ★ 방법론(수치 3종 구분·모델 개요·여론조사 리터러시). `korea-watch.qmd` — ★ Korea Watch(`gt_korea_watch()`, `data/korea_watch.csv`).
- `data/` — ★ 정규화 데이터. Mac mini가 여기에 커밋한다. `forecast.json` `generic_ballot.json` `approval.json` `senate_races.json` `senate_primaries.json` `model_dashboard.json` `polls_log.csv` `house_races.json` `house_cook_ratings.json` `house_cook_districts.json` `kalshi_prices.json` `ddhq_forecast.json`·`rtwh_forecast.json`(외부 모델 확률, 자동) `senate_ratings_feed.json`·`governor_ratings.json`(등급 피드, 자동) `senate_primaries.json`·`governor_primaries.json`(경선 캘린더, 수동) `candidates.json`(상원 후보 프로필·status=nominee|primary)·`governor_candidates.json`(주지사 경합 8주 16명 — 동일 스키마+`office`, `governors.qmd#candidates`가 소비, 수동) `governor_races.json`·`governor_polls.csv`(주지사 State Focus 데이터, 수동) `senate_polls.csv`(모델 입력) `model_v0.json`(자체 모델 산출) `approval_polls.csv`·`generic_polls.csv`·`pollster_series.json`(개별 조사 원자료, 자동) `rating_history.json` `state_legislatures.json`(수동) `korea_watch.csv`(스키마 고정: date,type,actor,affiliation,state_or_district,event,detail,race_link,significance,source_url). `data/history/<YYYY-MM-DD>/` — 주간 스냅샷(delta 추적).
- **집계값과 개별 조사는 다른 층이다** — `approval.json`·`generic_ballot.json`은 **집계기관의 평균**(Silver Bulletin 등), `approval_polls.csv`·`generic_polls.csv`·`pollster_series.json`은 그 평균에 들어간 **개별 조사 원자료**다(`scripts/fetch_pollster_polls.py`, VoteHub 공개 API·인증 불필요). 두 층은 산출 방식이 달라 값이 다르고, **원천 피드가 실시간이 아니라 개별 조사 쪽이 수 주 이르다** — `national.qmd`의 조사기관별 절은 최신값이 아니라 **기관 간 분산**을 읽는 용도이며 페이지에 callout으로 명시돼 있다. 하우스 이펙트는 21일 중심 이동평균 대비 평균 잔차이고, 부호의 뜻이 지표마다 반대다(순지지도 +=트럼프에 후함 / 일반투표 +=민주 우위 → **막대 색을 지표별로 뒤집어 칠한다**).
- **주간 스냅샷은 `scripts/publish_weekly.sh` §4.5**가 남긴다 — 검증·렌더를 통과한 `data/*`를 `data/history/<날짜>/`로 보관하고 주간 발행 커밋에 함께 실린다. `scripts/snapshot_and_publish.sh` + `com.us-elections.snapshot.plist`는 **수동 실행 전용**이며 launchd에 걸지 않는다(2026-08-13 확인: plist가 설치된 적이 없어 한 번도 실행되지 않았고, 스냅샷이 2026-06-08 1건에 머물러 delta 추적이 막혀 있었다 — 실행이 커밋으로 증명되는 주간 경로에 편입). 데이터 수치 갱신 자체는 수동 편집이 주도.
- `scripts/fetch_national_econ.py` — FRED API(`FRED_API_KEY` env — 키는 `~/.claude/settings.json`의 `env`에 저장됨, 2026-06-11 유효성 확인. **키를 레포에 커밋 금지**) → `data/national_econ.json`(CPI YoY·실업률·미시간 심리). `gt_national_econ()`이 렌더, 파일 없으면 안내문 렌더(빌드 안전). `scripts/fetch_fec_fundraising.py` — FEC API(`FEC_API_KEY` env — 키는 `~/.claude/settings.json`의 `env`에 저장됨, 2026-06-11 유효성 확인. **키를 레포에 커밋 금지**) → `data/fec_fundraising.json` 스테이징(단위 $M). 각 주 State Focus의 분기 신고 표는 `gt_state_fec()`가 이 파일에서 자동 렌더(2026-08-12 전환 — 종전에는 각 주 페이지에 Q1 표를 손으로 박아 둬 갱신되지 않았다). senate_races.json의 요약 상자 반영은 여전히 수동 병합(편집 통제).
- `scripts/fetch_kalshi_prices.py` — **예측시장 원가격**(Kalshi 공개 API, 인증 불필요) → `data/kalshi_prices.json`. 상원 다수 계약(CONTROLS-2026)·상원 35·주지사 35개 레이스의 마지막 체결가. **270towin의 '등급 환산값'을 쓰지 말 것** — 91¢가 "Solid D"로 보여 전문가 등급과 구분되지 않는다. **Kalshi 티커는 신뢰 금지**: 사이클 접미사가 주마다 다르고(GA `-26`/KS `-27`/NH `-28`), 주 약자가 틀린 것도 있다(`SENATELA-26`의 실제 대상은 켄터키). 주는 `rules_primary`, 사이클은 `expected_expiration`으로 각각 판정한다.
- **270toWin의 '의회 다수 확률' 위젯은 모델이 아니라 Kalshi 시장이다** (2026-08-06 확인) — `Which Party Will Control the Senate?` 블록은 `kalshi-logo`·"most recent 'yes' trade"를 명시한 예측시장 위젯이다. 이를 '270toWin 컨센서스 모델 확률'로 인용하면 **시장 수치를 모델로 오기재**하게 된다. 같은 페이지의 주별 % 열(`kalshi_price`)도 시장가다. 등급 지도(consensus map_string)와는 완전히 별개.
- **270towin map_string 코드표** (정본: `https://www.270towin.com/js/maps/map.class.js`의 `mapCodeRatings`) — `0`=Toss-up `1`=Solid D `2`=Solid R `3`=Likely D `4`=Likely R `5`=Lean D `6`=Lean R `7`=Independent `8`=split `9`=미선거 `a`=**Tilt D** `b`=**Tilt R** `c`/`d`/`e`=당선(D/R/I) `f`=결선. Tilt는 Lean보다 좁은 등급으로 Inside Elections·RaceToTheWH·Kalshi가 쓴다(Cook·Sabato는 미사용). **정렬 검증은 양방향으로**: 선거석이 9가 아닌지 + 비선거석이 9인지 둘 다 봐야 다른 종류의 지도를 오독하지 않는다(2026-08-05 Split Ticket 사례).
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

- **두 대의 로컬 머신이 Dropbox로 같은 작업 사본을 공유한다.** 이 구조에서 나오는 두 가지 함정:
  ① **Dropbox 충돌 사본이 라이브로 나갈 수 있다** — `publish_weekly.sh` §5는 `git add data/ issues/ states/ ./*.qmd`로 디렉터리째 스테이징하고 `_quarto.yml`의 `render:`는 `"*.qmd"` 같은 glob이다. 그래서 `senate (Woo's conflicted copy 2026-08-20).qmd` 하나가 생기면 스테이징→커밋→push→CI 렌더를 그대로 통과해 **낡은 중복 페이지가 공개된다**(문법이 정상이라 렌더도 검증도 오류로 보지 않는다). 2026-08-20 3중 방어 추가: `.gitignore` 패턴 · `_quarto.yml` 부정 glob · `publish_weekly.sh` 시작 시 하드 게이트.
  ② **머신 종속 상태를 근거로 진단하지 말 것** — launchd plist·cron·로컬 캐시·로그 디렉터리는 한 머신에만 존재할 수 있다. "설치된 적 없음/실행된 적 없음"은 **커밋 이력으로 확인될 때만** 유효하다(스냅샷 건이 그 예다 — 파일시스템이 아니라 `data/history/`가 1건에 머문 사실이 근거였다).
  발행 스크립트의 레포 경로는 하드코딩을 걷어내고 스크립트 위치에서 유도한다(`US_ELECTIONS_REPO`로 덮어쓰기 가능).
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
- **[2026-08-30 주간 발행 때 처리] `dashboard.qmd` JS 비활성 폴백 복구** — `gt_model_states()`가 정의(`R/helpers.R:532`)만 있고 호출처가 없어 대시보드의 여섯 컨테이너가 빈 채로 출고된다(위 `dashboard.qmd` 항목 참조). `scenarios.qmd:20`이 쓰는 `gt_model_scenarios()`는 정상이므로 **대상은 `gt_model_states()` 하나**. 주의: JS가 켜진 환경에서는 JS 렌더 결과와 **이중 표시**되므로, 단순 호출 추가가 아니라 `.d-none`/`<noscript>`류로 한쪽만 보이게 하는 처리가 함께 필요하다. 사용자 지시로 8/30 발행 사이클에 배정(2026-08-29).
- ~~`actions/checkout@v4` Node 24 대응~~ — ✅ 완료(2026-06-11)
- **GA 결선(6/16) 후 데이터 갱신**: `data/senate_races.json`·`data/senate_primaries.json`·`data/model_dashboard.json`·`states/ga.qmd`

### 콘텐츠
- `issues/2026-06-14.qmd` 작성 — GA 6/16 결선 직전 동향·ME 압승 반영 (**GA 결선 이후 작성 권장**)
- ~~`states/me.qmd` Platner 77.7% 업데이트~~ — ✅ 반영됨
- ~~`house.qmd` 주목 레이스 카드·`house_races.json` margin/sabato/status 채우기~~ — ✅ 완료(2026-06-14): 18구 전 필드·주목 카드 7개·AZ-01/ME-02/NE-02 공석 정정
- ~~`korea-watch.qmd` 인물 명단~~ — ✅ 완료(2026-06-14): 16행 DB + 법안/인물 표
- ~~`states/nc.qmd`·`states/ak.qmd`·`states/oh.qmd` 슬롯 채우기~~ — ✅ 완료(2026-06-14): 8주 전부 6섹션 표준화
- `about.qmd` — evergreen 소개 실제 콘텐츠
- `data/model_dashboard.json` — NC Lean D prob 입력, 경선 결과 반영. **모델 확률은 사람이 입력** (null="산정 전"으로 렌더)
- `data/trends.json` — 일반투표 결측 8개 주 RealClearPolling 소급 보강

### 데이터 플래그 (홈 유의사항 callout에 공개)
- Barrett(MI-07) Korea Caucus 1차 출처 미검증 (재확인 필요)
- Platner 6/9 경선 77.7% 최종 인증치 미독립검증
- FEC 일부 수치 보도 기반

### 자동화 (2026-06-14 완료)
- ~~launchd 주간 스냅샷 활성화~~ — ✅ **`publish_weekly.sh` §4.5로 편입**(2026-08-13). 종전 기재("수집 파이프라인 스케줄러로 대체, 매일 09:00")는 **사실이 아니었다** — ⓐ 그 plist(`com.us-elections.pipeline.plist`)는 `.disabled`로 비활성 상태이고 ⓑ `run_pipeline.sh`는 애초에 스냅샷을 하지 않는다(헤드리스 Claude로 브리핑을 쓰는 별개 파이프라인). 스냅샷은 2026-06-08 1건에서 멈춰 있었다.
- `data/*`의 `*_delta` 자동화 — 스냅샷 경로가 복구됐으므로(위) 2주치가 쌓이면 delta 계산 스크립트 추가 가능. **선행 조건이었던 "스냅샷이 쌓이지 않는 문제"는 해소됨.**

### 선택
- 예보 종합표 일부 모델 수치(RacetotheWH·Silver Bulletin 본선 확률) — 슬롯 상태
- 뉴스레터 배포 채널 분리(Pages는 이메일 발송 불가 → Buttondown/Substack 등)
- `korea_watch_db.csv` 매일 append → 중복 누적 가능성 — dedup 래퍼 추가 검토
