"""A finished route follows its authored link and preserves each guide's state."""
import unittest

from test_quest_engine import QuestEngineHost


DUN = "forever/alliance/dwarf-gnome/01-dun-morogh"
WEST = "forever/alliance/02-westfall"


class RouteHandoffTests(unittest.TestCase):
    def test_narm_explains_the_symbol_when_working_and_when_wow_offers_the_turnin(self):
        h = QuestEngineHost(catalog=True)
        h.state.faction, h.state.raceToken, h.state.classToken, h.state.level = "Alliance", "Dwarf", "PALADIN", 13
        h.globals.RutaXPCharDB = h.table({"activeGuide": DUN, "auto": True, "progress": {DUN: {"cursor": 70, "placed": True}}})
        h.quest(1783, onQuest=True, complete=False)
        h.initialize()
        for ready, action in ((False, "complete"), (True, "turnin")):
            h.quest(1783, onQuest=True, complete=ready)
            h.fire("QUEST_LOG_UPDATE")
            _, step, state = h.call("GetCurrent")
            rows, _ = h.call("GetStepGoalItems", step, state)
            self.assertEqual((state.cursor, rows[1].goal.t, rows[1].goal.quest), (70, action, 1783))
            self.assertIn("Símbolo de la Vida", rows[1].subtitle)
            self.assertIn("Narm Faulk", rows[1].subtitle)
            self.assertNotIn("Usal Symbol", rows[1].details)
        h.fire("QUEST_TURNED_IN", 1783)
        self.assertEqual(h.active()[0].quest, 1784)

    def test_tram_stays_on_route_when_both_optional_parcel_errands_are_off(self):
        h = QuestEngineHost(catalog=True)
        h.state.faction, h.state.raceToken, h.state.classToken, h.state.level = "Alliance", "Dwarf", "HUNTER", 12
        h.globals.RutaXPCharDB = h.table({"activeGuide": DUN, "auto": True, "optional": False,
            "progress": {DUN: {"cursor": 73, "placed": True, "confirmed": {"73:1": True}}}})
        h.initialize()
        self.assertEqual(h.cursor(DUN), 73)
        self.assertEqual((h.active()[0].t, h.active()[0].text), ("goto", "Tren subterráneo"))
        h.ns.IsAtWaypoint = h.lua.eval("function() return true end")
        h.call("OnNavigationTick")
        self.assertEqual(h.ns.char.activeGuide, WEST)

    def last_mission(self, previous=None):
        h = QuestEngineHost(catalog=True)
        h.state.faction, h.state.raceToken, h.state.classToken, h.state.level = "Alliance", "Dwarf", "MAGE", 13
        progress = {DUN: {"cursor": 80, "placed": True, "confirmed": {"73:1": True}}}
        if previous:
            progress[WEST] = previous
        h.globals.RutaXPCharDB = h.table({"activeGuide": DUN, "auto": True, "seen": True, "progress": progress})
        h.quest(1861, onQuest=True, complete=False)
        h.initialize()
        return h

    def test_finishing_last_live_quest_changes_zone_even_when_map_is_still_dun_morogh(self):
        h = self.last_mission()
        self.assertEqual(h.ns.char.activeGuide, DUN)
        self.assertIsNone(h.call("GetGuideContinuation")[0])
        h.quest(1861, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(h.ns.char.activeGuide, WEST)
        guide, step, state = h.call("GetCurrent")
        self.assertEqual((state.cursor, step.title), (1, "Colina del Centinela"))
        self.assertTrue(h.call("GetProgress", DUN).confirmed["73:1"])
        self.assertEqual(h.cursor(DUN), 81)
        h.state.mapID = h.ns.guides[DUN].zone
        self.assertNotEqual(h.call("GetRecommendedGuide").id, DUN)

    def test_personal_cursor_marks_and_review_in_destination_survive_handoff(self):
        h = self.last_mission({"cursor": 4, "confirmed": {"3:2": True}, "skipped": {"2:4": True}, "review": True})
        h.quest(1861, onQuest=True, complete=True)
        h.fire("QUEST_WATCH_UPDATE")
        self.assertEqual(h.ns.char.activeGuide, WEST)
        dest = h.call("GetProgress", WEST)
        self.assertEqual(dest.cursor, 4)
        self.assertTrue(dest.review and dest.confirmed["3:2"] and dest.skipped["2:4"])

    def test_all_published_routes_follow_their_explicit_successors_or_stop_at_the_end(self):
        h = QuestEngineHost(catalog=True)
        linked, terminal = 0, 0
        for source in h.ns.guides.values():
            h.state.faction = source.faction
            if source.next:
                expected = h.ns.guides[source.next]
                h.state.raceToken = expected.races[1] if expected.races else "Human"
                target = h.call("GetLinkedGuide", source)
                target = target[0] if isinstance(target, tuple) else target
                self.assertEqual(target.id, expected.id, source.id)
                linked += 1
            else:
                self.assertIsNone(h.call("GetLinkedGuide", source)[0])
                terminal += 1
        self.assertEqual((linked, terminal), (55, 2))

    def test_finished_save_with_a_cycle_or_two_valid_choices_stays_put(self):
        for loop in (True, False):
            with self.subTest(loop=loop):
                h = QuestEngineHost()
                h.guide("start", nextChoices=["one"] if loop else ["one", "two"])
                h.guide("one", next="start" if loop else None)
                h.guide("two")
                h.globals.RutaXPCharDB = h.table({"activeGuide": "start", "auto": True, "progress": {"start": {"cursor": 3}}})
                h.initialize()
                self.assertEqual(h.ns.char.activeGuide, "start")
                self.assertFalse(h.call("ContinueGuide")[0])
                self.assertIsNone(h.ns.char.progress["one"])
