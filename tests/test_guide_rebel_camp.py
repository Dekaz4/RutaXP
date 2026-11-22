"""Play the Alliance Rebel Camp visit from its saved cursor through Kurzen's camp."""
import unittest

from test_access_navigation import AccessHost, WORLD_STUBS
from test_duo_journey import JourneyHost
from test_quest_engine import ADDON, QuestEngineHost


GUIDE = "forever/alliance/30-40/04-stranglethorn-vale"


class RebelCampVisitTests(unittest.TestCase):
    def client(self, *, quests=None, cursor=9, optional=False, duo=False, old_skip=False):
        h = QuestEngineHost(catalog=True)
        h.globals.ACCESS_NS = h.ns
        h.lua.execute(WORLD_STUBS)
        for name in ("GuideMigrations", "Navigation", "QuestOfferAdvice", "NPCQuestContext", "TrackerPreview"):
            h.load((ADDON / f"{name}.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.ns.UpdateNavigation = None  # Query the real waypoint without creating arrow textures.
        h.state.classToken, h.state.level = "ROGUE", 34
        h.state.mapID, h.state.x, h.state.y = 1434, .404, .084
        for quest, fields in (quests or {}).items():
            h.quest(quest, **fields)
        h.globals.RutaXPCharDB = h.table({
            "activeGuide": GUIDE, "auto": True, "seen": True, "optional": optional,
            "duo": {"enabled": duo},
            "progress": {GUIDE: {"routeRevision": 2, "cursor": cursor, "placed": True,
                                 "confirmed": {}, "skipped": {"9:1": True} if old_skip else {}}},
        })
        h.initialize()
        return h

    def accept(self, h, quest):
        h.quest(quest, onQuest=True)
        h.fire("QUEST_ACCEPTED", 1, quest)

    def deliver(self, h, quest):
        h.quest(quest, delivered=True)
        h.fire("QUEST_TURNED_IN", quest)

    def assert_goal(self, h, cursor, action, quest, npc=None):
        _, step, state = h.call("GetCurrent")
        goal = h.active()[0]
        self.assertEqual((state.cursor, goal.t, goal.quest), (cursor, action, quest))
        if npc:
            point = h.call("GetStepWaypoint", step)
            self.assertIsNotNone(point)
            self.assertEqual((goal.npc, point.goal.npc, point.mapID), (npc, npc, 1434))
            if npc == 733:
                self.assertAlmostEqual(point.x, .3802)
                self.assertAlmostEqual(point.y, .0333)

    def test_skip_saved_at_ambush_does_not_skip_yohwa_in_reordered_visit(self):
        h = self.client(old_skip=True)
        self.assert_goal(h, 9, "accept", 203, 733)
        self.accept(h, 203)
        self.assert_goal(h, 9, "accept", 204, 733)
        self.accept(h, 204)
        self.assert_goal(h, 10, "kill", 203)
        self.assertFalse(h.call("IsQuestDelivered", 215))
        self.assertFalse(h.call("IsQuestActive", 215))

    def test_absent_thorsen_never_stalls_the_kurzen_trip_or_its_handins(self):
        for optional, duo in ((False, False), (True, False), (False, True)):
            with self.subTest(optional=optional, duo=duo):
                h = self.client(optional=optional, duo=duo)
                self.assert_goal(h, 9, "accept", 203, 733)
                self.assertEqual(h.call("GetQuestOfferAdvice", 215)[1], "opcional")
                guide = h.ns.guides[GUIDE]
                items, _ = h.call("GetStepGoalItems", guide.steps[9])
                note, = [row for row in items.values() if row.action == "note" and "Opcional" in row.title]
                self.assertIn("Thorsen", note.subtitle)
                self.assertFalse(note.isCurrent)
                self.assertIsNone(note.goal)
                upcoming = h.call("GetTrackerPlannedUpcomingItems", guide, 9, 12)
                preview = {row.questID for row in upcoming.values()}
                self.assertTrue(preview.isdisjoint({215, 200, 328, 329, 330, 331}), preview)
                self.assertTrue(preview.intersection({203, 204}), preview)
                self.accept(h, 203)
                self.assert_goal(h, 9, "accept", 204, 733)
                self.accept(h, 204)
                self.assert_goal(h, 10, "kill", 203)
                for quest in (203, 204):
                    h.quest(quest, onQuest=True, complete=True)
                h.fire("QUEST_LOG_UPDATE")
                self.assert_goal(h, 12, "turnin", 203, 733)
                self.deliver(h, 203)
                self.assert_goal(h, 12, "turnin", 204, 733)
                self.deliver(h, 204)
                self.assertEqual(h.cursor(GUIDE), 13)
                self.assertFalse(h.call("IsQuestDelivered", 215))

    def test_already_accepted_or_delivered_jungle_secrets_keeps_dorens_chain(self):
        for delivered in (False, True):
            with self.subTest(delivered=delivered):
                state = {"delivered": True} if delivered else {"onQuest": True, "complete": True}
                h = self.client(quests={215: state})
                self.assert_goal(h, 9, "accept", 203, 733)
                self.accept(h, 203)
                self.assert_goal(h, 9, "accept", 204, 733)
                self.accept(h, 204)
                if not delivered:
                    self.assert_goal(h, 9, "turnin", 215, 469)
                    self.deliver(h, 215)
                self.assert_goal(h, 9, "accept", 200, 469)
                self.accept(h, 200)
                self.assert_goal(h, 10, "kill", 203)

    def test_character_already_at_herods_documents_continues_according_to_journal(self):
        ready = {203: {"onQuest": True, "complete": True}, 204: {"onQuest": True, "complete": True}}
        self.assert_goal(self.client(cursor=11, quests=ready), 12, "turnin", 203, 733)
        with_herod = {**ready, 215: {"delivered": True}, 200: {"onQuest": True, "complete": True}}
        self.assert_goal(self.client(cursor=11, quests=with_herod), 11, "turnin", 200)

    def test_accepting_thorsen_on_the_way_to_kurzen_adds_a_delivery_on_the_return_visit(self):
        h = self.client(quests={203: {"onQuest": True}, 204: {"onQuest": True}})
        self.assert_goal(h, 10, "kill", 203)
        self.accept(h, 215)
        h.quest(215, onQuest=True, complete=True)
        self.assert_goal(h, 10, "kill", 203)
        for quest in (203, 204):
            h.quest(quest, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        for quest in (203, 204):
            self.assert_goal(h, 12, "turnin", quest, 733)
            self.deliver(h, quest)
        self.assert_goal(h, 12, "turnin", 215, 469)
        self.deliver(h, 215)
        self.assertEqual(h.cursor(GUIDE), 13)

    def test_only_thorsens_actual_offer_is_actionable_and_closing_it_resumes_the_route(self):
        for event, closed in (("GOSSIP_SHOW", "GOSSIP_CLOSED"), ("QUEST_DETAIL", "QUEST_FINISHED")):
            with self.subTest(menu=event):
                client = AccessHost(GUIDE, 9, 1, x=.404, y=.084)
                h, s, ns = client.h, client.s, client.ns
                s.level = 34
                ns.char.auto = True
                for quest in (203, 204):
                    s.quests[quest] = h.table({"onQuest": True})
                h.lua.execute("""
                    function UnitGUID(unit)
                        if unit == "npc" and TEST.contact then
                            return "Creature-0-1-2-3-" .. TEST.contact .. "-123"
                        end
                    end
                    C_GossipInfo = {GetAvailableQuests=function()
                        return TEST.offer and {{questID=TEST.offer}} or {}
                    end}
                    function GetQuestID() return TEST.detail end
                    function IsShiftKeyDown() return true end
                """)
                s.contact = 733
                if event == "GOSSIP_SHOW":
                    s.offer = 215
                else:
                    s.detail = 215
                self.assertFalse(ns.WantsQuest(ns, "accept", 215))
                s.contact = 738
                h.g.EmitAddonEvent(event)
                self.assertTrue(ns.WantsQuest(ns, "accept", 215))
                self.assertIsNone(s.quests[215])
                self.assertEqual(ns.char.progress[GUIDE].cursor, 9)
                s.contact, s.offer, s.detail = None, None, None
                h.g.EmitAddonEvent(closed)
                self.assertFalse(ns.WantsQuest(ns, "accept", 215))
                self.assertEqual(ns.char.progress[GUIDE].cursor, 10)

    def test_duo_keeps_the_wait_for_yohwa_but_not_for_a_partner_without_thorsen(self):
        h = JourneyHost()
        h.load((ADDON / "Leveling.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.state.level = h.state.friendLevel = 34
        h.ns.char.activeGuide = GUIDE
        h.call("GetProgress", GUIDE).cursor = 9
        h.ns.char.duo.wait = True
        h.peer(cursor=9)
        h.duo.peer.guideID = GUIDE
        h.quest(215, delivered=True)
        h.quest(200, onQuest=True)
        for quest in (203, 204):
            h.quest(quest, onQuest=True)
            h.remote(quest, 1)
        h.remote(215, 0)
        h.remote(200, 0)
        step = h.ns.guides[GUIDE].steps[9]
        self.assertFalse(h.dcall("GetStepWaitStatus", step).waiting)
        h.remote(204, 0)
        self.assertEqual(h.dcall("GetStepWaitStatus", step).questID, 204)


if __name__ == "__main__":
    unittest.main()
