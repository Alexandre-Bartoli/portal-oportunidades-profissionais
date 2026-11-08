import unittest

from providers_extra import smartrecruiters, breezy


class ProviderIntegrityTests(unittest.TestCase):
    def test_smartrecruiters_rejects_invalid_inventory_row(self):
        with self.assertRaises(ValueError):
            smartrecruiters('acme', get_json=lambda _: {'content': [None]})

    def test_breezy_rejects_missing_link(self):
        with self.assertRaises(ValueError):
            breezy('acme', get_json=lambda _: [{'id': '1', 'name': 'Estágio'}])

    def test_valid_unclassified_job_is_not_invalid(self):
        result = smartrecruiters('acme', get_json=lambda _: {'content': [
            {'id': '1', 'name': 'Analista de Dados', 'location': {}}]})
        self.assertEqual((len(result), result.raw_count, result.complete), (0, 1, True))

    def test_breezy_untrusted_url_marks_inventory_partial(self):
        result = breezy('acme', get_json=lambda _: [
            {'id': '1', 'name': 'Estágio', 'url': 'https://acme.breezy.hr.evil.test/p/1'}])
        self.assertFalse(result.complete)
