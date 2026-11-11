import http.client
import json
import os
import stat
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import app
import automatico
import core


class SegurancaLocalTests(unittest.TestCase):
    def test_untrusted_host_cannot_access_local_service(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'DB', Path(tmp)/'jobs.sqlite3'):
            server = ThreadingHTTPServer(('127.0.0.1',0), app.Handler)
            thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                conn.request('GET','/api/health',headers={'Host':'site-externo.example'})
                self.assertEqual(conn.getresponse().status,403)
                conn.close()
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                conn.request('GET','/api/health',headers={'Host':'localhost:1'})
                self.assertEqual(conn.getresponse().status,403)
                conn.close()
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                conn.request('GET','/api/health',headers={'Host':f'localhost:{server.server_port}'})
                self.assertEqual(conn.getresponse().status,200)
                conn.close()
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/health') as response:
                    self.assertEqual(response.status,200)
            finally:
                server.shutdown();server.server_close();thread.join(3)

    @unittest.skipUnless(os.name == 'posix', 'Permissões POSIX')
    def test_database_and_directory_are_private_even_with_permissive_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data'/'jobs.sqlite3'
            previous=os.umask(0o022)
            try:
                with patch.object(core,'DB',path): core.init()
            finally:
                os.umask(previous)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode),0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            path.parent.chmod(0o755);path.chmod(0o644)
            with patch.object(core,'DB',path): core.init()
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode),0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)

    @unittest.skipUnless(os.name == 'posix', 'Links simbólicos POSIX')
    def test_collect_does_not_follow_symlink_in_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=root/'data'; data.mkdir()
            (root/'sources.json').write_text(json.dumps({'sources':[]}),encoding='utf-8')
            victim=root/'documento.txt'; victim.write_text('original',encoding='utf-8')
            status=data/'ultima_coleta.json'; status.symlink_to(victim)
            with patch.object(automatico,'BASE',root), patch.object(automatico,'STATE',status), \
                 patch.object(core,'DB',data/'jobs.sqlite3'):
                automatico.collect_once()
            self.assertEqual(victim.read_text(encoding='utf-8'),'original')
            self.assertFalse(status.is_symlink())
            self.assertEqual(json.loads(status.read_text())['collected'],0)

    @unittest.skipUnless(os.name == 'posix', 'Links simbólicos POSIX')
    def test_database_does_not_follow_a_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); victim=root/'documento.txt';victim.write_text('original')
            db=root/'jobs.sqlite3';db.symlink_to(victim)
            with patch.object(core, 'DB', db), self.assertRaises((ValueError,OSError)):
                core.init()
            self.assertEqual(victim.read_text(),'original')

    def test_known_provider_url_is_allowed(self):
        from link_checks import allowed_link
        self.assertTrue(allowed_link('ashby','https://jobs.ashbyhq.com/empresa/vaga'))
        self.assertFalse(allowed_link('ashby','https://jobs.ashbyhq.com.site-externo.example/vaga'))

    def test_external_domain_is_not_shown_as_verified_application_link(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core,'DB',Path(tmp)/'jobs.sqlite3'):
            job=core.make_job('ashby','empresa',{'id':'1','title':'Internship',
                  'jobUrl':'https://site-externo.example/vaga'})
            core.save([job])
            server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/vaga?id={job["id"]}') as response:
                    page=response.read().decode()
                self.assertNotIn('href="https://site-externo.example/vaga"',page)
                self.assertIn('Link não confirmado',page)
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/jobs?kind=all') as response:
                    result=json.load(response)['results'][0]
                self.assertIsNone(result['url'])
                self.assertFalse(result['link_permitido'])
            finally:
                server.shutdown();server.server_close();thread.join(3)
