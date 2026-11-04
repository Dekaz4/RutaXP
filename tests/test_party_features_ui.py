"""Shipping UI, real modules and two isolated Lua clients for party controls."""
import unittest

import test_talent_trainer_regressions as full
import test_duo as duo_tests


class PartyUIHost:
    def __init__(self, name="Uno", friend="Dos"):
        self.host = full.TalentTrainerHost(full_toc=True)
        self.h = self.host
        self.h.lua.execute(duo_tests.DUO_STUBS)
        self.s, self.ns = self.h.state, self.h.ns
        self.s.playerName, self.s.friendName = name, friend
        self.s.level, self.s.friendLevel = 10, 10
        self.s.classToken = self.s.friendClass = "WARRIOR"
        self.s.raceToken = self.s.friendRace = "Human"
        self.s.faction, self.s.friendFaction = "Alliance", "Alliance"
        self.ns.RegisterGuide(self.ns, self.h.table({
            "id": "party-route", "title": "Ruta compartida", "faction": "Alliance",
            "minLevel": 10, "maxLevel": 20, "zone": 37,
            "steps": [
                {"title": "Recoger", "goals": [{"t": "accept", "quest": 100, "npc": 123, "map": 37, "x": 42, "y": 63}]},
                {"title": "Objetivo juntos", "goals": [{"t": "complete", "quest": 100, "oi": 1, "map": 37, "x": 43, "y": 64}]},
                {"title": "Entregar", "goals": [{"t": "turnin", "quest": 100, "npc": 123, "map": 37, "x": 42, "y": 63}]},
            ],
        }))
        self.h.g.RutaXPCharDB = self.h.table({"seen": True, "activeGuide": "party-route", "progress": {
            "party-route": {"cursor": 2, "confirmed": {"user-mark": True}, "review": True, "placed": True},
        }})
        self.quest(5)
        self.h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        self.h.g.EmitAddonEvent("PLAYER_LOGIN")
        self.ns.Duo.SetEnabled(self.ns.Duo, True)

    def quest(self, count):
        self.s.quests[100] = self.h.table({"title": "Objetos individuales", "onQuest": True, "complete": False,
            "objectives": [{"text": f"Objetos: {count}/8", "type": "item", "numFulfilled": count,
                            "numRequired": 8, "finished": count == 8}]})

    def tick(self):
        self.s.now += 1
        self.ns.featureDriver.scripts.OnUpdate(self.ns.featureDriver, 1)

    def deliver(self, other):
        for packet in self.s.outgoing.values():
            other.h.g.EmitAddonEvent("CHAT_MSG_ADDON", packet.prefix, packet.message, packet.channel,
                                   self.s.playerName + "-Forever")
        self.s.outgoing = self.h.lua.table()

    def panel(self, name):
        self.ns.ToggleFeatures(self.ns, name)
        return self.ns.featuresPanel

    def click_text(self, text):
        for button in self.ns.featuresPanel.actions.values():
            if button.shown and button.text == text:
                self.h.g.Click(button)
                return
        raise AssertionError(f"Missing action: {text}")


class PartyFeatureUITests(unittest.TestCase):
    def pair(self):
        a, b = PartyUIHost(), PartyUIHost("Dos", "Uno")
        b.quest(3)
        for _ in range(30):
            a.tick(); b.tick(); a.deliver(b); b.deliver(a)
        return a, b

    def test_all_six_party_pages_and_commands_have_real_content(self):
        a = PartyUIHost()
        before = a.ns.char.activeGuide
        for tab in ["duo", "duo-route", "duo-differences", "duo-meeting", "duo-checkpoint", "duo-stops"]:
            f = a.panel(tab)
            self.assertTrue(f.body.text, tab)
            self.assertEqual(f.scroll.height, 302)
            self.assertTrue(all(b.shown for b in f.duoTabs.values()))
        for command in ["comun", "diferencias", "reunion", "partida", "paradas"]:
            a.ns.Command(a.ns, command)
        self.assertEqual(a.ns.char.activeGuide, before)
        a.panel("session")
        self.assertEqual(a.ns.featuresPanel.scroll.height, 334)
        self.assertTrue(all(not b.shown for b in a.ns.featuresPanel.duoTabs.values()))

    def test_live_partner_counter_is_in_original_goal_row_and_does_not_duplicate(self):
        a, b = self.pair()
        a.ns.RefreshUI(a.ns)
        self.assertIn("Amigo: 3/8", a.ns.trackerRows[1].sub.text)
        original = a.ns.trackerRows[1].sub.text
        height = a.ns.tracker.height
        for _ in range(3):
            a.ns.RefreshUI(a.ns)
            self.assertEqual(a.ns.trackerRows[1].sub.text, original)
            self.assertEqual(a.ns.tracker.height, height)
        self.assertEqual(a.ns.char.progress["party-route"].cursor, 2)
        self.assertTrue(a.ns.char.progress["party-route"].confirmed["user-mark"])

    def test_meeting_is_shared_but_following_is_an_explicit_local_action(self):
        a, b = self.pair()
        a.panel("duo-meeting")
        a.click_text("Reunirnos en mi posición")
        for _ in range(15):
            a.tick(); b.tick(); a.deliver(b); b.deliver(a)
        b.panel("duo-meeting")
        self.assertIsNone(b.ns.Duo.GetMeetingWaypoint(b.ns.Duo))
        b.click_text("Seguir punto de reunión")
        point = b.ns.Duo.GetMeetingWaypoint(b.ns.Duo)
        self.assertIsNotNone(point)
        self.assertEqual(point.source, "duo-meeting")
        b.click_text("Volver al objetivo de la guía")
        self.assertIsNone(b.ns.Duo.GetMeetingWaypoint(b.ns.Duo))
        self.assertEqual(b.ns.char.progress["party-route"].cursor, 2)

    def test_checkpoint_buttons_preserve_existing_marks_and_forward_progress(self):
        a, b = self.pair()
        a.panel("duo-checkpoint")
        a.click_text("Guardar partida juntos")
        a.ns.char.progress["party-route"].cursor = 3
        a.ns.char.progress["party-route"].review = True
        a.click_text("Retomar mi ruta guardada")
        self.assertEqual(a.ns.char.progress["party-route"].cursor, 3)
        self.assertTrue(a.ns.char.progress["party-route"].confirmed["user-mark"])
        a.click_text("Copiar resumen de partida")
        self.assertTrue(a.ns.featureExport.shown)
        self.assertTrue(a.ns.featureExport.edit.text)

    def test_separation_alert_is_visible_locally_and_does_not_repeat_each_tick(self):
        a = PartyUIHost()
        a.h.lua.execute("function UnitInRange() return false, true end")
        before = len(a.s.messages)
        for _ in range(8):
            a.tick()
        alerts = [a.s.messages[i] for i in range(before + 1, len(a.s.messages) + 1)
                  if "alcance" in a.s.messages[i]]
        self.assertEqual(len(alerts), 1)
        self.assertIn("fuera de alcance", a.ns.duoTracker.text)

    def test_active_stop_keeps_other_proposal_descriptions_visible(self):
        a, b = self.pair()
        a.h.lua.execute('''
            C_Container = {
                GetContainerNumFreeSlots=function() return 0,0 end,
                GetContainerNumSlots=function(bag) return bag==0 and 16 or 0 end,
            }
            function GetInventoryItemDurability(slot)
                if slot==1 then return 10,100 end
            end
        ''')
        a.panel("duo-stops")
        a.click_text("Proponer parada 1")
        self.assertIn("Propuestas disponibles", a.ns.featuresPanel.body.text)
        self.assertIn("Reparar equipo", a.ns.featuresPanel.body.text)
        a.click_text("Proponer parada 2")
        self.assertEqual(a.ns.DuoJourney.GetStopStatus(a.ns.DuoJourney).kind, "repair")


if __name__ == "__main__":
    unittest.main()
