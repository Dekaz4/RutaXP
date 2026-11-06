"""The real Dun Morogh cooking objective has a sourced point, not fake completion."""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from test_access_navigation import AccessHost, DWARF


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP" / "Source"


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cooking_goals(document):
    guide = next(g for g in document["guides"] if g["id"] == DWARF)
    goals = guide["steps"][18]["goals"]
    complete = next(g for g in goals if g.get("quest") == 96629 and g["t"] == "complete")
    turnin = next(g for g in goals if g.get("quest") == 96629 and g["t"] == "turnin")
    return complete, turnin


class CookingGuideNavigationTests(unittest.TestCase):
    def test_real_goal_has_the_same_sourced_instructor_point_as_its_turnin(self):
        h = AccessHost(DWARF, 19, 6, x=.4767, y=.5231)
        h.h.lua.execute("C_QuestLog.GetNextWaypoint=function() return nil end")
        before = h.progress()
        point = h.point()
        self.assertIsNotNone(point, "The objective must work without a live quest marker")
        self.assertEqual(h.goal.npc, 1699)
        self.assertEqual(h.goal.npcName, "Gremlock Pilsnor")
        self.assertEqual(h.goal.f, "e")
        self.assertEqual(point.mapID, 1426)
        self.assertAlmostEqual(point.x, .4767)
        self.assertAlmostEqual(point.y, .5231)
        self.assertEqual(point.z, 398.9)
        self.assertIn("aprende Cocina", h.goal.note)
        for key in ("npc", "npcName", "map", "x", "y", "z", "f"):
            self.assertEqual(h.goal[key], h.step.goals[7][key])
        self.assertEqual(h.progress(), before)

    def test_arrival_and_trainer_interaction_do_not_complete_cooking(self):
        h = AccessHost(DWARF, 19, 6, x=.4767, y=.5231)
        h.s.height = 398.9
        before = h.progress()
        for event in ("GOSSIP_SHOW", "TRAINER_SHOW", "QUEST_LOG_UPDATE"):
            h.h.g.EmitAddonEvent(event)
            h.ns.Sync(h.ns)
            self.assertEqual(h.ns.GetActiveGoal(h.ns)[1], 6)
        self.assertEqual(h.ns.GetGoalStatus(h.ns, h.goal, h.step, None, 6)[0], "active")
        self.assertEqual(h.progress(), before)

    def test_game_completion_moves_to_turnin_and_only_delivery_finishes_the_step(self):
        h = AccessHost(DWARF, 19, 6, x=.4767, y=.5231)
        h.ns.char.auto = True
        h.s.quests[96629].complete = True
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        active = h.ns.GetActiveGoal(h.ns)
        self.assertEqual(active[1], 7)
        self.assertEqual(active[0].t, "turnin")
        state = h.ns.char.progress[DWARF]
        self.assertEqual(state.cursor, 19)
        self.assertIsNone(state.confirmed["19:6"])
        h.h.g.EmitAddonEvent("QUEST_TURNED_IN", 96629)
        self.assertGreater(state.cursor, 19)

    def test_missing_game_completion_api_does_not_infer_success_from_location(self):
        h = AccessHost(DWARF, 19, 6, x=.4767, y=.5231)
        h.h.lua.execute("C_QuestLog.IsComplete=nil;C_QuestLog.GetQuestObjectives=function() return nil end")
        before = h.progress()
        h.ns.Sync(h.ns)
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[1], 6)
        self.assertEqual(h.progress(), before)

    def test_terrain_routes_from_the_reported_kharanos_position_to_the_instructor(self):
        h = AccessHost(DWARF, 19, 6, x=.465, y=.538, terrain=True)
        h.h.lua.execute("C_QuestLog.GetNextWaypoint=function() return nil end")
        # Use the authored height of nearby Senir as a starting-floor sample;
        # the screenshot supplies XY only, so this is not a live position log.
        h.s.height = h.guide.steps[18].goals[1].z
        h.ns.Walking.Clear(h.ns.Walking)
        before = h.progress()
        pending = h.ns.GetArrowWaypoint(h.ns, h.step)
        self.assertTrue(pending.navigationBlocked)
        h.pump()
        point = h.ns.GetArrowWaypoint(h.ns, h.step)
        self.assertTrue(point.walking)
        self.assertEqual(h.ns.Walking.GetStatus(h.ns.Walking).phase, "walking")
        self.assertEqual(h.ns.Walking.target.z, 398.9)
        self.assertGreaterEqual(len(h.ns.Walking.points), 2)
        self.assertEqual(h.ns.Walking.points[len(h.ns.Walking.points)].z, 398.9)
        self.assertEqual(h.progress(), before)


class CookingGuideRebuildTests(unittest.TestCase):
    def test_overlay_is_idempotent_and_changes_only_the_stated_navigation_hint(self):
        builder = module_at("cooking_guide_builder", SOURCE / "build_guides.py")
        document = json.loads((SOURCE / "leveling.json").read_text(encoding="utf-8"))
        target, _ = cooking_goals(document)
        for key in ("npc", "npcName", "map", "x", "y", "z", "f"):
            target.pop(key)
        target["note"] = "Habla con Gremlock Pilsnor"
        before = copy.deepcopy(document)
        builder.apply_guide_overrides(document, SOURCE / "guide_overrides.json")
        fixed, donor = cooking_goals(document)
        expected = copy.deepcopy(before)
        wanted, _ = cooking_goals(expected)
        wanted.update({key: donor[key] for key in ("npc", "npcName", "map", "x", "y", "z", "f")})
        wanted["note"] = fixed["note"]
        self.assertEqual(document["guides"], expected["guides"])
        once = copy.deepcopy(document)
        builder.apply_guide_overrides(document, SOURCE / "guide_overrides.json")
        self.assertEqual(document, once)
        document["provenance"]["commit"] = "different-source"
        with self.assertRaisesRegex(ValueError, "pinned source"):
            builder.apply_guide_overrides(document, SOURCE / "guide_overrides.json")

    def test_standalone_builder_reproduces_shipping_lua_and_reimport_keeps_the_fix(self):
        builder = module_at("cooking_guide_rebuild", SOURCE / "build_guides.py")
        with tempfile.TemporaryDirectory(prefix="rutaxp-cooking-rebuild-") as temporary:
            output = Path(temporary)
            builder.build(SOURCE / "leveling.json", output)
            self.assertEqual((output / "Leveling.lua").read_bytes(), (ROOT / "RutaXP" / "Leveling.lua").read_bytes())
            upstream = ROOT / ".sources" / "SendaFH"
            if upstream.is_dir():
                destination = output / "imported"
                (destination / "Source").mkdir(parents=True)
                for filename in ("build_guides.py", "guide_overrides.json"):
                    shutil.copyfile(SOURCE / filename, destination / "Source" / filename)
                importer = module_at("cooking_guide_importer", ROOT / "tools" / "import_guides.py")
                importer.import_guides(upstream, destination, importer.PINNED_COMMIT)
                imported = json.loads((destination / "Source" / "leveling.json").read_text(encoding="utf-8"))
                actual, donor = cooking_goals(imported)
                self.assertEqual(actual, cooking_goals(json.loads((SOURCE / "leveling.json").read_text(encoding="utf-8")))[0])
                self.assertEqual(actual["npc"], donor["npc"])
                self.assertEqual(imported["provenance"]["localOverrides"]["applied"],
                                 ["dun-morogh-cooking-instructor", "darkshore-auberdine-pier-map"])


if __name__ == "__main__":
    unittest.main()
