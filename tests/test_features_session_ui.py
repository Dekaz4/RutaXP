"""Independent end-to-end feature-panel checks using the shipping UI and Lua.

Only host APIs are simulated. Production sources are not altered by this test.
"""
import unittest

from test_addon import ADDON, AddonHost


class FeaturesHost(AddonHost):
    def __init__(self, completed_prefix=False):
        super().__init__(real_ui=True)
        self.lua.execute("""
            TEST.now=0; TEST.level=10; TEST.xp=0
            function GetTime() return TEST.now end
            function GetServerTime() return 1000+TEST.now end
            function UnitXP() return TEST.xp end
            function UnitXPMax() return 1000 end
            function UnitIsAFK() return false end
            function UnitOnTaxi() return false end
            function UnitRace() return 'Humano','Human' end
            function UnitClass() return 'Guerrero','WARRIOR' end
        """)
        for name in ("Session.lua", "Adaptation.lua", "FeaturesUI.lua", "Extensions.lua"):
            self.load((ADDON / name).read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        first = {"title": "Uno"}
        if completed_prefix:
            first.update(action="turnin", questID=42)
            self.quest(42, delivered=True)
        self.guide("current", minLevel=10, maxLevel=20, zone=37, faction="Alliance", steps=[
            first, {"title": "Dos"}, {"title": "Tres"},
        ])
        self.initialize()

    def click(self, frame):
        self.globals.Click(frame)

    def tick(self, seconds=1):
        for _ in range(seconds):
            self.state.now += 1
            self.ns.featureDriver.scripts.OnUpdate(self.ns.featureDriver, 1)


class FeaturesSessionUIReviewTests(unittest.TestCase):
    def test_initial_completed_prefix_is_positioned_before_session_measurement_starts(self):
        h = FeaturesHost(completed_prefix=True)
        self.assertEqual(h.ns.char.progress.current.cursor, 2)
        self.assertEqual(h.ns.Session.context.cursor, 2)
        h.tick(1)
        summary = h.ns.Session.GetSummary(h.ns.Session)
        self.assertEqual(summary.stepsAdvanced, 0)
        self.assertEqual(summary.quests, 0)
        self.assertEqual(summary.stepTimings["current:2"].activeSeconds, 1)

    def test_core_initializes_session_once_and_central_driver_refreshes_measurements(self):
        h = FeaturesHost()
        self.assertTrue(h.ns.Session.initialized)
        self.assertIsNotNone(h.ns.toolsButton)
        self.assertIsNotNone(h.ns.Session.frame.events.QUEST_TURNED_IN)
        current = h.ns.Session.current
        driver = h.ns.featureDriver
        h.fire("PLAYER_LOGIN")
        same = h.lua.eval("function(a,b) return a==b end")
        self.assertTrue(same(current, h.ns.Session.current))
        self.assertTrue(same(driver, h.ns.featureDriver))
        h.call("ToggleFeatures", "session")
        before = h.ns.featuresPanel.body.text
        h.tick(3)
        self.assertEqual(h.ns.Session.GetSummary(h.ns.Session).activeSeconds, 3)
        self.assertNotEqual(before, h.ns.featuresPanel.body.text)

    def test_measurement_actions_pause_resume_start_session_and_copy_report(self):
        h = FeaturesHost()
        h.call("ToggleFeatures", "session")
        h.tick(4)
        self.assertEqual(h.ns.featuresPanel.actions[1].text, "Pausar medición")
        h.click(h.ns.featuresPanel.actions[1])
        self.assertTrue(h.ns.Session.GetSummary(h.ns.Session).paused)
        self.assertEqual(h.ns.featuresPanel.actions[1].text, "Reanudar medición")
        h.tick(2)
        h.click(h.ns.featuresPanel.actions[1])
        self.assertFalse(h.ns.Session.GetSummary(h.ns.Session).paused)
        self.assertEqual(h.ns.featuresPanel.actions[2].text, "Empezar otra sesión")
        h.click(h.ns.featuresPanel.actions[2])
        self.assertEqual(h.ns.Session.GetSummary(h.ns.Session).historyCount, 1)
        self.assertEqual(h.ns.Session.GetSummary(h.ns.Session).activeSeconds, 0)
        h.click(h.ns.featuresPanel.actions[3])
        self.assertTrue(h.ns.featureExport.shown)
        self.assertIn("Partida 1", h.ns.featureExport.edit.text)
        self.assertIn("no tiempo exclusivo ni XP por misión", h.ns.featureExport.edit.text)
        self.assertGreaterEqual(h.ns.featureExport.edit.height, 360)

    def test_apply_and_return_ui_actions_preserve_existing_progress_and_review_positions(self):
        h = FeaturesHost()
        h.guide("alternative", minLevel=10, maxLevel=20, zone=2000, faction="Alliance", steps=[
            {"title": "A"}, {"title": "B"}, {"title": "C"},
        ])
        h.call("RefreshUI")  # Create the target's normal UI progress once.
        for id in ("current", "alternative"):
            progress = h.ns.char.progress[id]
            progress.cursor = 2
            progress.review = True
            progress.confirmed["user-mark"] = True
        h.state.mapID = 2000
        h.call("ToggleFeatures", "adaptation")
        self.assertEqual(h.ns.char.activeGuide, "current")
        apply_button = None
        for i in range(1, 7):
            if h.ns.featuresPanel.actions[i].text.startswith("Aplicar propuesta"):
                apply_button = h.ns.featuresPanel.actions[i]
                break
        self.assertIsNotNone(apply_button)
        h.click(apply_button)
        self.assertEqual(h.ns.char.activeGuide, "alternative")
        self.assertEqual(h.ns.char.adaptation.bookmarks[1].guideID, "current")
        for id in ("current", "alternative"):
            self.assertEqual(h.ns.char.progress[id].cursor, 2)
            self.assertTrue(h.ns.char.progress[id].review)
            self.assertTrue(h.ns.char.progress[id].confirmed["user-mark"])
        back_button = None
        for i in range(1, 7):
            if h.ns.featuresPanel.actions[i].text == "Volver a ruta anterior":
                back_button = h.ns.featuresPanel.actions[i]
                break
        self.assertIsNotNone(back_button)
        h.click(back_button)
        self.assertEqual(h.ns.char.activeGuide, "current")
        self.assertEqual(h.ns.char.progress.current.cursor, 2)
        self.assertTrue(h.ns.char.progress.current.review)

    def test_periodic_panel_refresh_does_not_change_selected_route_or_reset_scroll(self):
        h = FeaturesHost()
        h.call("ToggleFeatures", "adaptation")
        h.ns.featuresPanel.scroll.SetVerticalScroll(h.ns.featuresPanel.scroll, 120)
        h.tick(12)
        self.assertEqual(h.ns.char.activeGuide, "current")
        self.assertEqual(h.ns.featuresPanel.scroll.scroll, 120)
        self.assertIsNone(h.ns.char.adaptation)


if __name__ == "__main__":
    unittest.main()
