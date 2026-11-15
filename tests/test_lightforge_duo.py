"""Each partner keeps their real early Lightforge branch and shared waits."""
import unittest

from test_addon import ADDON
from test_duo_journey import JourneyHost, primitive_copy


ROUTE = "forever/alliance/test"
CHAIN = [270, 321, 324, 526, 322]


class LightforgeDuoHost(JourneyHost):
    def __init__(self):
        super().__init__()
        self.state.level = self.state.friendLevel = 28
        self.ns.guides[ROUTE] = self.table({"id": ROUTE, "title": "Lightforge", "steps": [
            {"title": "Chest", "goals": [
                {"t": "accept", "quest": 321, "pre": [270], "chainStarted": list(CHAIN)},
                {"t": "accept", "quest": 324, "pre": [321], "closedBy": [526, 322], "chainStarted": list(CHAIN)},
                {"t": "accept", "quest": 526, "pre": [321], "closedBy": [324, 322], "chainStarted": list(CHAIN)},
            ]},
            {"title": "Ingots", "goals": [
                {"t": "collect", "quest": 324, "oi": 1},
                {"t": "collect", "quest": 526, "oi": 1},
            ]},
            {"title": "Delivery", "goals": [
                {"t": "turnin", "quest": 324}, {"t": "turnin", "quest": 526},
            ]},
            {"title": "Common coast", "goals": [{"t": "complete", "quest": 289}]},
        ]})
        self.ns.char.activeGuide = ROUTE
        self.ns.char.progress[ROUTE].cursor = 2
        self.ns.char.progress[ROUTE].review = None
        self.ns.char.duo.wait = True
        self.peer(cursor=2)
        for quest in CHAIN:
            self.remote(quest, 0)
        self.remote(269, 1)
        self.quest(321, delivered=True)
        self.quest(324, onQuest=True, complete=True, objectives=[{
            "text": "Ingots: 5/5", "finished": True, "numFulfilled": 5, "numRequired": 5,
        }])
        self.load((ADDON / "DuoPlanner.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)

    @property
    def route(self):
        return self.ns.guides[ROUTE]

    def wait(self, step=2):
        return self.dcall("GetStepWaitStatus", self.route.steps[step])

    def items(self, step=2):
        return self.ns.DuoPlanner.GetSharedGoalItems(self.ns.DuoPlanner, ROUTE, step)


class LightforgeDuoTests(unittest.TestCase):
    def test_unstarted_partner_is_not_forced_to_recover_the_later_chain(self):
        h = LightforgeDuoHost()
        before = primitive_copy(h.ns.char)
        self.assertFalse(h.wait().waiting)
        item = h.items()[1]
        self.assertTrue(item.appliesMine)
        self.assertFalse(item.appliesPartner)
        self.assertTrue(item.individual)
        differences = h.ns.DuoPlanner.GetDifferences(h.ns.DuoPlanner)
        self.assertTrue(all(row.action is None for row in differences.values()))
        self.assertEqual(primitive_copy(h.ns.char), before)

    def test_alternative_partner_quest_excludes_work_and_delivery_only_for_that_owner(self):
        h = LightforgeDuoHost()
        h.remote(321, 3)
        h.remote(526, 1)
        self.assertFalse(h.wait().waiting)
        self.assertFalse(h.wait(3).waiting)
        items = h.items()
        self.assertTrue(items[1].appliesMine)
        self.assertFalse(items[1].appliesPartner)
        self.assertFalse(items[2].appliesMine)
        self.assertTrue(items[2].appliesPartner)
        self.assertTrue(items[1].individual and items[2].individual)

    def test_same_branch_keeps_waiting_for_slower_partner(self):
        h = LightforgeDuoHost()
        h.remote(324, 1, [{"finished": False, "known": True, "current": 2, "total": 5}])
        wait = h.wait()
        self.assertTrue(wait.waiting)
        self.assertEqual(wait.questID, 324)
        self.assertFalse(wait.unknown)
        item = h.items()[1]
        self.assertFalse(item.individual)
        self.assertTrue(item.appliesPartner)
        self.assertFalse(item.partner.done)
        h.remote(324, 2)
        self.assertFalse(h.wait().waiting)

    def test_unknown_branch_does_not_become_absent_and_requests_its_evidence(self):
        h = LightforgeDuoHost()
        h.duo.remoteQuests[321] = None
        wait = h.wait()
        self.assertTrue(wait.waiting)
        self.assertTrue(wait.unknown)
        self.assertIsNotNone(h.duo.outboundRequests[321])
        item = h.items()[1]
        self.assertTrue(item.appliesPartner)
        self.assertFalse(item.partner.known)
        self.assertFalse(item.individual)

    def test_actual_carried_quest_wins_over_an_alternative_history_flag(self):
        h = LightforgeDuoHost()
        h.remote(324, 1)
        h.remote(526, 3)
        self.assertTrue(h.wait().waiting)
        self.assertTrue(h.items()[1].appliesPartner)
        self.assertFalse(h.items()[1].partner.done)

    def test_local_and_peer_visit_interest_include_inherited_chain_ids(self):
        h = LightforgeDuoHost()
        local_ids, _ = h.dcall("GetLocalQuestIDs")
        self.assertTrue(set(CHAIN).issubset(set(local_ids.values())))
        h.ns.char.progress[ROUTE].cursor = 4
        h.duo.peer.headerSeen = h.state.now
        peer_ids = h.dcall("GetQuestIDs")
        self.assertTrue(set(CHAIN).issubset(set(peer_ids.values())))


if __name__ == "__main__":
    unittest.main()
