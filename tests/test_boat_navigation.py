"""Real chapter travel must reach the right pier and finish only on land."""
import unittest

from test_access_navigation import WORLD_STUBS
from test_duo import DUO_STUBS
from test_duo_journey import primitive_copy
from test_talent_trainer_regressions import TalentTrainerHost


GUIDE = "forever/alliance/07-thousand-needles"


class BoatHost:
    def __init__(self, saved=None, position=(1437, .10, .59)):
        self.h = TalentTrainerHost(full_toc=True)
        self.ns, self.s = self.h.ns, self.h.state
        self.h.g.ACCESS_NS = self.ns
        self.h.lua.execute(DUO_STUBS + WORLD_STUBS + '''
            function UnitOnTaxi() return TEST.flying==true end
            function UnitIsDeadOrGhost() return TEST.dead==true end
        ''')
        self.s.members, self.s.level = 0, 30
        self.s.classToken, self.s.raceToken = "ROGUE", "Human"
        self.s.mapID, self.s.x, self.s.y = position
        self.guide = self.ns.guides[GUIDE]
        self.step, self.goal = self.guide.steps[31], self.guide.steps[31].goals[3]
        self.h.g.RutaXPCharDB = self.h.table(saved or {
            "seen": True, "activeGuide": GUIDE, "auto": True,
            "duo": {"enabled": False, "autoPair": False},
            "progress": {GUIDE: {"cursor": 31, "routeRevision": self.guide.routeRevision,
                "placed": True, "confirmed": {"31:1": True}, "skipped": {"31:2": True}}}})
        self.h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        self.h.g.EmitAddonEvent("PLAYER_LOGIN")
        self.b = self.ns.BoatNavigation

    def view(self):
        return self.b.CurrentView(self.b)

    def point(self):
        return self.ns.GetStepWaypoint(self.ns, self.step)

    def move(self, position):
        self.s.mapID, self.s.x, self.s.y = position

    def tick(self):
        self.b.Tick(self.b, .6)

    def complete(self):
        return self.b.IsComplete(self.b, self.goal, self.guide, 31, 3, self.ns.char.progress[GUIDE])

    def progress(self):
        return primitive_copy(self.ns.char.progress)


class BoatNavigationTests(unittest.TestCase):
    def test_the_real_step_pins_the_south_pier_even_when_its_quest_was_skipped(self):
        h = BoatHost()
        before = h.progress()
        self.assertEqual((h.goal.t, h.ns.char.progress[GUIDE].cursor), ("boat", 31))
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[2], "active")
        self.assertFalse(h.ns.IsStepComplete(h.ns, h.step))
        point = h.point()
        self.assertEqual(point.mapID, 1437)
        self.assertAlmostEqual(point.x, .0474)
        self.assertAlmostEqual(point.y, .6376)
        self.assertTrue(point.boatNavigation)
        arrow = h.ns.GetArrowWaypoint(h.ns, h.step)
        self.assertTrue(arrow.boatNavigation, "Walking must preserve the boat's navigation ownership")
        self.assertEqual(h.view().state, "approach")
        self.assertFalse(h.complete())
        self.assertEqual(h.progress(), before)

    def test_at_the_departure_pier_it_waits_without_a_path_across_the_water(self):
        h = BoatHost(position=(1437, .0474, .6376))
        before = h.progress()
        self.assertEqual(h.view().state, "boarding")
        self.assertIsNone(h.point())
        h.tick()
        self.assertFalse(h.complete())
        self.assertEqual(h.progress(), before)
        # The vessel can still belong to the departure map while moving away.
        h.move((1437, .025, .6376))
        self.assertEqual(h.view().state, "boarding")
        self.assertIsNone(h.point())
        reloaded = BoatHost(saved=primitive_copy(h.ns.char), position=(1437, .025, .6376))
        self.assertEqual(reloaded.view().state, "boarding")
        self.assertIsNone(reloaded.point())
        self.assertFalse(reloaded.complete())

    def test_walking_back_to_the_port_restores_the_departure_arrow(self):
        h = BoatHost(position=(1437, .0474, .6376))
        self.assertEqual(h.view().state, "boarding")
        before = h.progress()
        h.move((1437, .0952, .5966))
        self.assertEqual(h.view().state, "approach")
        self.assertAlmostEqual(h.point().x, .0474)
        self.assertAlmostEqual(h.point().y, .6376)
        self.assertIsNone(h.ns.char.boatNavigation.boarding)
        self.assertEqual(h.progress(), before)

    def test_waiting_and_landing_show_transport_instructions_in_the_arrow(self):
        h = BoatHost(position=(1437, .0474, .6376))
        h.ns.UpdateNavigation(h.ns)
        frame = h.ns.navigationFrame
        self.assertEqual(frame.navigationState, "boarding")
        self.assertIn("Espera el barco", frame.hint.text)
        self.assertIn("Permanece a bordo", frame.destinationText)
        self.assertFalse(frame.arrow.IsShown(frame.arrow))
        h.move((1445, .7173, .5666))
        h.ns.UpdateNavigation(h.ns)
        self.assertIn("Desembarca", frame.hint.text)
        self.assertIn("Baja del barco", frame.destinationText)

    def test_a_map_change_or_destination_dock_does_not_prove_disembarkation(self):
        h = BoatHost()
        before = h.progress()
        for position in ((999, .5, .5), (1445, .8, .65), (1445, .7173, .5666)):
            with self.subTest(position=position):
                h.move(position)
                h.tick()
                self.assertFalse(h.complete())
                self.assertEqual(h.progress(), before)
        self.assertEqual(h.view().state, "landing")
        self.assertIn("Baja del barco", h.view().text)
        self.assertEqual(h.point().mapID, 1445)
        self.assertAlmostEqual(h.point().x, .6746)
        self.assertAlmostEqual(h.point().y, .512)

    def test_crossing_holds_the_arrow_until_docking_then_remembers_the_land_stage(self):
        h = BoatHost(position=(1437, .0474, .6376))
        self.assertEqual(h.view().state, "boarding")
        h.move((1445, .8, .65))
        self.assertEqual(h.view().state, "crossing")
        self.assertIsNone(h.point())
        self.assertFalse(h.complete())
        h.move((1445, .7173, .5666))
        self.assertEqual(h.view().state, "landing")
        self.assertIsNotNone(h.point())
        h.move((1445, .69, .53))
        reloaded = BoatHost(saved=primitive_copy(h.ns.char), position=(1445, .69, .53))
        self.assertEqual(reloaded.view().state, "landing")
        self.assertIsNotNone(reloaded.point())
        self.assertFalse(reloaded.complete())

    def test_missing_the_destination_dock_tick_does_not_block_a_real_land_arrival(self):
        h = BoatHost(position=(1437, .0474, .6376))
        self.assertEqual(h.view().state, "boarding")
        h.move((1445, .6746, .512))
        h.tick()
        self.assertTrue(h.complete())
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 33)

    def test_land_arrival_advances_automatically_and_survives_leaving_and_reload(self):
        h = BoatHost()
        h.move((1445, .6746, .512))
        h.tick()
        self.assertTrue(h.complete())
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 33)
        self.assertIsNone(h.ns.char.progress[GUIDE].confirmed["31:3"])
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 474))
        h.move((1413, .5, .78))
        reloaded = BoatHost(saved=primitive_copy(h.ns.char), position=(1413, .5, .78))
        self.assertTrue(reloaded.complete())
        self.assertEqual(reloaded.ns.char.progress[GUIDE].cursor, 33)

    def test_taxi_ghost_or_unreadable_position_cannot_complete_the_land_checkpoint(self):
        for state in ("flying", "dead", "positionUnavailable"):
            with self.subTest(state=state):
                h = BoatHost()
                setattr(h.s, state, True)
                h.move((1445, .6746, .512))
                h.tick()
                self.assertFalse(h.complete())
                self.assertEqual(h.ns.char.progress[GUIDE].cursor, 31)

    def test_unreadable_taxi_state_cannot_be_treated_as_a_confirmed_landing(self):
        h = BoatHost()
        h.h.lua.execute('UnitOnTaxi=function() error("Not readable") end')
        h.move((1445, .6746, .512))
        h.tick()
        self.assertFalse(h.complete())
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 31)

    def test_review_future_rows_and_shared_previews_cannot_record_arrival(self):
        for mode in ("review", "future", "shared"):
            with self.subTest(mode=mode):
                h = BoatHost()
                h.move((1445, .6746, .512))
                if mode == "review":
                    h.ns.char.progress[GUIDE].review = True
                elif mode == "future":
                    h.ns.char.progress[GUIDE].cursor = 30
                before = primitive_copy(h.ns.char)
                if mode == "shared":
                    h.b.GetSharedView(h.b, h.goal, h.guide, 31, 3)
                elif mode == "review":
                    self.assertEqual(h.view().state, "landing")
                    self.assertAlmostEqual(h.point().x, .6746)
                    h.tick()
                    self.assertEqual(h.ns.char.progress[GUIDE].cursor, 31)
                else:
                    self.assertIsNone(h.view())
                self.assertFalse(h.complete())
                self.assertEqual(primitive_copy(h.ns.char), before)

    def test_manual_confirmation_or_skipping_cannot_create_an_arrival(self):
        h = BoatHost()
        state = h.ns.char.progress[GUIDE]
        state.confirmed["31:3"] = True
        h.ns.Sync(h.ns)
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[2], "active")
        self.assertEqual(state.cursor, 31)
        self.assertFalse(h.complete())
        state.skipped["31:3"] = True
        h.ns.Sync(h.ns)
        self.assertEqual(state.cursor, 33)
        self.assertFalse(h.complete())

    def test_already_in_theramore_on_land_needs_no_fictional_boarding_history(self):
        h = BoatHost(position=(1445, .6746, .512))
        h.tick()
        self.assertTrue(h.complete())
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 33)

    def test_manual_navigation_mode_keeps_its_preference_after_confirmed_arrival(self):
        h = BoatHost()
        h.ns.char.auto = False
        h.move((1445, .6746, .512))
        h.tick()
        self.assertTrue(h.complete())
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 31)

    def test_review_remembers_transport_phases_without_saving_or_confirming_them(self):
        h = BoatHost()
        h.ns.char.progress[GUIDE].review = True
        h.ns.char.boatNavigation = None
        before = primitive_copy(h.ns.char)
        for position, phase, has_point in (
            ((1437, .0474, .6376), "boarding", False),
            ((1437, .025, .6376), "boarding", False),
            ((1445, .8, .65), "crossing", False),
            ((1445, .7173, .5666), "landing", True),
            ((1445, .69, .53), "landing", True),
            ((1445, .6746, .512), "landing", True),
        ):
            with self.subTest(phase=phase, position=position):
                h.move(position)
                self.assertEqual(h.view().state, phase)
                self.assertEqual(h.point() is not None, has_point)
                h.tick()
                self.assertFalse(h.complete())
                self.assertEqual(primitive_copy(h.ns.char), before)
        h.move((1437, .0952, .5966))
        self.assertEqual(h.view().state, "approach")
        self.assertEqual(primitive_copy(h.ns.char), before)


if __name__ == "__main__":
    unittest.main()
