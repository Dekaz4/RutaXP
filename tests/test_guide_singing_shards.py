"""Follow the live shard count through the farm and Booty Bay visits in Journey."""
import unittest

from test_access_navigation import ADDON, AccessHost


GUIDE = "forever/alliance/30-40/04-stranglethorn-vale"
HORDE = "forever/horde/30-40/02-stranglethorn-vale"
QUEST, SHARD, CRANK = 605, 3918, 2498


class SingingShardsTests(unittest.TestCase):
    def client(self, action, guide=GUIDE):
        h = AccessHost(guide, find_goal={"quest": QUEST, "t": action}, x=.284, y=.769)
        if guide == HORDE:
            h.s.faction, h.s.raceToken = "Horde", "Orc"
        h.s.level, h.s.classToken, h.ns.char.auto = 35, "ROGUE", True
        h.h.lua.execute("""
            getmetatable(UIParent).__index.GetTexture = function(self) return self.texture end
            function GetItemCount(id, includeBank)
                if id ~= 3918 then return 0 end
                return (TEST.shards or 0) + (includeBank and TEST.bankShards or 0)
            end
        """)
        h.h.lua.execute((ADDON / "GuideOriginal.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        return h

    def update_count(self, h, count, *, bag_only=False):
        h.s.shards = count
        if not bag_only:
            h.s.quests[QUEST] = h.h.table({
                "onQuest": True, "complete": count == 10,
                "objectives": [{"text": f"Fragmento de cristal canto: {count}/10",
                                "numFulfilled": count, "numRequired": 10, "finished": count == 10}],
            })
        h.h.g.EmitAddonEvent("BAG_UPDATE_DELAYED" if bag_only else "QUEST_LOG_UPDATE")

    def assert_destination(self, h, cursor, action, count=None):
        _, step, state = h.ns.GetCurrent(h.ns)
        self.assertEqual(state.cursor, cursor)
        row = next(row for row in h.ns.OriginalGuidePresentation.Tasks().values() if row.isCurrent)
        self.assertEqual((row.questID, row.action, row.status), (QUEST, action, "active"))
        h.ns.GetArrowWaypoint(h.ns, step)
        waypoint = h.ns.OriginalGuidePresentation.Waypoint()
        self.assertIsNotNone(waypoint, "Journey must receive a navigable destination")
        map_id, x, y, _, _, point = waypoint
        self.assertEqual((map_id, point.goal.quest, point.goal.t), (1434, QUEST, action))
        pins = [p for p in h.ns.GetMapQuestPoints(h.ns, map_id).values() if p.questID == QUEST]
        if action == "collect":
            self.assertEqual(point.goal.item, SHARD)
            self.assertIn(f"{count}/10", row.text)
            self.assertIn("basilisco", row.text.lower())
            camps = {(24.2, 17.5), (26.7, 18.3)}
            self.assertIn((round(100 * x, 1), round(100 * y, 1)), camps)
            self.assertEqual({p.category for p in pins}, {"objective"})
            for pin in pins:
                self.assertIn((round(100 * pin.x, 1), round(100 * pin.y, 1)), camps)
        else:
            self.assertIn("Loquillo Pinchabujas", row.text)
            self.assertEqual(point.goal.npc, CRANK)
            self.assertAlmostEqual(x, .2712)
            self.assertAlmostEqual(y, .7721)
            self.assertEqual([(p.category, p.detail) for p in pins], [("turnin", "Loquillo Pinchabujas")])

    def deliver(self, h):
        h.s.quests[QUEST] = h.h.table({"delivered": True})
        h.s.shards, h.s.entries = 0, h.h.table([])
        h.h.g.EmitAddonEvent("QUEST_TURNED_IN", QUEST)

    def test_saved_booty_bay_visit_routes_back_to_farm_until_ten(self):
        for mark in (None, "skipped", "confirmed"):
            with self.subTest(old_farm_mark=mark):
                h = self.client("turnin")
                state = h.ns.char.progress[GUIDE]
                if mark:
                    state[mark]["17:1"] = True
                for count in (0, 9):
                    self.update_count(h, count)
                    self.assert_destination(h, 22, "collect", count)
                self.update_count(h, 10)
                self.assert_destination(h, 22, "turnin")
                self.deliver(h)
                self.assertNotEqual(h.ns.GetActiveGoal(h.ns)[0].quest, QUEST)
                if mark:
                    self.assertTrue(state[mark]["17:1"])

    def test_tenth_shard_on_farm_leads_straight_to_crank_before_continuing(self):
        h = self.client("collect")
        self.update_count(h, 9)
        self.assert_destination(h, 17, "collect", 9)
        self.update_count(h, 10, bag_only=True)  # The quest log still says 9/10 this frame.
        self.assert_destination(h, 17, "turnin")
        self.update_count(h, 10)
        self.assert_destination(h, 17, "turnin")
        self.deliver(h)
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 18)

    def test_live_objective_count_can_lead_completion_flags_and_bag_data(self):
        h = self.client("turnin")
        h.s.bankShards = 5
        self.update_count(h, 9)
        self.assert_destination(h, 22, "collect", 9)
        objective = h.s.quests[QUEST].objectives[1]
        objective.numFulfilled, objective.text = 10, "Fragmento de cristal canto: 10/10"
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        self.assert_destination(h, 22, "turnin")

    def test_horde_visit_uses_its_own_farm_then_drops_the_delivered_quest(self):
        h = self.client("turnin", HORDE)
        self.update_count(h, 9)
        self.assert_destination(h, 23, "collect", 9)
        self.update_count(h, 10)
        self.assert_destination(h, 23, "turnin")
        self.deliver(h)
        self.assertNotEqual(h.ns.GetActiveGoal(h.ns)[0].quest, QUEST)

    def test_abandoned_quest_never_sends_either_faction_out_to_farm(self):
        for guide in (GUIDE, HORDE):
            with self.subTest(guide=guide):
                h = self.client("turnin", guide)
                h.s.quests[QUEST], h.s.entries = h.h.table({}), h.h.table([])
                h.s.shards = 9
                h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
                point = h.point()
                self.assertFalse(point and point.goal and point.goal.quest == QUEST)

    def test_an_earlier_pending_handin_at_this_visit_keeps_priority(self):
        h = self.client("turnin")
        state = h.ns.char.progress[GUIDE]
        state.confirmed["22:2"] = None
        h.s.quests[575] = h.h.table({"onQuest": True, "complete": True})
        self.update_count(h, 9)
        point = h.point()
        self.assertEqual((state.cursor, point.goal.quest, point.goal.npc), (22, 575, 2495))


if __name__ == "__main__":
    unittest.main()
