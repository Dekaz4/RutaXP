"""A dwarf hunter and paladin keep their own class visits on the real route."""
import unittest

from test_access_navigation import DWARF, WORLD_STUBS
from test_auto_party_integration import AutomaticPartyHost


class HunterClassVisitTests(unittest.TestCase):
    @staticmethod
    def exchange(a, b, ticks):
        for _ in range(ticks):
            a.tick(); b.tick()
            a.deliver(b); b.deliver(a)

    def pair(self, automatic_pair):
        def player(name, friend, cls, other_class):
            saved = {"seen": True, "activeGuide": DWARF, "auto": False,
                     "progress": {DWARF: {"cursor": 6, "placed": True}},
                     "duo": {"enabled": True, "wait": False, "autoPair": automatic_pair}}
            h = AutomaticPartyHost(name, friend, active_guide=DWARF, race="Dwarf", cls=cls, saved=saved)
            h.s.friendClass = other_class
            h.s.level = h.s.friendLevel = 12
            h.s.quests[900100] = None
            h.s.mapID, h.s.zone = 1426, "Dun Morogh"
            h.h.g.ACCESS_NS = h.ns
            h.h.lua.execute(WORLD_STUBS)
            h.quest(233, count=1)
            return h
        a = player("Uno", "Dos", "HUNTER", "PALADIN")
        b = player("Dos", "Uno", "PALADIN", "HUNTER")
        a.roster(); b.roster()
        self.exchange(a, b, 45)
        return a, b

    def test_automatic_pair_shows_own_class_turnin_then_follows_from_train_step(self):
        hunter, paladin = self.pair(True)
        hunter.ns.char.progress[DWARF].cursor = 72
        paladin.ns.char.progress[DWARF].cursor = 70
        hunter.s.mapID, hunter.s.x, hunter.s.y, hunter.s.height = 1455, .60, .83, 500
        hunter.quest(6086, count=8)
        hunter.s.quests[6086].title = "Entrenar a la bestia"
        paladin.quest(1783, count=0)
        self.exchange(hunter, paladin, 18)

        self.assertTrue(hunter.status().active)
        self.assertFalse(hunter.view().following)
        guide, step, state = hunter.ns.GetDisplayedCurrent(hunter.ns)
        self.assertEqual((state.cursor, step.title), (72, "Clase Forjaz misiones"))
        self.assertEqual(hunter.ns.GetStepWaypoint(hunter.ns, step).goal.quest, 6086)
        self.assertIn("Entrenar a la bestia", hunter.ns.trackerRows[1].title.text)
        self.assertFalse(hunter.ns.DuoAuto.ShouldPauseAutomation(hunter.ns.DuoAuto))
        self.assertFalse(hunter.ns.IsStepComplete(hunter.ns, step, state))

        hunter.quest(6086, delivered=True)
        hunter.h.g.EmitAddonEvent("QUEST_TURNED_IN", 6086)
        self.exchange(hunter, paladin, 15)
        own_guide, own_step, own_state = hunter.ns.GetCurrent(hunter.ns)
        self.assertEqual((own_guide.id, own_state.cursor, own_step.title), (guide.id, 73, "El Tren subterráneo"))
        self.assertTrue(hunter.view().following)
        self.assertEqual(hunter.view().sharedCursor, 70)
        self.assertEqual(hunter.ns.trackerStep.text, "Tu amigo · " + guide.steps[70].title)
        self.assertEqual(hunter.ns.trackerProgress.text, "Amigo 70 · Tú 73")
        self.assertTrue(hunter.ns.DuoAuto.ShouldPauseAutomation(hunter.ns.DuoAuto)[0])

    def test_manual_pair_shows_taming_pickup_and_switches_to_taming_after_acceptance(self):
        hunter, paladin = self.pair(False)
        state = hunter.ns.char.progress[DWARF]
        state.cursor = 53
        # The hearth and trainer errands preceding Grif in this visit are done.
        state.confirmed["53:1"] = state.confirmed["53:2"] = True
        hunter.ns.char.auto = True
        paladin.ns.char.progress[DWARF].cursor = 70
        paladin.quest(1783, count=0)
        self.exchange(hunter, paladin, 15)
        def active():
            _, step, progress = hunter.ns.GetDisplayedCurrent(hunter.ns)
            goal = hunter.ns.GetActiveGoal(hunter.ns, step, progress)[0]
            return progress.cursor, goal.t, goal.quest
        self.assertEqual(active(), (53, "accept", 6064))
        self.assertIsNone(hunter.view())
        hunter.quest(6064, count=0)
        hunter.h.g.EmitAddonEvent("QUEST_ACCEPTED", 6064)
        self.assertEqual(active(), (54, "kill", 6064))
        self.assertEqual(paladin.ns.char.progress[DWARF].cursor, 70)


if __name__ == "__main__":
    unittest.main()
