"""Characters at Lake Mystral keep their live quests when Alonso's visit is retired."""
import unittest

from test_westfall_migration import MigrationHost


ALLIANCE = "forever/alliance/06-ashenvale"
HORDE = "forever/horde/07-ashenvale"
ALONSO_QUESTS = {78132, 78133, 78134}


class AshenvaleAlonsoTests(unittest.TestCase):
    def test_neither_route_displays_or_offers_an_alonso_quest(self):
        host = MigrationHost()
        for guide_id in (ALLIANCE, HORDE):
            for step in host.ns.guides[guide_id].steps.values():
                self.assertNotIn("Alonso", step.title)
                self.assertNotIn("Alonso", step.note or "")
                for goal in step.goals.values():
                    self.assertNotIn(goal.quest, ALONSO_QUESTS)
                    self.assertNotEqual(goal.npc, 210995)
        lake = host.ns.guides[ALLIANCE].steps[24]
        self.assertEqual([(g.t, g.quest) for g in lake.goals.values()],
                         [("accept", 1016), ("collect", 1016), ("turnin", 1016)])

    def test_last_lance_handover_retires_without_skipping_a_partners_pending_bracers(self):
        for delivered in (True, False):
            with self.subTest(bracers_delivered=delivered):
                saved = {"seen": True, "activeGuide": ALLIANCE, "auto": True, "progress": {ALLIANCE: {
                    "cursor": 24, "routeRevision": 4, "placed": True,
                    "skipped": {f"24:{index}": True for index in range(4, 9)}}}}
                host = MigrationHost(saved, {1016: {"delivered": delivered, "onQuest": not delivered},
                                            1034: {"onQuest": True}})
                host.state.level = 26
                host.initialize()
                guide, step, state = host.call("GetCurrent")
                self.assertEqual(guide.id, ALLIANCE)
                self.assertEqual(list(state.skipped.keys()), [])
                if delivered:
                    self.assertEqual((state.cursor, step.title, host.active()[0].quest),
                                     (25, "Las Ruinas del Polvo Estelar", 1034))
                else:
                    self.assertEqual((state.cursor, step.title, host.active()[0].quest),
                                     (24, "Lago Mystral", 1016))

    def test_horde_bookmarks_stay_with_tideress_and_later_objectives(self):
        for old_step, new_step in ((10, 10), (11, 11), (12, 11), (13, 12), (48, 47)):
            with self.subTest(old_step=old_step):
                saved = {"seen": True, "activeGuide": HORDE, "auto": False,
                         "progress": {HORDE: {"cursor": old_step, "review": True,
                                              "skipped": {"10:1": True, "11:6": True, "12:2": True}}},
                         "duo": {"autoSession": {"reviews": {HORDE: {"cursor": old_step}}}}}
                host = MigrationHost(saved)
                host.state.faction = "Horde"
                host.initialize()
                guide, step, state = host.call("GetCurrent")
                self.assertEqual(guide.id, HORDE)
                self.assertEqual(state.cursor, new_step)
                self.assertEqual(host.ns.char.duo.autoSession.reviews[HORDE].cursor, new_step)
                self.assertEqual(set(state.skipped.keys()), {"10:1", "11:2"})
                if old_step in (11, 12):
                    self.assertEqual(step.title, "Tideress")
                    self.assertEqual(step.goals[2].quest, 1918)
                elif old_step == 48:
                    self.assertIsNone(step)
