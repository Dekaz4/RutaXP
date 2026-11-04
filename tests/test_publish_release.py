"""Release publication is transactional at the draft boundary; no live calls."""

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import publish_release as publication


VERSION = "1.2.3"
HEAD = "a" * 40


def fixture(root):
    (root / "RutaXP").mkdir()
    (root / "RutaXP/RutaXP.toc").write_text("## Version: " + VERSION + "\nCore.lua\n", encoding="utf-8")
    (root / "notas.md").write_text("Mejoras de instalación y actualización. Conserva tu progreso.\n", encoding="utf-8")
    dist = root / "dist"
    dist.mkdir()
    runtime = {"RutaXP/RutaXP.toc": (root / "RutaXP/RutaXP.toc").read_bytes(), "RutaXP/Core.lua": b"local _,ns=..."}
    for name in publication.asset_names(VERSION)[:2]:
        with ZipFile(dist / name, "w") as archive:
            for relative, data in runtime.items():
                archive.writestr(relative, data)
            if "-addon" not in name:
                archive.writestr("README.md", "Instrucciones en español")
    (dist / "Instalador_RutaXP.exe").write_bytes(b"MZ fixture installer")
    (dist / "SHA256SUMS.txt").write_text("".join(
        f"{publication.digest(dist / name)}  {name}\n" for name in publication.asset_names(VERSION)[:-1]), encoding="utf-8")


class FakeCommands:
    def __init__(self, root, existing=None):
        self.root = root
        self.release = copy.deepcopy(existing)
        self.local_tag = self.remote_tag = HEAD
        self.remote_head = HEAD
        self.remote = "https://github.com/Dekaz4/RutaXP.git"
        self.dirty = False
        self.build_dirties_tree = False
        self.fail_upload = self.fail_tests = False
        self.corrupt_download = False
        self.other_releases = []
        self.calls, self.events = [], []

    def __call__(self, arguments, root, timeout):
        args = [str(a) for a in arguments]
        self.calls.append(args)
        if args[0] == "git":
            command = args[1]
            if command == "status":
                return " M RutaXP/Core.lua\n" if self.dirty else ""
            if command == "remote":
                return self.remote + "\n"
            if command == "tag" and args[2] == "--list":
                return "v" + VERSION + "\n" if self.local_tag else ""
            if command == "tag":
                self.local_tag = args[-1]
                self.events.append("create-tag")
                return ""
            if command == "fetch":
                self.local_tag = self.remote_tag
                self.events.append("fetch-tag")
                return ""
            if command == "push":
                self.remote_tag = self.local_tag
                self.events.append("push-tag")
                return ""
            if command == "rev-parse":
                return (HEAD if args[-1] == "HEAD" else self.local_tag) + "\n"
            if command == "ls-remote" and args[-1] == "HEAD":
                return self.remote_head + "\tHEAD\n"
            if command == "ls-remote":
                return self.remote_tag + "\trefs/tags/v" + VERSION + "\n" if self.remote_tag else ""
        if args[0] == sys.executable:
            if "tools/build_release.py" in args:
                self.events.append("build")
                if self.build_dirties_tree:
                    self.dirty = True
            else:
                self.events.append("tests")
                if self.fail_tests:
                    raise publication.PublishError("Simulated tests failure")
            return "OK"
        if args[:2] == ["gh", "api"]:
            endpoint = args[-1]
            if "?per_page=" in endpoint:
                return json.dumps([self.other_releases + ([self.release] if self.release else [])])
            return json.dumps(self.release)
        if args[:3] == ["gh", "release", "create"]:
            self.release = {"id": 7, "tag_name": "v" + VERSION, "draft": True, "prerelease": False, "assets": []}
            self.events.append("create-draft")
            return ""
        if args[:3] == ["gh", "release", "edit"]:
            if "--draft=false" in args:
                self.release["draft"] = False
                self.events.append("publish")
            else:
                self.events.append("edit-draft")
            return ""
        if args[:3] == ["gh", "release", "upload"]:
            self.events.append("upload")
            if self.fail_upload:
                raise publication.PublishError("Simulated upload failure")
            self.release["assets"] = [
                {"id": i, "name": name, "state": "uploaded", "size": (self.root / "dist" / name).stat().st_size,
                 "digest": "sha256:" + publication.digest(self.root / "dist" / name)}
                for i, name in enumerate(publication.asset_names(VERSION), 1)]
            return ""
        if args[:3] == ["gh", "release", "download"]:
            self.events.append("download")
            destination = Path(args[args.index("--dir") + 1])
            for name in publication.asset_names(VERSION):
                shutil.copyfile(self.root / "dist" / name, destination / name)
            if self.corrupt_download:
                (destination / "Instalador_RutaXP.exe").write_bytes(b"MZ corrupted")
            return ""
        raise AssertionError("Unexpected test command: " + repr(args))


class PublishReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="RutaXP publication test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture(self.root)
        self.commands = FakeCommands(self.root)
        self.publisher = publication.Publisher(self.root, self.commands)

    def publish(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.publisher.publish(VERSION, self.root / "notas.md")

    def test_default_mode_has_no_subprocess_write_build_test_or_network_side_effect(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(publication, "ROOT", self.root), patch.object(publication.subprocess, "run") as run:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(publication.main([]), 0)
            run.assert_not_called()
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_exact_four_assets_and_checksum_entries_are_required(self):
        self.assertEqual(len(publication.verify_local_assets(self.root / "dist", VERSION)), 4)
        path = self.root / "dist/SHA256SUMS.txt"
        path.write_text(path.read_text() + "a" * 64 + "  Actualizador_RutaXP.exe\n")
        with self.assertRaises(publication.PublishError):
            publication.verify_local_assets(self.root / "dist", VERSION)

    def test_existing_stale_dist_assets_are_never_uploaded(self):
        (self.root / "dist/RutaXP-0.1.0.zip").write_bytes(b"old")
        (self.root / "dist/Actualizador_RutaXP.exe").write_bytes(b"old")
        self.publish()
        upload = next(c for c in self.commands.calls if c[:3] == ["gh", "release", "upload"])
        self.assertFalse(any("0.1.0" in arg or "Actualizador_RutaXP.exe" in arg for arg in upload))

    def test_dirty_tree_wrong_remote_remote_head_and_wrong_tags_stop_before_any_build_or_upload(self):
        for field, value in [("dirty", True), ("remote", "https://github.com/other/RutaXP.git"),
                             ("remote_head", "b" * 40), ("local_tag", "b" * 40), ("remote_tag", "b" * 40)]:
            with self.subTest(field=field):
                commands = FakeCommands(self.root)
                setattr(commands, field, value)
                with self.assertRaises(publication.PublishError), contextlib.redirect_stdout(io.StringIO()):
                    publication.Publisher(self.root, commands).publish(VERSION, self.root / "notas.md")
                self.assertEqual(commands.events, [])

    def test_missing_tag_is_created_and_pushed_only_after_build_tests_and_asset_verification(self):
        self.commands.local_tag = self.commands.remote_tag = None
        self.publish()
        self.assertLess(self.commands.events.index("tests"), self.commands.events.index("create-tag"))
        self.assertLess(self.commands.events.index("push-tag"), self.commands.events.index("create-draft"))
        pushes = [c for c in self.commands.calls if c[:2] == ["git", "push"]]
        self.assertEqual(pushes, [["git", "push", "origin", "refs/tags/v1.2.3:refs/tags/v1.2.3"]])
        self.assertFalse(any("--force" in c for c in self.commands.calls))

    def test_existing_remote_tag_is_fetched_locally_without_moving_or_pushing_it(self):
        self.commands.local_tag = None
        self.publish()
        self.assertIn("fetch-tag", self.commands.events)
        self.assertNotIn("create-tag", self.commands.events)
        self.assertNotIn("push-tag", self.commands.events)

    def test_test_failure_or_build_changing_tracked_source_keeps_github_untouched(self):
        for field in ("fail_tests", "build_dirties_tree"):
            with self.subTest(field=field):
                commands = FakeCommands(self.root)
                setattr(commands, field, True)
                with self.assertRaises(publication.PublishError), contextlib.redirect_stdout(io.StringIO()):
                    publication.Publisher(self.root, commands).publish(VERSION, self.root / "notas.md")
                self.assertFalse(any(e in commands.events for e in ("create-tag", "push-tag", "create-draft", "upload", "publish")))

    def test_success_downloads_and_verifies_all_assets_before_marking_latest(self):
        self.assertTrue(self.publish().endswith("/releases/tag/v1.2.3"))
        self.assertLess(self.commands.events.index("download"), self.commands.events.index("publish"))
        self.assertFalse(self.commands.release["draft"])
        publish = next(c for c in self.commands.calls if "--draft=false" in c)
        self.assertIn("--latest", publish)
        self.assertIn(publication.HOST_REPOSITORY, publish)
        self.assertEqual({a["name"] for a in self.commands.release["assets"]}, set(publication.asset_names(VERSION)))

    def test_failed_upload_retains_a_draft_and_retry_recovers_that_same_draft(self):
        self.commands.fail_upload = True
        with self.assertRaises(publication.PublishError):
            self.publish()
        self.assertTrue(self.commands.release["draft"])
        self.assertNotIn("publish", self.commands.events)
        self.commands.fail_upload = False
        self.publish()
        self.assertEqual(self.commands.events.count("create-draft"), 1)
        self.assertEqual(self.commands.events.count("publish"), 1)

    def test_corrupt_download_never_publishes_partial_or_wrong_latest(self):
        self.commands.corrupt_download = True
        with self.assertRaises(publication.PublishError):
            self.publish()
        self.assertTrue(self.commands.release["draft"])
        self.assertNotIn("publish", self.commands.events)

    def test_published_release_is_never_edited(self):
        self.commands.release = {"id": 7, "tag_name": "v" + VERSION, "draft": False, "prerelease": False, "assets": []}
        with self.assertRaises(publication.PublishError):
            self.publish()
        self.assertEqual(self.commands.events, [])

    def test_unexpected_existing_draft_asset_is_not_deleted_or_overwritten(self):
        self.commands.release = {"id": 7, "tag_name": "v" + VERSION, "draft": True, "prerelease": False,
                                 "assets": [{"id": 99, "name": "private-backup.zip", "size": 1, "state": "uploaded"}]}
        with self.assertRaises(publication.PublishError):
            self.publish()
        self.assertNotIn("upload", self.commands.events)
        self.assertNotIn("edit-draft", self.commands.events)

    def test_release_older_than_an_existing_stable_release_cannot_become_latest(self):
        self.commands.other_releases = [{"tag_name": "v2.0.0", "draft": False, "prerelease": False}]
        with self.assertRaises(publication.PublishError):
            self.publish()
        self.assertEqual(self.commands.events, [])

    def test_local_corruption_and_mismatched_zip_versions_fail_before_upload(self):
        (self.root / "dist/Instalador_RutaXP.exe").write_bytes(b"MZ altered")
        with self.assertRaises(publication.PublishError):
            self.publish()
        self.assertNotIn("create-draft", self.commands.events)

    def test_versions_and_github_hosts_are_matched_exactly(self):
        for version in ("v1.2.3", "1.2", "01.2.3", "1.2.3-beta", "1.2.3+build"):
            with self.assertRaises(publication.PublishError):
                publication.stable_version(version)
        for remote in ("https://github.com.evil/Dekaz4/RutaXP", "https://token@github.com/Dekaz4/RutaXP",
                       "ssh://git@github.comDekaz4/RutaXP", "https://github.com/Dekaz4/RutaXP-extra"):
            self.assertFalse(publication.official_remote(remote))
        self.assertTrue(publication.official_remote("git@github.com:Dekaz4/RutaXP.git"))


if __name__ == "__main__":
    unittest.main()
