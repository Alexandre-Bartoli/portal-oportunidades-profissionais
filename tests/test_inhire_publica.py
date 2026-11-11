import unittest

import inhire
from source_quality import validate_sources
from source_reviews import pending_technical_review, source_review


class InHirePublicaTests(unittest.TestCase):
    def test_experimental_access_does_not_claim_review(self):
        entry = {'provider': 'inhire', 'slug': 'dtidigital', 'enabled': True,
                 'experimental_access': True}
        validate_sources({'sources': [entry]})
        self.assertFalse(pending_technical_review(entry))
        self.assertEqual(source_review(entry)['status'], 'pending')
        self.assertFalse(source_review(entry)['republication_reviewed'])
        entry['usage_review'] = 'rejected'
        self.assertTrue(pending_technical_review(entry))

    def test_country_requires_explicit_brazil_in_location(self):
        def get(location):
            def fake(url, **kwargs):
                if url.endswith('/pages'):
                    return {'jobsPage': [{'jobId': '123'}]}
                return {'displayName': 'Estágio', 'description': 'Atividades',
                        'location': location, 'contractType': ['Estágio']}
            return inhire.fetch('empresa', fake)[0]['country']
        self.assertEqual(get('Belo Horizonte, MG, BR'), 'BR')
        self.assertIsNone(get('Belo Horizonte, MG'))
        self.assertIsNone(get('Remote, BR, US'))

    def test_limits_number_of_detail_requests(self):
        calls = []
        def fake(url, **kwargs):
            if url.endswith('/pages'):
                return {'jobsPage': [{'jobId': str(i)} for i in range(60)]}
            calls.append(url)
            return {'displayName': 'Estágio', 'description': 'Atividades',
                    'contractType': ['Estágio']}
        result = inhire.fetch('empresa', fake)
        self.assertEqual(len(calls), 50)
        self.assertEqual(result.raw_count, 60)
        self.assertFalse(result.complete)


if __name__ == '__main__':
    unittest.main()
