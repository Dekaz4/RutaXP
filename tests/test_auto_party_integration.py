"""End-to-end automatic parties: two real TOCs, isolated SavedVariables, real wire."""

import unittest

from test_duo import DUO_STUBS
from test_duo_journey import primitive_copy
from test_duo_enhanced import ENHANCED_STUBS
import test_talent_trainer_regressions as full


ROUTE_ID = "auto-review/common"
QUEST_ID = 900100


class AutomaticPartyHost:
    def __init__(self, name="Uno", friend="Dos", cursor=2, review=True, auto=False,
                 active_guide=ROUTE_ID, saved=None, race="Human", cls="WARRIOR", legacy=False, now=0):
        self.h = full.TalentTrainerHost(full_toc=True)
        self.h.lua.execute(DUO_STUBS)
        self.h.lua.execute(ENHANCED_STUBS)
        self.s, self.ns = self.h.state, self.h.ns
        self.s.playerName, self.s.friendName = name, friend
        self.s.members, self.s.now = 0, now
        self.s.classToken = self.s.friendClass = cls
        self.s.raceToken = self.s.friendRace = race
        self.s.faction = self.s.friendFaction = "Alliance"
        self.s.level = self.s.friendLevel = 10
        self.s.mana, self.s.maximumMana = 100, 100
        self.s.friendInRange, self.s.rangeChecked = True, True
        self.legacy = legacy
        self.packets = []
        # Supply a real map transform so the shipping arrow can measure points.
        self.h.lua.execute('''
            function CreateVector2D(x,y) return {GetXY=function() return x,y end} end
            function C_Map.GetWorldPosFromMapPos(mapID,position)
                local x,y=position:GetXY();return 0,CreateVector2D(y*1000,x*1000)
            end
        ''')
        for route_id in [ROUTE_ID, "auto-review/uno-solo", "auto-review/dos-solo"]:
            self.register_route(route_id)
        self.register_route("auto-review/warrior", classes=["WARRIOR"], quest_id=QUEST_ID + 1)
        self.register_route("auto-review/mage", classes=["MAGE"], quest_id=QUEST_ID + 2)
        self.register_route("auto-review/human", races=["Human"], quest_id=QUEST_ID + 3)
        self.register_route("auto-review/nightelf", races=["NightElf"], quest_id=QUEST_ID + 4)
        if saved is None:
            progress = {route_id: {"cursor": cursor, "review": review, "placed": True,
                                    "confirmed": {"user-confirmed": True}, "skipped": {"user-skipped": True}}
                        for route_id in [ROUTE_ID, "auto-review/uno-solo", "auto-review/dos-solo",
                                         "auto-review/warrior", "auto-review/mage", "auto-review/human", "auto-review/nightelf"]}
            saved = {"seen": True, "activeGuide": active_guide, "auto": auto, "progress": progress,
                     "duo": {"enabled": False, "wait": False}}
        self.h.g.RutaXPCharDB = self.h.table(saved)
        personal_quests = {"auto-review/warrior": QUEST_ID + 1, "auto-review/mage": QUEST_ID + 2,
                           "auto-review/human": QUEST_ID + 3, "auto-review/nightelf": QUEST_ID + 4}
        self.quest(personal_quests.get(active_guide, QUEST_ID), count=8 if cursor >= 3 else 3)
        self.h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        self.h.g.EmitAddonEvent("PLAYER_LOGIN")
        self.h.g.NS = self.ns
        self.h.lua.execute('''
            TEST.syncCalls,TEST.syncDepth,TEST.maxSyncDepth=0,0,0
            local sync=NS.Sync
            function NS:Sync(...)
                TEST.syncCalls=TEST.syncCalls+1;TEST.syncDepth=TEST.syncDepth+1
                TEST.maxSyncDepth=math.max(TEST.maxSyncDepth,TEST.syncDepth)
                assert(TEST.syncDepth<8,"Recursive Sync while negotiating an automatic party")
                sync(self,...);TEST.syncDepth=TEST.syncDepth-1
            end
        ''')

    def register_route(self, route_id, classes=None, races=None, quest_id=QUEST_ID):
        only = {}
        if classes:
            only["classes"] = classes
        if races:
            only["races"] = races
        goals = [
            {"t": "accept", "quest": quest_id, "npc": 123, "npcName": "Guía de prueba", "map": 1429, "x": 40, "y": 60},
            {"t": "complete", "quest": quest_id, "oi": 1, "map": 1429, "x": 45, "y": 65},
            {"t": "turnin", "quest": quest_id, "npc": 123, "npcName": "Guía de prueba", "map": 1429, "x": 40, "y": 60},
        ]
        if only:
            for goal in goals:
                goal["only"] = {key: values.copy() for key, values in only.items()}
        guide = {"id": route_id, "title": route_id, "faction": "Alliance", "minLevel": 10, "maxLevel": 20,
                 "zone": 1429, "steps": [{"title": title, "goals": [goal]} for title, goal in zip(
                     ["Aceptar de ambos", "Objetivo del compañero", "Entregar de ambos"], goals)]}
        guide.update({key: values.copy() for key, values in only.items()})
        self.ns.RegisterGuide(self.ns, self.h.table(guide))

    def quest(self, quest_id=QUEST_ID, count=3, delivered=False):
        self.s.quests[quest_id] = self.h.table({"title": "Objetivo compartido de prueba", "onQuest": not delivered,
            "complete": count == 8 and not delivered, "delivered": delivered,
            "objectives": [{"text": f"Objetos: {count}/8", "numFulfilled": count, "numRequired": 8, "finished": count == 8}]})
        self.s.entries = self.h.table([{"questID": quest_id, "isHeader": False}])

    def roster(self, members=2):
        self.s.members = members
        self.h.g.EmitAddonEvent("GROUP_ROSTER_UPDATE")

    def tick(self):
        self.s.now += 1
        self.ns.featureDriver.scripts.OnUpdate(self.ns.featureDriver, 1)

    def deliver(self, other):
        for packet in self.s.outgoing.values():
            fields = packet.message.split("|")
            kind = fields[1]
            self.packets.append({"kind": kind, "message": packet.message, "channel": packet.channel})
            if (self.legacy or other.legacy) and kind in ("A", "P"):
                continue
            message = "|".join(fields[:18]) if self.legacy and kind == "H" else packet.message
            other.h.g.EmitAddonEvent("CHAT_MSG_ADDON", packet.prefix, message, packet.channel,
                                    self.s.playerName + "-Forever")
        self.s.outgoing = self.h.lua.table()

    def view(self):
        return self.ns.DuoAuto.GetSharedView(self.ns.DuoAuto)

    def status(self):
        return self.ns.DuoAuto.GetStatus(self.ns.DuoAuto)

    def progress(self, include_reviews=True):
        result = primitive_copy(self.ns.char.progress)
        if not include_reviews:
            for state in result.values():
                if isinstance(state, dict):
                    state.pop("review", None)
        return result


class AutomaticPartyIntegrationTests(unittest.TestCase):
    def pair(self, **options):
        a = AutomaticPartyHost(**options)
        b = AutomaticPartyHost("Dos", "Uno", **options)
        return a, b

    def exchange(self, a, b, ticks=75):
        for _ in range(ticks):
            a.tick(); b.tick(); a.deliver(b); b.deliver(a)

    def form(self, a, b, ticks=75):
        a.roster(); b.roster()
        self.exchange(a, b, ticks)

    def test_group_formation_negotiates_automatic_party_without_commands(self):
        a, b = self.pair()
        before_a, before_b = a.progress(False), b.progress(False)
        self.assertEqual(len(a.s.outgoing), 0)
        self.form(a, b)
        self.assertTrue(a.status().active)
        self.assertTrue(b.status().active)
        self.assertEqual(a.view().guideID, b.view().guideID)
        self.assertEqual(a.view().guideID, ROUTE_ID)
        self.assertEqual(a.progress(False), before_a)
        self.assertEqual(b.progress(False), before_b)
        self.assertTrue(any(p["kind"] == "A" for h in (a, b) for p in h.packets))
        self.assertTrue(any(p["kind"] == "P" for h in (a, b) for p in h.packets))
        self.assertLessEqual(a.s.maxSyncDepth, 2)
        self.assertLessEqual(b.s.maxSyncDepth, 2)

    def test_advanced_player_helps_lower_cursor_without_rewinding_or_clicking_future(self):
        a, b = AutomaticPartyHost(cursor=3), AutomaticPartyHost("Dos", "Uno", cursor=2)
        before_a, before_b = a.progress(False), b.progress(False)
        self.form(a, b)
        self.assertTrue(a.view().following)
        self.assertEqual(a.view().sharedCursor, 2)
        self.assertEqual(a.view().ownCursor, 3)
        _, step, _ = a.ns.GetCurrent(a.ns)
        point = a.ns.GetStepWaypoint(a.ns, step)
        self.assertEqual(point.source, "duo-follow")
        self.assertIn("Objetivo del compañero", a.ns.trackerStep.text)
        a.ns.Next(a.ns)
        a.ns.SkipStep(a.ns)
        a.ns.ToggleGoalConfirm(a.ns, 1)
        self.assertEqual(a.progress(False), before_a)
        self.assertEqual(b.progress(False), before_b)
        # Old review=true preferences are leased, rather than blocking setup.
        self.assertFalse(a.ns.char.progress[ROUTE_ID].review)
        a.ns.DuoAuto.SetEnabled(a.ns.DuoAuto, False)
        self.assertTrue(a.ns.char.progress[ROUTE_ID].review)

    def test_different_initial_guides_converge_without_replacing_either_characters_marks(self):
        a = AutomaticPartyHost(active_guide="auto-review/uno-solo", cursor=3)
        b = AutomaticPartyHost("Dos", "Uno", active_guide="auto-review/dos-solo", cursor=2)
        before_a, before_b = a.progress(False), b.progress(False)
        self.form(a, b)
        self.assertTrue(a.status().active)
        self.assertTrue(b.status().active)
        self.assertEqual(a.ns.char.activeGuide, b.ns.char.activeGuide)
        self.assertEqual(a.view().guideID, b.view().guideID)
        self.assertEqual(a.view().sharedCursor, 2)
        self.assertEqual(a.view().ownCursor, 3)
        self.assertEqual(a.status().coordinator, "dos-forever")
        self.assertEqual(b.status().coordinator, "dos-forever")
        self.assertEqual(a.progress(False), before_a)
        self.assertEqual(b.progress(False), before_b)

    def test_real_advancement_does_not_restore_an_old_review_flag_after_leaving(self):
        a, b = self.pair()
        self.form(a, b)
        # Both complete the pending objective through the actual quest APIs.
        a.quest(count=8); b.quest(count=8)
        for _ in range(20):
            a.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
            b.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
            self.exchange(a, b, 1)
        self.assertEqual(a.ns.char.progress[ROUTE_ID].cursor, 3)
        self.assertEqual(b.ns.char.progress[ROUTE_ID].cursor, 3)
        a.roster(0); b.roster(0)
        self.exchange(a, b, 3)
        for h in (a, b):
            state = h.ns.char.progress[ROUTE_ID]
            self.assertFalse(state.review)
            self.assertEqual(state.cursor, 3)
            self.assertTrue(state.confirmed["user-confirmed"])
            self.assertTrue(state.skipped["user-skipped"])

    def test_leaving_and_opt_out_restore_personal_settings_and_keep_progress(self):
        a, b = self.pair()
        before_a, before_b = a.progress(), b.progress()
        self.form(a, b)
        a.roster(0); b.roster(0)
        self.exchange(a, b, 3)
        for h, before in [(a, before_a), (b, before_b)]:
            self.assertIsNone(h.view())
            self.assertFalse(h.ns.char.auto)
            self.assertFalse(h.ns.char.duo.enabled)
            self.assertFalse(h.ns.char.duo.wait)
            self.assertEqual(h.progress(), before)
        self.form(a, b)
        self.assertTrue(a.status().active)
        a.ns.DuoAuto.SetEnabled(a.ns.DuoAuto, False)
        # The restored disabled transport is silent; the peer expires its
        # last confirmed capability/header within the protocol's 15 seconds.
        self.exchange(a, b, 20)
        self.assertIsNone(a.view())
        self.assertFalse(a.ns.char.auto)
        self.assertFalse(a.ns.char.duo.enabled)
        self.assertEqual(a.progress(), before_a)
        self.assertIsNone(b.view())
        a.ns.DuoAuto.SetEnabled(a.ns.DuoAuto, True)
        self.exchange(a, b)
        self.assertTrue(a.status().active)
        self.assertTrue(b.status().active)
        self.assertEqual(a.view().guideID, b.view().guideID)
        self.assertEqual(a.progress(False), {key: {field: value for field, value in state.items() if field != "review"}
                                            for key, state in before_a.items()})

    def test_reload_while_paired_and_then_leave_restores_baseline_without_rewinding(self):
        a, b = self.pair()
        before = a.progress(False)
        self.form(a, b)
        saved = primitive_copy(a.ns.char)
        reloaded = AutomaticPartyHost(saved=saved, now=a.s.now + 1)
        reloaded.roster(2)
        self.exchange(reloaded, b)
        self.assertEqual(reloaded.progress(False), before)
        reloaded.roster(0)
        self.exchange(reloaded, b, 3)
        self.assertFalse(reloaded.ns.char.auto)
        self.assertFalse(reloaded.ns.char.duo.wait)
        self.assertEqual(reloaded.progress(False), before)
        self.assertTrue(reloaded.ns.char.progress[ROUTE_ID].review)

    def test_old_capability_raid_three_players_and_cross_faction_never_force_route(self):
        for scenario in ("legacy", "three", "raid", "cross"):
            with self.subTest(scenario=scenario):
                a = AutomaticPartyHost(active_guide="auto-review/uno-solo")
                b = AutomaticPartyHost("Dos", "Uno", active_guide="auto-review/dos-solo", legacy=scenario == "legacy")
                if scenario == "legacy":
                    b.ns.char.duo.enabled = True
                if scenario == "raid":
                    a.s.raid = b.s.raid = True
                if scenario == "cross":
                    a.s.friendFaction, b.s.faction = "Horde", "Horde"
                    b.s.friendFaction = "Alliance"
                if scenario == "three":
                    a.roster(3); b.roster(3)
                    self.exchange(a, b, 40)
                else:
                    self.form(a, b, ticks=40)
                self.assertIsNone(a.view())
                if scenario == "legacy":
                    self.assertFalse(a.ns.Duo.GetContext(a.ns.Duo).partnerAutoCompatible)
                    self.assertFalse(a.ns.char.auto)
                    self.assertFalse(a.ns.char.duo.wait)
                self.assertEqual(a.ns.char.activeGuide, "auto-review/uno-solo")
                self.assertEqual(b.ns.char.activeGuide, "auto-review/dos-solo")

    def test_unknown_quest_apis_do_not_automatically_choose_a_route(self):
        a = AutomaticPartyHost(active_guide="auto-review/uno-solo")
        b = AutomaticPartyHost("Dos", "Uno", active_guide="auto-review/dos-solo")
        before_a, before_b = a.progress(), b.progress()
        for h in (a, b):
            h.h.lua.execute('''
                C_QuestLog.IsOnQuest=function() return nil end
                C_QuestLog.IsQuestFlaggedCompleted=function() return nil end
                IsQuestFlaggedCompleted=nil
            ''')
        self.form(a, b)
        self.assertIsNone(a.view())
        self.assertIsNone(b.view())
        self.assertEqual(a.ns.char.activeGuide, "auto-review/uno-solo")
        self.assertEqual(b.ns.char.activeGuide, "auto-review/dos-solo")
        self.assertEqual(a.progress(), before_a)
        self.assertEqual(b.progress(), before_b)

    def test_changing_partner_does_not_adopt_old_peer_view_or_progress(self):
        a, b = self.pair()
        before = a.progress(False)
        self.form(a, b)
        a.s.friendName = "Tres"
        a.roster()
        self.exchange(a, b, 5)
        self.assertIsNone(a.view())
        c = AutomaticPartyHost("Tres", "Uno")
        before_c = c.progress(False)
        c.roster()
        self.exchange(a, c)
        self.assertTrue(a.status().active)
        self.assertEqual(a.status().partnerName, "tres-forever")
        self.assertEqual(a.progress(False), before)
        self.assertEqual(c.progress(False), before_c)
        self.assertLessEqual(a.s.maxSyncDepth, 2)

    def test_class_and_race_starter_branches_can_complete_without_waiting_on_other_branch(self):
        cases = [("auto-review/warrior", "auto-review/mage", "Human", "Human", "WARRIOR", "MAGE", 1, 2),
                 ("auto-review/human", "auto-review/nightelf", "Human", "NightElf", "WARRIOR", "WARRIOR", 3, 4)]
        for guide_a, guide_b, race_a, race_b, class_a, class_b, offset_a, offset_b in cases:
            with self.subTest(guide_a=guide_a):
                a = AutomaticPartyHost(active_guide=guide_a, race=race_a, cls=class_a, review=False, auto=True)
                b = AutomaticPartyHost("Dos", "Uno", active_guide=guide_b, race=race_b, cls=class_b, review=False, auto=True)
                a.quest(QUEST_ID + offset_a, count=3)
                b.quest(QUEST_ID + offset_b, count=3)
                self.form(a, b)
                a.quest(QUEST_ID + offset_a, count=8)
                a.ns.Sync(a.ns)
                self.assertEqual(a.ns.char.progress[guide_a].cursor, 3)
                self.assertFalse(a.ns.char.progress[guide_a].skipped["2:1"])
                self.assertEqual(b.ns.char.progress[guide_b].cursor, 2)

    def test_unknown_remote_helper_target_never_falls_back_to_own_future_pin(self):
        a, b = AutomaticPartyHost(cursor=3), AutomaticPartyHost("Dos", "Uno", cursor=2)
        self.form(a, b)
        self.assertTrue(a.view().following)
        future = a.ns.guides[ROUTE_ID].steps[3]
        future.waypoint = a.h.table({"mapID": 1429, "x": .4, "y": .6})
        b.h.lua.execute('''
            C_QuestLog.IsOnQuest=function() return nil end
            C_QuestLog.IsQuestFlaggedCompleted=function() return nil end
            IsQuestFlaggedCompleted=nil
        ''')
        self.exchange(a, b, 12)
        self.assertTrue(a.view().following)
        self.assertIsNone(a.ns.GetStepWaypoint(a.ns, future))
        a.ns.UpdateNavigation(a.ns)
        self.assertFalse(a.ns.navigationFrame.arrow.shown)
        calls = a.s.waypointCalls
        self.assertFalse(a.ns.Navigate(a.ns))
        self.assertEqual(a.s.waypointCalls, calls)
        self.assertEqual(a.ns.char.progress[ROUTE_ID].cursor, 3)

    def test_completed_shared_guide_explains_its_state_before_and_after_rejoining(self):
        a, b = self.pair()
        self.form(a, b)
        for h in (a, b):
            h.quest(count=8, delivered=True)
        for _ in range(20):
            a.h.g.EmitAddonEvent("QUEST_TURNED_IN", QUEST_ID)
            b.h.g.EmitAddonEvent("QUEST_TURNED_IN", QUEST_ID)
            self.exchange(a, b, 1)
        for h in (a, b):
            self.assertEqual(h.ns.char.progress[ROUTE_ID].cursor, 4)
            text = h.status().text.lower()
            self.assertTrue(any(word in text for word in ("complet", "termin", "siguiente", "final", "otra ruta")), text)
        a.roster(0); b.roster(0)
        self.exchange(a, b, 2)
        self.form(a, b)
        for h in (a, b):
            self.assertEqual(h.ns.char.progress[ROUTE_ID].cursor, 4)
            self.assertTrue(h.status().text)
            self.assertLessEqual(h.s.maxSyncDepth, 2)


if __name__ == "__main__":
    unittest.main()
