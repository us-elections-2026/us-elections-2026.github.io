# 상원 일일 정리·발행 — 호스트 launchd (2026-10-08)

Cowork 10:15 작업(샌드박스/클라우드 루틴에서만 돌아 Dropbox 접근 불가)을 대체한다. 매일 10:15 KST에 `run_daily.sh`가
정리본을 `claude -p`로 만들고(`check_site_digest.py` 대조), `publish_daily.sh --catchup`으로 발행한다.

## 설치 (Mac Studio, 1회)
```
mkdir -p ~/.local/us_elections ~/.cache/us_elections
cp scripts/launchd/run_daily.sh ~/.local/us_elections/run_daily.sh && chmod +x ~/.local/us_elections/run_daily.sh
cp scripts/launchd/com.kang.us-elections-daily.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kang.us-elections-daily.plist
```
**전제(사람이 1회)**: 시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 권한 → `+` → `/bin/zsh` 추가.
launchd가 띄우는 잡은 /bin/zsh가 책임 프로세스라 이 권한이 없으면 `~/Library/CloudStorage/Dropbox/…` 읽기가
`Operation not permitted`로 막힌다(2026-10-08 실측, 2026-08 파이프라인도 같은 원인으로 실패).
발행용 저장소는 `~/code/us_elections.github.io`(Dropbox 밖 클론) — 없으면 Dropbox 저장소를 쓴다.

## 시험·운영
```
launchctl kickstart -k gui/$(id -u)/com.kang.us-elections-daily   # 지금 한 번 실행(launchd 맥락)
tail -20 ~/.cache/us_elections/daily.log                            # 결과
~/.local/us_elections/run_daily.sh 2026-10-07                       # 특정 날짜를 사람이 직접(터미널 맥락)
DIGEST_ONLY=1 ~/.local/us_elections/run_daily.sh                    # 정리본만
launchctl bootout gui/$(id -u)/com.kang.us-elections-daily          # 중지
```
성공 판정: `daily.log`에 `✓ 정리본 저장` + `✅ 발행·배포 트리거 완료`, `senate_daily/site/<날짜>_site_KR.md` 생성, 커밋 `일일 자동 발행: …`.
래퍼를 고치면 `scripts/launchd/run_daily.sh`를 고치고 `~/.local/us_elections/`로 다시 복사한다(정본은 저장소).
