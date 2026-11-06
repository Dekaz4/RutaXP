"""The shipped Alba chain, old saves and PARTY messages on two isolated clients."""

import unittest

from test_auto_party_integration import AutomaticPartyHost
from test_access_navigation import WORLD_STUBS
from test_duo_journey import primitive_copy


WESTFALL = "forever/alliance/02-westfall"
OTHER = "auto-review/uno-solo"


class AlbaPartyHost(AutomaticPartyHost):
    def __init__(self, name="Uno", friend="Dos", cls="PALADIN", gills=3):
        self.starting_gills = gills
        saved = {
            "seen": True, "activeGuide": WESTFALL, "auto": True,
            "progress": {
                WESTFALL: {
                    "cursor": 6, "review": False, "placed": True,
                    "confirmed": {"1:3": True, "12:9": True},
                    "skipped": {"1:11": True, "20:2": True},
                },
                OTHER: {"cursor": 2, "review": True,
                        "confirmed": {"1:1": True}, "skipped": {"2:1": True}},
            },
            "duo": {"enabled": True, "wait": True, "autoPair": True, "autoEpoch": 4},
        }
        super().__init__(name, friend, active_guide=WESTFALL, saved=saved, race="Dwarf", cls=cls)

    def quest(self, *args, **kwargs):
        # AutomaticPartyHost invokes this before PLAYER_LOGIN. Seed the real
        # journal before migration, not after it has selected a repair step.
        self.s.level = self.s.friendLevel = 14
        self.s.mapID = 1436
        self.h.g.ACCESS_NS = self.ns
        self.h.lua.execute(WORLD_STUBS)
        self.set_quest(92742, delivered=True)
        self.set_quest(92744, counts=[(self.starting_gills, 7)])
        self.set_quest(92745, active=False, counts=[(0, 4), (0, 6)])
        self.set_quest(38, counts=[(0, 3), (3, 3), (0, 3), (0, 3)])

    def set_quest(self, qid, *, active=True, delivered=False, counts=()):
        objectives = [
            {"text": f"Objetivo: {current}/{required}", "numFulfilled": current,
             "numRequired": required, "finished": current >= required}
            for current, required in counts
        ]
        self.s.quests[qid] = self.h.table({
            "title": f"Misión {qid}", "onQuest": active and not delivered,
            "complete": bool(objectives) and all(o["finished"] for o in objectives) and not delivered,
            "delivered": delivered, "objectives": objectives,
        })
        self.s.entries = self.h.table([
            {"questID": key, "isHeader": False}
            for key, quest in self.s.quests.items() if quest.onQuest
        ])

    def event(self, name="QUEST_LOG_UPDATE", *args):
        self.h.g.EmitAddonEvent(name, *args)

    @property
    def cursor(self):
        return self.ns.char.progress[WESTFALL].cursor

    def active_goal(self):
        result = self.ns.GetActiveGoal(self.ns)
        return result[0] if isinstance(result, tuple) else result

    def point(self):
        _, step, _ = self.ns.GetCurrent(self.ns)
        return self.ns.GetStepWaypoint(self.ns, step)


class WestfallAlbaPartyTests(unittest.TestCase):
    def pair(self):
        a = AlbaPartyHost()
        b = AlbaPartyHost("Dos", "Uno", cls="HUNTER", gills=5)
        a.s.friendClass, b.s.friendClass = "HUNTER", "PALADIN"
        for host in (a, b):
            host.roster()
        self.exchange(a, b, 75)
        return a, b

    def exchange(self, a, b, ticks=40):
        for _ in range(ticks):
            a.tick(); b.tick()
            self.assertLessEqual(len(a.s.outgoing), 1)
            self.assertLessEqual(len(b.s.outgoing), 1)
            a.deliver(b); b.deliver(a)

    def assert_not_sent_to_mine(self, host):
        point = host.point()
        if point is not None and point.goal is not None:
            self.assertFalse(point.goal.quest == 92745 and point.goal.t == "kill")

    def test_two_old_saves_rejoin_gills_before_mines_without_sharing_progress(self):
        a, b = self.pair()
        for host, current in ((a, 3), (b, 5)):
            self.assertEqual(host.ns.guides[WESTFALL].routeRevision, 2)
            self.assertEqual(host.cursor, 6)
            self.assertTrue(host.status().active)
            goal = host.active_goal()
            self.assertEqual((goal.t, goal.quest), ("collect", 92744))
            self.assertEqual(host.s.quests[92744].objectives[1].numFulfilled, current)
            self.assertFalse(host.ns.IsQuestActive(host.ns, 92745))
            state = host.ns.char.progress[WESTFALL]
            self.assertTrue(state.confirmed["1:3"])
            self.assertTrue(state.confirmed["13:7"])
            self.assertTrue(state.skipped["21:2"])
            self.assertIsNone(state.skipped["7:3"])
            self.assertEqual(primitive_copy(host.ns.char.progress[OTHER]), {
                "cursor": 2, "review": True,
                "confirmed": {"1:1": True}, "skipped": {"2:1": True},
            })
            self.assert_not_sent_to_mine(host)
        self.assertEqual(a.ns.Duo.GetPartnerQuest(a.ns.Duo, 92744).state, 1)
        self.assertEqual(b.ns.Duo.GetPartnerQuest(b.ns.Duo, 92744).state, 1)

    def test_group_waits_for_both_gills_delivery_and_real_mine_acceptance(self):
        a, b = self.pair()
        before_other = [primitive_copy(host.ns.char.progress[OTHER]) for host in (a, b)]
        a.set_quest(92744, counts=[(7, 7)])
        a.event()
        self.exchange(a, b)
        self.assertEqual((a.cursor, b.cursor), (6, 6))
        self.assertEqual(b.s.quests[92744].objectives[1].numFulfilled, 5)
        for host in (a, b):
            self.assert_not_sent_to_mine(host)

        b.set_quest(92744, counts=[(7, 7)])
        b.event()
        self.exchange(a, b)
        self.assertEqual((a.cursor, b.cursor), (7, 7))
        for host in (a, b):
            goal = host.active_goal()
            self.assertEqual((goal.t, goal.quest, goal.npc), ("turnin", 92744, 253092))
            self.assertEqual(host.point().goal.npc, 253092)

        a.set_quest(92744, delivered=True)
        a.event("QUEST_TURNED_IN", 92744)
        a.set_quest(92745, counts=[(0, 4), (0, 6)])
        a.event("QUEST_ACCEPTED", 92745)
        self.exchange(a, b)
        self.assertEqual((a.cursor, b.cursor), (7, 7))
        self.assertFalse(b.ns.IsQuestActive(b.ns, 92745))
        self.assertFalse(b.ns.IsQuestDelivered(b.ns, 92744))
        for host in (a, b):
            self.assert_not_sent_to_mine(host)

        b.set_quest(92744, delivered=True)
        b.event("QUEST_TURNED_IN", 92744)
        self.exchange(a, b)
        self.assertEqual((a.cursor, b.cursor), (7, 7))
        goal = b.active_goal()
        self.assertEqual((goal.t, goal.quest, goal.npc), ("accept", 92745, 253092))
        self.assertEqual(b.point().goal.npc, 253092)

        b.set_quest(92745, counts=[(0, 4), (0, 6)])
        b.event("QUEST_ACCEPTED", 92745)
        self.exchange(a, b)
        self.assertEqual((a.cursor, b.cursor), (8, 8))
        for host, other in zip((a, b), before_other):
            goal = host.active_goal()
            self.assertEqual((goal.t, goal.quest, goal.oi, goal.npc), ("kill", 92745, 2, 1426))
            self.assertEqual(host.point().goal.npc, 1426)
            self.assertFalse(host.ns.IsQuestDelivered(host.ns, 92745))
            self.assertEqual(primitive_copy(host.ns.char.progress[OTHER]), other)
            self.assertTrue(host.ns.char.auto)
            self.assertTrue(host.ns.char.duo.autoPair)
            self.assertTrue(host.status().active)
            self.assertLessEqual(host.s.maxSyncDepth, 2)
            self.assertTrue(all(len(packet["message"]) <= 255 for packet in host.packets))

    def test_gills_delivery_alone_does_not_unlock_mines_when_samples_are_still_in_log(self):
        a, b = self.pair()
        # Set up the return visit with opposite local states: one character
        # still carries the ready samples, while their buddy has accepted mines.
        a.set_quest(92742, counts=[(1, 1), (1, 1)])
        for host in (a, b):
            host.set_quest(92744, delivered=True)
            host.ns.char.progress[WESTFALL].cursor = 7
        b.set_quest(92745, counts=[(0, 4), (0, 6)])
        a.event(); b.event()
        self.exchange(a, b)
        self.assertEqual((a.cursor, b.cursor), (7, 7))
        step = a.ns.guides[WESTFALL].steps[7]
        status = a.ns.GetGoalStatus(a.ns, step.goals[3], step, a.ns.char.progress[WESTFALL], 3)
        self.assertEqual(status[0], "blocked")
        self.assertFalse(a.ns.WantsQuest(a.ns, "accept", 92745))
        self.assertFalse(a.ns.IsQuestDelivered(a.ns, 92742))
        self.assertFalse(a.ns.IsQuestActive(a.ns, 92745))
        self.assertEqual((a.active_goal().t, a.active_goal().quest), ("turnin", 92742))
        self.assertEqual(a.point().goal.npc, 253092)
        self.assert_not_sent_to_mine(b)

        a.set_quest(92742, delivered=True)
        a.event("QUEST_TURNED_IN", 92742)
        self.exchange(a, b)
        self.assertEqual((a.cursor, b.cursor), (7, 7))
        self.assertTrue(a.ns.WantsQuest(a.ns, "accept", 92745))
        self.assertEqual((a.active_goal().t, a.active_goal().quest), ("accept", 92745))
        a.set_quest(92745, counts=[(0, 4), (0, 6)])
        a.event("QUEST_ACCEPTED", 92745)
        self.exchange(a, b)
        self.assertEqual((a.cursor, b.cursor), (8, 8))


if __name__ == "__main__":
    unittest.main()
