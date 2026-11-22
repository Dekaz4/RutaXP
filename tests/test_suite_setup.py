import hashlib
from contextlib import contextmanager
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
        self.client = self.work / "World of Warcraft/_forever_"
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

    def test_composition_uses_only_local_modules_and_never_installs(self):
        inputs = {"OpenMap": self.addons / "OpenMap", "ForeverDungeonJournal": self.addons / "ForeverDungeonJournal"}
        output = self.work / "private.zip"
        with patch.object(suite_setup, "find_native_sources", return_value=inputs), \
                patch.object(suite_setup.composer, "compose") as compose, \
                patch.object(suite_setup.official_sources, "acquire") as acquire, \
                patch.object(suite_setup, "activate") as activate:
            self.assertIn(str(output), suite_setup.run(self.client, self.work, output, compose_only=True))
            self.assertEqual(compose.call_args.args[1], inputs)
            activate.assert_not_called()
            acquire.assert_not_called()
            with self.assertRaises(ValueError):
                suite_setup.compose_bundle(self.client, self.addons / "unsafe.zip", self.work)

    def test_normal_install_resolves_all_missing_sources_only_for_composition(self):
        cache = self.work / "cache"
        expected = {"OpenMap", "ForeverDungeonJournal", "Journey"}
        active = {}
        requested = []

        @contextmanager
        def download(name, folder, progress):
            self.assertEqual(folder, cache)
            self.assertIs(progress, report)
            with tempfile.TemporaryDirectory(dir=self.work) as temporary:
                root = Path(temporary) / name
                root.mkdir()
                (root / (name + ".toc")).touch()
                requested.append(name)
                active[name] = root
                try:
                    yield root
                finally:
                    del active[name]

        def prepare(template, roots, prepared, progress):
            self.assertEqual(set(roots), expected)
            for name, root in roots.items():
                self.assertTrue((root / (name + ".toc")).is_file())
            prepared.mkdir()

        def install(client, *, prepared):
            self.assertFalse(active)
            self.assertTrue(prepared.is_dir())
            return "installed"

        report = lambda _: None
        with patch.object(suite_setup.official_sources, "acquire", side_effect=download), \
                patch.object(suite_setup.composer, "prepare_directory", side_effect=prepare), \
                patch.object(suite_setup, "activate", side_effect=install):
            self.assertEqual(suite_setup.run(self.client, cache, report=report), "installed")
            self.assertCountEqual(requested, expected)
            requested.clear()
            (self.addons / "OpenMap").mkdir()
            (self.addons / "OpenMap/OpenMap.toc").touch()
            tx = suite_setup.backup_store(self.client) / ("2" * 17 + "-" + "b" * 32)
            prior = tx / "prior/0"
            prior.mkdir(parents=True)
            (prior / "ForeverDungeonJournal.toc").touch()
            (tx / "plan.json").write_text(json.dumps({"rows": [{"dest": "Interface/AddOns/ForeverDungeonJournal"}]}))
            (tx / "committed").touch()
            self.assertEqual(suite_setup.run(self.client, cache, report=report), "installed")
            self.assertEqual(requested, ["Journey"])

    def test_missing_journey_during_download_releases_earlier_sources_before_activation(self):
        active = []

        @contextmanager
        def acquire(name, cache, progress):
            if name == "Journey":
                raise OSError("Journey unavailable")
            active.append(name)
            try:
                yield self.work / name
            finally:
                active.remove(name)

        with patch.object(suite_setup.official_sources, "acquire", side_effect=acquire), \
                patch.object(suite_setup.composer, "prepare_directory") as prepare, \
                patch.object(suite_setup, "activate") as activate:
            with self.assertRaisesRegex(OSError, "Journey unavailable"):
                suite_setup.run(self.client, self.work)
            self.assertFalse(active)
            prepare.assert_not_called()
            activate.assert_not_called()
            self.assertFalse(list(suite_setup.backup_store(self.client).glob(".RutaXP-stage-*")))

    def test_second_update_finds_journey_after_it_moved_out_of_addons(self):
        for name in ("OpenMap", "ForeverDungeonJournal"):
            (self.addons/name).mkdir()
            (self.addons/name/(name+".toc")).touch()
        tx = suite_setup.backup_store(self.client) / ("2"*17 + "-" + "b"*32)
        prior = tx / "prior/0"
        prior.mkdir(parents=True)
        (prior/"Journey.toc").touch()
        (tx/"plan.json").write_text(json.dumps({"rows":[{"dest":"Interface/AddOns/Journey"}]}))
        (tx/"committed").touch()
        self.assertEqual(suite_setup.find_native_sources(self.client)["Journey"], prior)

    def test_store_scopes_to_installation_and_flavor_outside_battlenet_root(self):
        store = self.work / "RutaXP-Suite-Backups/World of Warcraft"
        self.assertEqual(suite_setup.backup_store(self.client), store / "_forever_")
        beta = self.client.parent / "_classic_beta_"
        self.assertEqual(suite_setup.backup_store(beta), store / "_classic_beta_")
        custom = self.client.parent / "Custom"
        (custom.parent / ".build.info").touch()
        self.assertEqual(suite_setup.backup_store(custom), store / "Custom")
        other = self.work / "Second installation/_forever_"
        self.assertNotEqual(suite_setup.backup_store(other), suite_setup.backup_store(self.client))
        collision = self.work / "RutaXP-Suite-Backups/_forever_"
        self.assertEqual(suite_setup.backup_store(collision),
                         self.work / "RutaXP-Suite-Backups-External/RutaXP-Suite-Backups/_forever_")

    def test_upgrades_personal_install_without_standalone_sources_or_first_pc_backups(self):
        from tools import suite_journey
        installed = self.addons / "RutaXP"
        installed.mkdir()
        files = {"Bindings.xml": b'<Bindings><Binding name="OPENMAP_FIND"/><Binding name="FOREVERDUNGEONJOURNAL_TOGGLE"/></Bindings>'}
        toc = ["## X-RutaXP-Embedded: OpenMap, ForeverDungeonJournal, RXPGuides",
               "## SavedVariables: OpenMapDB, ForeverDungeonJournalDB, RutaXPRestedDB",
               "## SavedVariablesPerCharacter: OpenMapCharDB, ForeverDungeonJournalCharacterDB, RXPCData",
               "## X-RutaXP-Journey-UI: 4.00.13"]
        for name in ("OpenMap", "ForeverDungeonJournal"):
            toc.extend((f"## X-{name}-Title: {name}", f"## X-{name}-Version: 1", f"Modules/{name}/Init.lua"))
            files[f"Modules/{name}/Init.lua"] = b"-- integrated native source"
        for file in suite_journey.entries(None):
            files[file] = b"setfenv(1, RutaXPJourneyEnvironment())\n"
            toc.append(file)
        arrow = "Modules/Journey/lib/TomCats/Arrows.lua"
        files[arrow] += b"GetWorldPosFromMapPos(mapID, { x = targetX, y = targetY })"
        for asset in suite_journey.IMAGES:
            files["Modules/Journey/images/" + asset] = b"art"
        files["Modules/Journey/license.txt"] = b"license"
        files["Modules/RXPGuides/unwanted.lua"] = b"-- old runtime"
        files["RutaXP.toc"] = "\n".join(toc).encode()
        for name, data in files.items():
            target = installed / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (installed / "manifest.sha256").write_text("\n".join(
            f"{hashlib.sha256(data).hexdigest()}  {name}" for name,data in files.items()))
        template = self.work / "template/RutaXP"
        template.mkdir(parents=True)
        (template / "RutaXP.toc").write_text("## Version: 1.2.0\nLeveling.lua\n")
        (template / "Leveling.lua").write_text("-- current guide")
        for name in ("NOTICE.md", "LICENSE"):
            (template.parent / name).write_text(name)
        output = self.work / "suite.zip"
        roots = suite_setup.find_native_sources(self.client)
        self.assertEqual(set(roots), {"OpenMap", "ForeverDungeonJournal", "Journey"})
        suite_setup.composer.compose(template, roots, output)
        captured = []
        def verify_prepared(client, *, prepared):
            self.assertEqual(client, self.client)
            self.assertEqual(prepared.parent.parent, suite_setup.backup_store(self.client))
            captured.append(prepared)
            with ZipFile(output) as archive:
                files = {f.relative_to(prepared).as_posix(): f for f in prepared.rglob("*") if f.is_file()}
                self.assertEqual(set(archive.namelist()), {"RutaXP/" + name for name in files})
                for name, file in files.items():
                    self.assertEqual(file.read_bytes(), archive.read("RutaXP/" + name), name)
            return "installed"

        with patch.object(suite_setup, "resources", return_value=template.parent), \
                patch.object(suite_setup.composer, "compose", side_effect=AssertionError("unexpected ZIP")), \
                patch.object(suite_setup, "activate", side_effect=verify_prepared):
            self.assertEqual(suite_setup.run(self.client, self.work, report=lambda _: None), "installed")
        self.assertFalse(captured[0].parent.exists())
        with ZipFile(output) as archive:
            self.assertNotIn("RutaXP/Modules/RXPGuides/unwanted.lua", archive.namelist())
            self.assertNotIn(b"RutaXPRestedDB", archive.read("RutaXP/RutaXP.toc"))
            self.assertIn(b"OpenMapCharDB", archive.read("RutaXP/RutaXP.toc"))
            self.assertIn(b"CreateVector2D", archive.read("RutaXP/" + arrow))
        (installed / "Modules/OpenMap/Init.lua").write_text("changed")
        with self.assertRaisesRegex(ValueError, "ha cambiado"):
            suite_setup.composer.compose(template, roots, output)
        backup = self.addons / (".RutaXP.backup." + "b" * 32)
        installed.rename(backup)
        self.assertEqual(set(suite_setup.find_native_sources(self.client).values()), {backup})

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
