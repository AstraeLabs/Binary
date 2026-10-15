"""Offline regression tests for fail-closed download integrity controls."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "scripts" / "download_binaries.py"
spec = importlib.util.spec_from_file_location("download_binaries", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        yield self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, *_args, **_kwargs):
        self.calls += 1
        return FakeResponse(self.payload)


class SourceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.downloader = module.BinaryDownloader(base_path=self.temp.name)
        self.url = "https://example.invalid/test.bin"
        self.destination = Path(self.temp.name) / "test.bin"
        self.good_bytes = b"verified test payload"
        self.good_hash = hashlib.sha256(self.good_bytes).hexdigest()

    def test_pinned_digest_accepted(self):
        self.downloader.trusted_sha256[self.url] = self.good_hash
        session = FakeSession(self.good_bytes)
        self.assertTrue(self.downloader._download(self.url, self.destination, session=session))
        self.assertEqual(self.destination.read_bytes(), self.good_bytes)
        self.assertFalse(self.downloader.failures)

    def test_mismatch_refused_preserves_existing_binary(self):
        self.destination.write_bytes(b"existing known file")
        self.downloader.trusted_sha256[self.url] = "0" * 64
        session = FakeSession(self.good_bytes)
        self.assertFalse(self.downloader._download(self.url, self.destination, session=session))
        self.assertEqual(self.destination.read_bytes(), b"existing known file")
        self.assertEqual(len(self.downloader.failures), 1)
        self.assertFalse(self.destination.with_name("test.bin.unverified").exists())

    def test_unpinned_source_never_requested(self):
        session = FakeSession(self.good_bytes)
        self.assertFalse(self.downloader._download(self.url, self.destination, session=session))
        self.assertEqual(session.calls, 0)
        self.assertFalse(self.destination.exists())

    def test_non_https_refused(self):
        url = "http://example.invalid/test.bin"
        self.downloader.trusted_sha256[url] = self.good_hash
        session = FakeSession(self.good_bytes)
        self.assertFalse(self.downloader._download(url, self.destination, session=session))
        self.assertEqual(session.calls, 0)

    def test_lockfile_contains_valid_hashes_and_urls(self):
        lock_path = Path(__file__).with_name("trusted_source_hashes.json")
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(lock["schema_version"], 1)
        self.assertGreater(len(lock["sha256_by_url"]), 40)
        for url, checksum in lock["sha256_by_url"].items():
            self.assertTrue(url.startswith("https://github.com/"), url)
            self.assertRegex(checksum, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
