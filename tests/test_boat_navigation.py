"""Real chapter travel must reach the right pier and finish only on land."""
import unittest

from test_access_navigation import WORLD_STUBS
from test_duo import DUO_STUBS
from test_duo_journey import primitive_copy
from test_talent_trainer_regressions import TalentTrainerHost


GUIDE = "forever/alliance/07-thousand-needles"
DESOLACE = "forever/alliance/30-40/02-desolace"


class BoatHost:
    def __init__(self, saved=None, position=(1437, .10, .59), guide_id=GUIDE, step_index=31, quests=None):
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
        self.guide = self.ns.guides[guide_id]
        self.step_index = step_index
        self.step = self.guide.steps[step_index]
        self.goal_index, self.goal = next((gi, goal) for gi, goal in self.step.goals.items()
                                         if goal.t == "boat")
        self.goal_key = f"{step_index}:{self.goal_index}"
        for quest, value in (quests or {}).items():
            self.s.quests[quest] = self.h.table(value)
        self.h.g.RutaXPCharDB = self.h.table(saved or {
            "seen": True, "activeGuide": guide_id, "auto": True,
            "duo": {"enabled": False, "autoPair": False},
            "progress": {guide_id: {"cursor": step_index, "routeRevision": self.guide.routeRevision,
                "placed": True, "confirmed": {f"{step_index}:1": True} if self.goal_index > 1 else {},
                "skipped": {f"{step_index}:{gi}": True for gi in range(2, self.goal_index)}}}})
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
        return self.b.IsComplete(self.b, self.goal, self.guide, self.step_index, self.goal_index,
                                 self.ns.char.progress[self.guide.id])

    def progress(self):
        return primitive_copy(self.ns.char.progress)


class BoatNavigationTests(unittest.TestCase):
    def old_boat_key(self, h, key):
        self.assertGreater(h.guide.routeRevision, 5)
        self.assertEqual(h.goal_index, 4)
        prefix = f"{GUIDE}:{h.guide.routeRevision}:31:{h.goal_index}:"
        self.assertTrue(key.startswith(prefix))
        return f"{GUIDE}:5:31:3:" + key[len(prefix):]

    def test_real_arrival_survives_moving_the_boat_row_in_a_route_repair(self):
        h = BoatHost()
        h.move((1445, .6746, .512))
        h.tick()
        arrivals = h.ns.char.boatNavigation.arrivals
        key = next(iter(arrivals.keys()))
        old = self.old_boat_key(h, key)
        arrivals[key], arrivals[old] = None, True
        h.move((1413, .5, .78))
        before = primitive_copy(h.ns.char)
        self.assertTrue(h.complete())
        self.assertEqual(primitive_copy(h.ns.char), before)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 98223))

    def test_transport_phase_survives_the_same_explicit_boat_mapping(self):
        for phase, position, expected in (
            ("boarding", (1437, .025, .6376), "boarding"),
            ("landing", (1445, .69, .53), "landing"),
        ):
            with self.subTest(phase=phase):
                h = BoatHost(position=(1437, .0474, .6376))
                h.view()
                saved = h.ns.char.boatNavigation
                old = self.old_boat_key(h, saved.boarding)
                saved.boarding = old
                if phase == "landing":
                    saved.landing = old
                h.move(position)
                self.assertEqual(h.view().state, expected)
                self.assertFalse(h.complete())
                if phase == "landing":
                    self.assertIsNotNone(h.point())

    def test_other_slot_or_changed_endpoints_do_not_inherit_old_arrival(self):
        h = BoatHost(position=(1437, .0474, .6376))
        h.view()
        old = self.old_boat_key(h, h.ns.char.boatNavigation.boarding)
        for invalid in (old.replace(":5:31:3:", ":5:31:2:"),
                        old.replace("1437,e,", "1437,l,", 1),
                        old + ",different", old.replace(":5:31:3:", ":99:31:3:")):
            with self.subTest(key=invalid):
                h.ns.char.boatNavigation.arrivals = h.h.table({invalid: True})
                self.assertFalse(h.complete())

    def test_retired_or_unmapped_old_action_does_not_count_as_arrived(self):
        h = BoatHost(position=(1437, .0474, .6376))
        h.view()
        old = self.old_boat_key(h, h.ns.char.boatNavigation.boarding)
        h.guide.routeRevision = 6
        h.ns.char.boatNavigation.arrivals = h.h.table({old: True})
        for mapping in ({}, {"31:3": "31:4"}):
            h.guide.progressMigrations = h.h.table([{
                "from": 5, "to": 6, "goalMap": mapping,
                "retiredGoalKeys": {"31:3": True} if mapping else {},
            }])
            self.assertFalse(h.complete())

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
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[0].quest, 1104)

    def test_land_arrival_advances_automatically_and_survives_leaving_and_reload(self):
        h = BoatHost()
        h.move((1445, .6746, .512))
        h.tick()
        self.assertTrue(h.complete())
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[0].quest, 1104)
        self.assertIsNone(h.ns.char.progress[GUIDE].confirmed[h.goal_key])
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 474))
        h.move((1413, .5, .78))
        reloaded = BoatHost(saved=primitive_copy(h.ns.char), position=(1413, .5, .78))
        self.assertTrue(reloaded.complete())
        self.assertEqual(reloaded.ns.GetActiveGoal(reloaded.ns)[0].quest, 1104)

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
                    h.b.GetSharedView(h.b, h.goal, h.guide, 31, h.goal_index)
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
        state.confirmed[h.goal_key] = True
        h.ns.Sync(h.ns)
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[2], "active")
        self.assertEqual(state.cursor, 31)
        self.assertFalse(h.complete())
        state.skipped[h.goal_key] = True
        h.ns.Sync(h.ns)
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[0].quest, 1104)
        self.assertFalse(h.complete())

    def test_already_in_theramore_on_land_needs_no_fictional_boarding_history(self):
        h = BoatHost(position=(1445, .6746, .512))
        h.tick()
        self.assertTrue(h.complete())
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[0].quest, 1104)

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


class AuberdineBoatTests(unittest.TestCase):
    def journey(self, position=(1437, .096, .597), *, saved=None, quest=True):
        quests = {98209: {"onQuest": True, "complete": True}} if quest else {}
        return BoatHost(saved, position, DESOLACE, 2, quests)

    def test_north_pier_stopover_and_disembarkation_lead_to_thundris(self):
        h = self.journey()
        point = h.point()
        self.assertEqual(h.view().state, "approach")
        self.assertEqual(point.mapID, 1437)
        self.assertAlmostEqual(point.x, .0449)
        self.assertAlmostEqual(point.y, .5666)
        h.move((1437, .0449, .5666))
        self.assertIn("Costasur", h.view().shortText)
        self.assertIsNone(h.point())
        h.move((1424, .5067, .7044))
        h.ns.UpdateNavigation(h.ns)
        self.assertEqual(h.ns.navigationFrame.navigationState, "stopover")
        self.assertIn("Quédate a bordo", h.ns.navigationFrame.hint.text)
        self.assertIsNone(h.point())
        self.assertFalse(h.complete())
        h = self.journey((1424, .465, .782), saved=primitive_copy(h.ns.char))
        self.assertEqual(h.view().state, "stopover")
        self.assertIsNone(h.point())
        h.move((1439, .3234, .4413))
        h.tick()
        self.assertFalse(h.complete(), "The ship at its final dock is not proof of landing")
        self.assertEqual(h.view().state, "landing")
        h.move((1439, .3704, .4413))
        h.tick()
        self.assertTrue(h.complete())
        goal = h.ns.GetActiveGoal(h.ns)[0]
        self.assertEqual((goal.t, goal.quest, goal.npc), ("turnin", 98209, 3649))
        self.assertAlmostEqual(h.point().x, .374)

    def test_entering_the_stopover_from_land_points_to_the_local_pier(self):
        h = self.journey((1424, .4944, .521))
        self.assertEqual(h.view().state, "approach")
        p = h.point()
        self.assertEqual(p.mapID, 1424)
        self.assertAlmostEqual(p.x, .5067)
        h.move((1424, .5067, .7044))
        self.assertEqual(h.view().state, "stopover")

    def test_real_stopover_chapter_keeps_astranaar_flight_without_the_flower(self):
        h = self.journey((1439, .364, .455), quest=False)
        h.tick()
        self.assertTrue(h.complete())
        self.assertEqual(h.ns.char.progress[DESOLACE].cursor, 2)
        goal = h.ns.GetActiveGoal(h.ns)[0]
        self.assertEqual((goal.t, goal.location), ("fly", "Astranaar"))

    def test_returning_to_menethil_with_a_completed_quest_still_requires_crossing(self):
        h = self.journey(quest=False)
        h.s.quests[98209] = h.h.table({"delivered": True})
        self.assertFalse(h.complete())
        self.assertEqual(h.view().state, "approach")
        h.move((1424, .5067, .7044))
        self.assertFalse(h.complete())
        self.assertEqual(h.view().state, "stopover")

    def test_saved_flight_and_astranaar_do_not_reopen_the_crossing(self):
        h = self.journey(quest=False)
        h.s.quests[98209] = h.h.table({"delivered": True})
        h.s.flying = True
        h.move((1439, .374, .55))
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[0].t, "fly")
        h.s.flying = False
        h.move((1440, .345, .4802))
        self.assertEqual(h.ns.FlightNavigation.CurrentView(h.ns.FlightNavigation).state, "arrived")
        h.ns.Sync(h.ns)
        self.assertGreater(h.ns.char.progress[DESOLACE].cursor, 2)
        self.assertFalse(primitive_copy(h.ns.char.boatNavigation.arrivals),
                         "Taking a flight independently must not record a ship landing")


if __name__ == "__main__":
    unittest.main()
