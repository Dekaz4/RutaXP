"""Price optional stops through the shipped Forever mesh, including the onward leg."""
import json
import unittest

from test_access_navigation import ADDON, AccessHost
from tools.build_travel_enemies import build_circuit_creatures


STRANGLETHORN = "forever/alliance/30-40/04-stranglethorn-vale"


class CircuitCreatureDataTests(unittest.TestCase):
    def test_ambiguous_localized_name_never_implies_shared_kill_credit(self):
        catalog = {"guides":[{"steps":[{"goals":[
            {"t":"kill","npc":1,"target":"Raptor"},
            {"t":"collect","fromKind":"npc","from":"Raptor","fromAlso":"Raptor joven"},
        ]}]}]}
        npc_db = "[1] = {'Raptor',\n[2] = {'Other raptor',\n"
        names = 'add("esES", "npc", {\n[1]="Raptor",\n[2]="Raptor",\n})\n'
        result = build_circuit_creatures(catalog, {1:(33,34,0),2:(34,36,0)}, npc_db, names)
        self.assertNotIn('["Raptor"]', result)
        self.assertNotIn('["Raptor joven"]', result)

    def test_shipped_data_identifies_basilisks_and_the_shared_tanaris_mage(self):
        catalog = json.loads((ADDON / "Source/leveling.json").read_text(encoding="utf8"))
        by_quest = {}
        for guide in catalog["guides"]:
            for step in guide["steps"]:
                for goal in step["goals"]:
                    if goal.get("fromKind") == "npc" and goal.get("quest") in (605,1878):
                        by_quest[goal["quest"]] = goal["from"]
        data = (ADDON / "CircuitCreatureData.lua").read_text(encoding="utf8")
        for quest, record in ((605,"id=689,min=34,max=35"),(1878,"id=5617,min=41,max=43")):
            self.assertIn('["' + by_quest[quest] + '"]={' + record + '}', data)


class CircuitTerrainTests(unittest.TestCase):
    def host(self):
        h = AccessHost(STRANGLETHORN, 13, 1, x=.266, y=.168, terrain=True)
        h.s.mapID, h.s.height = 1434, None
        h.h.lua.execute((ADDON / "CircuitTerrain.lua").read_text(encoding="utf8"), "RutaXP", h.ns)
        h.ns.Walking.Clear(h.ns.Walking)
        h.h.lua.execute("""
            local after = C_Timer.After
            function C_Timer.After(delay, callback)
                if delay == 0 then after(0, callback) else TEST.deadline = callback end
            end
            ACCESS_NS.RefreshUI = function() end
        """)
        return h

    def point(self, h, x, y):
        return h.h.table({"mapID": 1434, "x": x, "y": y})

    def test_raptor_clearing_can_share_the_basilisk_visit_but_not_a_booty_bay_round_trip(self):
        h = self.host()
        mesh = h.ns.CircuitTerrain
        panthers = self.point(h, .285, .163)
        basilisk = self.point(h, .267, .183)
        booty_bay = self.point(h, .2712, .7721)
        before = h.progress()
        self.assertIsNone(mesh.Check(mesh, "west-clearing", basilisk, panthers, 350))
        h.pump()
        self.assertTrue(mesh.Check(mesh, "west-clearing", basilisk, panthers, 350))
        self.assertIsNone(mesh.Check(mesh, "booty-bay", booty_bay, panthers, 350))
        h.pump()
        self.assertFalse(mesh.Check(mesh, "booty-bay", booty_bay, panthers, 350))
        self.assertEqual(h.progress(), before)

    def test_timeout_and_old_callback_cannot_approve_a_different_journey(self):
        h = self.host()
        h.h.lua.execute("""
            TEST.calls, TEST.cancelled = {}, 0
            RutaXPPathEngine.FindMany = function(_,_,_,callback)
                table.insert(TEST.calls, callback)
                return {}
            end
            RutaXPPathEngine.Cancel = function() TEST.cancelled = TEST.cancelled + 1 end
        """)
        mesh = h.ns.CircuitTerrain
        camp = self.point(h, .267, .183)
        anchor = self.point(h, .285, .163)
        self.assertIsNone(mesh.Check(mesh, "old", camp, anchor))
        self.assertIsNone(mesh.Check(mesh, "new", camp, anchor))
        h.s.calls[1](h.h.table([25, 30]))
        h.s.deadline()
        h.s.calls[2](h.h.table([25, 30]))
        self.assertEqual(h.s.cancelled, 2)
        self.assertFalse(mesh.Check(mesh, "new", camp, anchor))
        self.assertEqual(len(h.s.calls), 2)

    def test_two_remaining_raptors_cut_walking_to_the_same_handin_on_the_forever_mesh(self):
        def replay(automatic):
            h = self.host()
            for name in ("CircuitCreatureData.lua", "LocalCircuit.lua"):
                h.h.lua.execute((ADDON / name).read_text(encoding="utf8"), "RutaXP", h.ns)
            h.s.level, h.ns.char.auto = 35, automatic
            for quest, count in ((191, 0), (194, 8)):
                h.s.quests[quest] = h.h.table({"onQuest": True, "complete": False, "objectives": [{
                    "finished": False, "numFulfilled": count, "numRequired": 10}]})
            state = h.ns.char.progress[STRANGLETHORN]
            total, order = 0, []

            def walk_to(point):
                nonlocal total
                _, x, y = h.ns.GetWaypointWorldPosition(h.ns, self.point(h, h.s.x, h.s.y))
                continent, nx, ny = h.ns.GetWaypointWorldPosition(h.ns, point)
                if abs(nx-x) + abs(ny-y) > 1:
                    path, yards = h.engine.FindSync(continent, h.h.table({"x":x,"y":y}),
                                                   h.h.table({"x":nx,"y":ny}))[:2]
                    self.assertIsNotNone(path, (point.x, point.y, yards))
                    total += yards
                h.s.x, h.s.y = point.x, point.y

            for _ in range(2):
                goal = h.ns.GetActiveGoal(h.ns, h.step, state)[0]
                selected = h.ns.GetLocalCircuitStop(h.ns, h.step)
                if selected:
                    goal = selected.goal
                order.append(goal.quest)
                walk_to(h.ns.GetGoalWaypoint(h.ns, goal))
                h.s.quests[goal.quest].complete = True
                h.s.quests[goal.quest].objectives[1].finished = True
                h.s.quests[goal.quest].objectives[1].numFulfilled = 10
                h.ns.LocalCircuit.Invalidate(h.ns.LocalCircuit)
            hemet = h.guide.steps[14].goals[1]
            self.assertEqual((hemet.t, hemet.quest), ("turnin", 194))
            walk_to(h.ns.GetGoalWaypoint(h.ns, hemet))
            return order, total

        authored, baseline_yards = replay(False)
        circuit, circuit_yards = replay(True)
        self.assertEqual(authored, [191, 194])
        self.assertEqual(circuit, [194, 191])
        self.assertLess(circuit_yards, baseline_yards)

    def test_parallel_floors_and_unavailable_mesh_do_not_start_a_comparison(self):
        h = self.host()
        mesh = h.ns.CircuitTerrain
        point = self.point(h, .267, .183)
        h.h.lua.execute("""
            local pos=UnitPosition
            UnitPosition=function(...) local x,y,z,c=pos(...) return x+200,y,z,c end
            RutaXPPathEngine.FindMany=function() error("unexpected search") end
        """)
        self.assertIsNone(mesh.Check(mesh, "phase", point, point))
        h.engine.Available = h.h.lua.eval("function() return false end")
        self.assertIsNone(mesh.Check(mesh, "no map", point, point))


if __name__ == "__main__":
    unittest.main()
