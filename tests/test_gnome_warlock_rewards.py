import sys
import unittest

from test_quest_engine import ADDON, QuestEngineHost

sys.path.insert(0, str(ADDON.parent / "tools"))
from build_warlock_rewards import caster_gear


class GnomeWarlockRewardTests(unittest.TestCase):
    def test_catalog_eligibility(self):
        for raw in ("17 20 10 2 2 1 int10", "5 20 10 2 4 2 sp9", "13 20 10 2 2 7 str4 sta4",
                    "26 20 10 2 2 19 dmin10 dmax20 speed1500 cls16", "5 20 10 2 4 1 heal9"):
            with self.subTest(raw=raw):
                self.assertIsNone(caster_gear(raw))
        wand = caster_gear("26 20 10 2 2 19 dmin10 dmax20 speed1500 cls256")
        self.assertEqual((wand["kind"], wand["stat"], wand["value"]), ("Varita", "dps", 10))
        self.assertEqual(caster_gear("17 20 10 2 2 10 int2 sp9")["stat"], "sp")

    def test_planned_westfall_wand_appears_only_for_gnome_warlock(self):
        h = QuestEngineHost()
        h.state.classToken, h.state.raceToken = "WARLOCK", "Gnome"
        for module in ("WarlockRewardData.lua", "RogueRewards.lua"):
            h.load((ADDON / module).read_text(encoding="utf-8"), "RutaXP", h.ns)
        h.group([{"t": "accept", "quest": 14}])
        h.initialize()
        _, step, state = h.call("GetCurrent")
        rows, _ = h.call("GetStepGoalItems", step, state)
        self.assertIn("Varita", rows[1].subtitle)
        self.assertIn("Chispa de la Milicia del Pueblo", rows[1].details)
        for race, cls in (("Gnome", "ROGUE"), ("Human", "WARLOCK"), ("Gnome", "MAGE")):
            h.state.raceToken, h.state.classToken = race, cls
            self.assertIsNone(h.call("GetLevelingQuestRewardInfo", 14))
