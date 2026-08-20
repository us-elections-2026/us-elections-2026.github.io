#!/bin/zsh
# 주간호 자동 발행 헬퍼 — Cowork '월요일 로직'이 issue .qmd를 작성한 뒤 호출한다.
#   렌더 검증 → 커밋 → 최신 main 동기화(rebase) → push(main) → GitHub Actions 자동 배포.
#
# 사용: scripts/publish_issue.sh issues/2026-07-06.qmd
#
# 설계 원칙:
#   - 렌더가 깨지면 발행하지 않는다(깨진 페이지가 라이브로 나가지 않게).
#   - main 브랜치에서만 동작(오발행 방지). 커밋은 자동 발행이므로 main 직접(→자동배포).
#   - push 전 origin/main을 rebase로 흡수(병렬 커밋과 충돌 최소화). 충돌 시 중단하고 로컬 커밋 보존.
set -u
export LANG=en_US.UTF-8
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
# 레포 경로는 스크립트 위치에서 유도한다(publish_weekly.sh와 동일). 하드코딩된
# Dropbox 경로는 머신·클론 위치가 바뀌면 엉뚱한 사본을 발행한다.
REPO="${US_ELECTIONS_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"

ISSUE="${1:-}"
[ -n "$ISSUE" ] || { echo "[publish] 사용법: publish_issue.sh <issue.qmd>"; exit 2; }
cd "$REPO" || { echo "[publish] repo 접근 불가: $REPO"; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "[publish] git 레포가 아님: $REPO"; exit 1; }
[ -f "$ISSUE" ] || { echo "[publish] 파일 없음: $ISSUE"; exit 1; }

br=$(git branch --show-current)
[ "$br" = "main" ] || { echo "[publish] main 브랜치가 아님(현재 '$br') — 중단"; exit 1; }

echo "[publish] 데이터 무결성 검증(validate_data.R)"
Rscript scripts/validate_data.R || { echo "[publish] 데이터 검증 실패 — 발행 중단"; exit 1; }

echo "[publish] 렌더 검증: $ISSUE"
quarto render "$ISSUE" || { echo "[publish] 렌더 실패 — 발행 중단"; exit 1; }

# 이슈 + 이번 주 갱신된 data/ 파일(전국 환경 등)을 함께 스테이징
git add "$ISSUE" data/
if git diff --cached --quiet; then
  echo "[publish] 커밋할 변경 없음 — 종료(이미 발행됨)"; exit 0
fi
git commit -m "주간호 자동 발행: $(basename "$ISSUE" .qmd)" || { echo "[publish] 커밋 실패"; exit 1; }

echo "[publish] 최신 main 동기화(rebase)"
git fetch origin main && git rebase origin/main || {
  echo "[publish] rebase 충돌 — 수동 해결 필요(로컬 커밋은 보존됨)"; exit 1; }

git push origin main && echo "[publish] ✅ 발행·배포 트리거 완료: $ISSUE" || {
  echo "[publish] push 실패"; exit 1; }
