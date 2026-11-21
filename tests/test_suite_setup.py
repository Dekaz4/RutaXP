import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from tools import build_suite_setup, suite_setup


class PortableSuiteSetupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.client = self.work / "_forever_"
        self.addons = self.client / "Interface/AddOns"
        self.addons.mkdir(parents=True)

    def test_detects_existing_game_targets_and_saved_client(self):
        for candidate in (self.addons, self.client, self.client.parent):
            self.assertEqual(suite_setup.client_from(candidate), self.client)
        (self.work / "client.txt").write_text(str(self.addons), encoding="utf-8-sig")
        with patch.object(suite_setup, "settings_root", return_value=self.work):
            self.assertEqual(suite_setup.detect_client(), self.client)

    def test_repeated_build_uses_only_committed_originals_and_prefers_active_versions(self):
        tx = self.client / "RutaXP-Suite-Backups" / ("1" * 17 + "-" + "a" * 32)
        rows = []
        for index, module in enumerate(("OpenMap", "ForeverDungeonJournal")):
            prior = tx / "prior" / str(index)
            prior.mkdir(parents=True)
            (prior / (module + ".toc")).touch()
            rows.append({"dest": f"Interface/AddOns/{module}"})
        (tx / "plan.json").write_text(json.dumps({"rows": rows}))
        with self.assertRaisesRegex(ValueError, "OpenMap"):
            suite_setup.find_native_sources(self.client)
        (tx / "committed").touch()
        (self.addons / "OpenMap").mkdir()
        (self.addons / "OpenMap/OpenMap.toc").touch()
        self.assertEqual(suite_setup.find_native_sources(self.client),
                         {"OpenMap": self.addons / "OpenMap", "ForeverDungeonJournal": tx / "prior/1"})

    def test_composition_uses_official_rested_and_never_installs(self):
        inputs = {"OpenMap": self.addons / "OpenMap", "ForeverDungeonJournal": self.addons / "ForeverDungeonJournal"}
        output = self.work / "private.zip"
        with patch.object(suite_setup, "prepare_official_source", return_value=self.work / "stock") as source, \
                patch.object(suite_setup, "find_native_sources", return_value=inputs), \
                patch.object(suite_setup.composer, "compose") as compose, \
                patch.object(suite_setup, "activate") as activate:
            self.assertIn(str(output), suite_setup.run(self.client, self.work, output, compose_only=True))
            self.assertIsNone(source.call_args.args[0])
            self.assertEqual(compose.call_args.args[1]["RXPGuides"], self.work / "stock")
            activate.assert_not_called()
            with self.assertRaises(ValueError):
                suite_setup.compose_bundle(self.client, self.addons / "unsafe.zip", self.work)

    def test_public_data_inputs_only(self):
        allowed = build_suite_setup.bundle_inputs(build_suite_setup.ROOT)
        self.assertTrue(all(p.is_file() for p in allowed))
        self.assertTrue(all(p.suffix.lower() not in (".zip", ".exe", ".blp") for p in allowed))
        self.assertFalse(any("Modules" in p.parts or ".sources" in p.parts for p in allowed))

    @unittest.skipUnless(os.name == "nt", "Requires the Windows setup executable")
    def test_frozen_installer_relocates_from_active_addon_and_can_restore(self):
        binary = build_suite_setup.ROOT / "dist/Instalar_Suite_RutaXP.exe"
        if not binary.is_file():
            self.skipTest("Build the public setup executable first")
        addon = self.addons / "RutaXP"
        addon.mkdir()
        original_exe = addon / binary.name
        shutil.copyfile(binary, original_exe)
        body = b"## X-RutaXP-Embedded: OpenMap, ForeverDungeonJournal, RXPGuides\n"
        bundle = self.work / "suite.zip"
        with ZipFile(bundle, "w") as archive:
            archive.writestr("RutaXP/RutaXP.toc", body)
            archive.writestr("RutaXP/manifest.sha256", hashlib.sha256(body).hexdigest() + "  RutaXP.toc\n")
        env = {**os.environ, "LOCALAPPDATA": str(self.work / "local")}
        launch = subprocess.run([str(original_exe), "--client", str(self.client), "--archive", str(bundle)],
                                cwd=self.work, env=env, capture_output=True, timeout=120)
        self.assertEqual(launch.returncode, 0, launch.stderr)
        self.assertTrue((addon / "RutaXP.toc").exists(), launch.stdout + launch.stderr)
        self.assertFalse(original_exe.exists())
        restore = subprocess.run([str(binary), "--client", str(self.client), "--restore"], cwd=self.work,
                                 env=env, capture_output=True, timeout=90)
        self.assertEqual(restore.returncode, 0, restore.stderr)
        self.assertTrue(original_exe.is_file())
