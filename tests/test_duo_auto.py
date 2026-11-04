"""Automatic pairing negotiates a shared view without copying saved progress."""
import unittest

import test_duo_enhanced as enhanced
from test_quest_engine import ADDON


PLAN_STUB = r'''
function InstallAutomaticPlanner(ns)
    local function plan()
        if TEST.noPlan then return nil,'Faltan datos comprobados' end
        local ctx=ns.Duo:GetContext()
        local mine=ns.char.progress['auto/shared'].cursor
        local other=ctx.cursor
        if ctx.guideID~='auto/shared' then other=TEST.otherCursor or 1 end
        if not other then return nil,'Esperando perfil' end
        local reference
        if mine<other then reference=ctx.ownName
        elseif other<mine then reference=ctx.partnerName
        else reference=ctx.ownName<ctx.partnerName and ctx.ownName or ctx.partnerName end
        return {guideID='auto/shared',verified=true,ownCursor=mine,partnerCursor=other,
            ownCursorObserved=true,referenceName=reference,referenceCursor=math.min(mine,other),sharedCursor=math.min(mine,other)}
    end
    ns.DuoPlanner={
        GetAutomaticPlan=function() return plan() end,
        ValidateAutomaticGuide=function(_,id)
            local p,reason=plan()
            return p~=nil and id=='auto/shared',reason,p
        end,
        GetSharedStepStatus=function() return {known=true,individualOnly=TEST.individual==true} end,
        GetSharedWaypoint=function(_,id,cursor) return {mapID=1429,x=.3,y=.4,label='Shared NPC'} end,
    }
end
'''


class AutoHost(enhanced.EnhancedHost):
    def __init__(self, player="Uno", friend="Dos", cursor=1, review=False):
        super().__init__(player, friend)
        self.state.members = 0
        self.ns.char.duo.enabled, self.ns.char.duo.wait, self.ns.char.auto = False, False, False
        self.guide("auto/shared", steps=[{"title": "Step " + str(i), "goals": [{"t": "note", "text": "Manual " + str(i)}]}
                                        for i in range(1, 7)])
        progress = self.call("GetProgress", "auto/shared")
        progress.cursor, progress.review = cursor, review
        progress.confirmed["saved-mark"] = True
        progress.skipped = self.table({"saved-skip": True})
        self.ns.char.activeGuide = "auto/shared"
        self.lua.execute(PLAN_STUB)
        self.globals.InstallAutomaticPlanner(self.ns)
        self.load((ADDON / "DuoAuto.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        self.auto = self.ns.DuoAuto
        self.acall("Initialize")

    def acall(self, name, *args):
        return self.auto[name](self.auto, *args)

    def tick(self, seconds=1):
        self.state.now += seconds
        self.acall("Tick", seconds)
        self.dcall("Tick", seconds)


class AutomaticDuoTests(unittest.TestCase):
    def pair(self, a_cursor=5, b_cursor=2, review=False):
        a, b = AutoHost(cursor=a_cursor, review=review), AutoHost("Dos", "Uno", cursor=b_cursor)
        a.state.members, b.state.members = 2, 2
        return a, b

    def exchange(self, a, b, ticks=25):
        for _ in range(ticks):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)

    def test_group_bootstrap_enables_all_after_capability_and_negotiates_the_lagger(self):
        a, b = self.pair()
        self.exchange(a, b)
        for h in (a, b):
            self.assertTrue(h.ns.char.duo.enabled)
            self.assertTrue(h.ns.char.duo.wait)
            self.assertTrue(h.ns.char.auto)
            self.assertTrue(h.acall("GetStatus").active)
            self.assertEqual(h.acall("GetStatus").coordinator, "dos-forever")
            self.assertEqual(h.acall("GetSharedView").sharedCursor, 2)
            self.assertTrue(h.call("GetProgress", "auto/shared").confirmed["saved-mark"])
            self.assertTrue(h.call("GetProgress", "auto/shared").skipped["saved-skip"])
        self.assertEqual(a.call("GetProgress", "auto/shared").cursor, 5)
        self.assertEqual(b.call("GetProgress", "auto/shared").cursor, 2)
        self.assertTrue(a.acall("GetSharedView").following)
        self.assertFalse(b.acall("GetSharedView").following)
        self.assertTrue(a.acall("ShouldWaitForStep")[0])
        self.assertFalse(b.acall("ShouldWaitForStep"))
        self.assertEqual(a.acall("GetNavigationOverride").source, "duo-follow")

    def test_initial_manual_disabled_migrates_but_explicit_auto_opt_out_does_not_loop(self):
        a = AutoHost()
        self.assertTrue(a.ns.char.duo.autoPair)
        a.acall("SetEnabled", False)
        a.state.members = 2
        for _ in range(20):
            a.tick()
        self.assertFalse(a.ns.char.duo.autoPair)
        self.assertFalse(a.ns.char.duo.enabled)
        self.assertFalse(a.ns.char.duo.wait)
        self.assertFalse(a.ns.char.auto)
        self.assertIsNone(a.ns.char.duo.autoSession)

    def test_leaving_restores_previous_flags_and_does_not_rewind_progress(self):
        a, b = self.pair()
        a.ns.char.duo.wait = True
        self.exchange(a, b)
        a.state.members = 0
        a.tick()
        self.assertFalse(a.ns.char.duo.enabled)
        self.assertTrue(a.ns.char.duo.wait)
        self.assertFalse(a.ns.char.auto)
        self.assertEqual(a.call("GetProgress", "auto/shared").cursor, 5)
        self.assertIsNone(a.acall("GetSharedView"))

    def test_manual_override_preserves_peer_and_operational_flags_for_the_user_action(self):
        a, b = self.pair()
        self.exchange(a, b)
        a.acall("UseManualMode", "Continuar sin esperar")
        self.assertFalse(a.ns.char.duo.autoPair)
        self.assertTrue(a.dcall("GetContext").known)
        self.assertTrue(a.ns.char.duo.enabled)
        self.assertTrue(a.ns.char.auto)
        a.dcall("SetWait", False)
        self.exchange(a, b, 5)
        self.assertFalse(a.ns.char.duo.wait)
        self.assertIsNone(a.acall("GetSharedView"))

    def test_previous_review_is_suspended_at_commit_and_restored_only_if_cursor_unchanged(self):
        a, b = self.pair(review=True)
        self.exchange(a, b)
        state = a.call("GetProgress", "auto/shared")
        self.assertFalse(bool(state.review))
        self.assertEqual(state.cursor, 5)
        self.assertTrue(a.acall("GetSharedView").following)
        a.acall("SetEnabled", False)
        self.assertTrue(state.review)
        a.acall("SetEnabled", True)
        self.exchange(a, b, 25)
        self.assertFalse(bool(state.review))
        state.cursor = 6
        a.acall("SetEnabled", False)
        self.assertFalse(bool(state.review))

    def test_reload_preserves_the_original_preferences_in_the_lease(self):
        a, b = self.pair(review=True)
        self.exchange(a, b)
        self.assertTrue(a.ns.char.auto)
        a.load((ADDON / "DuoAuto.lua").read_text(encoding="utf-8-sig"), "RutaXP", a.ns)
        a.auto = a.ns.DuoAuto
        a.acall("Initialize")
        a.state.members = 0
        a.tick()
        self.assertFalse(a.ns.char.auto)
        self.assertFalse(a.ns.char.duo.enabled)
        self.assertFalse(a.ns.char.duo.wait)
        self.assertTrue(a.call("GetProgress", "auto/shared").review)

    def test_legacy_peer_does_not_enable_wait_or_auto(self):
        a = AutoHost()
        legacy = enhanced.EnhancedHost("Dos", "Uno")
        a.state.members = 2
        self.exchange(a, legacy, 20)
        self.assertTrue(a.ns.char.duo.enabled)  # Discovery only.
        self.assertTrue(a.dcall("GetContext").known)
        self.assertFalse(a.dcall("GetContext").partnerAutoCompatible)
        self.assertFalse(a.ns.char.duo.wait)
        self.assertFalse(a.ns.char.auto)
        self.assertIsNone(a.acall("GetSharedView"))

    def test_invalid_party_faction_and_unreadable_faction_never_bootstrap(self):
        for field, value in [("members", 3), ("raid", True), ("friendFaction", "Horde")]:
            with self.subTest(field=field):
                h = AutoHost()
                h.state.members = 2
                setattr(h.state, field, value)
                h.tick()
                self.assertFalse(h.ns.char.duo.enabled)
        h = AutoHost()
        h.state.members = 2
        h.lua.execute('UnitFactionGroup=function() return nil end')
        h.tick()
        self.assertFalse(h.ns.char.duo.enabled)

    def test_unknown_common_route_does_not_copy_the_peer_guide_or_cursor(self):
        a, b = self.pair()
        a.state.noPlan, b.state.noPlan = True, True
        self.exchange(a, b)
        self.assertIsNone(a.acall("GetSharedView"))
        self.assertEqual(a.call("GetProgress", "auto/shared").cursor, 5)
        self.assertEqual(b.call("GetProgress", "auto/shared").cursor, 2)
        self.assertFalse(a.acall("ShouldPauseAutomation"))
        self.assertFalse(a.dcall("ShouldWaitForStep", a.call("GetCurrent")[1]))

    def test_class_or_race_individual_branch_is_not_held_by_a_missing_joint_plan(self):
        a, b = self.pair()
        a.state.noPlan, b.state.noPlan = True, True
        a.state.individual = True
        self.exchange(a, b)
        self.assertFalse(a.acall("ShouldWaitForStep"))
        self.assertFalse(a.acall("ShouldPauseAutomation"))

    def test_replayed_or_wrong_sender_proposals_cannot_change_progress(self):
        a, b = self.pair()
        self.exchange(a, b)
        cursor = a.call("GetProgress", "auto/shared").cursor
        packet = "2|A|" + str(a.duo.peer.nonce) + "|999|other|auto/shared|0|2|1"
        self.assertFalse(a.dcall("Receive", a.duo.prefix, packet, "PARTY", "Extra-Forever"))
        self.assertFalse(a.dcall("Receive", a.duo.prefix, packet, "PARTY", "Dos-Forever"))
        self.assertEqual(a.call("GetProgress", "auto/shared").cursor, cursor)

    def test_negotiation_retries_remain_bounded_and_party_only(self):
        a, b = self.pair()
        count = 0
        for _ in range(30):
            a.tick(); b.tick()
            for h in (a, b):
                self.assertLessEqual(len(h.state.outgoing), 1)
                for packet in h.state.outgoing.values():
                    self.assertEqual(packet.channel, "PARTY")
                    self.assertLessEqual(len(packet.message.encode("utf-8")), 255)
                    count += "|A|" in packet.message or "|P|" in packet.message
            a.deliver_to(b); b.deliver_to(a)
        self.assertLess(count, 15)
        self.assertTrue(a.acall("GetStatus").active)

    def test_auto_handshake_does_not_starve_twenty_four_quest_snapshots(self):
        a, b = self.pair()
        quest_ids = [100] + list(range(1000, 1023))
        for h in (a, b):
            h.dcall("SetMeetingPoint")
            h.dcall("RegisterCheckpointProvider", h.lua.eval('function() return {checkpointID="1",stopKind="repair",stopReady=true} end'))
            for step in h.ns.guides["auto/shared"].steps.values():
                step.goals = h.table([{"t": "complete", "quest": q, "oi": 1} for q in quest_ids])
            for q in quest_ids:
                h.quest(q, onQuest=True, objectives=[{"finished": False, "numFulfilled": 3, "numRequired": 9}])
        for tick in range(100):
            for h in (a, b):
                for q in quest_ids[1:]:
                    h.dcall("RequestQuest", q)
                h.tick()
                self.assertLessEqual(len(h.state.outgoing), 1)
                for packet in h.state.outgoing.values():
                    self.assertLessEqual(len(packet.message.encode("utf-8")), 255)
            a.deliver_to(b); b.deliver_to(a)
            if tick >= 39:
                for h in (a, b):
                    self.assertTrue(h.acall("GetStatus").active)
                    for q in quest_ids:
                        snapshot = h.dcall("GetPartnerQuest", q)
                        self.assertIsNotNone(snapshot)
                        self.assertLessEqual(h.state.now - snapshot.seen, 35)


if __name__ == "__main__":
    unittest.main()
