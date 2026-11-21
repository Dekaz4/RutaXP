"""Exercise the gnome warlock's opening spell guide through the live panel."""

import unittest

from test_talent_trainer_regressions import TalentTrainerHost


class GnomeWarlockBeginnerPanelTests(unittest.TestCase):
    def open_panel(self, race="Gnome", player_class="WARLOCK", preview=None, level=1):
        host = TalentTrainerHost(full_toc=True)
        host.state.raceToken, host.state.classToken, host.state.level = race, player_class, level
        host.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        host.g.EmitAddonEvent("PLAYER_LOGIN")
        host.t.selectedClass = preview
        host.ns.Command(host.ns, "talentos")
        return host, host.t.panel

    def test_level_one_shows_starting_spells_and_how_to_obtain_the_others(self):
        _, panel = self.open_panel()
        self.assertIn("LIBRO DE HECHIZOS", panel.nextCard.header.text)
        self.assertIn("Piel de demonio", panel.nextCard.main.text)
        rows = {row.tipTitle: row for row in panel.rows.values() if row.shown}
        self.assertIn("[Inicial]", rows["Nivel 1 · Descarga de las Sombras y Piel de demonio"].spec.text)
        self.assertIn("compra", rows["Nivel 1 · Inmolar"].tipBody.lower())
        self.assertIn("[Misión]", rows["Nivel 1 · Invocar a diablillo"].spec.text)
        self.assertIn("[COMPRAR]", rows["Nivel 4 · Corrupción"].spec.text)

    def test_imp_instructions_follow_quest_progress_in_the_open_panel(self):
        host, panel = self.open_panel()
        self.assertIn("Sten", panel.infoCard.text.text)
        host.state.quests[179] = host.table({"delivered": True})
        host.g.EmitAddonEvent("QUEST_TURNED_IN", 179)
        self.assertIn("trogg", panel.infoCard.text.text)
        host.state.quests[1599] = host.table({"onQuest": True})
        host.g.EmitAddonEvent("QUEST_ACCEPTED", 1, 1599)
        self.assertIn("Novicios Peloescarcha", panel.infoCard.text.text)

        host.state.quests[1599].complete = True
        host.g.EmitAddonEvent("QUEST_WATCH_UPDATE", 1599)
        self.assertIn("Durnan", panel.infoCard.text.text)

        panel.tabTalentsBtn.scripts.OnClick(panel.tabTalentsBtn)
        host.state.quests[1599] = host.table({"delivered": True})
        host.g.EmitAddonEvent("QUEST_TURNED_IN", 1599)
        self.assertIn("barra de tu mascota", panel.infoCard.text.text)
        self.assertIn("NIVEL 10", panel.nextCard.header.text)

    def test_personal_advice_is_limited_to_actual_gnome_warlocks_below_ten(self):
        for race, player_class, preview, level in [
            ("Human", "WARLOCK", None, 1),
            ("Gnome", "MAGE", "WARLOCK", 1),
            ("Gnome", "WARLOCK", None, 10),
        ]:
            with self.subTest(race=race, player_class=player_class, preview=preview, level=level):
                _, panel = self.open_panel(race, player_class, preview, level)
                self.assertNotIn("Sten", panel.infoCard.text.text)
                self.assertNotIn("LIBRO DE HECHIZOS", panel.nextCard.header.text)
