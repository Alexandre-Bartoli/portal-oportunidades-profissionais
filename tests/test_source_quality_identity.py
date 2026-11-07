import unittest
import urllib.error
from source_quality import validate_sources, classify_error, audit_result, audit_summary
from listing_identity import canonical_url, stable_identity, deduplicate_listings

class SourceQualityTests(unittest.TestCase):
    def test_config(self):
        self.assertEqual(validate_sources({'sources':[{'provider':'lever','slug':'company','enabled':True}]}), {'total':1,'enabled':1})
    def test_duplicate(self):
        with self.assertRaises(ValueError):
            validate_sources({'sources':[{'provider':'lever','slug':'X','enabled':True},{'provider':'lever','slug':'x','enabled':False}]})
    def test_disabled_must_be_boolean(self):
        with self.assertRaises(ValueError):
            validate_sources({'sources':[{'provider':'lever','slug':'x','enabled':'false'}]})
    def test_invalid_gupy_slug(self):
        with self.assertRaises(ValueError):
            validate_sources({'sources':[{'provider':'gupy','slug':'qualquer','enabled':True}]})
    def test_network_not_empty(self):
        r=audit_result('lever','company',error=urllib.error.URLError('offline'))
        self.assertEqual((r['status'],r['reason'],r['jobs']),('error','network_error',None))
    def test_empty(self):
        r=audit_result('lever','company',items=[])
        self.assertEqual((r['status'],r['jobs']),('empty',0))
    def test_http_codes(self):
        def err(code):return urllib.error.HTTPError('https://example.org',code,'error',{},None)
        self.assertEqual(classify_error(err(429)),'rate_limited')
        self.assertEqual(classify_error(err(404)),'not_found')
    def test_summary(self):
        s=audit_summary([audit_result('lever','a',items=[{'kind':'internship'}]),audit_result('lever','b',items=[]),audit_result('ashby','c',error=ValueError())])
        self.assertEqual((s['ok'],s['empty'],s['error'],s['jobs']),(1,1,1,1))

class IdentityTests(unittest.TestCase):
    def test_strips_tracking(self):
        self.assertEqual(canonical_url('https://EXAMPLE.org/jobs/7/?utm_source=x&k=1#top'),'https://example.org/jobs/7?k=1')
    def test_never_accepts_untrusted_scheme(self):
        self.assertIsNone(canonical_url('http://example.org/job'))
        self.assertIsNone(canonical_url('https://u:p@example.org/job'))
    def test_stable_id(self):
        a=stable_identity('ashby','abc','1')
        self.assertEqual(a,stable_identity('ashby','abc','1'))
        self.assertNotEqual(a,stable_identity('lever','abc','1'))
    def test_duplicate_url(self):
        a={'provider':'lever','source':'c','external_id':'1','url':'https://example.org/jobs/1?utm_source=test'}
        b={'provider':'ashby','source':'d','external_id':'2','url':'https://example.org/jobs/1'}
        self.assertEqual(len(deduplicate_listings([a,b])),1)
    def test_same_title_not_sufficient(self):
        a={'provider':'lever','source':'x','external_id':'1','url':'https://example.org/a','title':'Intern'}
        b={'provider':'lever','source':'x','external_id':'2','url':'https://example.org/b','title':'Intern'}
        self.assertEqual(len(deduplicate_listings([a,b])),2)

if __name__=='__main__':unittest.main()