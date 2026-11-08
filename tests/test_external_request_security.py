import unittest
from unittest.mock import patch
import core


class ExternalRequestSecurityTests(unittest.TestCase):
    def test_non_provider_url_rejected_before_network(self):
        for url in ('https://127.0.0.1/private', 'https://api.lever.co.evil.test/',
                    'https://api.lever.co@127.0.0.1/', 'https://api.lever.co:444/'):
            with self.subTest(url=url), patch('urllib.request.build_opener') as opener:
                with self.assertRaises(ValueError):
                    core.get_json(url)
                opener.assert_not_called()

    def test_redirect_is_not_followed(self):
        handler = core.NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(None, None, 302, '', {}, 'http://127.0.0.1/private'))
