"""Whole-catalog guarantees for evidence-based navigation enrichment."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest

from test_access_navigation import AccessHost


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP" / "Source"
spec = importlib.util.spec_from_file_location("guide_coverage_audit", ROOT / "tools" / "audit_guides.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)

# Captured before enrichment from all 7,444 source actions, conditions,
# prerequisites, objective indices, item IDs, counts and profession requirements.
ORIGINAL_SEMANTICS = "46bc091cc7034231f3f7138dc301eaff00126460d6abfe7745a3233ada32350d"


def undo_visit_optimization(guide, revision):
    """Restore source slots from authored references independently of the runtime cursor map."""
    restored = {}
    for step, spec in zip(guide["steps"], revision["steps"], strict=True):
        if "sourceStep" in spec:
            si = spec["sourceStep"]
            count = revision["previousGoalCounts"][si - 1]
            refs = [(si, gi) for gi in range(1, count + 1) if gi not in spec.get("omitGoals", ())]
        else:
            refs = spec["goals"]
        for ref, goal in zip(refs, step["goals"], strict=True):
            if isinstance(ref, dict):
                added = revision["addedGoals"][ref["added"]]["goal"]
                for field in audit_module.SEMANTIC_FIELDS:
                    if goal.get(field) != added.get(field):
                        raise AssertionError(f"Changed addition {revision['id']}: {ref}")
                continue
            key = f"{ref[0]}:{ref[1]}"
            if key in restored:
                raise AssertionError(f"Repeated source slot {revision['id']}: {key}")
            restored[key] = goal
    for key, retirement in revision.get("retiredGoals", {}).items():
        goal = retirement["evidence"]["originalGoal"]
        if key in restored or any(goal.get(k) != v for k, v in retirement["match"].items()):
            raise AssertionError(f"Inconsistent retirement {revision['id']}: {key}")
        restored[key] = copy.deepcopy(goal)
    for key, previous in revision["evidence"].get("previousNavigation", {}).items():
        if not previous.keys() <= {"map", "x", "y", "z", "f", "r", "spots"}:
            raise AssertionError(f"Unexpected navigation evidence {revision['id']}: {key}")
        restored[key].update(copy.deepcopy(previous))
    for si, (count, step) in enumerate(zip(revision["previousGoalCounts"], guide["steps"], strict=True), 1):
        step["goals"] = [restored.pop(f"{si}:{gi}") for gi in range(1, count + 1)]
    if restored:
        raise AssertionError(f"Unexpected source slots {revision['id']}: {sorted(restored)}")


def original_order(document):
    """Undo reviewed moves and exact prerequisite edits before the old digest."""
    result = copy.deepcopy(document)
    revisions = json.loads((SOURCE / "guide_revisions.json").read_text(encoding="utf-8"))["revisions"]
    guides = {guide["id"]: guide for guide in result["guides"]}
    for revision in reversed(revisions):
        if revision.get("preservePendingVisits"):
            undo_visit_optimization(guides[revision["guideID"]], revision)
    darkshore = next(g for g in result["guides"] if g["id"] == "forever/alliance/03-darkshore")
    ashenvale = next(g for g in result["guides"] if g["id"] == "forever/alliance/06-ashenvale")
    arbal = darkshore["steps"][31]["goals"].pop(2)
    if arbal["quest"] != 98013 or arbal.pop("preAll") != [950]:
        raise AssertionError("The reviewed Arbal visit changed")
    escort = ashenvale["steps"][4]
    if [(q["t"], q["quest"]) for q in escort["goals"]] != [("accept", 5321), ("complete", 5321)]:
        raise AssertionError("The reviewed Kerlonian escort changed")
    darkshore["steps"][27]["goals"].extend([arbal, escort["goals"][0]])
    escort["goals"] = [{"t": "goto", "map": 1439, "x": 44.4, "y": 76.4, "f": "e"}, {"t": "note"}]
    for revision in reversed(revisions):
        if revision.get("preservePendingVisits") or not revision.get("addedGoals") or revision.get("retiredGoals"):
            continue
        guide = next(g for g in result["guides"] if g["id"] == revision["guideID"])
        migration = next(m for m in guide["progressMigrations"] if m["from"] == revision["previousRevision"])
        old = []
        for si, count in enumerate(revision["previousGoalCounts"], 1):
            step = copy.deepcopy(guide["steps"][migration["stepMap"][str(si)] - 1])
            step["goals"] = []
            for gi in range(1, count + 1):
                ni, nj = (int(value) for value in migration["goalMap"].get(f"{si}:{gi}", f"{si}:{gi}").split(":"))
                goal = copy.deepcopy(guide["steps"][ni - 1]["goals"][nj - 1])
                for patch in revision.get("goalChanges", []):
                    if all(goal.get(key) == value for key, value in patch["match"].items()) and goal.get("t") == "accept":
                        for key, value in patch["set"].items():
                            if key not in ("preAll", "preTitles") or goal.get(key) != value:
                                raise AssertionError("A reviewed successor prerequisite changed")
                            del goal[key]
                step["goals"].append(goal)
            old.append(step)
        guide["steps"] = old
    revision = next(r for r in revisions if r["id"] == "darkshore-holy-diver-3")
    migration = next(m for m in darkshore["progressMigrations"] if m["from"] == 2 and m["to"] == 3)
    original = []
    for si, count in enumerate(revision["previousGoalCounts"], 1):
        step = copy.deepcopy(darkshore["steps"][si - 1])
        step["goals"] = []
        for gi in range(1, count + 1):
            target = migration["goalMap"].get(f"{si}:{gi}", f"{si}:{gi}")
            ni, nj = (int(value) for value in target.split(":"))
            goal = copy.deepcopy(darkshore["steps"][ni - 1]["goals"][nj - 1])
            if goal.get("t") == "accept" and goal.get("quest") == 87760:
                if goal.get("preAll") != [4722, 4723, 4725, 4727, 4728, 4730, 4731, 4732, 4733]:
                    raise AssertionError("The reviewed Holy Diver prerequisite group changed")
                del goal["preAll"]
                goal.pop("preTitles", None)
            if goal.get("t") == "accept" and goal.get("quest") == 98025:
                if goal.get("minLevel") != 15:
                    raise AssertionError("The reviewed Jai'vhanel minimum level changed")
                goal["minLevel"] = 10
            step["goals"].append(goal)
        original.append(step)
    darkshore["steps"] = original
    pier = darkshore["steps"][36]["goals"][4]
    if (pier.get("t"), pier.get("map"), pier.get("x"), pier.get("y"), pier.get("f")) != ("goto", 1439, 32.4, 43.8, "e"):
        raise AssertionError("The reviewed Auberdine map correction changed")
    pier["map"] = 1450
    for revision in reversed(revisions):
        if not revision["id"].endswith("-prerequisites-metadata"):
            continue
        guide = next(g for g in result["guides"] if g["id"] == revision["guideID"])
        for patch in revision["goalChanges"]:
            goals = [goal for step in guide["steps"] for goal in step["goals"]
                     if all(goal.get(key) == value for key, value in patch["match"].items())]
            if len(goals) != patch["count"]:
                raise AssertionError("A corroborated requirement target changed")
            for goal in goals:
                for key, value in patch["set"].items():
                    if key not in ("pre", "preAll", "preTitles") or goal.get(key) != value:
                        raise AssertionError("A corroborated requirement changed")
                    del goal[key]
    corrected = {"zephras-alliance-service-2", "redridge-alther-bridge-2", "mulgore-malah-centaurs-2",
                 "tirisfal-rear-guard-2", "silverpine-quinn-potions-2"}
    for revision in revisions:
        if revision["id"] not in corrected:
            continue
        guide = next(g for g in result["guides"] if g["id"] == revision["guideID"])
        migration = next(m for m in guide["progressMigrations"] if m["from"] == 1 and m["to"] == 2)
        old = []
        for si, count in enumerate(revision["previousGoalCounts"], 1):
            step = copy.deepcopy(guide["steps"][migration["stepMap"][str(si)] - 1])
            step["goals"] = []
            for gi in range(1, count + 1):
                new_si, new_gi = (int(v) for v in migration["goalMap"].get(f"{si}:{gi}", f"{si}:{gi}").split(":"))
                goal = copy.deepcopy(guide["steps"][new_si - 1]["goals"][new_gi - 1])
                if goal.get("t") == "accept" and str(goal.get("quest")) in revision["evidence"]["prerequisites"]:
                    if goal["quest"] == 92860:
                        goal["pre"] = [92840]
                    else:
                        goal.pop("pre", None)
                step["goals"].append(goal)
            old.append(step)
        guide["steps"] = old
    west = next(guide for guide in result["guides"] if guide["id"] == "forever/alliance/02-westfall")
    # Revision 3 fixes only the optional engineering branch. Restore its
    # original positions and semantics independently of the overlay builder.
    current = west["steps"]
    engineering_accept = copy.deepcopy(current[11]["goals"][5])
    engineering_work = copy.deepcopy(current[11]["goals"][6])
    if engineering_accept.get("preAll") != [92910] or engineering_work.get("t") != "complete" or "oi" in engineering_work:
        raise AssertionError("The reviewed engineering correction changed")
    del engineering_accept["preAll"]
    engineering_work.update(t="collect", oi=1)
    engineering_work.pop("navigationMode", None)
    engineering_work.pop("navigationHint", None)
    current[1]["goals"].insert(4, engineering_accept)
    current[4]["goals"].insert(4, engineering_work)
    del current[11]["goals"][5:7]
    for visit in current:
        for goal in visit["goals"]:
            if goal.get("quest") in (92910, 92911) or goal.get("item") == 255155:
                for key in ("profLine", "profRank", "profName"):
                    goal.pop(key, None)
                if not (goal.get("quest") == 92911 and goal["t"] == "turnin"):
                    goal.pop("optional", None)
    revised = west["steps"]
    # Explicit independent inverse of revision 2's authored visit mapping.
    source_positions = [1, 2, 3, 4, 5, 8, 9, 6, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
    old = [copy.deepcopy(revised[position - 1]) for position in source_positions]
    acceptance = copy.deepcopy(revised[6]["goals"][2])
    if acceptance.get("preAll") != [92742, 92744]:
        raise AssertionError("The reviewed prerequisite correction changed")
    del acceptance["preAll"]
    old[0]["goals"].append(acceptance)
    old[11]["goals"][4:4] = copy.deepcopy(revised[6]["goals"][:2])
    west["steps"] = old
    return result


class WholeGuideCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((SOURCE / "leveling.json").read_text(encoding="utf-8"))
        locations_path = SOURCE / "guide_locations.json"
        cls.locations = json.loads(locations_path.read_text(encoding="utf-8")) if locations_path.exists() else None
        cls.revisions = json.loads((SOURCE / "guide_revisions.json").read_text(encoding="utf-8"))
        cls.report = audit_module.audit(cls.document, locations=cls.locations, revisions=cls.revisions)

    def test_inventory_accounts_for_every_goal_and_keeps_legitimate_exceptions_explicit(self):
        report = self.report
        self.assertEqual(report["totals"]["guides"], 57)
        self.assertEqual(report["totals"]["goals"], 7458)
        self.assertEqual(report["totals"]["steps"], 2343)
        self.assertEqual(sum(r["counts"]["goals"] for r in report["byGuide"]), 7458)
        self.assertEqual(sum(r["goals"] for r in report["byAction"].values()), 7458)
        self.assertEqual(sum(report["totals"].get(k, 0) for k in
                             ("direct", "spots", "candidates", "missing", "no_fixed_navigation", "conditional_navigation")), 7458)
        self.assertEqual(report["invalidNavigation"], [])
        for item in report["missingNavigation"]:
            self.assertTrue(item["classification"])
            self.assertTrue(item["reason"])
            self.assertTrue(item["source"]["commit"])
            if item["action"] in ("hearth", "level", "note"):
                self.assertFalse(item["unresolved"])
                self.assertEqual(item["classification"], "semantic_no_location")
            elif item["classification"] == "item_start":
                self.assertEqual(item["action"], "accept")
                self.assertFalse(item["unresolved"])
            elif item["classification"] in ("documented_navigation_mode", "documented_mixed_objective"):
                self.assertIn(item["navigationMode"], {"inventory", "ability", "escort"})
                self.assertFalse(item["unresolved"])
            else:
                self.assertTrue(item["unresolved"])

    def test_enrichment_preserves_every_semantic_except_the_reviewed_chain_corrections(self):
        original = original_order(self.document)
        self.assertEqual(audit_module.audit(original)["preservation"]["semanticsSha256"], ORIGINAL_SEMANTICS)

    def test_authored_direct_points_are_preserved_when_the_optional_original_audit_is_available(self):
        baseline_path = ROOT / ".backups" / "guides-audit-initial.json"
        if not baseline_path.exists():
            self.skipTest("Optional pre-enrichment coordinate baseline is not part of the addon package")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        before = baseline["preservation"]["authoredDirectDigests"]
        after = audit_module.audit(original_order(self.document), include_baseline=True)["preservation"]["authoredDirectDigests"]
        self.assertEqual(len(before), 6560)
        for key, expected in before.items():
            self.assertEqual(after.get(key), expected, key)

    def test_audit_is_read_only_and_does_not_hide_instructions_missing_from_the_source(self):
        document = copy.deepcopy(self.document)
        before = copy.deepcopy(document)
        report = audit_module.audit(document)
        self.assertEqual(document, before)
        self.assertEqual(report["totals"].get("missing_goal_note_text", 0),
                         sum(not (audit_module.text(goal.get("note")) or audit_module.text(goal.get("text")))
                             for _, _, _, _, goal in audit_module.iter_goals(document)))
        # Additional navigation cannot by itself turn a title-only objective
        # into a fully authored explanation of the required action.
        example = {"guides": [{"id": "audit", "title": "Audit", "steps": [{"goals": [
            {"t": "complete", "quest": 10, "title": "Unknown objective", "map": 1, "x": 20, "y": 30}
        ]}]}]}
        self.assertEqual(audit_module.audit(example)["totals"]["unclear_instruction"], 1)

    def test_item_start_and_objective_absence_never_mean_a_turnin_npc_was_verified(self):
        document = {"guides": [{"id": "audit", "title": "Audit", "steps": [{"goals": [
            {"t": "accept", "quest": 10, "item": 200, "itemName": "A dropped note"},
            {"t": "complete", "quest": 10, "title": "Escort someone"},
            {"t": "turnin", "quest": 10, "npc": 300, "map": 1, "x": 20, "y": 30},
            {"t": "fly", "location": "A destination, not a departure"},
        ]}]}]}
        missing = audit_module.audit(document)["missingNavigation"]
        self.assertEqual([row["classification"] for row in missing],
                         ["item_start", "unlocated_objective", "taxi_departure_unknown"])
        self.assertEqual([row["unresolved"] for row in missing], [False, True, True])

    def test_an_escort_reference_point_is_not_counted_as_an_active_arrow_or_verified_without_evidence(self):
        document = {"provenance": {"commit": "source"}, "guides": [{"id": "audit", "title": "Audit",
            "steps": [{"goals": [{"t": "complete", "quest": 10, "navigationMode": "escort",
                "candidates": [{"map": 1, "x": 20, "y": 30}]}]}]}]}
        unresolved = audit_module.audit(document)
        self.assertEqual(unresolved["totals"]["no_fixed_navigation"], 1)
        self.assertNotIn("candidates", unresolved["totals"])
        self.assertEqual(unresolved["totals"]["unresolved"], 1)
        proof = {"sourceCommit": "source", "sourceFiles": {"guide": "a" * 64}, "patches": [
            {"guideID": "audit", "step": 1, "goal": 1, "set": {"navigationMode": "escort"},
             "evidence": [{"sourceFile": "guide", "sourceSha256": "a" * 64}]}]}
        expected = audit_module.audit(document, locations=proof)
        self.assertEqual(expected["totals"]["no_fixed_point_expected"], 1)
        self.assertEqual(expected["totals"]["reference_only"], 1)
        self.assertEqual(expected["missingNavigation"][0]["referenceNavigationKind"], "candidates")
        self.assertFalse(expected["missingNavigation"][0]["unresolved"])

        document["guides"][0]["steps"][0]["goals"][0]["navigationMode"] = "inventory"
        proof["patches"][0]["set"]["navigationMode"] = "inventory"
        mixed = audit_module.audit(document, locations=proof)
        self.assertEqual(mixed["totals"]["conditional_navigation"], 1)
        self.assertEqual(mixed["missingNavigation"][0]["classification"], "documented_mixed_objective")
        self.assertNotIn("reference_only", mixed["totals"])

    def test_all_enrichment_candidates_have_bound_source_evidence_and_no_semantic_patches(self):
        overlay_path = SOURCE / "guide_locations.json"
        if not overlay_path.exists():
            self.skipTest("Coordinate overlay has not been integrated yet")
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        self.assertEqual(overlay["sourceCommit"], self.document["provenance"]["commit"])
        guides = {guide["id"]: guide for guide in self.document["guides"]}
        ids = set()
        for patch in overlay["patches"]:
            self.assertNotIn(patch["id"], ids)
            ids.add(patch["id"])
            guide = guides[patch["guideID"]]
            key = f'{patch["step"]}:{patch["goal"]}'
            for migration in guide.get("progressMigrations", []):
                key = migration.get("goalMap", {}).get(key, key)
            si, gi = (int(value) for value in key.split(":"))
            goal = guide["steps"][si - 1]["goals"][gi - 1]
            for field, value in patch["match"].items():
                self.assertEqual(goal.get(field), value, patch["id"])
            self.assertLessEqual(set(patch["set"]), {"candidates", "navigationHint", "navigationMode"})
            if "navigationMode" in patch["set"]:
                self.assertIn(patch["set"]["navigationMode"], {"inventory", "ability", "escort"})
            candidates = patch["set"].get("candidates", [])
            covered = set()
            for evidence in patch["evidence"]:
                self.assertIn(evidence["kind"], {"quest-objective", "item-source", "same-entity", "flight-node",
                                                "inn-area", "quest-event", "authored-action"})
                self.assertEqual(evidence["sourceSha256"], overlay["sourceFiles"][evidence["sourceFile"]])
                self.assertRegex(evidence["sourceSha256"], r"^[0-9a-f]{64}$")
                index = evidence.get("candidateIndex")
                if index is None:
                    self.assertIn(patch["set"].get("navigationMode"), {"inventory", "ability", "escort"})
                    self.assertIn(evidence["kind"], {"authored-action", "item-source", "quest-objective"})
                    if candidates:
                        self.assertEqual(evidence["kind"], "authored-action")
                        self.assertEqual(evidence["classification"], patch["set"]["navigationMode"])
                    continue
                self.assertIsInstance(index, int)
                self.assertTrue(1 <= index <= len(candidates), patch["id"])
                candidate = candidates[index - 1]
                self.assertTrue(audit_module.has_point(candidate), patch["id"])
                entity_type = evidence["entityType"]
                self.assertIn(entity_type, {"npc", "object", "quest", "item", "taxi-node"})
                if entity_type in ("npc", "object"):
                    self.assertEqual(candidate[entity_type], evidence["entityID"], patch["id"])
                elif entity_type == "quest":
                    self.assertEqual(goal["quest"], evidence["entityID"], patch["id"])
                if "objectiveIndex" in candidate:
                    self.assertEqual(candidate["objectiveIndex"], evidence["objectiveIndex"], patch["id"])
                covered.add(index)
            self.assertEqual(covered, set(range(1, len(candidates) + 1)), patch["id"])


class ShippedGuideRenderingTests(unittest.TestCase):
    def test_inventory_ability_and_moving_escort_actions_do_not_emit_static_npc_pins(self):
        host = AccessHost()
        host.h.g.COVER_NS = host.ns
        count = host.h.lua.execute('''
            local count=0
            for _,id in ipairs(COVER_NS.order) do
              for _,step in ipairs(COVER_NS.guides[id].steps) do
                for _,goal in ipairs(step.goals) do
                  if goal.navigationMode=="ability" or goal.navigationMode=="escort"
                      or (goal.navigationMode=="inventory" and #(goal.candidates or {})==0) then
                    assert(COVER_NS:GetGoalWaypoint(goal)==nil,"A reference-only action emitted a static pin")
                    count=count+1
                  end
                end
              end
            end
            return count
        ''')
        self.assertGreater(count, 0)

    def test_navigation_filters_finished_objective_candidates_without_setting_goal_oi_or_guessing_unknowns(self):
        host = AccessHost()
        host.s.mapID, host.s.x, host.s.y = 1429, .5, .5
        host.s.quests[900001] = host.h.table({"onQuest": True, "complete": False, "objectives": [
            {"text": "First objective", "finished": True},
            {"text": "Second objective", "finished": False},
        ]})
        goal = host.h.table({"t": "complete", "quest": 900001, "candidates": [
            {"map": 1429, "x": 50, "y": 50, "npc": 10, "objectiveIndex": 1},
            {"map": 1429, "x": 80, "y": 80, "npc": 20, "objectiveIndex": 2},
        ]})
        point = host.ns.GetGoalWaypoint(host.ns, goal)
        self.assertEqual(point.candidate.objectiveIndex, 2)
        self.assertIsNone(goal.oi)
        goal.navigationMode = "inventory"
        host.s.quests[900001].objectives[2].finished = True
        host.h.g.C_QuestLog.GetNextWaypoint = host.h.lua.eval("function() return 1429,.9,.9 end")
        self.assertIsNone(host.ns.GetGoalWaypoint(host.ns, goal))
        host.s.quests[900001].objectives = None
        self.assertIsNotNone(host.ns.GetGoalWaypoint(host.ns, goal))
        self.assertIsNone(goal.oi)

    def test_every_shipped_goal_has_a_readable_instruction_without_rewriting_its_action(self):
        host = AccessHost()
        ns, lua = host.ns, host.h.lua
        self.assertIsNotNone(ns.GetGoalInstruction, "Shipping engine must expose the instruction renderer")
        host.h.g.COVER_NS = ns
        result = lua.execute('''
            local count,errorCount,errors=0,0,{}
            for _,id in ipairs(COVER_NS.order) do
              local guide=COVER_NS.guides[id]
              for si,step in ipairs(guide.steps) do
                for gi,goal in ipairs(step.goals) do
                  local beforeAction,beforeQuest,beforeOi=goal.t,goal.quest,goal.oi
                  local line=COVER_NS:GetGoalInstruction(goal,step)
                  if type(line)~="string" or not line:find("%S") then
                    errorCount=errorCount+1
                    if #errors<10 then errors[#errors+1]=id..":"..si..":"..gi end
                  end
                  assert(goal.t==beforeAction and goal.quest==beforeQuest and goal.oi==beforeOi,
                    "Rendering an instruction changed quest semantics")
                  count=count+1
                end
              end
            end
            return count,errorCount,table.concat(errors,"; ")
        ''')
        self.assertEqual(result, (7458, 0, ""))

    def test_all_bundled_points_and_candidate_frames_resolve_with_the_real_navigation_converter(self):
        host = AccessHost()
        host.h.g.COVER_NS = host.ns
        count, errors = host.h.lua.execute('''
            local count,errors=0,{}
            local function check(raw,key)
              if raw.map and raw.x~=nil and raw.y~=nil then
                local point=COVER_NS:ResolveWaypointPoint(raw)
                if not point or point.x<0 or point.x>1 or point.y<0 or point.y>1 then errors[#errors+1]=key end
                count=count+1
              end
            end
            for _,id in ipairs(COVER_NS.order) do
              for si,step in ipairs(COVER_NS.guides[id].steps) do
                for gi,goal in ipairs(step.goals) do
                  local key=id..":"..si..":"..gi
                  check(goal,key)
                  for ci,candidate in ipairs(goal.candidates or {}) do check(candidate,key..":candidate"..ci) end
                end
              end
            end
            return count,table.concat(errors,"; ")
        ''')
        self.assertGreater(count, 6560)
        self.assertEqual(errors, "")


if __name__ == "__main__":
    unittest.main()
