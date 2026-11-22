"""Original addon downloads are verified before any files reach the composer."""
import hashlib
from http.client import IncompleteRead
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZIP_DEFLATED, ZipFile

from tools import official_sources as official


def archive_bytes(entries):
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return stream.getvalue()


class OfficialSourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.cache = self.work / "cache"
        self.downloads = self.work / "downloads"
        self.cache.mkdir()
        self.downloads.mkdir()
        self.data = archive_bytes([("Journey/Journey.toc", b"## Version: 1"),
                                   ("Journey/art/arrow", b"arrow"),
                                   ("OtherAddon/OtherAddon.toc", b"unused")])
        self.source = official.Source("Journey-1.zip", hashlib.sha256(self.data).hexdigest(),
                                      "https://cdn.example.com/Journey-1.zip",
                                      "https://example.com/download/journey")
        self.cached = self.cache / self.source.filename
        self.report = Mock()
        self.enter_patch(patch.dict(official.SOURCES, {"Journey": self.source}))
        self.enter_patch(patch.object(official, "downloads_directory", return_value=self.downloads))
        self.browser = self.enter_patch(patch.object(official.webbrowser, "open",
                                                     side_effect=AssertionError("unexpected browser launch")))
        self.http = self.enter_patch(patch.object(official, "urlopen", side_effect=AssertionError("unexpected HTTP")))

    def enter_patch(self, patcher):
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_verified_cache_can_be_used_offline_and_only_requested_addon_is_unpacked(self):
        self.cached.write_bytes(self.data)
        with self.assertRaisesRegex(RuntimeError, "composer interrupted"):
            with official.acquire("Journey", self.cache, self.report) as root:
                self.assertEqual((root / "Journey.toc").read_bytes(), b"## Version: 1")
                self.assertEqual((root / "art/arrow").read_bytes(), b"arrow")
                self.assertFalse((root.parent / "OtherAddon").exists())
                raise RuntimeError("composer interrupted")
        self.assertFalse(root.parent.exists())
        self.assertEqual(list(self.cache.iterdir()), [self.cached])
        self.assertEqual(self.cached.read_bytes(), self.data)
        self.browser.assert_not_called()
        self.http.assert_not_called()

    def test_existing_numbered_browser_download_promotes_only_matching_zip(self):
        self.cached.write_bytes(b"corrupt cache")
        (self.downloads / self.source.filename).write_bytes(b"corrupt download")
        numbered = self.downloads / "Journey-1 (2).zip"
        numbered.write_bytes(self.data)
        with official.acquire("Journey", self.cache, self.report) as root:
            self.assertTrue((root / "Journey.toc").is_file())
        self.assertEqual(self.cached.read_bytes(), self.data)
        self.assertEqual(numbered.read_bytes(), self.data)
        self.assertFalse(root.parent.exists())
        self.browser.assert_not_called()
        self.http.assert_not_called()

    def test_fresh_install_downloads_pinned_file_without_browser_or_user_input(self):
        self.http.side_effect = lambda *_args, **_kwargs: io.BytesIO(self.data)
        with official.acquire("Journey", self.cache, self.report) as root:
            self.assertEqual((root / "Journey.toc").read_bytes(), b"## Version: 1")
        self.assertEqual(self.cached.read_bytes(), self.data)
        self.assertEqual(self.http.call_args.args[0].full_url, self.source.url)
        self.browser.assert_not_called()

    def test_blocked_cache_promotion_does_not_interrupt_verified_install(self):
        self.cached.write_bytes(b"old content")
        self.http.side_effect = lambda *_args, **_kwargs: io.BytesIO(self.data)
        with patch.object(Path, "replace", side_effect=PermissionError(5, "Access denied")) as replace:
            with official.acquire("Journey", self.cache, self.report) as root:
                self.assertEqual((root / "art/arrow").read_bytes(), b"arrow")
        replace.assert_called_once()
        self.assertEqual(self.cached.read_bytes(), b"old content")
        self.assertTrue(any("continúa" in call.args[0] for call in self.report.call_args_list))
        self.assertEqual(list(self.cache.iterdir()), [self.cached])
        self.browser.assert_not_called()

    def test_existing_directory_at_cache_filename_is_preserved(self):
        self.cached.mkdir()
        sentinel = self.cached / "existing.txt"
        sentinel.write_bytes(b"keep")
        self.http.side_effect = lambda *_args, **_kwargs: io.BytesIO(self.data)
        with official.acquire("Journey", self.cache, self.report) as root:
            self.assertEqual((root / "Journey.toc").read_bytes(), b"## Version: 1")
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_read_only_cache_stages_in_system_temp_and_uses_downloads_offline(self):
        (self.downloads / self.source.filename).write_bytes(self.data)
        temp_factory = tempfile.TemporaryDirectory
        def tempdir(*args, **kwargs):
            if kwargs.get("dir") == self.cache:
                raise PermissionError(5, "Access denied")
            return temp_factory(*args, **kwargs)
        with patch.object(official.tempfile, "TemporaryDirectory", side_effect=tempdir):
            with official.acquire("Journey", self.cache, self.report) as root:
                self.assertEqual((root / "art/arrow").read_bytes(), b"arrow")
                self.assertFalse(root.is_relative_to(self.cache))
        self.assertFalse(root.exists())
        self.assertEqual(list(self.cache.iterdir()), [])
        self.http.assert_not_called()
        self.browser.assert_not_called()

    def test_browser_download_finishes_after_an_incomplete_candidate(self):
        downloaded = self.downloads / "Journey-1 (1).zip"
        downloaded.write_bytes(b"in progress")
        self.browser.side_effect = None
        self.browser.return_value = True
        self.http.side_effect = OSError("offline")
        with patch.object(official.time, "sleep", side_effect=lambda _: downloaded.write_bytes(self.data)) as wait:
            with official.acquire("Journey", self.cache, self.report) as root:
                self.assertEqual((root / "art/arrow").read_bytes(), b"arrow")
        self.browser.assert_called_once_with(self.source.browser_url, new=2)
        wait.assert_called_once()
        self.http.assert_called_once()
        self.assertEqual(self.cached.read_bytes(), self.data)
        self.assertFalse(root.parent.exists())

    def test_missing_browser_download_times_out_without_replacing_cache(self):
        self.cached.write_bytes(b"prior")
        self.browser.side_effect = None
        self.browser.return_value = True
        self.http.side_effect = OSError("HTTP service unavailable")
        with patch.object(official.time, "monotonic", side_effect=[10, 311]):
            with self.assertRaisesRegex(ValueError, "Journey-1.zip"):
                with official.acquire("Journey", self.cache, self.report):
                    self.fail("unverified files reached the composer")
        self.assertEqual(list(self.cache.iterdir()), [self.cached])
        self.assertEqual(self.cached.read_bytes(), b"prior")
        self.http.assert_called_once()

    def test_browser_recovers_interrupted_or_invalid_response_and_only_caches_verified_zip(self):
        class InterruptedResponse(io.BytesIO):
            def read(self, *args):
                raise IncompleteRead(b"partial")

        for direct in (io.BytesIO(b"<html>not the addon</html>"), InterruptedResponse()):
            with self.subTest(response=direct):
                self.http.side_effect = lambda *_args, **_kwargs: direct
                downloaded = self.downloads / self.source.filename
                self.browser.side_effect = lambda *_args, **_kwargs: bool(downloaded.write_bytes(self.data))
                with official.acquire("Journey", self.cache, self.report) as root:
                    self.assertEqual((root / "art/arrow").read_bytes(), b"arrow")
                self.assertEqual(self.cached.read_bytes(), self.data)
                self.cached.unlink()
                downloaded.unlink()

    def test_direct_download_with_bad_hash_never_replaces_cache(self):
        source = official.Source(self.source.filename, self.source.sha256, self.source.url)
        self.cached.write_bytes(b"prior")
        self.http.side_effect = lambda *_args, **_kwargs: io.BytesIO(b"truncated HTTP response")
        with patch.dict(official.SOURCES, {"Journey": source}):
            with self.assertRaisesRegex(ValueError, "Journey"):
                with official.acquire("Journey", self.cache, self.report):
                    self.fail("unverified files reached the composer")
        self.assertEqual(list(self.cache.iterdir()), [self.cached])
        self.assertEqual(self.cached.read_bytes(), b"prior")
        self.http.assert_called_once()
        self.browser.assert_not_called()

    def test_tree_pin_accepts_repacked_release_but_rejects_content_and_path_changes(self):
        entries = [("data/boss.lua", b"123"), ("Journal.toc", b"journal")]
        manifest = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n"
                           for name, data in sorted(entries))
        pin = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
        source = official.Source("journal.zip", pin, "https://example.com/journal", tree_root="Journal",
                                 archive_sha256="0" * 64)
        archive = self.downloads / source.filename
        for description, contents, expected in (
            ("original", entries, True),
            ("reordered", list(reversed(entries)), True),
            ("same-size edit", [("data/boss.lua", b"456"), entries[1]], False),
            ("renamed", [("data/else.lua", b"123"), entries[1]], False),
            ("missing", entries[:1], False),
            ("extra", [*entries, ("Core.lua", b"")], False),
        ):
            with self.subTest(description=description):
                archive.write_bytes(archive_bytes([("Journal/" + name, data) for name, data in contents]))
                self.assertEqual(official.matches(archive, source), expected)


class DownloadsFolderTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows known-folder registry")
    def test_windows_downloads_directory_follows_redirected_known_folder(self):
        import winreg
        redirected = Path("E:/Descargas de juegos")
        with patch.object(winreg, "OpenKey"), \
                patch.object(winreg, "QueryValueEx", return_value=("%RUTAXP_TEST_DOWNLOADS%", winreg.REG_EXPAND_SZ)), \
                patch.dict(os.environ, {"RUTAXP_TEST_DOWNLOADS": str(redirected)}):
            self.assertEqual(official.downloads_directory(), redirected)
