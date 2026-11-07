import unittest
from unittest.mock import patch
from automatico import collect_once

class AutomaticTests(unittest.TestCase):
 def test_config_enabled(self):
  import json
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