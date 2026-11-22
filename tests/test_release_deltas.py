import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools import release_deltas as deltas
from tools.publish_release import version_from_toc


class ReleaseDeltaTests(unittest.TestCase):
    def test_every_supported_baseline_produces_only_its_changed_payload(self):
        root = Path(__file__).resolve().parents[1]
        version = version_from_toc((root / "RutaXP/RutaXP.toc").read_text(encoding="utf-8-sig"))
        new = json.loads((root / deltas.CATALOG / (version + ".json")).read_bytes())
        with tempfile.TemporaryDirectory() as work:
            for old in deltas.compatible_bases(root, new):
                with self.subTest(base=old["version"]):
                    path = Path(work) / "delta.zip"
                    deltas.write_delta(root, old, new, path)
                    with ZipFile(path) as archive:
                        header, *rows = archive.read("delta.tsv").decode().splitlines()
                        self.assertEqual(header, f'RutaXP-delta-v1\t{old["version"]}\t{version}')
                        expected = {name for name in old["files"].keys() | new["files"].keys()
                                    if old["files"].get(name) != new["files"].get(name)}
                        self.assertEqual({row.split("\t")[2] for row in rows}, expected)
                        payload = {"delta.tsv", "old/RutaXP.toc"}
                        self.assertEqual(deltas.sha(archive.read("old/RutaXP.toc")), old["files"]["RutaXP.toc"])
                        for row in rows:
                            before, after, name = row.split("\t")
                            self.assertEqual(before, old["files"].get(name, "-"))
                            self.assertEqual(after, new["files"].get(name, "-"))
                            if after != "-":
                                payload.add("files/" + name)
                                self.assertEqual(deltas.sha(archive.read("files/" + name)), after)
                        self.assertEqual(payload, set(archive.namelist()))
                        self.assertEqual(len(payload), len(archive.namelist()))

    def test_skips_incompatible_recipe_and_newer_installations(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            catalog = root / deltas.CATALOG
            catalog.mkdir(parents=True)
            for version, recipe in (("1.2.8", "old"), ("1.2.9", "current"), ("1.2.10", "current"),
                                    ("1.2.12", "current"), ("1.2.13", "current")):
                (catalog / (version + ".json")).write_text(json.dumps(dict(version=version, recipe=recipe)))
            bases = deltas.compatible_bases(root, {"version": "1.2.12", "recipe": "current"})
            self.assertEqual({item["version"] for item in bases}, {"1.2.9", "1.2.10"})
