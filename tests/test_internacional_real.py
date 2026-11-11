import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core


def ashby(ident, country, employment='FullTime', title='Software Engineer'):
    return {'id': ident, 'title': title, 'jobUrl': 'https://jobs.ashbyhq.com/example/' + ident,
            'employmentType': employment, 'location': 'Local não utilizado para definir o país',
            'address': {'postalAddress': {'addressCountry': country}}}


class InternacionalRealTests(unittest.TestCase):
    def test_real_ashby_country_and_employment_values_reach_filter(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(core, 'DB', Path(directory) / 'jobs.sqlite3'):
            rows = [ashby('1', 'Canada'), ashby('2', 'United States', 'Intern', 'Intern'),
                    ashby('3', 'Brazil'), ashby('4', 'European Union')]
            core.save([job for row in rows if (job := core.make_job('ashby', 'example', row))])
            found = core.query(kind='', region='international')
            self.assertEqual({(j['external_id'], j['country'], j['kind']) for j in found},
                             {('1', 'CA', 'employment'), ('2', 'US', 'internship')})
            self.assertEqual(core.query(kind='employment', region='brazil')[0]['country'], 'BR')

    def test_ambiguous_or_missing_country_is_not_inferred(self):
        for value in ('European Union', 'Unknown', None):
            with self.subTest(value=value):
                self.assertIsNone(core.make_job('ashby', 'example', ashby('1', value))['country'])

    def test_parttime_is_employment_but_contract_is_not_assumed(self):
        self.assertEqual(core.make_job('ashby', 'example', ashby('1', 'United Kingdom', 'PartTime'))['kind'], 'employment')
        self.assertIsNone(core.make_job('ashby', 'example', ashby('2', 'United Kingdom', 'Contract')))
