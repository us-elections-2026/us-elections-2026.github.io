#!/bin/zsh
# 주간 발행 묶음 — Cowork 루틴이 issue.qmd 작성 + data/*.json 정규화를 마친 뒤 마지막에 호출한다.
#   결정론 파트(FRED·FEC 취득 · Korea Watch 동기화)를 실행한 다음,
#   데이터 검증 → 전체 렌더 → 커밋 → origin/main rebase → push(main) → GitHub Actions 배포.
#
# 사용: scripts/publish_weekly.sh
#
# 설계 원칙(publish_issue.sh 계승):
#   - 렌더가 깨지면 발행하지 않는다(깨진 페이지가 라이브로 나가지 않게).
#   - main 브랜치에서만 동작. push 전 origin/main을 rebase로 흡수(병렬 커밋 충돌 최소화).
#   - fetch 스크립트는 키가 없거나 실패해도 '경고 후 계속'(부분 갱신 허용). 검증·렌더는 하드 게이트.
#   - LLM이 하는 프로즈 작성·수치 정규화는 이 스크립트 밖(루틴)에서 끝낸 상태로 가정한다.
set -u
export LANG=en_US.UTF-8
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
# 레포 경로는 스크립트 위치에서 유도한다(snapshot_and_publish.sh와 동일 방식).
# 종전에는 Dropbox 경로를 하드코딩했는데, 그러면 클론을 옮기거나 머신마다 위치가
# 다를 때 조용히 엉뚱한 사본을 발행한다. US_ELECTIONS_REPO로 덮어쓸 수 있다.
REPO="${US_ELECTIONS_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"

cd "$REPO" || { echo "[weekly] repo 접근 불가: $REPO"; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "[weekly] git 레포가 아님: $REPO"; exit 1; }
br=$(git branch --show-current)
[ "$br" = "main" ] || { echo "[weekly] main 브랜치가 아님(현재 '$br') — 중단"; exit 1; }

# Dropbox 동기화 충돌 사본 차단 — 하드 게이트.
#   §5가 `git add data/ issues/ states/ ./*.qmd`로 디렉터리째 스테이징하고,
#   _quarto.yml의 render 목록은 "*.qmd"·"issues/" 같은 glob이다. 따라서
#   "senate (Woo's conflicted copy 2026-08-20).qmd" 한 개가 생기면
#   스테이징 → 커밋 → push → CI가 glob으로 잡아 렌더 → 낡은 중복 페이지가
#   그대로 라이브로 나간다. 렌더도 검증도 이걸 오류로 보지 않는다(문법은 정상).
#   두 머신이 Dropbox로 같은 작업 사본을 공유하는 구조에서 실제로 발생 가능하다.
conflicts=$(find . -path ./.git -prune -o \
  \( -iname '*conflicted copy*' -o -iname '*충돌*사본*' -o -iname '*conflicted-copy*' \) -print 2>/dev/null)
if [ -n "$conflicts" ]; then
  echo "[weekly] ✗ Dropbox 충돌 사본이 있어 중단합니다 — 발행 전에 정리하세요:"
  echo "$conflicts" | sed 's/^/    /'
  exit 1
fi

echo "[weekly] 최신 main 동기화(pull --ff-only)"
git fetch origin main -q && git merge --ff-only origin/main -q 2>/dev/null || echo "[weekly] (ff-only 불가 — 로컬 커밋 존재, 계속)"

# 1) 결정론 데이터 취득 — 키 없거나 실패 시 경고 후 계속(하드 실패 아님)
if [ -n "${FRED_API_KEY:-}" ]; then
  echo "[weekly] FRED 경제지표 취득"; python3 scripts/fetch_national_econ.py || echo "[weekly] ! FRED 실패(건너뜀)"
else echo "[weekly] ! FRED_API_KEY 없음 — national_econ 건너뜀"; fi
if [ -n "${FEC_API_KEY:-}" ]; then
  echo "[weekly] FEC 모금 취득(스테이징)"; python3 scripts/fetch_fec_fundraising.py || echo "[weekly] ! FEC 실패(건너뜀)"
else echo "[weekly] ! FEC_API_KEY 없음 — fec_fundraising 건너뜀"; fi

# 1.5) Cook 하원 등급 자동 취득(270towin 재게시분 · 435개구 해독) — 실패해도 계속
echo "[weekly] Cook 하원 등급 취득"
python3 scripts/fetch_cook_house.py || echo "[weekly] ! Cook 취득 실패(건너뜀 — 직전 데이터 유지)"

# 1.6) 상원·주지사 등급 피드 취득(270towin 재게시분) — 실패해도 계속
echo "[weekly] 상원·주지사 등급 취득"
python3 scripts/fetch_senate_ratings.py || echo "[weekly] ! 상원 등급 취득 실패(건너뜀)"
python3 scripts/fetch_governor_ratings.py || echo "[weekly] ! 주지사 등급 취득 실패(건너뜀)"
# 등급이 바뀐 주만 이력에 축적(동일하면 미기록) — 주지사 변동 매트릭스의 원천
python3 scripts/snapshot_ratings.py || echo "[weekly] ! 등급 스냅샷 실패(건너뜀)"

# 1.7) 예측시장 원가격(Kalshi 공개 API) — 270towin의 '등급 환산값'이 아니라 가격 자체
echo "[weekly] Kalshi 예측시장 가격 취득"
python3 scripts/fetch_kalshi_prices.py || echo "[weekly] ! Kalshi 가격 취득 실패(건너뜀 — 직전 값 유지)"
# 외부 모델 확률 — 원천이 구조화 데이터로 확인되는 DDHQ만 자동 취득
python3 scripts/fetch_ddhq_forecast.py || echo "[weekly] ! DDHQ 예측 취득 실패(건너뜀 — 직전 값 유지)"
python3 scripts/fetch_rtwh_forecast.py || echo "[weekly] ! RtWH 예측 취득 실패(건너뜀 — 직전 값 유지)"

# 1.8) 개별 조사 원자료(조사기관별 시계열·하우스 이펙트) — 집계기관 평균과는 다른 층
echo "[weekly] 조사기관별 개별 조사 취득"
python3 scripts/fetch_pollster_polls.py || echo "[weekly] ! 개별 조사 취득 실패(건너뜀 — 직전 값 유지)"

# 2) Korea Watch 동기화(_NIS DB → data/korea_watch.csv, idempotent)
echo "[weekly] Korea Watch 동기화"
python3 scripts/sync_korea_watch.py || echo "[weekly] ! KW 동기화 경고(계속)"

# 2.5) 자체 모델 v0 재실행 (senate_polls.csv·등급·시장가 최신분 반영 → data/model_v0.json)
if [ -f scripts/model/run_model.R ]; then
  echo "[weekly] 자체 모델 v0 실행"
  Rscript scripts/model/run_model.R || echo "[weekly] ! 모델 실행 실패(건너뜀 — 직전 산출물 유지)"
fi

# 2.7) 예보 종합표 조립 — 위에서 취득한 Kalshi·DDHQ·RtWH와 자체 모델 v0에서 생성.
#      (반드시 2.5 모델 실행 뒤에 와야 자체 모델 행이 최신값으로 들어간다)
echo "[weekly] 예보 종합표 생성"
python3 scripts/build_forecast.py || echo "[weekly] ! 예보 종합표 생성 실패(건너뜀 — 직전 값 유지)"

# 3) 데이터 무결성 검증 — 하드 게이트
echo "[weekly] 데이터 검증(validate_data.R)"
Rscript scripts/validate_data.R || { echo "[weekly] 데이터 검증 실패 — 발행 중단"; exit 1; }

# 4) 전체 렌더 — 하드 게이트(깨지면 발행 안 함)
echo "[weekly] 전체 렌더(quarto render)"
quarto render || { echo "[weekly] 렌더 실패 — 발행 중단"; exit 1; }

# 4.5) 주간 스냅샷 — 검증·렌더를 통과한 상태만 data/history/<날짜>/에 보관.
#      편집 3원칙 ②(delta 추적)의 "지난 값"이 여기서 나온다. 다음 §5의 git add data/ 에 포함돼
#      주간 발행 커밋과 함께 나간다(별도 커밋·push 없음).
#      2026-08-13: 종전에는 snapshot_and_publish.sh를 launchd(월 09:10)가 돌기로 돼 있었으나
#      plist가 ~/Library/LaunchAgents/에 설치된 적이 없어 한 번도 실행되지 않았다(로그 디렉터리
#      미생성으로 확인). 스냅샷이 2026-06-08 1건에 머물러 delta 추적이 불가능했으므로,
#      실행이 커밋으로 증명되는 이 주간 경로에 편입했다. 스케줄러를 하나 더 세우지 않는다.
#      glob 대신 find를 쓰는 이유: 이 스크립트는 zsh이고, zsh는 매치가 없으면 "no matches
#      found"를 stderr로 뱉는다(bash처럼 조용히 리터럴로 두지 않는다). 첫 실행이나 history/가
#      빈 클론에서 발행 로그에 가짜 에러가 남는다.
SNAP_TODAY="$(date +%F)"
SNAP_HIST="data/history/$SNAP_TODAY"
SNAP_PREV="$(find data/history -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -1)"
snap_changed=1
if [ -n "$SNAP_PREV" ]; then
  snap_changed=0
  for f in $(find data -maxdepth 1 -type f \( -name '*.json' -o -name '*.csv' \) | sort); do
    cmp -s "$f" "$SNAP_PREV/$(basename "$f")" || { snap_changed=1; break; }
  done
fi
if [ "$snap_changed" -eq 0 ]; then
  echo "[weekly] 스냅샷 건너뜀 — 직전($SNAP_PREV)과 동일"
else
  echo "[weekly] 주간 스냅샷 → $SNAP_HIST"
  mkdir -p "$SNAP_HIST" \
    && find data -maxdepth 1 -type f \( -name '*.json' -o -name '*.csv' \) -exec cp {} "$SNAP_HIST"/ \; \
    || echo "[weekly] ! 스냅샷 실패(건너뜀 — 발행은 계속)"
fi

# 5) 스테이징·커밋·push (data/ + issues/ + states/ + governors/ + 최상위 .qmd)
# governors/ 가 빠져 있었다(2026-08-30 발견) — 주지사 State Focus 8곳은 CLAUDE.md가
# 관리 대상으로 명시한 디렉터리인데 스테이징 목록에 없어, 그쪽을 고쳐도 주간 발행에
# 실리지 않고 조용히 남았다. R/·assets/·theme/ 은 코드·스타일이라 의도적으로 제외한다
# (사람이 별도 커밋한다).
git add data/ issues/ states/ governors/ ./*.qmd
if git diff --cached --quiet; then
  echo "[weekly] 커밋할 변경 없음 — 종료(이미 최신)"; exit 0
fi
STAMP=$(git log -1 --format=%cd --date=format:%Y-%m-%d 2>/dev/null)
git commit -m "주간 자동 발행: data·issue·standing 갱신 (${STAMP:-latest})" \
  -m "publish_weekly.sh: FRED·FEC·KW 동기화 + 루틴 정규화분 포함. 원천 _NIS 주간." \
  || { echo "[weekly] 커밋 실패"; exit 1; }

echo "[weekly] origin/main rebase"
git fetch origin main -q && git rebase origin/main || {
  echo "[weekly] rebase 충돌 — 수동 해결 필요(로컬 커밋 보존됨)"; exit 1; }

git push origin main && echo "[weekly] ✅ 발행·배포 트리거 완료" || { echo "[weekly] push 실패"; exit 1; }
