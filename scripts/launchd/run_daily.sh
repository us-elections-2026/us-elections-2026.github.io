#!/bin/zsh
# 상원 일일 정리본 생성 + 사이트 발행 — 호스트(Mac Studio) launchd 래퍼 (2026-10-08, Cowork 10:15 작업 대체)
#
# 설치 위치: ~/.local/us_elections/run_daily.sh (TCC 비보호 경로; 이 파일의 사본 — 고치면 다시 복사)
# 호출: launchd(com.kang.us-elections-daily, 매일 10:15 KST) 또는 사람이 직접 `run_daily.sh [YYYY-MM-DD]`(날짜를 주면 그 날만, 없으면 최근 7일 보충)
# 잠자기: launchd 달력 작업은 잠자기 중 안 돌고 깨어나면 1회 보충 실행 → 원문 도착 20분 대기 + 최근 7일 정리본 보충으로 빈틈을 메운다.
# 환경변수: DIGEST_ONLY=1 → 정리본만 만들고 발행 생략 · US_ELECTIONS_REPO → 발행용 저장소(기본 ~/code 클론, 없으면 Dropbox 저장소)
# 전제: launchd 잡은 /bin/zsh로 뜨므로 /bin/zsh에 전체 디스크 접근(FDA)이 있어야 Dropbox CloudStorage를 읽는다(2026-10-08 실측).
#
# 동작: ① 원문(_NIS senate_daily/<날짜>_일일브리핑_KR.md) 확인
#       ② 최근 7일 중 원문은 있고 정리본이 없는 날짜마다 `claude -p`로 작성 — 정리 프롬프트 §2·§3 규칙; 프롬프트+원문을 stdin으로 넣고 stdout을 받는다(도구 권한 불필요)
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
log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; echo "[run_daily] $*"; }

echo "===== $(date '+%F %T') run_daily.sh $DATE · user=$(id -un) · HOME=$HOME · repo=$REPO =====" >> "$LOG"

# ① 폴더 접근 — TCC로 막히면 'Operation not permitted': 시스템 설정 > 개인정보 보호 및 보안 > 전체 디스크 접근 권한에 /bin/zsh 추가
if ! ls "$NIS/senate_daily" >/dev/null 2>&1; then
  log "✗ _NIS 폴더 읽기 불가(TCC): $(ls "$NIS/senate_daily" 2>&1 | head -1) — /bin/zsh에 전체 디스크 접근 권한 필요"; exit 1
fi
# 잠자기에서 깨어난 직후면 Dropbox가 07:12 원문을 아직 안 내려받았을 수 있다 — 오늘 원문을 최대 20분(60초×20) 기다린다
RAW_TODAY="$NIS/senate_daily/${DATE}_일일브리핑_KR.md"
if [ ! -r "$RAW_TODAY" ] && [ -z "${1:-}" ]; then
  for i in {1..20}; do [ -r "$RAW_TODAY" ] && break; sleep 60; done
  [ -r "$RAW_TODAY" ] && log "원문 도착 대기 ${i}분 후 확인" || log "원문 없음(20분 대기 후에도): $(basename "$RAW_TODAY") — 발행만 catch-up"
fi

# ② 정리본 — 오늘뿐 아니라 최근 7일 중 원문은 있는데 정리본이 없는 날짜 전부(잠자기로 하루를 통째로 놓친 경우 보충)
gen() {  # $1 = 날짜 · $2 = 재시도 시 붙일 지적문
  local D="$1" R="$NIS/senate_daily/$1_일일브리핑_KR.md"
  {
    cat "$PROMPT"; echo; echo
    echo "===== 오늘($D) 원문 — senate_daily/${D}_일일브리핑_KR.md ====="; cat "$R"; echo; echo
    echo "===== 지시 ====="
    echo "위 정리 프롬프트의 §2(형식)·§2-1(조사 표)·§2-2(문체)·§3(금지) 규칙대로, 위 원문의 사이트 정리본을 작성하라."
    echo "§1·§4·§5(경로·발행·보고)는 하지 말 것 — 이 래퍼 스크립트가 저장·대조·발행을 한다. 웹 검색·도구 사용 없이 원문만으로 쓴다."
    echo "출력은 정리본 마크다운 본문만. 코드펜스·머리말·설명·질문을 붙이지 말 것. 첫 줄은 정확히: # 2026 상원 선거 일일 브리핑 — $D (사이트 정리본)"
    [ -n "${2:-}" ] && { echo; echo "===== 직전 시도의 대조 실패 지적(원문과 맞춰 고칠 것) ====="; echo "$2"; }
  } | claude -p --output-format text 2>>"$LOG"
}
make_digest() {  # $1 = 날짜
  local D="$1" RAW="$NIS/senate_daily/$1_일일브리핑_KR.md" DIGEST="$NIS/senate_daily/site/$1_site_KR.md" TMP CHK rc
  [ -r "$RAW" ] || return 0
  [ -s "$DIGEST" ] && { log "정리본 이미 있음: site/$(basename "$DIGEST")"; return 0; }
  [ -s "$NIS/senate_daily/site/failed/${D}_site_KR.failed.md" ] && { log "정리본 실패분 있음(site/failed/) — $D 재시도 안 함"; return 0; }
  TMP="$LOGDIR/${D}_site_KR.tmp.md"
  gen "$D" "" > "$TMP"
  if ! head -1 "$TMP" | grep -q "^# 2026 상원 선거 일일 브리핑"; then
    log "✗ $D 정리본 출력이 정리본 형식이 아님($(wc -c < "$TMP" | tr -d ' ') bytes) — 원문 전재로 진행"; mv "$TMP" "$LOGDIR/${D}_site_KR.badformat.md"; return 0
  fi
  CHK="$(cd "$REPO" && python3 scripts/check_site_digest.py "$RAW" "$TMP" 2>&1)"; rc=$?
  if [ $rc -ne 0 ]; then
    log "$D 정리본 대조 실패(1차) — 지적문을 붙여 재생성"; echo "$CHK" | tail -20 >> "$LOG"
    gen "$D" "$(echo "$CHK" | tail -40)" > "$TMP"
    CHK="$(cd "$REPO" && python3 scripts/check_site_digest.py "$RAW" "$TMP" 2>&1)"; rc=$?
  fi
  if [ $rc -eq 0 ]; then
    mkdir -p "$(dirname "$DIGEST")" && mv "$TMP" "$DIGEST" && log "✓ 정리본 저장: site/$(basename "$DIGEST") ($(wc -c < "$DIGEST" | tr -d ' ') bytes)"
  else
    mkdir -p "$NIS/senate_daily/site/failed"; mv "$TMP" "$NIS/senate_daily/site/failed/${D}_site_KR.failed.md"
    log "✗ $D 정리본 대조 2회 실패 — site/failed/ 에 두고 원문 전재로 진행"; echo "$CHK" | tail -20 >> "$LOG"
  fi
}
if [ -n "${1:-}" ]; then
  make_digest "$DATE"
else
  for k in 6 5 4 3 2 1 0; do make_digest "$(date -v-${k}d +%F)"; done
fi

# ④ 발행
[ "${DIGEST_ONLY:-0}" = "1" ] && { log "DIGEST_ONLY — 발행 생략"; exit 0; }
cd "$REPO" || { log "✗ repo 접근 불가: $REPO"; exit 1; }
git checkout -q main 2>>"$LOG"; git pull -q --rebase origin main 2>>"$LOG"
US_ELECTIONS_REPO="$REPO" PD_LOG="$LOG" scripts/publish_daily.sh --catchup >> "$LOG" 2>&1; rc=$?
log "publish_daily.sh --catchup exit=$rc"
exit $rc
