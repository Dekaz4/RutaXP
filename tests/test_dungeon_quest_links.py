import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from lupa.lua51 import LuaRuntime

from tools import build_dungeon_quest_links as generator


class DungeonQuestLinksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lua = LuaRuntime()
        ns = lua.table()
        lua.execute(
            (generator.ROOT / "RutaXP/DungeonQuestData.lua").read_text(
                encoding="utf-8"
            ),
            "RutaXP",
            ns,
        )
        cls.data = ns.DungeonQuestData

    def test_real_inside_outside_and_shared_followups(self):
        qs = self.data.quests
        self.assertEqual(self.data.dungeons["The Deadmines"].instanceID, 36)
        self.assertIn(167, list(self.data.dungeons["The Deadmines"].quests.values()))
        self.assertEqual(
            (qs[167].pickup.npc, qs[167].pickup.map, qs[167].pickup.inside),
            (656, 1453, False),
        )
        self.assertEqual((qs[96395].pickup.inside, qs[96395].pickup.map), (True, None))
        self.assertEqual((qs[2948].pickup.inside, qs[2948].pickup.map), (False, 1455))
        self.assertIn(155, list(qs[214].pre.values()))
        self.assertTrue(qs[214].workInside)
        self.assertEqual(qs[79946].classToken, "PALADIN")
        self.assertTrue(qs[7761].unavailable)
        self.assertIsNone(qs[2930001])  # Punch-card checklist; not a quest ID.

    def test_every_reachable_quest_is_named_and_prerequisites_form_a_dag(self):
        finished, pending = set(), set()

        def visit(id):
            if id in finished:
                return
            self.assertNotIn(id, pending)
            pending.add(id)
            q = self.data.quests[id]
            self.assertTrue(q.title, id)
            for kind in ("pre", "preAll"):
                for previous in generator.ARRAY(q[kind]):
                    visit(abs(previous))
            pending.remove(id)
            finished.add(id)

        for dungeon in self.data.dungeons.values():
            self.assertLessEqual(dungeon.minLevel, dungeon.maxLevel)
            for q in dungeon.quests.values():
                visit(q)
        self.assertEqual(finished, set(self.data.quests.keys()))
        for q in self.data.quests.values():
            for point in (q.pickup, q.turnin):
                if point.map:
                    self.assertTrue(0 <= point.x <= 100 and 0 <= point.y <= 100)
                    self.assertIn(point.f, ("e", "l"))
                    self.assertIsNot(point.inside, True)

    def test_selects_only_first_party_active_forever_dsl_and_converts_world_coordinates(
        self,
    ):
        with TemporaryDirectory() as tmp:
            archive = Path(tmp) / "official.zip"
            with ZipFile(archive, "w") as z:
                z.writestr(
                    "RX/Guides/forever/Alliance-example.lua",
                    "#name Westfall\nstep\n.accept 42\n--.turnin 404\nstep\n"
                    ".goto 1436/0,50,0\n.turnin 42\n.complete 43,2\nstep\n"
                    "#completewith next\n.goto 1436/0,80,0\n.complete 44,1\nstep\n"
                    ".goto 1436/0,50,0\n.goto 1436/0,80,0\n.turnin 45\nstep\n"
                    ".goto 1436/0,50,0\n.turnin 46\nstep\n.goto 1436/0,70,0\n.turnin 46",
                )
                z.writestr(
                    "RX/Guides/forever/dungeon/guide.lua",
                    "#name 18-20 The Deadmines\nstep\n"
                    ".goto 1436/0,50,0\n.accept 51\n.complete 51,1\nstep\n.turnin 52",
                )
                z.writestr(
                    "RX/lang/Guides-esES/forever/dungeon/guide.lua", ".accept 7654"
                )
                z.writestr("RX/Guides/other/imported.lua", ".accept 12345")
            with self.assertRaises(ValueError):
                generator.rxp_facts(archive, {})
            frames = {
                "1436": {"c": 0, "left": 100, "right": 0, "top": 10, "bottom": -30}
            }
            with patch.object(
                generator,
                "ARCHIVE_HASH",
                hashlib.sha256(archive.read_bytes()).hexdigest(),
            ):
                world, dungeon, acts, places, targets = generator.rxp_facts(
                    archive, frames
                )
            self.assertEqual(world, {42, 43, 44, 45, 46})
            self.assertEqual(dungeon, {51, 52})
            self.assertEqual(acts["Deadmines", "complete"], {51})
            self.assertEqual(
                places[51, "pickup"], {"map": 1436, "x": 50, "y": 25, "f": "e"}
            )
            self.assertEqual(set(targets), {42, 43})
            point = {"map": 1436, "x": 50, "y": 25, "f": "e", "faction": "Alliance"}
            self.assertEqual(targets[42], {"turnin": point})
            self.assertEqual(targets[43], {"work": {**point, "objectiveIndex": 2}})
