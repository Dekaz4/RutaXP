"""The physical journey owns its tracker, map pin and arrow without editing quests."""
import unittest

from test_access_navigation import AccessHost, DWARF


class GuideTravelUITests(unittest.TestCase):
    def journey(self, **leg):
        h = AccessHost(DWARF, 6, x=.4, y=.5)
        h.s.travel = h.h.table(leg)
        h.h.lua.execute("""
            function ACCESS_NS:GetGuideTravel() return TEST.travel end
            function ACCESS_NS:SkipGuideTravel()
                TEST.travelSkips = (TEST.travelSkips or 0) + 1
                TEST.travel = nil
                self:RefreshUI()
            end
        """)
        h.ns.char.trackerSize = h.h.table({"width": 430, "height": 410})
        h.ns.RefreshUI(h.ns)
        h.ns.UpdateNavigation(h.ns)
        return h

    def test_landmark_replaces_quest_rows_and_all_map_and_arrow_targets(self):
        h = self.journey(title="Puente a Poniente", text="Cruza el puente.",
                         index=4, total=6, point={"mapID": 1426, "x": .5, "y": .6})
        # Travel also wins when the regular quest arrow would direct us to the partner.
        h.ns.Duo.GetMeetingWaypoint = h.h.lua.eval('function() return {mapID=1426,x=.2,y=.3,source="duo-meeting"} end')
        before = h.progress()
        h.ns.RefreshUI(h.ns)
        h.ns.UpdateNavigation(h.ns)
        for title in (h.ns.stepTitle, h.ns.trackerStep):
            self.assertEqual(title.text, "Puente a Poniente")
        for label in (h.ns.stepCount, h.ns.trackerProgress):
            self.assertEqual(label.text, "Viaje 4/6")
        self.assertEqual(h.ns.trackerText.text, "Cruza el puente.")
        self.assertEqual(h.ns.trackerCurrentCount, 0)
        self.assertEqual(h.ns.trackerPreviewCount, 0)
        self.assertTrue(all(not row.shown for row in h.ns.trackerRows.values()))
        self.assertTrue(h.ns.trackerMap.enabled)
        for getter in (h.ns.GetStepWaypoint, h.ns.GetArrowWaypoint):
            point = getter(h.ns, h.step)
            self.assertEqual((point.mapID, point.x, point.y), (1426, .5, .6))
        self.assertIn("Puente a Poniente", h.ns.navigationFrame.destinationText)
        for name in ("nextButton", "trackerNext", "previousButton", "trackerPrevious"):
            button = h.ns[name]
            self.assertFalse(button.enabled)
            h.h.g.Click(button)
        self.assertEqual(h.progress(), before)

    def test_train_and_wait_with_completed_source_cursor_do_not_point_at_another_map(self):
        for waiting in (True, False):
            with self.subTest(waiting=waiting):
                h = self.journey(title="Andén" if not waiting else "Esperando al compañero",
                                 text="Espera aquí.", waiting=waiting)
                h.ns.char.progress[DWARF].cursor = len(h.guide.steps) + 1
                h.ns.Duo.GetMeetingWaypoint = h.h.lua.eval('function() return {mapID=1453,x=.5,y=.5} end')
                h.ns.RefreshUI(h.ns)
                h.ns.UpdateNavigation(h.ns)
                frame = h.ns.navigationFrame
                self.assertTrue(frame.shown)
                self.assertFalse(frame.arrow.shown)
                self.assertEqual(frame.distance.text, "")
                self.assertEqual(frame.statusText, h.s.travel.title)
                self.assertEqual(frame.destinationText, "Espera aquí.")
                self.assertEqual(frame.navigationState, "waiting" if waiting else "instruction")
                self.assertEqual(h.ns.trackerProgress.text, "Viaje")
                self.assertEqual(h.ns.trackerText.text, "Espera aquí.")
                self.assertIsNone(h.ns.GetStepWaypoint(h.ns, None))
                self.assertFalse(h.ns.trackerMap.enabled)
                self.assertFalse(h.ns.mapButton.enabled)
                self.assertEqual(h.ns.trackerSkip.enabled, not waiting)

    def test_skip_in_tracker_and_library_ends_only_the_trip(self):
        for button in ("trackerSkip", "skipButton"):
            with self.subTest(button=button):
                h = self.journey(title="Estación", text="Coge el tren.")
                before = h.progress()
                self.assertEqual(h.ns[button].label.text, "Omitir viaje")
                h.h.g.Click(h.ns[button])
                self.assertEqual(h.s.travelSkips, 1)
                self.assertIsNone(h.s.travel)
                self.assertEqual(h.progress(), before)
                self.assertGreater(h.ns.trackerCurrentCount, 0)
                self.assertEqual(h.ns.trackerStep.text, h.step.title)
                self.assertEqual(h.ns.trackerSkip.label.text, "Saltar")

    def test_arrival_with_restricted_chat_offers_only_local_start(self):
        for name in ("trackerNext", "nextButton"):
            with self.subTest(button=name):
                h = self.journey(title="Colina del Centinela", waiting=True, localStart=True,
                                 text="Si habéis llegado los dos, pulsad Empezar aquí.")
                h.h.lua.execute("""
                    function ACCESS_NS:StartTravelHere()
                        TEST.startedHere = (TEST.startedHere or 0) + 1
                        TEST.travel = nil
                        self:RefreshUI()
                        return true
                    end
                """)
                quest_progress, duo = h.progress(), h.ns.char.duo
                auto_pair, wait = duo.autoPair, duo.wait
                self.assertFalse(h.ns.trackerSkip.enabled)
                self.assertFalse(h.ns.skipButton.enabled)
                button = h.ns[name]
                self.assertTrue(button.enabled)
                self.assertEqual(button.label.text, "Empezar aquí")
                h.h.g.Click(button)
                self.assertEqual(h.s.startedHere, 1)
                self.assertIsNone(h.s.travelSkips)
                self.assertEqual(h.progress(), quest_progress)
                self.assertEqual((duo.autoPair, duo.wait), (auto_pair, wait))
                for other in (h.ns.trackerNext, h.ns.nextButton):
                    self.assertEqual(other.label.text, "Siguiente >")
                    self.assertFalse(other.startsTravelHere)
