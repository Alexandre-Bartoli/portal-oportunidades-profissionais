"""Testes de persistência, backup, restauração e revisão, sem acesso à rede."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import core
from homologacao import collect_staging
from link_checks import allowed_link, audit_links, check_link, sample_jobs
from providers_extra import ListingBatch
from source_reviews import review_report, source_review
from stage_storage import (backup_list, backup_staging, restore_staging, staging_lock,
                           storage_dir, _validate_staging_db, write_private_report)


def configuration(*names):
    return {'sources':[{'provider':p, 'slug':s, 'enabled':True} for p,s in names]}


def row(source, num, url=None):
    return core.make_job('lever',source,{'id':str(num), 'text':'Estágio em Administração',
            'hostedUrl':url or f'https://jobs.lever.co/{source}/{num}',
            'categories':{'location':'Barbacena'}})


class StageStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root/'homologacao.sqlite3'
        self.report = self.root/'report.json'
        self.previous_db = core.DB
        core.DB = self.root/'principal.sqlite3'
        self.config = configuration(('lever','empresa'))

    def tearDown(self):
        core.DB = self.previous_db
        self.tmp.cleanup()

    def collect(self, items):
        return collect_staging(self.config,db_path=self.db,report_path=self.report,
               min_sources=1,fetcher=lambda *_: ListingBatch(items,raw_count=len(items)))

    def test_backup_restores_prior_state_and_creates_safety_snapshot(self):
        self.collect([row('empresa',1)])
        stamp=datetime(2026,11,8,tzinfo=timezone.utc)
        first=backup_staging(self.db,now=stamp)
        self.assertEqual(first['active_jobs_at_backup'],1)
        self.assertEqual(_validate_staging_db(self.root/'backups'/first['created']),1)
        self.collect([row('empresa',1),row('empresa',2)])
        self.assertEqual(_validate_staging_db(self.db),2)
        result=restore_staging(first['created'],db_path=self.db,confirm=True)
        self.assertEqual(result['active_jobs_after_restore'],1)
        self.assertEqual(_validate_staging_db(self.db),1)
        self.assertIsNotNone(result['safety_backup_before_restore'])
        self.assertEqual(_validate_staging_db(self.root/'backups'/result['safety_backup_before_restore']),2)
        self.assertFalse(core.DB == self.db)

    def test_backups_rotate_and_are_named_deterministically(self):
        self.collect([row('empresa',1)])
        now=datetime(2026,11,8,tzinfo=timezone.utc)
        for delta in (0,1,2):
            backup_staging(self.db,now=now+timedelta(seconds=delta),retain=2)
        found=backup_list(self.root/'backups')
        self.assertEqual(len(found),2)
        self.assertNotIn('homologacao-20261108T000000000000Z.sqlite3', [item['name'] for item in found])
        self.assertTrue(all(item['bytes'] > 0 for item in found))

    def test_restoring_oldest_backup_does_not_delete_it_during_rotation(self):
        self.collect([row('empresa',1)])
        stamp=datetime(2026,11,8,tzinfo=timezone.utc)
        first=backup_staging(self.db,now=stamp,retain=10)['created']
        for i in range(1,10):
            backup_staging(self.db,now=stamp+timedelta(seconds=i),retain=10)
        self.collect([row('empresa',1),row('empresa',2)])
        self.assertEqual(_validate_staging_db(self.db),2)
        restored=restore_staging(first,db_path=self.db,confirm=True)
        self.assertEqual(restored['active_jobs_after_restore'],1)
        self.assertEqual(_validate_staging_db(self.db),1)

    def test_restore_fails_closed_without_confirm_or_for_traversal(self):
        self.collect([row('empresa',1)])
        name=backup_staging(self.db)['created']
        with self.assertRaises(ValueError):
            restore_staging(name,db_path=self.db)
        with self.assertRaises(ValueError):
            restore_staging('../'+name,db_path=self.db,confirm=True)
        self.assertEqual(_validate_staging_db(self.db),1)

    def test_damaged_backup_does_not_replace_live_database(self):
        self.collect([row('empresa',1)])
        name=backup_staging(self.db)['created']
        (self.root/'backups'/name).write_text('not sqlite',encoding='utf-8')
        with self.assertRaises((ValueError,sqlite3.DatabaseError)):
            restore_staging(name,db_path=self.db,confirm=True)
        self.assertEqual(_validate_staging_db(self.db),1)

    def test_symlink_backup_is_never_accepted(self):
        self.collect([row('empresa',1)])
        name=backup_staging(self.db)['created']
        path=self.root/'backups'/name
        path.unlink()
        path.symlink_to(self.db)
        with self.assertRaises(ValueError):
            restore_staging(name,db_path=self.db,confirm=True)
        self.assertEqual(backup_list(self.root/'backups'),[])

    def test_lock_prevents_restore_while_shared_reader_is_running(self):
        if os.name == 'nt':
            self.skipTest('flock test específico de Unix')
        with staging_lock(self.root):
            with self.assertRaises(RuntimeError):
                with staging_lock(self.root,exclusive=True):
                    self.fail('não deveria adquirir lock exclusivo')

    def test_configuration_requires_absolute_external_directory(self):
        with patch.dict(os.environ, {'PORTAL_STAGING_DIR':'relative/data'}):
            with self.assertRaises(ValueError):storage_dir()
        with patch.dict(os.environ, {'PORTAL_STAGING_DIR':str(self.root/'private')}):
            self.assertEqual(storage_dir(),(self.root/'private').resolve())

    def test_private_reports_do_not_get_public_permissions(self):
        result=write_private_report({'ok':True},self.root/'private'/'status.json')
        self.assertTrue(json.loads(result.read_text())['ok'])
        if os.name != 'nt':
            self.assertEqual(result.stat().st_mode & 0o077,0)
            self.assertEqual(result.parent.stat().st_mode & 0o077,0)


class SourceReviewsTests(unittest.TestCase):
    def test_all_sources_pending_without_evidence(self):
        report=review_report(configuration(('lever','empresa')))
        self.assertEqual(report['status'],'manual_review_required')
        self.assertEqual(report['technical_probes_allowed'],0)
        self.assertEqual(report['republication_reviews_completed'],0)

    def test_forged_approval_without_evidence_does_not_pass(self):
        entry={'provider':'lever','slug':'empresa','enabled':True,'usage_review':'approved'}
        self.assertEqual(source_review(entry)['status'],'invalid_evidence')

    def test_technical_access_is_not_republication(self):
        entry={'provider':'lever','slug':'empresa','enabled':True,'usage_review':'approved',
               'usage_evidence_url':'https://example.org/terms', 'usage_reviewed_at':'2026-10-01',
               'usage_reviewed_by':'Responsável','usage_scope':'technical_access'}
        a=source_review(entry)
        self.assertTrue(a['technical_probe_allowed'])
        self.assertFalse(a['republication_reviewed'])
        self.assertEqual(a['status'],'approved_access_only')
        entry['usage_scope']='republication'
        self.assertTrue(source_review(entry)['republication_reviewed'])

    def test_invalid_future_date_and_insecure_evidence(self):
        entry={'provider':'lever','slug':'empresa','enabled':True,'usage_review':'approved',
               'usage_evidence_url':'http://example.org/terms','usage_reviewed_at':'2099-01-01',
               'usage_reviewed_by':'Responsável','usage_scope':'republication'}
        self.assertEqual(source_review(entry)['status'],'invalid_evidence')


class LinkChecksTests(unittest.TestCase):
    setUp = StageStorageTests.setUp
    tearDown = StageStorageTests.tearDown
    collect = StageStorageTests.collect

    def test_unknown_host_is_never_probed(self):
        for url in ['https://jobs.lever.co.evil.example/empresa/1',
                    'http://jobs.lever.co/empresa/1',
                    'https://user@jobs.lever.co/empresa/1',
                    'https://jobs.lever.co:8443/empresa/1',
                    'https://127.0.0.1/private']:
            self.assertFalse(allowed_link('lever',url),url)
        self.assertTrue(allowed_link('lever','https://jobs.lever.co/empresa/1'))

    def test_no_network_by_default(self):
        self.collect([row('empresa',1)])
        result=audit_links(self.db,self.config,checker=lambda *_:self.fail('rede proibida'))
        self.assertEqual(result['statuses'],{'not_checked':1})
        self.assertNotIn('jobs.lever.co',json.dumps(result))

    def test_network_requires_review_for_each_source(self):
        self.collect([row('empresa',1)])
        result=audit_links(self.db,self.config,network=True,checker=lambda *_:self.fail('rede sem revisão'))
        self.assertEqual(result['statuses'],{'pending_source_review':1})

    def test_reviewed_source_is_probed_but_not_deactivated(self):
        self.collect([row('empresa',1)])
        reviewed=configuration(('lever','empresa'))
        reviewed['sources'][0].update(usage_review='approved',
            usage_evidence_url='https://example.org/terms', usage_reviewed_at='2026-10-01',
            usage_reviewed_by='Responsável',usage_scope='technical_access')
        result=audit_links(self.db,reviewed,network=True,
             checker=lambda *_:{'status':'not_found_unverified','http_status':404},
             report_path=self.root/'link_status.json')
        self.assertEqual(result['statuses'],{'not_found_unverified':1})
        self.assertEqual(_validate_staging_db(self.db),1)
        self.assertNotIn('jobs.lever.co',(self.root/'link_status.json').read_text())

    def test_head_200_does_not_mean_open_job(self):
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):return False
        class FakeOpen:
            def open(self,*a,**k):return Response()
        checked=check_link('lever','https://jobs.lever.co/empresa/1',opener=FakeOpen())
        self.assertEqual(checked['status'],'http_reachable_unverified')

    def test_balanced_samples_cover_more_than_one_source(self):
        configuration2=configuration(('lever','empresa'),('lever','outra'))
        def fetch(_,slug):
            return ListingBatch([row(slug,n) for n in (1,2,3)],raw_count=3)
        collect_staging(configuration2,db_path=self.db,report_path=self.report,
                        fetcher=fetch,min_sources=2)
        sample=sample_jobs(self.db,limit=2)
        self.assertEqual({item[2] for item in sample},{'empresa','outra'})