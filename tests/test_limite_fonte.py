import tempfile
import unittest
from pathlib import Path

from source_limits import acquire, RateLimited


class SourceLimitTests(unittest.TestCase):
    def test_rate_limit_persists_across_connections_and_clock_reversal(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'limits.sqlite3'
            acquire('remotive',path,now=100000)
            with self.assertRaises(RateLimited):acquire('remotive',path,now=100001)
            with self.assertRaises(RateLimited):acquire('remotive',path,now=90000)
            acquire('remotive',path,now=121600)

    def test_rejects_symlink_database(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/'target';target.write_text('x')
            path=Path(root)/'link';path.symlink_to(target)
            with self.assertRaises(ValueError):acquire('remotive',path,now=1)

    def test_simultaneous_requests_reserve_only_one_slot(self):
        import threading
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'limits.sqlite3'
            start=threading.Barrier(2)
            outcomes=[]
            def attempt():
                start.wait()
                try:
                    acquire('remotive',path,now=100000)
                    outcomes.append('accepted')
                except RateLimited:
                    outcomes.append('blocked')
            workers=[threading.Thread(target=attempt) for _ in range(2)]
            for worker in workers:worker.start()
            for worker in workers:worker.join(timeout=6)
            self.assertCountEqual(outcomes,['accepted','blocked'])

    def test_http_json_response_size_is_limited(self):
        from unittest.mock import patch
        import core
        class Response:
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def read(self, limit=-1): return b'x' * (10_000_001 if limit < 0 else min(limit,10_000_001))
        with patch('urllib.request.build_opener') as factory:
            factory.return_value.open.return_value=Response()
            with self.assertRaisesRegex(ValueError,'excede'):core.get_json('https://remotive.com/api/remote-jobs',attempts=1)
