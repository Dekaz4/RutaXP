"""The two real navigation buttons expose the same manual guide handoff."""

import unittest

from test_access_navigation import AccessHost, DWARF


WESTFALL = "forever/alliance/02-westfall"


class GuideContinuationUITests(unittest.TestCase):
    def completed_visit(self):
        h = AccessHost(DWARF, step=6)
        h.s.level = 13
        h.ns.char.progress[DWARF].cursor = len(h.guide.steps) + 1
        return h

    def test_tracker_and_library_continue_from_dun_morogh_to_westfall(self):
        for button_name in ("trackerNext", "nextButton"):
            with self.subTest(button=button_name):
                h = self.completed_visit()
                h.ns.RefreshUI(h.ns)
                button = h.ns[button_name]
                self.assertTrue(button.enabled)
                self.assertEqual(button.label.text, "Continuar")
                title = h.ns.guides[WESTFALL].title
                self.assertIn(title, h.ns.trackerText.text)
                self.assertIn(title, h.ns.stepText.text)
                h.h.g.Click(button)
                self.assertEqual(h.ns.char.activeGuide, WESTFALL)
                self.assertEqual(h.ns.char.progress[DWARF].cursor, len(h.guide.steps) + 1)
                self.assertEqual(button.label.text, "Siguiente >")

    def test_wait_reason_disables_both_buttons_and_keeps_the_final_cursor(self):
        h = self.completed_visit()
        reason = "El compañero sigue en el paso 79 con su paladín."
        h.ns.GetGuideContinuation = h.h.lua.eval('function(reason) return function() return nil, reason, true end end')(reason)
        before = h.progress()
        h.ns.RefreshUI(h.ns)
        for button in (h.ns.nextButton, h.ns.trackerNext):
            self.assertFalse(button.enabled)
            h.h.g.Click(button)
        self.assertEqual(h.ns.stepTitle.text, "Tu parte está hecha")
        self.assertEqual(h.ns.trackerStep.text, "Tu parte está hecha")
        self.assertNotIn("completad", h.ns.stepCount.text.lower())
        self.assertNotIn("completad", h.ns.trackerProgress.text.lower())
        self.assertIn(reason, h.ns.stepText.text)
        self.assertIn(reason, h.ns.trackerText.text)
        self.assertEqual(h.progress(), before)
        self.assertEqual(h.ns.char.activeGuide, DWARF)


if __name__ == "__main__":
    unittest.main()
