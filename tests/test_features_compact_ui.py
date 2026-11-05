"""The first party screen presents a status, with advanced tools behind a click."""
import unittest

from test_duo_journey import primitive_copy
from test_party_features_ui import PartyUIHost
from test_tracker_resize import GEOMETRY_STUBS


class CompactFeaturesUITests(unittest.TestCase):
    def visible_actions(self, host):
        return [b for b in host.ns.featuresPanel.actions.values() if b.shown]

    def test_default_duo_has_one_main_control_and_no_exploratory_quest_report(self):
        h = PartyUIHost()
        h.h.lua.execute("""
            function RutaXPCompactNoReport() error('Expanded report read on summary screen') end
        """)
        h.ns.Duo.GetReport = h.h.g.RutaXPCompactNoReport
        before = primitive_copy(h.ns.char)
        f = h.panel("duo")
        self.assertFalse(f.expanded)
        self.assertEqual((f.width, f.height), (540, 336))
        self.assertFalse(f.footer.shown)
        self.assertEqual(f.footer.text, "")
        self.assertTrue(all(not b.shown for b in f.tabs.values()))
        self.assertTrue(all(not b.shown for b in f.duoTabs.values()))
        self.assertIn("Compañero: dos-forever", f.body.text)
        self.assertIn("Esperando", f.body.text)
        self.assertNotIn("Objetos individuales", f.body.text)
        self.assertNotIn("Razas distintas", f.body.text)
        self.assertEqual(self.visible_actions(h)[0].text, "Automático al agruparse: sí")
        self.assertLessEqual(len(self.visible_actions(h)), 2)
        self.assertEqual(primitive_copy(h.ns.char), before)
        self.assertIn("detalles", f.detailsButton.text)

    def test_connected_summary_shows_only_partner_and_route_without_six_manual_actions(self):
        h = PartyUIHost()
        header = "2|H|peer|1|10|WARRIOR|Human|party-route|2|0|Alliance"
        self.assertTrue(h.ns.Duo.Receive(h.ns.Duo, h.ns.Duo.prefix, header, "PARTY", "Dos-Forever"))
        f = h.panel("duo")
        self.assertIn("Conectados.", f.body.text)
        self.assertIn("Su guía: Ruta compartida · paso 2", f.body.text)
        self.assertEqual(len(self.visible_actions(h)), 1)
        self.assertNotIn("tú:", f.body.text)

    def test_real_chat_restriction_is_not_displayed_as_waiting_for_a_reply(self):
        h = PartyUIHost()
        h.s.restricted = True
        f = h.panel("duo")
        self.assertIn("restringe", f.body.text)
        self.assertNotIn("Esperando respuesta", f.body.text)
        self.assertNotIn("Conectados.", f.body.text)
        self.assertNotIn("WoW acepta", f.body.text)
        self.assertNotIn("Sincronizar de nuevo", {b.text for b in self.visible_actions(h)})
        self.assertEqual(len(self.visible_actions(h)), 1)
        h.s.restricted = False
        h.ns.UpdateFeatures(h.ns)
        self.assertIn("Sincronizar de nuevo", {b.text for b in self.visible_actions(h)})
        h.s.restricted = True
        self.assertTrue(h.ns.Duo.Receive(h.ns.Duo, h.ns.Duo.prefix,
            "2|H|peer|1|10|WARRIOR|Human|party-route|2|0|Alliance", "PARTY", "Dos-Forever"))
        h.ns.UpdateFeatures(h.ns)
        self.assertIn("restringe", f.body.text)
        self.assertNotIn("Conectados.", f.body.text)
        self.assertNotIn("Sincronizar de nuevo", {b.text for b in self.visible_actions(h)})
        h.h.g.Click(f.detailsButton)
        self.assertIn("Sincronizar de nuevo", {b.text for b in self.visible_actions(h)})

    def test_optional_details_keep_manual_controls_and_return_without_progress_mutation(self):
        h = PartyUIHost()
        f = h.panel("duo")
        before = primitive_copy(h.ns.char)
        h.h.g.Click(f.detailsButton)
        self.assertTrue(f.expanded)
        self.assertEqual((f.width, f.height), (720, 550))
        self.assertTrue(f.footer.shown)
        self.assertTrue(all(b.shown for b in f.tabs.values()))
        self.assertTrue(all(b.shown for b in f.duoTabs.values()))
        controls = {b.text for b in self.visible_actions(h)}
        self.assertEqual(len(controls), 6)
        self.assertIn("Desactivar dúo", controls)
        self.assertIn("Esperar al amigo", controls)
        self.assertIn("Sincronizar de nuevo", controls)
        self.assertIn("Razas distintas", f.body.text)
        h.h.g.Click(f.detailsButton)
        self.assertFalse(f.expanded)
        self.assertTrue(all(not b.shown for b in f.tabs.values()))
        self.assertTrue(all(not b.shown for b in f.duoTabs.values()))
        self.assertEqual(primitive_copy(h.ns.char), before)

    def test_direct_commands_reveal_the_requested_tool_but_duo_reopens_its_summary(self):
        h = PartyUIHost()
        for command, tab in (("comun", "duo-route"), ("diferencias", "duo-differences"),
                             ("reunion", "duo-meeting"), ("partida", "duo-checkpoint"),
                             ("paradas", "duo-stops"), ("sesion", "session"),
                             ("recuperar", "recovery"), ("adaptar", "adaptation"), ("puntos", "waypoints")):
            with self.subTest(command=command):
                h.ns.Command(h.ns, command)
                self.assertEqual(h.ns.featureTab, tab)
                self.assertTrue(h.ns.featuresPanel.expanded)
                self.assertTrue(h.ns.featuresPanel.body.text)
        f = h.panel("duo")
        self.assertFalse(f.expanded)
        h.h.g.Click(f.detailsButton)
        self.assertTrue(f.expanded)
        h.ns.ToggleFeatures(h.ns)
        self.assertFalse(f.shown)
        h.ns.ToggleFeatures(h.ns)
        self.assertFalse(f.expanded)
        self.assertEqual(h.ns.featureTab, "duo")

    def test_periodic_refresh_preserves_details_and_scroll(self):
        h = PartyUIHost()
        f = h.panel("duo")
        h.h.g.Click(f.detailsButton)
        f.scroll.SetVerticalScroll(f.scroll, 80)
        h.tick()
        self.assertTrue(f.expanded)
        self.assertEqual(f.scroll.scroll, 80)

    def test_main_automatic_button_changes_its_actual_setting_and_keeps_quest_marks(self):
        h = PartyUIHost()
        f = h.panel("duo")
        h.ns.DuoAuto.SetEnabled(h.ns.DuoAuto, False)
        h.ns.UpdateFeatures(h.ns)
        before = primitive_copy(h.ns.char.progress)
        self.assertEqual(self.visible_actions(h)[0].text, "Automático al agruparse: no")
        h.h.g.Click(self.visible_actions(h)[0])
        self.assertTrue(h.ns.char.duo.autoPair)
        self.assertEqual(self.visible_actions(h)[0].text, "Automático al agruparse: sí")
        self.assertEqual(primitive_copy(h.ns.char.progress), before)

    def test_collapsed_and_expanded_buttons_fit_and_do_not_cover_the_scroll_content(self):
        h = PartyUIHost()
        h.h.lua.execute(GEOMETRY_STUBS)
        f = h.panel("duo")
        def rect(frame):
            return tuple(h.h.g.TrackerRect(frame, f))
        def overlaps(a, b):
            return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
        for expanded in (False, True):
            with self.subTest(expanded=expanded):
                if expanded:
                    h.h.g.Click(f.detailsButton)
                controls = [f.closeButton, f.detailsButton] + [b for group in (f.tabs, f.duoTabs, f.actions)
                                                for b in group.values() if b.shown]
                boxes = [rect(b) for b in controls]
                for box in boxes:
                    self.assertGreaterEqual(box[0], 0)
                    self.assertGreaterEqual(box[1], 0)
                    self.assertLessEqual(box[0] + box[2], f.width)
                    self.assertLessEqual(box[1] + box[3], f.height)
                    self.assertFalse(overlaps(box, rect(f.scroll)))
                for index, box in enumerate(boxes):
                    self.assertFalse(any(overlaps(box, other) for other in boxes[index + 1:]))
                if expanded:
                    self.assertEqual({rect(b)[0] for b in f.tabs.values()}, {20})
                    self.assertEqual({rect(b)[0] for b in f.duoTabs.values()}, {20})
                else:
                    self.assertEqual(f.body.width, 458)
                    self.assertLessEqual(f.heading.width + 20, rect(f.closeButton)[0])
                    self.assertFalse(f.footer.shown)


if __name__ == "__main__":
    unittest.main()
