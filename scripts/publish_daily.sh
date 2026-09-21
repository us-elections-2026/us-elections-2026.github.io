#!/bin/zsh
# 일일 발행 — 상원 일일 브리핑(KR)을 data/senate_daily_log.json 에 적재하고 사이트를 재발행한다.
#   Cowork 상원 일일 작업(~07:00 KST)이 _NIS senate_daily/ 에 파일을 남긴 뒤,
#   별도 Cowork 예약 작업(10:15 KST)이 이 스크립트를 호출한다(publish_weekly.sh와 같은 방식).
#
# 사용: scripts/publish_daily.sh [YYYY-MM-DD]     # 날짜 생략 시 오늘(KST)
#       DRY_RUN=1 scripts/publish_daily.sh          # push 직전까지만(커밋 안 함)
#
# 설계 원칙(publish_weekly.sh 계승):
#   - main 브랜치에서만 동작. Dropbox 충돌 사본이 있으면 중단.
#   - 그날 일일 브리핑이 없으면 '발행 없음'으로 정상 종료(0) — 결손을 만들어 채우지 않는다.
#   - 검증(validate_data.R)·렌더(quarto render)는 하드 게이트. 깨지면 발행하지 않는다.
#   - 스테이징은 data/senate_daily_log.json 한 파일만. 사람이 편집 중인 다른 파일을 딸려 보내지 않는다
#     (주간 발행은 디렉터리째 스테이징하지만, 일일은 매일 돌므로 범위를 좁힌다).
#   - 주간 발행(일요일 밤)과 시간대가 겹치지 않는다. 겹치더라도 rebase로 흡수한다.
set -u
export LANG=en_US.UTF-8
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
REPO="${US_ELECTIONS_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG="data/senate_daily_log.json"
POLLS="data/senate_polls.csv"

cd "$REPO" || { echo "[daily] repo 접근 불가: $REPO"; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "[daily] git 레포가 아님: $REPO"; exit 1; }
br=$(git branch --show-current)
[ "$br" = "main" ] || { echo "[daily] main 브랜치가 아님(현재 '$br') — 중단"; exit 1; }

# Dropbox 충돌 사본 차단 — publish_weekly.sh와 같은 패턴(한글 리터럴 금지, NFD 문제)
conflicts=$(find . -path ./.git -prune -o -path ./.claude -prune -o -path ./_site -prune -o \
  \( -iname '* (*[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])*' \
     -o -iname '*conflicted copy*' -o -iname '*conflicted-copy*' \) -print 2>/dev/null)
if [ -n "$conflicts" ]; then
  echo "[daily] ✗ Dropbox 충돌 사본이 있어 중단합니다:"; echo "$conflicts" | sed 's/^/    /'; exit 1
fi

# 로그·조사 CSV에 미커밋 변경이 있으면(사람이 손댄 것) 덮어쓰지 않는다
for f in "$LOG" "$POLLS"; do
  if ! git diff --quiet -- "$f" 2>/dev/null; then
    echo "[daily] ✗ $f 에 미커밋 변경이 있어 중단 — 먼저 커밋하거나 되돌리세요"; exit 1
  fi
done

echo "[daily] 최신 main 동기화(pull --ff-only)"
git fetch origin main -q && git merge --ff-only origin/main -q 2>/dev/null || echo "[daily] (ff-only 불가 — 로컬 커밋 존재, 계속)"

# 0.5) 사이트 정리본 대조 — 하드 게이트 (2026-09-21)
#      10:15 Cowork 작업이 원문을 압축한 정리본(site/<날짜>_site_KR.md)이 있으면, 그 안의 모든 숫자가
#      원문에 존재하는지·9주 소절과 네 요소가 갖춰졌는지 확인한다. 실패하면 발행하지 않는다.
#      정리본이 없으면 원문을 그대로 싣는다(종전 방식).
DATE="${1:-$(TZ=Asia/Seoul date +%F)}"
SRC_DIR="$(python3 - <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ing", "scripts/ingest_senate_daily.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m.DEFAULT_SRC)
PY
)"
RAW="$SRC_DIR/${DATE}_일일브리핑_KR.md"; DIGEST="$SRC_DIR/site/${DATE}_site_KR.md"
if [ -f "$DIGEST" ]; then
  echo "[daily] 정리본 대조: site/$(basename "$DIGEST")"
  python3 scripts/check_site_digest.py "$RAW" "$DIGEST" || { echo "[daily] 정리본 대조 실패 — 발행 중단(정리본을 고친 뒤 재실행)"; exit 1; }
else
  echo "[daily] 정리본 없음 — 원문을 그대로 싣는다"
fi

# 1) 적재 — 그날 파일이 없으면 정상 종료(2 → 0). 결손은 페이지에 그대로 비워 둔다.
echo "[daily] 상원 일일 브리핑 적재: $DATE"
python3 scripts/ingest_senate_daily.py --date "$DATE"
rc=$?
if [ $rc -eq 2 ]; then echo "[daily] $DATE 일일 브리핑 없음 — 발행하지 않음(정상 종료)"; exit 0; fi
[ $rc -eq 0 ] || { echo "[daily] 적재 실패(rc=$rc) — 중단"; exit 1; }

# 1.5) 여론조사 — 정리본의 「새로운 여론조사」 고정 표에서 본선 조사를 뽑아
#      senate_polls.csv 에 append. 같은 조사는 몇 번 언급돼도 한 행(중복 제거는 스크립트가 한다).
#      날짜·%·URL 중 하나라도 '?'이면 append 하지 않고 후보 파일에만 남긴다.
echo "[daily] 여론조사 표 → senate_polls.csv"
python3 scripts/extract_daily_polls.py --date "$DATE" --apply || echo "[daily] ! 조사 추출 실패(건너뜀 — CSV 미변경)"

if git diff --quiet -- "$LOG" "$POLLS"; then
  echo "[daily] 로그·조사 변경 없음(이미 적재된 날짜) — 종료"; exit 0
fi

# 2) 데이터 검증 — 하드 게이트
echo "[daily] 데이터 검증(validate_data.R)"
Rscript scripts/validate_data.R || { echo "[daily] 데이터 검증 실패 — 발행 중단"; git checkout -- "$LOG" "$POLLS"; exit 1; }

# 3) 렌더 — 하드 게이트. 일일 로그는 states/ 9쪽 + dashboard 에만 실리지만,
#    CI가 전체를 다시 렌더하므로 로컬도 전체를 돌려 깨진 곳이 없는지 본다.
echo "[daily] 전체 렌더(quarto render)"
quarto render || { echo "[daily] 렌더 실패 — 발행 중단"; git checkout -- "$LOG" "$POLLS"; exit 1; }

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "[daily] DRY_RUN — 커밋·push 생략. 변경 요약:"; git diff --stat -- "$LOG" "$POLLS"; exit 0
fi

# 4) 커밋·push — 로그 + 조사 CSV 두 파일만
git add "$LOG" "$POLLS"
NPOLL=$(git diff --cached --numstat -- "$POLLS" | awk '{print $1+0}')
git commit -m "일일 자동 발행: 상원 일일 로그 ($DATE)${NPOLL:+ · 조사 +${NPOLL}행}" \
  -m "publish_daily.sh: _NIS senate_daily/${DATE}_일일브리핑_KR.md → data/senate_daily_log.json(일일 절) + senate_polls.csv(고정 표 추출, 중복 제거)." \
  || { echo "[daily] 커밋 실패"; exit 1; }

echo "[daily] origin/main rebase"
git fetch origin main -q && git rebase origin/main || {
  echo "[daily] rebase 충돌 — 수동 해결 필요(로컬 커밋 보존됨)"; exit 1; }

git push origin main && echo "[daily] ✅ 발행·배포 트리거 완료 ($DATE)" || { echo "[daily] push 실패"; exit 1; }
