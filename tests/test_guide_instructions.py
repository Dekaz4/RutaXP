"""Presentation enrichment stays grounded in authored data and never changes a goal."""
from copy import deepcopy
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("guide_instructions", ROOT / "tools" / "guide_instructions.py")
instructions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(instructions)


class GuideInstructionTests(unittest.TestCase):
    def text(self, **goal):
        return instructions.instruction_for(goal)

    def test_accepts_from_a_bag_item_instead_of_sending_the_player_to_an_npc(self):
        text = self.text(t="accept", quest=184, title="La escritura", item=1972, itemName="Escritura de Poniente")
        self.assertIn("bolsas", text)
        self.assertIn("clic derecho", text)
        self.assertIn("Escritura de Poniente", text)
        self.assertNotIn("Habla", text)
        self.assertNotIn("Ve a", text)

    def test_npc_and_object_quest_sources_are_distinct(self):
        self.assertIn("Habla con «Farley» y acepta «Encargo»", self.text(t="accept", npcName="Farley", title="Encargo"))
        self.assertIn("Interactúa con «Cartel» y acepta", self.text(t="accept", objName="Cartel", title="Encargo"))
        self.assertIn("Habla con «Farley» y entrega", self.text(t="turnin", npcName="Farley", title="Encargo"))

    def test_counts_and_actual_drop_sources_are_preserved(self):
        text = self.text(t="collect", itemName="Musgovil", count=8, **{"from": "Grellín", "fromAlso": "Grell", "fromKind": "npc"})
        self.assertIn("Musgovil", text)
        self.assertIn("8 en total", text)
        self.assertIn("botín de «Grellín» o «Grell»", text)
        objects = self.text(t="collect", itemName="Suministros", count=4, **{"from": "Caja", "fromKind": "object"})
        self.assertIn("Interactúa con «Caja»", objects)
        self.assertNotIn("Derrota", objects)

    def test_unknown_drop_mechanic_does_not_invent_a_creature_or_object(self):
        text = self.text(t="collect", itemName="Tótem", count=4)
        self.assertIn("Reúne «Tótem»", text)
        self.assertNotIn("botín", text)
        self.assertNotIn("Interactúa", text)

    def test_hunter_taming_is_a_display_override_and_preserves_kill_semantics(self):
        raw = {"t": "kill", "quest": 6069, "target": "Jabalí", "count": 1,
               "note": "Tame con el Fusta de domador", "preAll": [6068], "only": {"classes": ["HUNTER"]}}
        original = deepcopy(raw)
        enriched = instructions.enrich_goal(raw)
        self.assertEqual(raw, original)
        self.assertEqual(enriched["t"], "kill")
        self.assertEqual(enriched["instructionVerb"], "Domestica")
        self.assertIn("Domestica a «Jabalí»", enriched["instruction"])
        self.assertIn("Fusta de domador", enriched["instruction"])
        self.assertNotIn("Derrota", enriched["instruction"])
        self.assertEqual(enriched["note"], original["note"])

    def test_negative_or_ordinary_item_notes_do_not_infer_taming(self):
        for note in ("No domar este enemigo", "Usa el objeto después", "Tame Beast"):
            with self.subTest(note=note):
                goal = instructions.enrich_goal({"t": "kill", "target": "Criatura", "note": note})
                self.assertNotIn("instructionVerb", goal)

    def test_dun_morogh_rods_after_creature_names_are_taming_instructions(self):
        document = json.loads((ROOT / "RutaXP/Source/leveling.json").read_text(encoding="utf-8"))
        guide = next(g for g in document["guides"] if g["id"] == "forever/alliance/dwarf-gnome/01-dun-morogh")
        for index, quest, npc, beast in ((0, 6064, 1126, "Grande jabalí del risco"),
                                         (3, 6084, 1201, "Leopardo de la nieve"),
                                         (6, 6085, 1196, "Oso zarpahelada")):
            with self.subTest(quest=quest):
                raw = guide["steps"][53]["goals"][index]
                enriched = instructions.enrich_goal(raw)
                self.assertEqual((enriched["t"], enriched["quest"], enriched["npc"], enriched["oi"]),
                                 ("kill", quest, npc, 1))
                self.assertEqual(enriched["instructionVerb"], "Domestica")
                self.assertIn(f"Domestica a «{beast}»", enriched["instruction"])
                self.assertIn("«Fusta de domador» que te entrega «Grif Corazón Salvaje»", enriched["instruction"])
                self.assertIn("vuelve a Grif para entregar", enriched["instruction"])
                self.assertNotIn("Derrota", enriched["instruction"])
                for key, value in raw.items():
                    if key not in instructions.GENERATED_FIELDS:
                        self.assertEqual(enriched[key], value)
                for altered in ({**raw, "npc": 999999}, {**raw, "oi": 2},
                                {**raw, "note": "Recoge el botín del jabalí"}):
                    self.assertNotIn("instructionVerb", instructions.enrich_goal(altered))
                future = instructions.enrich_goal(enriched, source_commit="unreviewed")
                self.assertNotIn("instructionVerb", future)

    def test_compiled_dun_morogh_taming_chain_preserves_actions_order_and_runtime_titles(self):
        from test_quest_engine import QuestEngineHost
        host = QuestEngineHost(catalog=True)
        guide = host.ns.guides["forever/alliance/dwarf-gnome/01-dun-morogh"]
        step = guide.steps[54]
        self.assertEqual(len(step.goals), 9)
        self.assertEqual([(goal.t, goal.quest) for goal in step.goals.values()], [
            ("kill", 6064), ("turnin", 6064), ("accept", 6084),
            ("kill", 6084), ("turnin", 6084), ("accept", 6085),
            ("kill", 6085), ("turnin", 6085), ("accept", 6086)])
        self.assertEqual(step.only.classes[1], "HUNTER")
        first = guide.steps[53].goals[3]
        self.assertEqual((first.t, first.quest, first.minLevel, first.npc), ("accept", 6064, 10, 1231))
        for index in (1, 4, 7):
            goal = step.goals[index]
            self.assertEqual(goal.instructionVerb, "Domestica")
            self.assertTrue(host.call("GetGoalTitle", goal).startswith("Domestica:"))
            self.assertNotIn("Derrota", goal.instruction)
        final = guide.steps[72].goals[1]
        self.assertEqual((final.t, final.quest, final.npc), ("turnin", 6086, 10090))

    def test_dwarf_taming_evidence_covers_each_creature_rod_and_instructor_name(self):
        evidence = json.loads((ROOT / "RutaXP/Source/guide_instructions_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["sourceCommit"], instructions.PINNED_COMMIT)
        records = evidence["tamingObjectives"]
        self.assertEqual({r["questID"]: r["npcID"] for r in records}, {6064: 1126, 6084: 1201, 6085: 1196})
        checkout = ROOT / ".sources/SendaFH"
        if not checkout.is_dir():
            return  # The shipped evidence is usable without the optional checkout.
        for record in records:
            guide = record["guideEvidence"]
            payload = (checkout / guide["sourceFile"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), guide["sourceSha256"])
            lines = payload.decode("utf-8-sig").splitlines()
            self.assertEqual(guide["text"], "\n".join(lines[guide["sourceLine"] - 1:guide["sourceEndLine"]]))
            self.assertIn(f"quest {record['questID']}.1", lines[record["objectiveSourceLine"] - 1])
            self.assertIn("tame it with the Taming Rod", lines[record["objectiveSourceLine"] - 1])
            names = record["nameEvidence"]
            payload = (checkout / names["sourceFile"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), names["sourceSha256"])
            lines = payload.decode("utf-8-sig").splitlines()
            sourced_names = "\n".join(lines[line - 1] for line in names["sourceLines"])
            for name in ("Grif Corazón Salvaje", "Belia Tronagranito", "Fusta de domador"):
                self.assertIn(name, sourced_names)

    def test_note_and_text_mechanics_survive_together_in_the_presentation(self):
        text = self.text(t="interact", quest=92597, objName="Ley Line", note="Evita al élite que patrulla.",
                         text="Cast Read Ley Line en el Ley Line")
        self.assertIn("Evita al élite que patrulla.", text)
        self.assertIn("Lanza «Read Ley Line» sobre «Ley Line»", text)
        self.assertNotIn("Haz clic", text)

    def test_specific_complete_mechanic_takes_priority_over_registry_fallback(self):
        text = self.text(t="complete", quest=96606, title="The Great Outdoors",
                         note="/sit por la fogata de Lyreena hasta que consigas Boosted Rest")
        self.assertIn("Escribe /sit junto a la fogata", text)
        self.assertIn("hasta que consigas Boosted Rest", text)
        self.assertNotIn("Abre", text)

    def test_unknown_complete_uses_the_real_quest_log_without_inventing_an_action(self):
        text = self.text(t="complete", quest=999001, title="Encargo desconocido", npcName="Persona")
        self.assertIn("registro", text)
        for invented in ("mata", "Derrota", "Habla", "Interactúa", "Usa", "entrega"):
            self.assertNotIn(invented, text)

    def test_use_target_and_source_location_are_not_dropped(self):
        text = self.text(t="use", itemName="Pipeta", target="Pozo", note="Conserva la muestra; la necesitas después.")
        self.assertIn("Usa «Pipeta» sobre «Pozo»", text)
        self.assertIn("Conserva la muestra", text)

    def test_fly_describes_the_flight_map_and_does_not_send_the_player_to_walk_to_arrival(self):
        text = self.text(t="fly", location="Auberdine", npcName="Vesprystus", **{"from": "Dolanaar"})
        self.assertIn("Vesprystus", text)
        self.assertIn("Dolanaar", text)
        self.assertIn("mapa de vuelos", text)
        self.assertIn("selecciona «Auberdine»", text)
        self.assertNotIn("camina", text.lower())

    def test_hearth_level_and_note_require_no_fixed_map_coordinate(self):
        self.assertIn("vinculada a «Kharanos»", self.text(t="hearth", location="Kharanos"))
        self.assertIn("nivel 4", self.text(t="level", level=4, note="Unos cuantos troggs más si te falta experiencia."))
        self.assertIn("Mantén vivo al escoltado", self.text(t="note", text="Mantén vivo al escoltado; evita el camino sur."))

    def test_candidates_do_not_choose_the_first_instructor_for_every_class(self):
        text = self.text(t="train", candidates=[{"npcName": "Instructor de guerreros", "classes": ["WARRIOR"]},
                                                {"npcName": "Instructor de magos", "classes": ["MAGE"]}])
        self.assertIn("de tu clase", text)
        self.assertNotIn("Instructor de guerreros", text)
        self.assertNotIn("Instructor de magos", text)

    def test_cooking_uses_the_profession_without_class_training_claims(self):
        text = self.text(t="train", skill="Cooking", rank=1, rankMax=75)
        self.assertIn("Cocina", text)
        self.assertNotIn("de tu clase", text)
        self.assertNotIn("compra todas", text.lower())

    def test_wow_colors_and_hyperlinks_keep_visible_warning_and_item_names(self):
        goal = {"t": "collect", "itemName": "|cffffffff|Hitem:123|h[Colmillo]|h|r", "count": 2,
                "note": "|cffff0000Peligro: élite dentro de la cueva.|r"}
        enriched = instructions.enrich_goal(goal)
        self.assertIn("[Colmillo]", enriched["instruction"])
        self.assertIn("Peligro: élite dentro de la cueva.", enriched["instruction"])
        self.assertNotIn("|c", enriched["instruction"])
        self.assertEqual(enriched["note"], goal["note"])

    def test_prerequisites_optional_group_and_original_data_survive_without_made_up_titles(self):
        goal = {"t": "accept", "quest": 10, "npcName": "Ana", "preAll": [111, 222],
                "closedBy": [333], "optional": True, "group": 3, "count": 0, "f": "e", "x": 55.4,
                "rewards": [{"item": 7}], "note": "Solo si encontraste la carta; no vendas la llave."}
        enriched = instructions.enrich_goal(goal)
        for key, value in goal.items():
            self.assertEqual(enriched[key], value)
        self.assertIn("Opcional", enriched["instruction"])
        self.assertIn("grupo de 3", enriched["instruction"])
        self.assertIn("no vendas la llave", enriched["instruction"])
        self.assertNotIn("111", enriched["instruction"])
        self.assertNotIn("0 en total", enriched["instruction"])
        enriched["rewards"][0]["item"] = 99
        self.assertEqual(goal["rewards"][0]["item"], 7)

    def test_document_enrichment_is_pure_idempotent_and_does_not_spread_step_notes(self):
        source = {"schemaVersion": 1, "provenance": {"commit": "pinned"}, "statistics": {"goalCount": 2}, "guides": [
            {"id": "a", "zone": 1, "zoneName": "Bosque", "steps": [{"note": "Detalle de todo el paso.", "goals": [
                {"t": "talk", "npcName": "Ana", "map": 1}, {"t": "talk", "npcName": "Luis", "map": 2}]}]}]}
        before = deepcopy(source)
        enriched = instructions.enrich_document(source)
        self.assertEqual(source, before)
        self.assertEqual(enriched, instructions.enrich_document(enriched))
        self.assertEqual(enriched["provenance"], before["provenance"])
        self.assertEqual(enriched["statistics"], before["statistics"])
        first, second = enriched["guides"][0]["steps"][0]["goals"]
        self.assertIn("Zona: Bosque", first["instruction"])
        self.assertNotIn("Zona: Bosque", second["instruction"])
        self.assertNotIn("Detalle de todo", first["instruction"])
        self.assertEqual(enriched["guides"][0]["steps"][0]["note"], "Detalle de todo el paso.")

    def test_navigation_hint_is_only_an_authored_detail_and_has_no_coordinate_claim(self):
        text = self.text(t="complete", quest=99, navigationHint="Acceso por la boca norte, según la guía.")
        self.assertIn("Acceso por la boca norte", text)
        self.assertNotIn("metros", text)
        self.assertNotIn("atraviesa", text.lower())

    def test_inventory_combinations_have_sourced_actions_and_expiry_warning(self):
        doll = self.text(t="complete", quest=5149)
        self.assertIn("Combina las tres piezas desde tus bolsas", doll)
        self.assertIn("fantasmas", doll)
        charm = self.text(t="complete", quest=5051)
        self.assertIn("Combínala en tus bolsas", charm)
        self.assertIn("necrófagos farfullantes", charm)
        rot = self.text(t="complete", quest=6022)
        self.assertIn("7 «Caña viva»", rot)
        self.assertIn("Mano y almirez", rot)
        self.assertIn("10 minutos", rot)

    def test_inventory_quantities_are_not_copied_between_two_different_quests(self):
        self.assertIn("10 «Mañagrana»", self.text(t="complete", quest=3786))
        self.assertNotIn("10", self.text(t="complete", quest=3804))
        self.assertIn("cantidad", self.text(t="complete", quest=3804))
        cleansing = self.text(t="complete", quest=1046)
        self.assertIn("Calavera de Ran Sangradientes", cleansing)
        self.assertIn("Vara de transformación de Dartol", cleansing)

    def test_conflicting_crate_source_does_not_invent_a_gift_or_opening_a_sealed_crate(self):
        for quest, item in ((91899, 248765), (91904, 248770)):
            with self.subTest(quest=quest):
                text = self.text(t="complete", quest=quest)
                self.assertIn(str(item), text)
                self.assertIn("discrepan", text)
                self.assertNotIn("te entrega", text)
                self.assertNotIn("Abre", text)

    def test_only_reviewed_crate_quests_replace_conflicting_display_context(self):
        for quest in (91899, 91904):
            goal = {"t": "complete", "quest": quest, "note": "Open cada caja que le da."}
            result = instructions.enrich_goal(goal)
            self.assertTrue(result["instructionReplacesContext"])
            self.assertEqual(result["note"], goal["note"])
            future = instructions.enrich_goal(result, source_commit="not-the-reviewed-commit")
            self.assertNotIn("instructionReplacesContext", future)
        for goal in ({"t": "complete", "quest": 6001, "note": "Usa el polvo."},
                     {"t": "complete", "quest": 91899, "oi": 2}):
            self.assertNotIn("instructionReplacesContext", instructions.enrich_goal(goal))
        for quest in (91899, 91904):
            for action in ("accept", "turnin"):
                self.assertTrue(instructions.enrich_goal({"t": action, "quest": quest})["instructionReplacesContext"])

    def test_skyborne_kill_credit_is_not_a_kill_instruction_when_the_guide_says_talk(self):
        first = self.text(t="complete", quest=94568)
        rally = self.text(t="complete", quest=92640)
        self.assertIn("Habla con «Talaanis Shadowsong»", first)
        for name in ("Valennia Stormfist", "Ayessa Dawnsinger", "Elaadrin Evengale"):
            self.assertIn(name, rally)
        self.assertIn("Habla", rally)
        self.assertNotIn("Derrota", rally)
        # The exception affects completion instructions, never quest acceptance.
        self.assertNotIn("conversación", self.text(t="accept", quest=94568, npcName="Talaanis Shadowsong"))

    def test_bear_form_requires_the_sourced_use_fight_and_spirit_conversation(self):
        for quest, item, place in ((6001, 15208, "Costa Oscura"), (6002, 15710, "Mulgore")):
            with self.subTest(quest=quest):
                text = self.text(t="complete", quest=quest)
                self.assertIn(str(item), text)
                self.assertIn(place, text)
                self.assertIn("derrota a Garraluna", text)
                self.assertIn("habla después con el Espíritu", text)

    def test_residue_is_enchanting_processing_instead_of_a_fictitious_ground_object(self):
        text = self.text(t="complete", quest=96873, optional=True)
        self.assertIn("Encantamiento", text)
        self.assertIn("desencanta «Hexed Pendant»", text)
        self.assertIn("3 «Luminous Residue»", text)
        self.assertIn("Opcional", text)
        self.assertNotIn("Haz clic", text)

    def test_walk_on_air_instruction_does_not_infer_a_jump_or_attack(self):
        text = self.text(t="complete", quest=92474)
        self.assertIn("habilidad «Walk on Air»", text)
        for invented in ("salta", "Derrota", "mata", "recoge"):
            self.assertNotIn(invented, text)

    def test_documented_exceptions_are_not_reused_on_a_different_source_commit(self):
        document = {"provenance": {"commit": instructions.PINNED_COMMIT}, "guides": [
            {"id": "a", "steps": [{"goals": [{"t": "complete", "quest": 5149}]}]}]}
        pinned = instructions.enrich_document(document)
        self.assertIn("Combina las tres", pinned["guides"][0]["steps"][0]["goals"][0]["instruction"])
        pinned["provenance"]["commit"] = "a-new-unreviewed-commit"
        new = instructions.enrich_document(pinned)
        self.assertNotIn("Combina las tres", new["guides"][0]["steps"][0]["goals"][0]["instruction"])
        self.assertIn("registro", new["guides"][0]["steps"][0]["goals"][0]["instruction"])

    def test_every_documented_exception_ships_its_matching_source_evidence(self):
        evidence = json.loads((ROOT / "RutaXP/Source/guide_instructions_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["sourceCommit"], instructions.PINNED_COMMIT)
        records = {row["questID"]: row for row in evidence["quests"]}
        self.assertEqual(set(records), set(instructions.DOCUMENTED_INSTRUCTIONS))
        for quest, text in instructions.DOCUMENTED_INSTRUCTIONS.items():
            self.assertEqual(records[quest]["instruction"], text)
            self.assertTrue(records[quest]["codex"]["sourceSha256"])

    def test_evidence_file_lines_and_hashes_match_the_pinned_checkout_when_available(self):
        checkout = ROOT / ".sources/SendaFH"
        if not checkout.is_dir():
            self.skipTest("Optional pinned source checkout is unavailable")
        evidence = json.loads((ROOT / "RutaXP/Source/guide_instructions_evidence.json").read_text(encoding="utf-8"))
        cache = {}
        for row in evidence["quests"]:
            for source in [row["codex"], *row["guideEvidence"], *row["itemEvidence"]]:
                relative = source.get("sourceFile")
                if not relative:
                    continue
                if relative not in cache:
                    payload = (checkout / relative).read_bytes()
                    cache[relative] = hashlib.sha256(payload).hexdigest(), payload.decode("utf-8-sig").splitlines()
                digest, lines = cache[relative]
                self.assertEqual(source["sourceSha256"], digest)
                self.assertLessEqual(source["sourceLine"], len(lines))
                if "text" in source:
                    self.assertEqual(source["text"], "\n".join(lines[source["sourceLine"] - 1:source["sourceEndLine"]]))

    def test_every_shipped_goal_has_nonempty_instructions_and_keeps_original_fields(self):
        source = json.loads((ROOT / "RutaXP/Source/leveling.json").read_text(encoding="utf-8"))
        enriched = instructions.enrich_document(source)
        count, taming = 0, 0
        for old_guide, new_guide in zip(source["guides"], enriched["guides"]):
            for old_step, new_step in zip(old_guide["steps"], new_guide["steps"]):
                for old_goal, new_goal in zip(old_step["goals"], new_step["goals"]):
                    self.assertTrue(new_goal["instruction"].strip())
                    for key, value in old_goal.items():
                        if key not in instructions.GENERATED_FIELDS:
                            self.assertEqual(value, new_goal[key])
                    taming += new_goal.get("instructionVerb") == "Domestica"
                    count += 1
        self.assertEqual(count, 7446)
        self.assertEqual(taming, 11)
        self.assertEqual(enriched, instructions.enrich_document(enriched))

    def test_cli_writes_only_the_requested_copy_and_check_detects_stale_content(self):
        source = {"guides": [{"id": "a", "steps": [{"goals": [{"t": "talk", "npcName": "Ana"}]}]}]}
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            input_path, output = Path(folder) / "source.json", Path(folder) / "result.json"
            input_path.write_text(json.dumps(source), encoding="utf-8")
            original_bytes = input_path.read_bytes()
            self.assertEqual(instructions.main(["--input", str(input_path), "--check"]), 1)
            self.assertEqual(instructions.main(["--input", str(input_path), "--output", str(output)]), 0)
            self.assertEqual(input_path.read_bytes(), original_bytes)
            self.assertEqual(instructions.main(["--input", str(output), "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
