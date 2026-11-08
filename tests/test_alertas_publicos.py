import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import app
import core
from signals import analyze


class PublicAlertsTests(unittest.TestCase):
    def test_internal_applicants_are_only_a_signal(self):
        result=analyze('Estágio', 'Vaga exclusiva para colaboradores da empresa')
        self.assertIn('selecao_interna',[x['type'] for x in result])

    def test_detail_page_shows_payment_signal_not_fraud_verdict(self):
        with tempfile.TemporaryDirectory() as root, patch.object(core,'DB',Path(root)/'jobs.sqlite3'):
            job=core.make_job('lever','one',{'id':'1','text':'Estágio',
                'hostedUrl':'https://example.org/1',
                'descriptionPlain':'Pague taxa de inscrição para participar.'})
            core.save([job])
            server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with urllib.request.urlopen('http://127.0.0.1:'+str(server.server_port)+'/vaga?id='+job['id']) as response:
                    page=response.read().decode('utf-8')
                self.assertIn('Sinais para conferir',page)
                self.assertIn('possível cobrança',page.lower())
                self.assertNotIn('fraude confirmada',page.lower())
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)
