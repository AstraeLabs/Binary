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

    def test_new_release_without_pin_uses_publisher_digest(self):
        url = "https://github.com/AstraeLabs/Flux/releases/download/Init/flux-linux-x64"
        self.downloader._digest_cache[("github.com", "AstraeLabs/Flux/releases/download/Init")] = {
            "flux-linux-x64": self.good_hash
        }
        self.assertTrue(self.downloader._download(url, self.destination, session=FakeSession(self.good_bytes)))
        self.assertEqual(self.destination.read_bytes(), self.good_bytes)

    def test_publisher_digest_mismatch_refused(self):
        url = "https://github.com/AstraeLabs/Flux/releases/download/Init/flux-linux-x64"
        self.downloader._digest_cache[("github.com", "AstraeLabs/Flux/releases/download/Init")] = {
            "flux-linux-x64": "0" * 64
        }
        self.assertFalse(self.downloader._download(url, self.destination, session=FakeSession(self.good_bytes)))
        self.assertFalse(self.destination.exists())

    def test_asset_without_publisher_digest_refused(self):
        url = "https://github.com/AstraeLabs/Flux/releases/download/Init/flux-linux-x64"
        self.downloader._digest_cache[("github.com", "AstraeLabs/Flux/releases/download/Init")] = {}
        session = FakeSession(self.good_bytes)
        self.assertFalse(self.downloader._download(url, self.destination, session=session))
        self.assertEqual(session.calls, 0)

    def test_github_release_digests_parsed_from_api(self):
        self.downloader._github_api = lambda path: {
            "assets": [
                {"name": "flux-linux-x64", "digest": f"sha256:{self.good_hash}"},
                {"name": "SHA256SUMS", "digest": None},
            ]
        } if path == "/repos/AstraeLabs/Flux/releases/tags/Init" else {}
        url = "https://github.com/AstraeLabs/Flux/releases/download/Init/flux-linux-x64"
        self.assertEqual(self.downloader._expected_sha256(url), self.good_hash)

    def test_non_https_refused(self):
        url = "http://example.invalid/test.bin"
        self.downloader.trusted_sha256[url] = self.good_hash
        session = FakeSession(self.good_bytes)
        self.assertFalse(self.downloader._download(url, self.destination, session=session))
        self.assertEqual(session.calls, 0)

    def test_manual_refresh_defaults_to_checked_in_release(self):
        import os
        from unittest.mock import patch
        root = Path(__file__).resolve().parents[1]
        for tool, env in (("yt-dlp", "YT_DLP_VERSION"), ("mkvtoolnix", "MKVTOOLNIX_VERSION"), ("deno", "DENO_VERSION")):
            version = (root / "binaries" / f"{tool}.version").read_text(encoding="utf-8").strip()
            with patch.dict(os.environ, {env: ""}):
                self.assertEqual(module._configured_version(tool, env, "outdated"), version)
            with patch.dict(os.environ, {env: "2099.01.01"}):
                self.assertEqual(module._configured_version(tool, env, "outdated"), "2099.01.01")

    def test_lockfile_contains_valid_hashes_and_urls(self):
        lock_path = Path(__file__).with_name("trusted_source_hashes.json")
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(lock["schema_version"], 1)
        self.assertGreater(len(lock["sha256_by_url"]), 15)
        for url, checksum in lock["sha256_by_url"].items():
            from urllib.parse import urlsplit
            parsed = urlsplit(url)
            self.assertEqual(parsed.scheme, "https", url)
            self.assertIn(parsed.hostname, {"github.com", "mkvtoolnix.download"}, url)
            self.assertRegex(checksum, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
