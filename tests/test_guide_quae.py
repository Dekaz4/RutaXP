"""Replay the Hillsbrad referral from the Alliance Arathi guide, step 28."""
import unittest

from test_access_navigation import ADDON, AccessHost


GUIDE = "forever/alliance/30-40/05-arathi-highlands"
ARATHI, HILLSBRAD = 1417, 1424
PHIN = (HILLSBRAD, .5035, .5905)
QUAE = (ARATHI, .6018, .5385)


class QuaeReferralTests(unittest.TestCase):
    def client(self, quests=None):
        h = AccessHost(GUIDE, 28, 1, .605, .529)
        h.s.level, h.s.classToken = 38, "ROGUE"
        h.s.quests = h.h.table(quests or {})
        h.s.entries = h.h.table([{"questID": quest, "isHeader": False}
                                 for quest, flags in (quests or {}).items() if flags.get("onQuest")])
        h.h.lua.execute("""
            getmetatable(UIParent).__index.GetTexture = function(frame) return frame.texture end
            -- RestedXP may cache the folder before either quest is accepted.
            RXPCData = {questObjectivesCache={[658]={{text="Carpeta sellada: 0/1", finished=false}}}}
        """)
        for module in ("DestinationTravel", "CircuitCreatureData", "CircuitTerrain", "LocalCircuit", "GuideOriginal"):
            h.h.lua.execute((ADDON / f"{module}.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.ns.char.auto = True
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        return h

    def move(self, h, location):
        h.s.mapID, h.s.x, h.s.y = location
        h.h.g.EmitAddonEvent("ZONE_CHANGED_NEW_AREA")

    def assert_goal(self, h, action, quest, npc, name):
        goal, _, status, _ = h.ns.GetActiveGoal(h.ns)
        self.assertEqual((goal.t, goal.quest, goal.npc, status), (action, quest, npc, "active"))
        row, = [r for r in h.ns.OriginalGuidePresentation.Tasks().values() if r.isCurrent]
        self.assertEqual((row.action, row.questID, row.status), (action, quest, "active"))
        self.assertIn(name, row.text)
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 28)
        return row

    def assert_local_arrow(self, h, coords, npc):
        point = h.ns.GetArrowWaypoint(h.ns, h.step, False)
        self.assertIsNotNone(point)
        waypoint = h.ns.OriginalGuidePresentation.Waypoint()
        self.assertIsNotNone(waypoint)
        map_id, x, y = waypoint[:3]
        self.assertEqual((point.goal.npc, map_id), (npc, coords[0]))
        self.assertAlmostEqual(x, coords[1])
        self.assertAlmostEqual(y, coords[2])

    def test_absent_referral_sends_player_from_quae_to_phin_and_back_on_acceptance(self):
        h = self.client()
        self.assert_goal(h, "accept", 659, 2711, "Phin Odelic")
        self.assertEqual(h.point().goal.map, HILLSBRAD)
        _, subtitle, _ = h.ns.OriginalGuidePresentation.Headings()
        self.assertIn("Phin", subtitle)
        self.assertIn("Costasur", subtitle)
        pins = h.ns.GetMapQuestPoints(h.ns, HILLSBRAD)
        self.assertTrue(any(p.questID == 659 and p.category == "accept" and p.detail == "Phin Odelic"
                            for p in pins.values()))

        # At the real road crossing, the compass points to the next zone.
        self.move(h, (ARATHI, .2034, .2973))
        crossing = h.ns.GetArrowWaypoint(h.ns, h.step, False)
        view = h.ns.GetDestinationTravelView(h.ns)
        self.assertIsNotNone(crossing)
        self.assertEqual((crossing.mapID, view.kind, view.state), (ARATHI, "road", "crossing"))
        self.move(h, PHIN)
        self.assert_local_arrow(h, PHIN, 2711)
        h.s.quests[659] = h.h.table({"onQuest": True})
        h.s.entries = h.h.table([{"questID": 659}])
        h.h.g.EmitAddonEvent("QUEST_ACCEPTED", 1, 659)
        self.assert_goal(h, "turnin", 659, 2712, "Quae")
        self.assertEqual(h.point().goal.map, ARATHI)
        self.assertNotIn("Phin", h.ns.OriginalGuidePresentation.Headings()[1])
        self.assertFalse(any(p.questID == 659 and p.category == "accept"
                             for p in h.ns.GetMapQuestPoints(h.ns, HILLSBRAD).values()))
        pins = h.ns.GetMapQuestPoints(h.ns, ARATHI)
        self.assertTrue(any(p.questID == 659 and p.category == "turnin" and p.detail == "Quae"
                            for p in pins.values()))
        self.move(h, QUAE)
        self.assert_local_arrow(h, QUAE, 2712)

        h.s.quests[659] = h.h.table({"delivered": True})
        h.s.entries = h.h.table([])
        h.h.g.EmitAddonEvent("QUEST_TURNED_IN", 659)
        self.assert_goal(h, "accept", 658, 2712, "Quae")
        self.assert_local_arrow(h, QUAE, 2712)
        h.s.quests[658] = h.h.table({"onQuest": True})
        h.h.g.EmitAddonEvent("QUEST_ACCEPTED", 1, 658)
        next_goal = h.ns.GetActiveGoal(h.ns)[0]
        self.assertEqual((h.ns.char.progress[GUIDE].cursor, next_goal.t, next_goal.quest), (29, "collect", 658))
        state = h.ns.char.progress[GUIDE]
        self.assertTrue(state.skipped["user-skipped"])
        self.assertTrue(state.confirmed["user-confirmed"])

    def test_opening_the_guide_with_referral_in_journal_or_delivered_never_repeats_phin(self):
        for flags, action, quest in (({"onQuest": True}, "turnin", 659), ({"delivered": True}, "accept", 658)):
            with self.subTest(flags=flags):
                h = self.client({659: flags})
                self.assert_goal(h, action, quest, 2712, "Quae")
                self.assert_local_arrow(h, QUAE, 2712)

    def test_missing_live_history_or_journal_does_not_send_the_player_to_southshore(self):
        for api in ("active", "delivered"):
            with self.subTest(unavailable=api):
                h = self.client()
                if api == "active":
                    h.h.lua.execute("C_QuestLog.IsOnQuest=function() return nil end")
                else:
                    h.h.lua.execute("C_QuestLog.IsQuestFlaggedCompleted=nil; IsQuestFlaggedCompleted=nil")
                h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
                goal, _, status, _ = h.ns.GetActiveGoal(h.ns)
                self.assertEqual(status, "blocked")
                self.assertNotEqual((goal.npc, goal.t), (2711, "accept"))
                self.assertIsNone(h.ns.GetArrowWaypoint(h.ns, h.step, False))
                self.assertEqual(h.ns.char.progress[GUIDE].cursor, 28)

    def test_live_later_link_with_missing_ancestor_flags_never_routes_back_to_phin(self):
        cases = [
            (658, "onQuest", 29, "collect", 658), (658, "delivered", 30, "accept", 657),
            (657, "onQuest", 30, "turnin", 657), (657, "delivered", 30, "accept", 660),
            (660, "onQuest", 31, "complete", 660), (660, "delivered", 32, "accept", 661),
            (661, "onQuest", 33, "accept", 642), (661, "delivered", 33, "accept", 642),
        ]
        for quest, flag, cursor, action, expected_id in cases:
            with self.subTest(quest=quest, flag=flag):
                h = self.client({quest: {flag: True}})
                goal = h.ns.GetActiveGoal(h.ns)[0]
                self.assertEqual((h.ns.char.progress[GUIDE].cursor, goal.t, goal.quest), (cursor, action, expected_id))
                pending = h.ns.OriginalGuidePresentation.Tasks()
                self.assertFalse(any(row.isCurrent and row.action == "accept" and row.questID == 659
                                     for row in pending.values()))

    def test_saved_explicit_skip_on_referral_row_is_retained(self):
        h = self.client()
        state = h.ns.char.progress[GUIDE]
        state.skipped["28:1"] = True
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        goal = h.ns.GetActiveGoal(h.ns)[0]
        self.assertNotEqual((goal.t, goal.quest), ("accept", 659))
        self.assertTrue(state.skipped["28:1"])
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 659))

    def test_arrival_does_not_fake_acceptance_and_abandonment_restores_phin(self):
        h = self.client({659: {"onQuest": True}})
        h.s.quests[659], h.s.entries = None, h.h.table([])
        h.h.g.EmitAddonEvent("QUEST_REMOVED", 659)
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        self.move(h, PHIN)
        h.h.g.EmitAddonEvent("GOSSIP_SHOW")
        self.assert_goal(h, "accept", 659, 2711, "Phin Odelic")
        self.assertFalse(h.ns.IsQuestActive(h.ns, 659))
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 659))

    def test_phins_menu_selects_and_accepts_the_referral_by_id(self):
        h = self.client()
        self.move(h, PHIN)
        h.h.lua.execute("""
            function UnitGUID(unit)
                if unit == "npc" then return "Creature-0-1-2-3-2711-ABC" end
            end
            C_GossipInfo = {
                GetAvailableQuests=function()
                    return {{questID=660,title="Sospechas de una nueva Peste"},
                            {questID=659,title="Sospechas de una nueva Peste"}}
                end,
                SelectAvailableQuest=function(id) TEST.offerSelected=id end,
            }
            function GetQuestID() return TEST.detail end
            function AcceptQuest() TEST.offerAccepted=GetQuestID() end
        """)
        h.h.g.EmitAddonEvent("GOSSIP_SHOW")
        self.assertEqual(h.s.offerSelected, 659)
        h.s.detail = 660
        h.h.g.EmitAddonEvent("QUEST_DETAIL")
        self.assertIsNone(h.s.offerAccepted)
        h.s.detail = h.s.offerSelected
        h.h.g.EmitAddonEvent("QUEST_DETAIL")
        self.assertEqual(h.s.offerAccepted, 659)
        self.assertFalse(h.ns.IsQuestActive(h.ns, 659))
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 28)


if __name__ == "__main__":
    unittest.main()
