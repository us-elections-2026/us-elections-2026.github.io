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
REPO="$HOME/Library/CloudStorage/Dropbox/gitpages/us_elections.github.io"

cd "$REPO" || { echo "[weekly] repo 접근 불가: $REPO"; exit 1; }
br=$(git branch --show-current)
[ "$br" = "main" ] || { echo "[weekly] main 브랜치가 아님(현재 '$br') — 중단"; exit 1; }

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

# 2) Korea Watch 동기화(_NIS DB → data/korea_watch.csv, idempotent)
echo "[weekly] Korea Watch 동기화"
python3 scripts/sync_korea_watch.py || echo "[weekly] ! KW 동기화 경고(계속)"

# 2.5) 자체 모델 v0 재실행 (senate_polls.csv·등급·시장가 최신분 반영 → data/model_v0.json)
if [ -f scripts/model/run_model.R ]; then
  echo "[weekly] 자체 모델 v0 실행"
  Rscript scripts/model/run_model.R || echo "[weekly] ! 모델 실행 실패(건너뜀 — 직전 산출물 유지)"
fi

# 3) 데이터 무결성 검증 — 하드 게이트
echo "[weekly] 데이터 검증(validate_data.R)"
Rscript scripts/validate_data.R || { echo "[weekly] 데이터 검증 실패 — 발행 중단"; exit 1; }

# 4) 전체 렌더 — 하드 게이트(깨지면 발행 안 함)
echo "[weekly] 전체 렌더(quarto render)"
quarto render || { echo "[weekly] 렌더 실패 — 발행 중단"; exit 1; }

# 5) 스테이징·커밋·push (data/ + issues/ + states/ + 최상위 .qmd)
git add data/ issues/ states/ ./*.qmd
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
