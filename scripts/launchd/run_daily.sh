#!/bin/zsh
# 상원 일일 정리본 생성 + 사이트 발행 — 호스트(Mac Studio) launchd 래퍼 (2026-10-08, Cowork 10:15 작업 대체)
#
# 설치 위치: ~/.local/us_elections/run_daily.sh (TCC 비보호 경로; 이 파일의 사본 — 고치면 다시 복사)
# 호출: launchd(com.kang.us-elections-daily, 매일 10:15 KST) 또는 사람이 직접 `run_daily.sh [YYYY-MM-DD]`
# 환경변수: DIGEST_ONLY=1 → 정리본만 만들고 발행 생략 · US_ELECTIONS_REPO → 발행용 저장소(기본 ~/code 클론, 없으면 Dropbox 저장소)
# 전제: launchd 잡은 /bin/zsh로 뜨므로 /bin/zsh에 전체 디스크 접근(FDA)이 있어야 Dropbox CloudStorage를 읽는다(2026-10-08 실측).
#
# 동작: ① 원문(_NIS senate_daily/<날짜>_일일브리핑_KR.md) 확인
#       ② 정리본이 없으면 `claude -p`로 작성 — 정리 프롬프트 §2·§3 규칙; 프롬프트+원문을 stdin으로 넣고 stdout을 받는다(도구 권한 불필요)
#       ③ check_site_digest.py 대조, 실패 시 지적문을 붙여 한 번 재생성, 또 실패면 site/failed/에 두고 원문 전재로 진행
#       ④ publish_daily.sh --catchup (밀린 날짜 포함) · 로그 ~/.cache/us_elections/daily.log
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 TZ=Asia/Seoul

NIS="$HOME/Library/CloudStorage/Dropbox/_NIS/2026_senate_election/2026_midterm_outlook"
REPO="${US_ELECTIONS_REPO:-$HOME/code/us_elections.github.io}"
[ -d "$REPO/.git" ] || REPO="$HOME/Library/CloudStorage/Dropbox/gitpages/us_elections.github.io"
PROMPT="$NIS/pipeline_prompts/상원_일일_사이트정리_프롬프트.md"
LOGDIR="$HOME/.cache/us_elections"; LOG="$LOGDIR/daily.log"; mkdir -p "$LOGDIR"
DATE="${1:-$(date +%F)}"
RAW="$NIS/senate_daily/${DATE}_일일브리핑_KR.md"
DIGEST="$NIS/senate_daily/site/${DATE}_site_KR.md"
log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; echo "[run_daily] $*"; }

echo "===== $(date '+%F %T') run_daily.sh $DATE · user=$(id -un) · HOME=$HOME · repo=$REPO =====" >> "$LOG"

# ① 원문 — TCC로 읽기가 막히면 'Operation not permitted': 시스템 설정 > 개인정보 보호 및 보안 > 전체 디스크 접근 권한에 /bin/zsh 추가
if ! ls "$NIS/senate_daily" >/dev/null 2>&1; then
  log "✗ _NIS 폴더 읽기 불가(TCC): $(ls "$NIS/senate_daily" 2>&1 | head -1) — /bin/zsh에 전체 디스크 접근 권한 필요"; exit 1
fi
[ -r "$RAW" ] || log "원문 없음(아직 수집 전이거나 결손): $(basename "$RAW") — 발행만 catch-up"

# ② 정리본
gen() {  # $1 = 재시도 시 붙일 지적문
  {
    cat "$PROMPT"; echo; echo
    echo "===== 오늘($DATE) 원문 — senate_daily/${DATE}_일일브리핑_KR.md ====="; cat "$RAW"; echo; echo
    echo "===== 지시 ====="
    echo "위 정리 프롬프트의 §2(형식)·§2-1(조사 표)·§2-2(문체)·§3(금지) 규칙대로, 위 원문의 사이트 정리본을 작성하라."
    echo "§1·§4·§5(경로·발행·보고)는 하지 말 것 — 이 래퍼 스크립트가 저장·대조·발행을 한다. 웹 검색·도구 사용 없이 원문만으로 쓴다."
    echo "출력은 정리본 마크다운 본문만. 코드펜스·머리말·설명·질문을 붙이지 말 것. 첫 줄은 정확히: # 2026 상원 선거 일일 브리핑 — $DATE (사이트 정리본)"
    [ -n "${1:-}" ] && { echo; echo "===== 직전 시도의 대조 실패 지적(원문과 맞춰 고칠 것) ====="; echo "$1"; }
  } | claude -p --output-format text 2>>"$LOG"
}
if [ -r "$RAW" ] && [ ! -s "$DIGEST" ]; then
  TMP="$LOGDIR/${DATE}_site_KR.tmp.md"
  gen "" > "$TMP"
  if ! head -1 "$TMP" | grep -q "^# 2026 상원 선거 일일 브리핑"; then
    log "✗ 정리본 출력이 정리본 형식이 아님($(wc -c < "$TMP" | tr -d ' ') bytes) — 원문 전재로 진행"; mv "$TMP" "$LOGDIR/${DATE}_site_KR.badformat.md"
  else
    CHK="$(cd "$REPO" && python3 scripts/check_site_digest.py "$RAW" "$TMP" 2>&1)"; rc=$?
    if [ $rc -ne 0 ]; then
      log "정리본 대조 실패(1차) — 지적문을 붙여 재생성"; echo "$CHK" | tail -20 >> "$LOG"
      gen "$(echo "$CHK" | tail -40)" > "$TMP"
      CHK="$(cd "$REPO" && python3 scripts/check_site_digest.py "$RAW" "$TMP" 2>&1)"; rc=$?
    fi
    if [ $rc -eq 0 ]; then
      mkdir -p "$(dirname "$DIGEST")" && mv "$TMP" "$DIGEST" && log "✓ 정리본 저장: site/$(basename "$DIGEST") ($(wc -c < "$DIGEST" | tr -d ' ') bytes)"
    else
      mkdir -p "$NIS/senate_daily/site/failed"; mv "$TMP" "$NIS/senate_daily/site/failed/${DATE}_site_KR.failed.md"
      log "✗ 정리본 대조 2회 실패 — site/failed/ 에 두고 원문 전재로 진행"; echo "$CHK" | tail -20 >> "$LOG"
    fi
  fi
elif [ -s "$DIGEST" ]; then
  log "정리본 이미 있음: site/$(basename "$DIGEST")"
fi

# ④ 발행
[ "${DIGEST_ONLY:-0}" = "1" ] && { log "DIGEST_ONLY — 발행 생략"; exit 0; }
cd "$REPO" || { log "✗ repo 접근 불가: $REPO"; exit 1; }
git checkout -q main 2>>"$LOG"; git pull -q --rebase origin main 2>>"$LOG"
US_ELECTIONS_REPO="$REPO" PD_LOG="$LOG" scripts/publish_daily.sh --catchup >> "$LOG" 2>&1; rc=$?
log "publish_daily.sh --catchup exit=$rc"
exit $rc
