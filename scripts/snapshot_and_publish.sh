#!/usr/bin/env bash
# 주기적 스냅샷 + 자동 배포 — 수동 실행 전용(2026-08-13부터).
#
# ⚠️ 정기 스냅샷은 이제 publish_weekly.sh §4.5가 담당한다. 이 스크립트를 launchd/cron에
#    다시 걸지 말 것 — 같은 스냅샷이 두 번 커밋된다. 동봉된 com.us-elections.snapshot.plist는
#    ~/Library/LaunchAgents/에 설치된 적이 없고(로그 디렉터리 미생성으로 확인) 설치하지 않는다.
#    이 파일은 주간 발행 밖에서 임시로 스냅샷을 남겨야 할 때만 손으로 실행한다.
#
# 하는 일:
#   1. data/*.json 의 현재 값이 직전 스냅샷과 다르면 data/history/<YYYY-MM-DD>/ 에 보관
#   2. 변경이 있으면 git commit + push  →  GitHub Actions 가 사이트를 재빌드
#
# 데이터 자체의 갱신(수치 수정)은 data/model_dashboard.json 등을 직접 편집하는 것으로 한다.
# 이 스크립트는 "기록을 주기적으로 남기고 배포"하는 역할만 한다.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

TODAY="$(date +%F)"
HIST="data/history/$TODAY"
LATEST_PREV="$(ls -d data/history/*/ 2>/dev/null | sort | tail -1 || true)"

# 직전 스냅샷과 현재 data/*.json 이 동일하면 아무것도 하지 않음 (빈 커밋 방지)
changed=1
if [ -n "$LATEST_PREV" ]; then
  changed=0
  for f in data/*.json data/*.csv; do
    [ -e "$f" ] || continue
    if ! cmp -s "$f" "$LATEST_PREV$(basename "$f")"; then changed=1; break; fi
  done
fi

if [ "$changed" -eq 0 ]; then
  echo "[$TODAY] 직전 스냅샷과 동일 — 건너뜀."
  exit 0
fi

mkdir -p "$HIST"
cp data/*.json data/*.csv "$HIST"/ 2>/dev/null || true

git add data/history "$HIST"
if git diff --cached --quiet; then
  echo "[$TODAY] 커밋할 변경 없음."
  exit 0
fi

git commit -m "snapshot: $TODAY 데이터 스냅샷" >/dev/null
git push origin main
echo "[$TODAY] 스냅샷 커밋 + push 완료 → Actions 재빌드 트리거됨."
