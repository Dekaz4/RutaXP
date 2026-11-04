"""Upgrade regressions: player-owned data and explicit route choices survive."""
import unittest

from test_quest_engine import QuestEngineHost


class PersistenceRegressions(unittest.TestCase):
    def test_saved_personal_guides_load_without_mutating_the_saved_source(self):
        h = QuestEngineHost()
        h.group([{"t": "accept", "quest": 100}], id="builtin")
        h.globals.RutaXPDB = h.table({"customGuides": [
            {"id": "personal", "title": "My own route", "steps": [{"title": "Manual instruction"}]},
            {"id": "damaged", "title": "Keep me", "steps": "invalid"},
        ]})
        h.globals.RutaXPCharDB = h.table({"activeGuide": "personal", "recording": "personal",
                                        "progress": {"personal": {"cursor": 1}}})
        h.initialize()
        self.assertEqual(len(h.ns.db.customGuides), 2)
        self.assertEqual(h.ns.db.customGuides[2].steps, "invalid")
        self.assertEqual(h.ns.guides.personal.title, "My own route")
        self.assertEqual(h.ns.char.activeGuide, "personal")
        self.assertEqual(h.ns.char.recording, "personal")
        self.assertIsNone(h.ns.guides.damaged)

    def test_reload_preserves_selected_beta_route_and_review_cursor(self):
        h = QuestEngineHost()
        for id in ("chosen", "recommended"):
            h.guide(id, status="beta", minLevel=1, maxLevel=60, steps=[
                {"title": str(i), "goals": [{"t": "accept", "quest": i}]} for i in range(1, 7)
            ])
        h.globals.RutaXPCharDB = h.table({"activeGuide": "chosen", "seen": True,
            "tracker": False, "trackerPosition": {"point": "RIGHT", "relativePoint": "RIGHT", "x": -20, "y": 80},
            "progress": {"chosen": {"cursor": 4, "review": True}}})
        h.ns.GetRecommendedGuide = h.lua.eval("function(self) return self.guides.recommended end")
        h.initialize()
        self.assertEqual(h.ns.char.activeGuide, "chosen")
        self.assertEqual(h.cursor("chosen"), 4)
        self.assertTrue(h.call("GetProgress", "chosen").review)
        self.assertFalse(h.ns.char.tracker)
        self.assertEqual(h.ns.char.trackerPosition.x, -20)

    def test_first_login_still_chooses_a_recommended_guide(self):
        h = QuestEngineHost(catalog=True)
        h.initialize()
        self.assertEqual(h.ns.char.activeGuide, "forever/alliance/human/01-elwynn-forest")


if __name__ == "__main__":
    unittest.main()
