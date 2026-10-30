import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sync', Path(__file__).parents[1] / 'scripts/sync_gitee.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

class Safeguards(unittest.TestCase):
    def test_gitee_null_missing_release_creates_release(self):
        target = {'tag_name':'v0.2.0-beta8', 'id':1}
        with patch.object(s, 'api', side_effect=[None, target]) as call:
            result = s.ensure_release('v0.2.0-beta8', {'name':'beta8'}, 'fake')
        self.assertEqual(result, target)
        self.assertEqual(call.call_args.args[3], 'POST')

    def test_release_permission_error_does_not_create_release(self):
        with patch.object(s, 'api', side_effect=s.SyncError('HTTP 403;')) as call, self.assertRaises(s.SyncError):
            s.ensure_release('v0.2.0-beta8', {'name':'beta8'}, 'fake')
        self.assertEqual(call.call_count, 1)
    def test_wrong_source_hash_rejected(self):
        row = {'version': '0.2.0-beta8', 'published': True, 'size_bytes': 8, 'sha256': 'a'*64}
        release = {'tag_name': 'v0.2.0-beta8', 'assets': [{'name': 'Yingji-0.2.0-beta8-win64-setup.exe', 'size':8, 'digest': 'sha256:'+'b'*64}]}
        with self.assertRaises(s.SyncError):
            s.select_release(release, {'releases':[row]}, 'v0.2.0-beta8')

    def test_zip_preserves_original_installer(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'test.exe'
            p.write_bytes(b'MZ' + b'a'*10000)
            before = s.sha(p)
            with patch.object(s, 'LIMIT', 1000):
                archive = s.prepare_installer(p, Path(tmp))
            self.assertLess(archive.stat().st_size, 1000)
            self.assertEqual(before, s.sha(p))

    def test_zip_is_stable_across_upload_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'test.exe'
            p.write_bytes(b'MZ' + b'a'*10000)
            with patch.object(s, 'LIMIT', 1000):
                before = s.sha(s.prepare_installer(p, Path(tmp)))
                s.os.utime(p, (1700000000, 1700000000))
                after = s.sha(s.prepare_installer(p, Path(tmp)))
            self.assertEqual(before, after)

    def test_oversized_archive_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'test.exe'
            p.write_bytes(b'MZ' + b'a'*100)
            with patch.object(s, 'LIMIT', 1), self.assertRaises(s.SyncError):
                s.prepare_installer(p, Path(tmp))

    def test_conflicting_existing_asset_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'test.exe'
            p.write_bytes(b'original')
            def fetch(url, path, *args): path.write_bytes(b'different')
            with patch.object(s, 'api', return_value=[{'name':p.name, 'browser_download_url':'https://gitee.com/file'}]) as call, patch.object(s, 'download', side_effect=fetch), self.assertRaises(s.SyncError):
                s.ensure_asset(1, p, 'not-a-real-token', Path(tmp))
            self.assertEqual(call.call_count, 1)  # GET only; no replace/delete/upload.

    def test_upload_rejection_stops_before_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'test.exe'
            p.write_bytes(b'original')
            with patch.object(s, 'api', side_effect=[[], s.SyncError('HTTP 413')]), patch.object(s, 'download') as fetch, self.assertRaises(s.SyncError):
                s.ensure_asset(1, p, 'not-a-real-token', Path(tmp))
            fetch.assert_not_called()

    def test_concurrent_metadata_change_is_not_overwritten(self):
        with patch.object(s, 'api', return_value={'sha':'newer'}) as call, self.assertRaises(s.SyncError):
            s.put_file(s.GH, 'not-a-real-token', 'version.json', b'old', expected_sha='previous')
        self.assertEqual(call.call_count, 1)

    def test_failed_download_never_publishes_metadata(self):
        row = {'version':'0.2.0-beta8', 'published':True, 'size_bytes':8, 'sha256':'a'*64}
        manifest = {'releases':[row]}
        entry = {'encoding':'base64', 'content':base64.b64encode(json.dumps(manifest).encode()).decode()}
        release = {'tag_name':'v0.2.0-beta8', 'assets':[{'name':'Yingji-0.2.0-beta8-win64-setup.exe', 'size':8, 'digest':'sha256:'+'a'*64, 'browser_download_url':'https://github.com/file'}]}
        with patch.dict(s.os.environ, {'GH_TOKEN':'fake', 'GITEE_TOKEN':'fake', 'RELEASE_TAG':'v0.2.0-beta8'}), patch.object(s, 'api', side_effect=[release, entry]), patch.object(s, 'download', side_effect=s.SyncError('unavailable')), patch.object(s, 'put_file') as put, self.assertRaises(s.SyncError):
            s.main()
        put.assert_not_called()

if __name__ == '__main__':
    unittest.main()
