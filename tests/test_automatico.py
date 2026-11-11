import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from automatico import collect_once
import automatico
import core

class AutomaticTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  root=Path(tmp.name)
  (root/'sources.json').write_text(json.dumps({'sources':[
   {'provider':'lever','slug':'a','enabled':True},
   {'provider':'ashby','slug':'b','enabled':True},
   {'provider':'ashby','slug':'c','enabled':True}]}))
  for obj,name,value in ((automatico,'BASE',root),(automatico,'STATE',root/'data'/'ultima_coleta.json'),
                         (core,'DB',root/'data'/'jobs.sqlite3')):
   p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
 def test_config_enabled(self):
  from core import BASE
  sources=json.loads((BASE/'sources.json').read_text())['sources']
  self.assertGreaterEqual(sum(s['enabled'] for s in sources),3)
 def test_collect_without_network(self):
  with patch('automatico.fetch_source',return_value=[]) as f:
   status=collect_once()
   self.assertGreaterEqual(f.call_count,3)
   self.assertEqual(status['collected'],0)
 def test_error_is_reported(self):
  with patch('automatico.fetch_source',side_effect=OSError('indisponível')):
   status=collect_once()
   self.assertTrue(any(s['status']=='error' for s in status['sources']))
