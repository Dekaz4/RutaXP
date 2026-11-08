"""Keep the quest catalogue and the player-facing route report in agreement."""
import json
from pathlib import Path
import sys
import unittest

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import review_human_rogue as review


class RogueCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / "RutaXP/Source"
        cls.document = json.loads((source / "leveling.json").read_bytes())
        cls.guides = list(review.route(cls.document))
        lua = LuaRuntime()
        ns = lua.table()
        lua.execute((ROOT / "RutaXP/RogueRewardData.lua").read_text(encoding="utf8"), "RutaXP", ns)
        cls.items = {qid: [dict(row.items()) for row in rows.values()] for qid, rows in ns.rogueQuestRewards.items()}

    def test_real_choices_and_guaranteed_reward_use_the_correct_slots(self):
        self.assertIn((3578, True, "agi", 7), [(i["id"], i["choice"], i["stat"], i["inv"]) for i in self.items[9]])
        blade, = self.items[2206]
        self.assertEqual((blade["id"], blade["choice"], blade["kind"], blade["agility"]), (7298, False, "Daga", 2))
        self.assertTrue(any(i["id"] == 2225 and not i["choice"] for i in self.items[38]))
        self.assertTrue(any(i["id"] == 4126 and i["kind"] == "Hacha" for i in self.items[204]))
        self.assertTrue(any(i["id"] == 3511 and i["kind"] == "Capa" for i in self.items[153]))

    def test_report_matches_applicable_actions_and_shipped_equipment(self):
        ids = {q.get("quest") for g in self.guides for s in g["steps"] if review.fits(s.get("only"), review.PERSONA)
               for q in s["goals"] if q["t"] in ("accept", "turnin") and review.fits(q.get("only"), review.PERSONA)}
        self.assertEqual(len(self.guides), 26)
        self.assertTrue(set(self.items).issubset(ids))
        self.assertGreaterEqual(len(self.items), 75)
        source = ROOT / "RutaXP/Source"
        report = review.review(self.guides, self.items, json.loads((source / "quest_requirements_audit.json").read_bytes()),
                               json.loads((source / "guide_revisions.json").read_bytes())["revisions"])
        self.assertEqual(report, (ROOT / "PICARO_HUMANO.md").read_text(encoding="utf8"))

    def test_filters_for_wearable_physical_gear(self):
        self.assertIsNone(review.gear("13 22 18 2 2 15 dmin10 dmax20 speed1500 cls4"))
        self.assertIsNone(review.gear("17 22 18 2 2 8 dmin10 dmax20 speed1500"))
        self.assertIsNone(review.gear("5 22 18 2 4 3 agi15"))
        self.assertIsNone(review.gear("5 22 18 2 4 2 int15"))
        self.assertEqual(review.gear("13 22 18 2 2 15 dmin10 dmax20 speed1500 cls8")["value"], 10)
