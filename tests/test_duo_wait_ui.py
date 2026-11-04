"""Explain a completed local visit and expose resync without skipping progress."""
import unittest

from test_access_navigation import AccessHost, DWARF


class DuoWaitUITests(unittest.TestCase):
    def visit(self):
        h = AccessHost(DWARF, step=6, x=.26, y=.71)
        h.s.friendRace, h.s.friendClass, h.s.members = "Dwarf", "WARRIOR", 2
        h.s.quests[233] = h.h.table({"delivered": True})
        h.s.quests[183] = h.h.table({"onQuest": True})
        h.s.quests[234] = h.h.table({"onQuest": True})
        h.ns.char.duo.wait = True
        h.ns.Duo.SetEnabled(h.ns.Duo, True)
        h.h.lua.execute('''
            GameTooltip={lines={}}
            function GameTooltip:SetOwner(owner) self.owner=owner;self.lines={} end
            function GameTooltip:AddLine(text) self.lines[#self.lines+1]=text end
            function GameTooltip:Show() self.shown=true end
            function GameTooltip:Hide() self.shown=false end
        ''')
        return h

    def test_no_peer_data_is_explained_without_claiming_an_unfinished_quest(self):
        h = self.visit()
        before = h.progress()
        h.ns.UpdateDuoTracker(h.ns)
        b = h.ns.duoTracker
        self.assertIn("sin datos del compañero", b.text)
        self.assertTrue(b.waitReason)
        b.scripts.OnEnter(b)
        self.assertIn(b.waitReason, list(h.h.g.GameTooltip.lines.values()))
        self.assertTrue(h.h.g.GameTooltip.shown)
        b.scripts.OnLeave(b)
        self.assertFalse(h.h.g.GameTooltip.shown)
        self.assertEqual(h.progress(), before)

    def test_confirmed_missing_acceptance_names_the_actual_quest_in_the_tooltip(self):
        h = self.visit()
        receive = h.ns.Duo.Receive
        self.assertTrue(receive(h.ns.Duo, h.ns.Duo.prefix,
            "2|H|friend|1|10|WARRIOR|Dwarf|" + DWARF + "|6|0|Alliance", "PARTY", "Dos-Forever"))
        self.assertTrue(receive(h.ns.Duo, h.ns.Duo.prefix,
            "2|B|friend|2|233,3,0,0,0,0,/183,1,0,0,0,0,/234,0,0,0,0,0,", "PARTY", "Dos-Forever"))
        h.ns.UpdateDuoTracker(h.ns)
        self.assertIn("falta aceptar", h.ns.duoTracker.text)
        self.assertIn(h.ns.GetQuestTitle(h.ns, 234), h.ns.duoTracker.waitReason)

    def test_resync_command_and_panel_button_preserve_cursor_marks_and_mode(self):
        h = self.visit()
        before, active = h.progress(), h.ns.char.activeGuide
        h.ns.Command(h.ns, "sincronizar")
        self.assertTrue(h.ns.featuresPanel.shown)
        buttons = [b for b in h.ns.featuresPanel.actions.values() if b.shown and b.text == "Sincronizar de nuevo"]
        self.assertEqual(len(buttons), 1)
        h.h.g.Click(buttons[0])
        self.assertEqual(h.progress(), before)
        self.assertEqual(h.ns.char.activeGuide, active)
        self.assertFalse(h.ns.char.auto)
        self.assertFalse(h.ns.char.duo.autoPair)
        self.assertTrue(h.ns.char.duo.wait)
        self.assertTrue(h.ns.char.duo.enabled)

    def test_live_peer_with_an_unknown_quest_is_syncing_not_missing_acceptance(self):
        h = self.visit()
        receive = h.ns.Duo.Receive
        self.assertTrue(receive(h.ns.Duo, h.ns.Duo.prefix,
            "2|H|friend|1|10|WARRIOR|Dwarf|" + DWARF + "|6|0|Alliance", "PARTY", "Dos-Forever"))
        self.assertTrue(receive(h.ns.Duo, h.ns.Duo.prefix,
            "2|B|friend|2|233,3,0,0,0,0,/183,1,0,0,0,0,", "PARTY", "Dos-Forever"))
        h.ns.UpdateDuoTracker(h.ns)
        self.assertIn("sincronizando misiones", h.ns.duoTracker.text)
        self.assertNotIn("falta aceptar", h.ns.duoTracker.text)
        self.assertIn(h.ns.GetQuestTitle(h.ns, 234), h.ns.duoTracker.waitReason)


if __name__ == "__main__":
    unittest.main()
