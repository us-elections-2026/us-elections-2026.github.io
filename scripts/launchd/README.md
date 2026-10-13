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

## 수집 품질 점검

`check_raw_briefing.py`의 원문 경고와 정리본의 주목 기관 누락 경고를 `senate_daily_log.json`의 날짜별 `source_validation`에 보존한다. 원문의 수집 결손도 정리본에 없더라도 보존하며, 사이트 일일 브리핑의 「수집 품질 점검」에 표시한다. 링크 누락은 원문에서 링크를 확인하지 못했다는 뜻이며 실제 수집 실패와 같다고 단정하지 않는다.

수집 담당자가 보충 여부를 판단할 때는 `python3 scripts/check_raw_briefing.py <원문.md> --strict`(경고 시 종료 코드 1) 또는 `--json`을 사용할 수 있다. 기본 발행은 기존처럼 경고를 보존해 표시하며 숫자·구조 대조는 기존 하드 게이트를 따른다. 로컬 표시 검증은 `python3 -m unittest discover -s tests`와 `Rscript tests/test_rendering.R`로 실행한다.

## 발행 실패와 정상 무변경 구분

`publish_daily.sh`는 루트 stdin의 `importlib` 호출로 원천 경로를 결정한다. 적재 모듈은 자신의 `scripts/` 경로에서 형제 검사 모듈을 찾도록 보장한다. 경로 결정·날짜 탐색·검사 프로그램·적재·렌더·push 실패는 비정상 종료하며, 정상적으로 탐색한 결과 새 날짜가 없을 때만 0으로 종료한다. zsh 검사 파이프라인에는 `pipefail`을 적용한다. 정확한 호출 방식과 실패 전파 검사는 `tests/test_daily_publisher.py`에 있다.

원문·정리본이 이미 생성된 발행 복구는 정리본 생성 래퍼를 다시 실행하지 않고 `scripts/publish_daily.sh --catchup`을 사용한다. 데이터·원격 커밋·Pages를 확인한 뒤 재실행이 정상 무변경으로 끝나는지 확인한다.
