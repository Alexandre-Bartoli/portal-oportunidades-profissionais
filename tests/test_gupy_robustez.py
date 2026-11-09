import unittest
from urllib.parse import parse_qs, urlsplit

import gupy


def posting(number, **overrides):
    data = {'id': number, 'name': 'Estágio', 'type': 'vacancy_type_internship',
            'jobUrl': f'https://empresa.gupy.io/jobs/{number}'}
    data.update(overrides)
    return data


class GupyRobustezTests(unittest.TestCase):
    def test_opt_in_allows_fetch_without_claiming_review(self):
        from source_reviews import pending_technical_review, source_review
        entry = {'provider':'gupy', 'slug':'estagio', 'enabled':True, 'experimental_access':True}
        self.assertFalse(pending_technical_review(entry))
        self.assertEqual(source_review(entry)['status'], 'pending')
        self.assertTrue(source_review(entry)['technical_probe_allowed'])
        entry['usage_review'] = 'rejected'
        self.assertTrue(pending_technical_review(entry))

    def test_company_search_link_is_converted_to_direct_job_link(self):
        item = gupy.normalize_item(posting(123, jobUrl='https://empresa.gupy.io/job/abc?jobBoardSource=gupy_portal'), 'internship')
        self.assertEqual(item['url'], 'https://empresa.gupy.io/jobs/123')

    def test_shared_portal_link_is_preserved_without_guessing_company(self):
        item = gupy.normalize_item(posting(123, jobUrl='https://portal.gupy.io/job/abc'), 'internship')
        self.assertEqual(item['url'], 'https://portal.gupy.io/job/abc')

    def test_pagination_respects_page_size_and_remains_partial(self):
        calls = []
        def fake(url):
            params = parse_qs(urlsplit(url).query)
            calls.append(int(params['offset'][0]))
            return {'data': [posting(1), posting(2)] if len(calls) == 1 else [posting(3)]}
        result = gupy.fetch('estágio', pages=3, limit=2, get_json=fake)
        self.assertEqual(calls, [0, 2])
        self.assertEqual(len(result), 3)
        self.assertEqual(result.raw_count, 3)
        self.assertFalse(result.complete)

    def test_repeated_page_is_rejected(self):
        with self.assertRaises(ValueError):
            gupy.fetch('estágio', pages=2, limit=1,
                       get_json=lambda _: {'data':[posting(1)]})

    def test_inconsistent_pagination_metadata_is_rejected(self):
        with self.assertRaises(ValueError):
            gupy.fetch('estágio', limit=2, get_json=lambda _: {
                'data':[posting(1)], 'pagination':{'offset':99,'limit':2,'total':1}})
        with self.assertRaises(ValueError):
            gupy.fetch('estágio', limit=2, get_json=lambda _: {
                'data':[posting(1)], 'pagination':{'offset':0,'limit':2,'total':0}})

    def test_malformed_rows_do_not_disappear_silently(self):
        for row in (None, {'id':1}, posting(1, jobUrl='')):
            with self.subTest(row=row), self.assertRaises(ValueError):
                gupy.fetch('estágio', get_json=lambda _: {'data':[row]})

    def test_urls_with_user_info_or_unusual_ports_are_rejected(self):
        for url in ('https://user@empresa.gupy.io/jobs/1',
                    'https://empresa.gupy.io:8443/jobs/1',
                    'https://empresa.gupy.io/',
                    'https://empresa.gupy.io.evil.test/jobs/1'):
            with self.subTest(url=url):
                self.assertEqual(gupy.safe_job_url(url), '')

    def test_workplace_filter_is_explicit_and_single(self):
        params = parse_qs(urlsplit(gupy.build_url('admin', workplace='hybrid')).query)
        self.assertEqual(params['workplaceType'], ['hybrid'])
        with self.assertRaises(ValueError):
            gupy.build_url('admin', workplace='remote,hybrid')
