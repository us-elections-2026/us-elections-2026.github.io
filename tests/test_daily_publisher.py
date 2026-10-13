"""실제 zsh 발행과 루트 stdin importlib 호출의 회귀 검사. Git/R/Quarto는 격리 fixture다."""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
ACTIVE = {'raw', 'digest', 'ingest', 'validation', 'render', 'push'}
PRELUDE = r'''
typeset -i RECOVERY_TEST_DIFF_CALLS=0
git() {
  print -r -- "$*" >> "$RECOVERY_TEST_GIT_LOG"
  case "$1" in
    --version) print 'git version fixture'; return 0 ;;
    rev-parse) print '.git'; return 0 ;;
    branch) print 'main'; return 0 ;;
    fetch) [[ "$RECOVERY_TEST_STAGE" = fetch ]] && return 9; return 0 ;;
    push) [[ "$RECOVERY_TEST_STAGE" = push ]] && return 9; return 0 ;;
    diff)
      if [[ "${2:-}" = --quiet ]]; then
        (( RECOVERY_TEST_DIFF_CALLS += 1 ))
        if [[ "$RECOVERY_TEST_DIFF_CALLS" -ge 4 && "$RECOVERY_TEST_STAGE" = (validation|render|push) ]]; then return 1; fi
      fi
      return 0 ;;
    *) return 0 ;;
  esac
}
python3() {
  if [[ "$1" = scripts/ingest_senate_daily.py && "$RECOVERY_TEST_STAGE" = ingest ]]; then return 7; fi
  if [[ "$1" = scripts/extract_daily_polls.py ]]; then return 0; fi
  command "$RECOVERY_TEST_PYTHON" "$@"
}
Rscript() {
  if [[ "$1" = -e ]]; then print 'fixture'; return 0; fi
  [[ "$RECOVERY_TEST_STAGE" = validation ]] && return 8
  return 0
}
quarto() {
  if [[ "$1" = --version ]]; then print 'fixture'; return 0; fi
  [[ "$RECOVERY_TEST_STAGE" = render ]] && return 8
  return 0
}
source scripts/publish_daily.sh --catchup
'''

class DailyPublisherTests(unittest.TestCase):
    def test_exact_root_stdin_importlib_call_without_pythonpath(self):
        source = (ROOT / 'scripts/publish_daily.sh').read_text()
        payload = source.split("python3 - <<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
        with tempfile.TemporaryDirectory() as folder:
            env = os.environ.copy(); env.pop('PYTHONPATH', None)
            env.update(NIS_SENATE_DAILY=folder, PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run([sys.executable, '-'], input=payload, cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), folder)

    def test_direct_and_package_execution_import_helpers(self):
        env = os.environ.copy(); env.pop('PYTHONPATH', None); env['PYTHONDONTWRITEBYTECODE'] = '1'
        for args in [['scripts/ingest_senate_daily.py', '--help'], ['-m', 'scripts.ingest_senate_daily', '--help']]:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def run_publisher(self, stage):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder); (repo/'scripts').mkdir(); (repo/'data').mkdir(); (repo/'.git').mkdir()
            src = repo/'source'; src.mkdir()
            for name in ['publish_daily.sh','ingest_senate_daily.py','check_raw_briefing.py','check_site_digest.py']:
                shutil.copy2(ROOT/'scripts'/name,repo/'scripts'/name)
            asof = (TODAY-dt.timedelta(days=1)).isoformat() if stage in ACTIVE else TODAY.isoformat()
            doc = {'as_of': asof, 'days': []}
            if stage == 'date': doc['as_of'] = 'not-a-date'
            (repo/'data/senate_daily_log.json').write_text('not JSON' if stage == 'data' else json.dumps(doc))
            (repo/'data/senate_polls.csv').write_text('state\n'); (repo/'data/state_ledger.json').write_text('{}\n')
            if stage in ACTIVE:
                raw = src/f'{TODAY}_일일브리핑_KR.md'
                raw.write_text(f'# 2026 상원 선거 일일 브리핑 — {TODAY}\n\n## 오늘의 핵심 요약\n검사 fixture\n\n## 주별 뉴스\n### 1. 조지아\n기록\n')
                if stage == 'raw': raw.write_bytes(b'\xff')
                if stage == 'digest':
                    (src/'site').mkdir(); (src/'site'/f'{TODAY}_site_KR.md').write_text('# 잘못된 정리본\n')
            if stage == 'module': (repo/'scripts/check_raw_briefing.py').unlink()
            env = os.environ.copy(); env.pop('PYTHONPATH',None)
            env.update(US_ELECTIONS_REPO=str(repo),NIS_SENATE_DAILY=str(src if stage!='path' else repo/'missing'),
                       PD_LOG=str(repo/'execution.log'),PD_CI='0' if stage in {'validation','render','push'} else '1',
                       PYTHONDONTWRITEBYTECODE='1',RECOVERY_TEST_STAGE=stage,
                       RECOVERY_TEST_PYTHON=sys.executable,RECOVERY_TEST_GIT_LOG=str(repo/'git.log'))
            result = subprocess.run(['/bin/zsh','-f','-c',PRELUDE],cwd=repo,env=env,capture_output=True,text=True,timeout=30)
            trace = (repo/'git.log').read_text() if (repo/'git.log').exists() else ''
            return result, trace

    def assert_failure(self, stage, message, allow_push=False):
        result, trace = self.run_publisher(stage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message,result.stdout)
        self.assertNotIn('새 날짜 없음(정상 종료)',result.stdout)
        self.assertNotIn('발행·배포 트리거 완료',result.stdout)
        if not allow_push: self.assertNotIn('push origin main',trace)

    def test_normal_no_changes_returns_zero(self):
        result, trace = self.run_publisher('none')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('새 날짜 없음(정상 종료)',result.stdout)
        self.assertNotIn('push origin main',trace)
    def test_module_load_failure_is_fatal(self): self.assert_failure('module','원천 경로 결정 실패')
    def test_missing_source_directory_is_fatal(self): self.assert_failure('path','원천 폴더가 없거나 읽을 수 없음')
    def test_corrupt_current_data_is_fatal(self): self.assert_failure('data','기준일 읽기 실패')
    def test_invalid_asof_date_is_fatal(self): self.assert_failure('date','날짜 탐색 실패')
    def test_fetch_failure_is_fatal(self): self.assert_failure('fetch','fetch 실패')
    def test_raw_checker_failure_propagates_through_tee_tail(self): self.assert_failure('raw','원문 점검 실행 실패')
    def test_digest_failure_propagates_through_tee_tail(self): self.assert_failure('digest','정리본 대조 실패')
    def test_ingest_failure_is_fatal(self): self.assert_failure('ingest','적재 실패(rc=7)')
    def test_validation_failure_is_fatal(self): self.assert_failure('validation','데이터 검증 실패')
    def test_render_failure_is_fatal(self): self.assert_failure('render','렌더 실패')
    def test_push_failure_is_fatal(self): self.assert_failure('push','push 실패',allow_push=True)

if __name__=='__main__': unittest.main()
