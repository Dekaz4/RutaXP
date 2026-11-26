"""Audit the shipped walking source without needing its development checkout."""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import unittest
import xml.etree.ElementTree as ET

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
PATHING = ROOT / "RutaXP/Pathing"


def tool(name):
    spec = importlib.util.spec_from_file_location("rutaxp_" + name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


class PathingVendorTests(unittest.TestCase):
    def test_manifest_hashes_every_original_and_generated_file(self):
        vendor = tool("vendor_pathing")
        manifest = json.loads((PATHING / "VENDORED.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source"]["commit"], vendor.COMMIT)
        self.assertFalse(manifest["adaptation"]["algorithmChanges"])
        expected = {**json.loads((PATHING / "PACK.json").read_text())["files"],
                    **json.loads((PATHING / "UPSTREAM.json").read_text())["files"], **vendor.EXTRA_HASHES}
        self.assertEqual(set(manifest["files"]), set(expected))
        for name, entry in manifest["files"].items():
            with self.subTest(name=name):
                self.assertEqual(entry["sourceSHA256"], expected[name])
                self.assertEqual(sha((PATHING / name).read_bytes()), entry["sha256"])
        for name, entry in manifest["generatedFiles"].items():
            self.assertEqual(sha((PATHING / name).read_bytes()), entry["sha256"])
        for name in ("LICENSE", "CREDITS.md", "UPSTREAM.json", "PACK.json"):
            self.assertEqual(sha((PATHING / name).read_bytes()), vendor.EXTRA_HASHES[name])

    def test_mechanical_changes_reverse_to_the_pinned_source_byte_for_byte(self):
        vendor = tool("vendor_pathing")
        manifest = json.loads((PATHING / "VENDORED.json").read_text())
        for name, entry in manifest["files"].items():
            if not name.endswith(".lua"):
                continue
            with self.subTest(name=name):
                text = (PATHING / name).read_bytes().decode("utf-8")
                self.assertTrue(text.startswith(vendor.HEADER))
                text = text[len(vendor.HEADER):]
                if name.startswith("Nav/"):
                    guard = "if not RutaXPPathingSupported then return end\n"
                    self.assertTrue(text.startswith(guard))
                    text = text[len(guard):]
                if name.startswith("Routing/"):
                    text = text.replace("local root = select(2, ...)\nlocal ns = root.PathingNamespace",
                                        "local ns = select(2, ...)", 1)
                elif name == "API.lua":
                    text = text.replace("local _, root = ...\nlocal ns = root.PathingNamespace",
                                        "local _, ns = ...", 1)
                for old, new in vendor.SUBSTITUTIONS.items():
                    text = text.replace(new, old)
                self.assertEqual(sha(text.encode("utf-8")), entry["sourceSHA256"])

    def test_complete_xml_load_without_decoding_api_is_safe_and_isolated(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        ns = lua.table(Path="original", PathGrid="original", PathSearch="original")
        lua.execute('SendaFHPathData={sentinel=true}; SendaFH_NavEngine="other-addon"')
        loaded = []

        def load(path):
            for element in ET.parse(path).getroot():
                relative = Path(element.attrib["file"])
                self.assertFalse(relative.is_absolute())
                self.assertNotIn("..", relative.parts)
                target = path.parent / relative
                if element.tag.endswith("Include"):
                    load(target)
                elif element.tag.endswith("Script"):
                    loaded.append(target.relative_to(PATHING).as_posix())
                    chunk = lua.execute("return function(...)\n" + target.read_text(encoding="utf-8") + "\nend")
                    chunk("RutaXP", ns)

        load(PATHING / "Pathing.xml")
        self.assertEqual(loaded[0], "Bootstrap.lua")
        self.assertEqual(loaded[-4:], ["Routing/PathGrid.lua", "Routing/Path.lua", "Routing/PathJobs.lua", "API.lua"])
        self.assertFalse(lua.globals().RutaXPPathingSupported)
        self.assertFalse(lua.globals().RutaXPPathEngine.Available(0))
        self.assertEqual(len(list(lua.globals().RutaXPPathData.items())), 0)
        self.assertTrue(lua.globals().SendaFHPathData.sentinel)
        self.assertEqual(lua.globals().SendaFH_NavEngine, "other-addon")
        self.assertEqual((ns.Path, ns.PathGrid, ns.PathSearch), ("original",) * 3)

    def test_waypoint_builder_changes_only_the_generated_catalog_line(self):
        builder = tool("build_waypoints")
        target = ROOT / "RutaXP/Waypoints.lua"
        before = target.read_bytes()
        after = builder.render(ROOT / "RutaXP/Source/waypoints.json", target)
        self.assertEqual(before, after)
        # Excluding Catalog, the engine is unchanged even if the editable
        # snapshot is rebuilt. The generator never emits quest operations.
        pattern = rb"(?m)^local Catalog = [^\r\n]*"
        self.assertEqual(re.sub(pattern, b"", before), re.sub(pattern, b"", after))


if __name__ == "__main__":
    unittest.main()
