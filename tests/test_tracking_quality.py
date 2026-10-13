import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_raw_briefing as raw_check
import check_site_digest as digest_check
import ingest_senate_daily as ingest
import fetch_cook_house as cook

class QualityTests(unittest.TestCase):
    def test_plain_domain_or_foreign_query_is_not_a_local_link(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'2026-10-12_일일브리핑_KR.md'
            path.write_text('# 2026-10-12\n## 주별 뉴스\n### 1. 조지아\n- [유세] 없음\nMention ajc.com and https://example.org/?source=ajc.com\n## Run self-audit\n- C: 1/1\n')
            result=raw_check.audit_file(path)
            self.assertEqual(result['missing_local_states'],['조지아'])
            self.assertTrue(any('자기보고 C' in w for w in result['warnings']))
            path.write_text(path.read_text().replace('Mention ajc.com and https://example.org/?source=ajc.com','[지역 보도](https://www.ajc.com/story)'))
            self.assertEqual(raw_check.audit_file(path)['missing_local_states'],[])
    def test_digest_cannot_hide_raw_gaps_or_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'site').mkdir()
            raw=root/'2026-10-12_일일브리핑_KR.md';site=root/'site/2026-10-12_site_KR.md'
            raw.write_text('# 2026-10-12\n## 주별 뉴스\n### 1. 조지아\nAARP 조사\n## 수집 결손\n지역 원문 접근 차단·미확인\n')
            site.write_text('# 2026-10-12 (사이트 정리본)\n## 주별 뉴스\n### 1. 조지아\n정리본\n')
            day=ingest.parse_file(site)
            self.assertIn('접근 차단',day['gaps'])
            self.assertIn('조지아',day['source_validation']['missing_local_states'])
            self.assertTrue(any('aarp' in w for w in day['source_validation']['warnings']))
            raw.unlink();day=ingest.parse_file(site)
            self.assertEqual(day['source_validation']['status'],'원문 점검 불가')
    def test_only_oregon_poll_is_marked_unverified(self):
        import csv
        with (Path(__file__).resolve().parents[1]/'data/governor_polls.csv').open() as source:
            rows=list(csv.DictReader(source))
        marked=[r for r in rows if '후보 방향 미확인' in r['note']]
        self.assertEqual([(r['state'],r['pollster']) for r in marked],[('OR','Oregonian/DHM Research')])
        texas=next(r for r in rows if r['state']=='TX' and r['pollster']=='UMass Lowell')
        self.assertEqual((texas['dem_pct'],texas['rep_pct'],texas['margin']),('44','48','-4'))

    def test_priority_absence_and_presence(self):
        self.assertTrue(digest_check.priority_warnings('AARP Marist', 'Marist'))
        self.assertEqual(digest_check.priority_warnings('AARP Marist', 'aarp MARIST'),[])
    def test_cook_date_bound_to_its_object_and_retrieval_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'data').mkdir()
            obj='{"url_title":"cook-political-report-2026-house-ratings","date_created":"2026-09-23","map_string":"'+'1'*435+'"}'
            other='{"url_title":"another-feed","date_created":"2026-10-13","map_string":"'+'2'*435+'"}'
            with patch.object(cook,'ROOT',folder), patch.object(cook,'get',side_effect=[other+obj,'']), patch.object(sys,'argv',['fetch_cook_house.py']), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cook.main(),0)
            for name in ['house_cook_ratings','house_cook_districts']:
                d=json.loads((Path(folder)/f'data/{name}.json').read_text())
                self.assertEqual(d['as_of'],'2026-09-23')
                self.assertNotEqual(d['fetched_at'][:10],d['as_of'])
                self.assertIn('원문 발표일 미확인',d['source_date_kind'])
    def test_invalid_cook_does_not_replace_existing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'data';p.mkdir();(p/'house_cook_ratings.json').write_text('existing')
            with patch.object(cook,'ROOT',folder), patch.object(cook,'get',return_value='no feed'), patch.object(sys,'argv',['fetch_cook_house.py']), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cook.main(),1)
            self.assertEqual((p/'house_cook_ratings.json').read_text(),'existing')

if __name__=='__main__':unittest.main()
