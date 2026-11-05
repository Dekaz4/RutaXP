"""Dwarf characters follow the inter-zone trip without modifying quest progress."""

import unittest

from test_access_navigation import DWARF, WORLD_STUBS, load_pathing
from test_auto_party_integration import AutomaticPartyHost
from test_duo import DUO_STUBS
from test_duo_enhanced import ENHANCED_STUBS
from test_duo_journey import primitive_copy
from test_talent_trainer_regressions import TalentTrainerHost


WEST = "forever/alliance/02-westfall"
KHARANOS = (1426, .47, .52)
IRONFORGE = (1455, .25, .24)
STORMWIND = (1453, .63, .17)
GOLDSHIRE = (1429, .42, .66)
WESTFALL_ENTRY = (1436, .60, .19)


def old_save(guide=DWARF, west_cursor=1, review=False, auto=True):
    return {
        "seen": True, "activeGuide": guide, "auto": auto,
        "duo": {"enabled": False, "autoPair": False, "wait": False},
        "progress": {
            DWARF: {"cursor": 81, "placed": True, "confirmed": {"73:1": True}},
            WEST: {"cursor": west_cursor, "placed": True, "review": review,
                   "confirmed": {"old-personal-mark": True}, "skipped": {"old-skip": True}},
        },
    }


class TravelHost(AutomaticPartyHost):
    """Set the real location and party state before the saved character logs in."""

    def __init__(self, location, saved, name="Uno", friend="Dos", members=0, restricted=False,
                 faction="Alliance", race="Dwarf", classes=("PALADIN", "HUNTER")):
        self.h = TalentTrainerHost(full_toc=True)
        self.h.lua.execute(DUO_STUBS)
        self.h.lua.execute(ENHANCED_STUBS)
        self.ns, self.s = self.h.ns, self.h.state
        self.h.g.ACCESS_NS = self.ns
        self.h.lua.execute(WORLD_STUBS)
        self.h.lua.execute("""
            function GetInstanceInfo()
                return TEST.instanceName or "", "none", 0, "", 0, 0, false, TEST.instance
            end
            function IsInInstance() return TEST.instance == 369, "none" end
            function GetRealZoneText() return TEST.instanceName or "" end
        """)
        self.s.playerName, self.s.friendName = name, friend
        self.s.classToken, self.s.friendClass = classes if name == "Uno" else classes[::-1]
        self.s.raceToken = self.s.friendRace = race
        self.s.faction = self.s.friendFaction = faction
        self.s.level = self.s.friendLevel = 13
        self.s.members, self.s.restricted = members, restricted
        self.s.friendInRange, self.s.rangeChecked = False, True
        self.s.mapID, self.s.x, self.s.y = location
        self.h.g.RutaXPCharDB = self.h.table(saved)
        self.legacy, self.packets = False, []
        self.h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        self.h.g.EmitAddonEvent("PLAYER_LOGIN")

    def travel(self):
        return self.ns.GetGuideTravel(self.ns)

    def pin(self):
        _, step, _ = self.ns.GetCurrent(self.ns)
        return self.ns.GetStepWaypoint(self.ns, step)

    def move(self, location, instance=0):
        self.s.mapID, self.s.x, self.s.y = location
        self.s.instance = instance
        self.s.instanceName = "Tren Subterráneo" if instance == 369 else ""
        self.h.g.EmitAddonEvent("PLAYER_ENTERING_WORLD")
        self.tick()

    def arrive(self):
        # All physical samples below use the same Era→live transform, including
        # the saved destination. The route's last point must be at Sentinel Hill.
        legs = self.ns.WestfallTravelLegs
        end = legs[len(legs)]
        if not (end.map == 1436 and 50 < end.x < 59 and 44 < end.y < 56):
            raise AssertionError("Travel does not end at Sentinel Hill in Westfall")
        self.s.height = end.z
        self.move((end.map, end.x / 100, end.y / 100))


class WestfallTravelTests(unittest.TestCase):
    def assert_marks(self, host, west_cursor=1):
        progress = host.ns.char.progress
        self.assertEqual(progress[DWARF].cursor, 81)
        self.assertTrue(progress[DWARF].confirmed["73:1"])
        self.assertEqual(progress[WEST].cursor, west_cursor)
        self.assertEqual(primitive_copy(progress[WEST].confirmed), {"old-personal-mark": True})
        self.assertEqual(primitive_copy(progress[WEST].skipped), {"old-skip": True})

    def exchange(self, a, b, ticks=50):
        for _ in range(ticks):
            a.tick()
            b.tick()
            a.deliver(b)
            b.deliver(a)

    def test_old_finished_dun_save_and_selected_westfall_both_open_physical_trip(self):
        for guide in (DWARF, WEST):
            with self.subTest(guide=guide):
                h = TravelHost(KHARANOS, old_save(guide))
                self.assertEqual(h.ns.char.activeGuide, WEST)
                self.assertTrue(h.travel().title and h.travel().text)
                self.assertEqual(h.pin().mapID, KHARANOS[0])
                self.assert_marks(h)

    def test_every_outdoor_and_city_leg_is_reachable_on_the_bundled_terrain(self):
        h = TalentTrainerHost(full_toc=True)
        terrain = load_pathing(h)

        def world(map_id, x, y, z=None):
            bounds = h.ns.mapFrames.era[map_id]
            return h.table({
                "x": bounds.top + (bounds.bottom - bounds.top) * y / 100,
                "y": bounds.left + (bounds.right - bounds.left) * x / 100,
                "z": z,
            })

        # Starts are sampled on the approach road or just outside the portal.
        entry = {
            1426: world(1426, 47.4, 52.5, 400),
            1455: world(1426, 53.63, 34.73, 497),
            1453: h.table({"x": -8346.46, "y": 514.03, "z": 96.60}),
            1429: world(1429, 32.33, 49.86, 92),
            1436: world(1436, 60.9, 19),
        }
        legs = h.ns.WestfallTravelLegs
        for index in range(1, len(legs) + 1):
            leg = legs[index]
            if leg.map is None:
                self.assertEqual(leg.instanceID, 369)
                continue
            target = world(leg.map, leg.x, leg.y, leg.z)
            with self.subTest(leg=leg.id):
                points, cost, _ = terrain.FindSync(0, entry[leg.map], target)
                self.assertIsNotNone(points, cost)
                self.assertGreater(len(points), 1)
            entry[leg.map] = target

    def test_road_progress_train_crossing_and_later_entry_resume_on_local_map(self):
        h = TravelHost(IRONFORGE, old_save())
        before = h.progress()
        self.assertEqual(h.pin().mapID, IRONFORGE[0])
        h.move((None, None, None), instance=369)
        train = h.travel()
        self.assertIsNotNone(train)
        self.assertIn("tren", (train.title + " " + train.text).lower())
        self.assertIsNone(h.pin(), "The tram has no verified indoor walking coordinates")
        for location in (STORMWIND, GOLDSHIRE, WESTFALL_ENTRY):
            h.move(location)
            self.assertEqual(h.pin().mapID, location[0])
        self.assertEqual(h.progress(), before)
        h.arrive()
        self.assertIsNone(h.travel())
        _, step, state = h.ns.GetCurrent(h.ns)
        self.assertEqual((state.cursor, step.title), (1, "Colina del Centinela"))
        self.assert_marks(h)

    def test_tram_portal_waits_for_transport_even_if_a_player_stands_at_the_entrance(self):
        h = TravelHost(IRONFORGE, old_save())
        entry = next(leg for leg in h.ns.WestfallTravelLegs.values() if leg.id == "tinker-town")
        for index in range(1, len(h.ns.WestfallTravelLegs) + 1):
            leg = h.ns.WestfallTravelLegs[index]
            if leg.map == entry.map and not leg.boundary:
                h.s.height = leg.z
                h.move((leg.map, leg.x / 100, leg.y / 100))
        h.s.height = entry.z
        h.move((entry.map, entry.x / 100, entry.y / 100))
        at_entry = h.travel()
        self.assertEqual(at_entry.index, next(i for i, leg in h.ns.WestfallTravelLegs.items() if leg.id == entry.id))
        for _ in range(20):
            h.tick()
        self.assertEqual(h.travel().index, at_entry.index)
        h.s.positionUnavailable = True
        h.move((None, None, None))
        h.s.positionUnavailable = False
        h.move((entry.map, entry.x / 100, entry.y / 100))
        self.assertEqual(h.travel().index, at_entry.index)
        self.assert_marks(h)

    def test_tram_instance_overrides_stale_city_map_and_micro_map_resolves_through_parent(self):
        h = TravelHost(IRONFORGE, old_save())
        h.move(IRONFORGE, instance=369)
        self.assertEqual(h.travel().id, "tram")
        self.assertIsNone(h.pin())
        # Some loads reveal the localized area before the instance ID, and
        # some indoor client maps identify only their parent outdoor city.
        h.h.lua.execute("""
            function C_Map.GetAreaInfo(id) if id == 2257 then return "Tren Subterráneo" end end
            function C_Map.GetMapInfo(id) if id == 99001 then return {parentMapID=1453} end end
        """)
        h.s.instance = 0
        h.tick()
        self.assertEqual(h.travel().id, "tram")
        h.move((99001, STORMWIND[1], STORMWIND[2]))
        self.assertEqual(h.travel().point.mapID, STORMWIND[0])
        self.assert_marks(h)

    def test_manual_player_on_elwynn_road_moves_and_resumes_without_skipping_quests(self):
        h = TravelHost(GOLDSHIRE, old_save(WEST, auto=False))
        self.assertEqual(h.pin().mapID, GOLDSHIRE[0])
        self.assertFalse(h.ns.char.auto)
        first = h.travel().index
        point = h.pin()
        h.s.height = point.z
        h.move((point.mapID, point.x, point.y))
        self.assertGreater(h.travel().index, first)
        h.move(WESTFALL_ENTRY)
        resume = TravelHost(WESTFALL_ENTRY, primitive_copy(h.ns.char))
        self.assertEqual(resume.travel().index, h.travel().index)
        self.assertEqual(resume.pin().mapID, WESTFALL_ENTRY[0])
        resume.arrive()
        self.assertIsNone(resume.travel())
        self.assert_marks(resume)
        self.assertFalse(resume.ns.char.auto)

    def test_travel_actions_do_not_skip_or_confirm_the_first_quest_in_westfall(self):
        for method, args in (("Next", ()), ("SkipStep", ()), ("ToggleGoalConfirm", (1,))):
            with self.subTest(method=method):
                h = TravelHost(STORMWIND, old_save(WEST))
                self.assertIsNotNone(h.travel())
                h.ns[method](h.ns, *args)
                self.assert_marks(h)

    def test_quest_refresh_cannot_close_the_trip_while_physically_in_ironforge(self):
        h = TravelHost(IRONFORGE, old_save(WEST))
        self.assertIsNotNone(h.travel())
        guide, step, state = h.ns.GetCurrent(h.ns)
        for index, goal in step.goals.items():
            if goal.quest:
                h.s.quests[goal.quest] = h.h.table({"delivered": True})
            else:
                state.confirmed[f"1:{index}"] = True
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        self.assertEqual((h.ns.char.activeGuide, state.cursor), (guide.id, 1))
        self.assertIsNotNone(h.travel())
        h.arrive()
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        self.assertIsNone(h.travel())
        self.assertGreater(state.cursor, 1)

    def test_existing_westfall_progress_and_manual_review_are_not_taken_over(self):
        for cursor, review in ((1, True), (4, False)):
            with self.subTest(cursor=cursor, review=review):
                h = TravelHost(IRONFORGE, old_save(WEST, cursor, review))
                self.assertIsNone(h.travel())
                self.assert_marks(h, west_cursor=cursor)

    def test_switching_guide_while_travelling_applies_the_new_quest_on_the_first_sync(self):
        h = TravelHost(IRONFORGE, old_save(WEST))
        self.assertIsNotNone(h.travel())
        guide_id = "travel-test/other-guide"
        h.register_route(guide_id, quest_id=900121)
        h.quest(900121, count=3)
        h.ns.SelectGuide(h.ns, guide_id)
        self.assertIsNone(h.travel())
        guide, step, state = h.ns.GetCurrent(h.ns)
        self.assertEqual((guide.id, state.cursor, step.goals[1].t), (guide_id, 2, "complete"))
        self.assert_marks(h)

    def test_restricted_group_at_old_end_gets_directions_without_advancing_peer(self):
        saved = old_save()
        saved["duo"] = {"enabled": True, "autoPair": False, "wait": True}
        h = TravelHost(IRONFORGE, saved, members=2, restricted=True)
        for _ in range(12):
            h.tick()
        self.assertEqual(h.ns.char.activeGuide, DWARF)
        self.assertIsNotNone(h.travel())
        self.assertEqual(h.pin().mapID, IRONFORGE[0])
        self.assertFalse(bool(h.travel().localStart))
        h.ns.StartTravelHere(h.ns)
        self.assertEqual(h.ns.char.activeGuide, DWARF, "Cannot start local quests from Forjaz")
        h.arrive()
        self.assertTrue(h.travel().localStart)
        settings_before = primitive_copy(h.ns.char.duo)
        h.ns.StartTravelHere(h.ns)
        self.assertEqual(h.ns.char.activeGuide, WEST)
        self.assertIsNone(h.travel())
        self.assertEqual(primitive_copy(h.ns.char.duo), settings_before)
        self.assertFalse(h.ns.Duo.GetContext(h.ns.Duo).partnerAtWestfall)
        # A repeated click must not advance the first Westfall quest.
        h.ns.StartTravelHere(h.ns)
        self.assert_marks(h)

    def test_finished_hunter_stays_with_paladins_confirmed_unfinished_visit(self):
        unfinished = old_save(auto=False)
        unfinished["progress"][DWARF]["cursor"] = 70
        unfinished["duo"] = {"enabled": True, "autoPair": False, "wait": True}
        finished = old_save()
        finished["duo"] = unfinished["duo"]
        paladin = TravelHost(KHARANOS, unfinished, members=2)
        hunter = TravelHost(IRONFORGE, finished, name="Dos", friend="Uno", members=2)
        self.exchange(paladin, hunter, ticks=30)
        self.assertEqual((paladin.ns.char.activeGuide, hunter.ns.char.activeGuide), (DWARF, DWARF))
        self.assertEqual((paladin.ns.char.progress[DWARF].cursor, hunter.ns.char.progress[DWARF].cursor), (70, 81))
        self.assertIsNone(hunter.travel())
        hunter.s.restricted = True
        hunter.arrive()
        hunter.ns.StartTravelHere(hunter.ns)
        self.assertEqual(hunter.ns.char.activeGuide, DWARF)

    def test_restricted_character_already_in_westfall_can_start_here_only_on_arrival(self):
        saved = old_save(WEST)
        saved["duo"] = {"enabled": True, "autoPair": False, "wait": True}
        h = TravelHost(WESTFALL_ENTRY, saved, members=2, restricted=True)
        self.assertFalse(bool(h.travel().localStart))
        h.arrive()
        self.assertTrue(h.travel().localStart)
        h.ns.StartTravelHere(h.ns)
        self.assertIsNone(h.travel())
        self.assertEqual(h.ns.char.activeGuide, WEST)
        self.assert_marks(h)

    def test_duo_receives_own_travel_leg_and_waits_for_the_later_arrival(self):
        saved = old_save()
        saved["duo"] = {"enabled": True, "autoPair": True, "wait": True}
        a = TravelHost(IRONFORGE, saved, members=2)
        b = TravelHost(GOLDSHIRE, saved, name="Dos", friend="Uno", members=2)
        self.exchange(a, b)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (WEST, WEST))
        self.assertEqual((a.pin().mapID, b.pin().mapID), (IRONFORGE[0], GOLDSHIRE[0]))
        a.arrive()
        b.move(WESTFALL_ENTRY)
        self.exchange(a, b, ticks=25)
        self.assertTrue(a.travel().waiting, "A peer still at the Westfall border has not reached the hill")
        self.assertIsNotNone(b.travel().point)
        a.s.friendInRange = b.s.friendInRange = True
        b.arrive()
        self.exchange(a, b)
        self.assertIsNone(a.travel())
        self.assertIsNone(b.travel())
        self.assert_marks(a)
        self.assert_marks(b)

    def test_skipping_guidance_in_ironforge_cannot_acknowledge_arrival_at_the_hill(self):
        saved = old_save(WEST)
        saved["duo"] = {"enabled": True, "autoPair": True, "wait": True}
        a = TravelHost(IRONFORGE, saved, members=2)
        b = TravelHost(WESTFALL_ENTRY, saved, name="Dos", friend="Uno", members=2)
        self.exchange(a, b)
        b.arrive()
        self.exchange(a, b, ticks=20)
        a.ns.SkipStep(a.ns)
        self.exchange(a, b, ticks=25)
        self.assertIsNone(a.travel(), "The local player chose to hide travel guidance")
        self.assertIsNotNone(b.travel(), "Skipping directions is not a physical arrival")
        self.assertTrue(b.travel().waiting, "The companion is still physically in Forjaz")
        self.assert_marks(a)
        a.arrive()
        self.exchange(a, b)
        self.assertIsNone(b.travel())
        self.assert_marks(b)


if __name__ == "__main__":
    unittest.main()
