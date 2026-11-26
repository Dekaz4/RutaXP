"""The visible heading may look ahead while the route cursor still approaches its bend."""

import math
import unittest

from test_walking_history import ROOT, WalkingHistoryHost


class WalkingLookaheadTests(unittest.TestCase):
    def follow(self, nodes, mesh=True, dynamic=False, open_road=False, configure_terrain=None):
        host = WalkingHistoryHost()
        if mesh:
            host.ns.PathingNamespace = host.table({"PathGrid": {"TILE": 512}})
            host.lua.globals().RutaXPPathData = host.table({0: {"cells": 128}})
        if open_road:
            self.loaded_road(host)
            if configure_terrain:
                configure_terrain(host.s.terrain)
        host.s.x, host.s.y, host.s.z = nodes[0]
        goal = host.point(nodes[-1][0], dynamic=dynamic)
        goal.y, goal.z = nodes[-1][1] / 1000, nodes[-1][2]
        host.w.Resolve(host.w, goal)
        path = host.table([{"map": 0, "x": x, "y": y, "z": z} for x, y, z in nodes])
        host.s.jobs[1].callback(path, 100)
        return host, goal, host.w.Resolve(host.w, goal)

    def loaded_road(self, host):
        # Actual PathGrid representation: one already-decoded cluster with
        # dry cells, single heights and all four cardinal/diagonal flags.
        host.lua.execute("""
            local st={C=128,ny=1,cs=4,x0=0,y0=0,GX=128,GY=128,val={[0]={}},
                z={[0]={}},moves={[0]={}},at={[0]={}},links={[0]={}}}
            for i=1,128*128 do st.val[0][i],st.z[0][i],st.moves[0][i]=1,12,15 end
            TEST.terrain=st
            AUDIT_NS.PathingNamespace.PathGrid.State=function() return st end
        """)

    def test_straight_approach_keeps_one_turn_through_lateral_drift_and_refresh(self):
        route = [(32, 32, 12), (48, 32, 12), (64, 32, 12), (96, 32, 12), (96, 80, 12)]
        h, goal, result = self.follow(route, dynamic=True, open_road=True)
        # PathJobs calls Idle immediately after the callback. The renderer can
        # use the route's bounded references but cannot ask the search to reload.
        h.lua.execute("""
            local t=TEST.terrain
            t.val,t.z,t.moves,t.at,t.links={},{},{},{},{}
            AUDIT_NS.PathingNamespace.PathGrid.State=function() error("UI read evicted mesh") end
        """)
        key = result.walkingRouteKey
        self.assertTrue(key)
        self.assertEqual(result.walkingTurn, "left")
        self.assertEqual(result.walkingTurnDistance, 64)
        seen = []
        for x, y in [(39, 37), (47, 39), (56, 38), (65, 35), (74, 34), (84, 32)]:
            h.s.x, h.s.y, h.s.now = x, y, h.s.now + .6
            if x == 74:
                goal.y += .009  # same objective, newly sampled endpoint
            result = h.w.Resolve(h.w, goal)
            self.assertTrue(result.walking)
            self.assertEqual(result.walkingRouteKey, key)
            self.assertEqual(result.walkingTurn, "left")
            self.assertAlmostEqual(result.walkingTurnDistance, 96-x, delta=7)
            seen.append((result.walkingWorld.north, result.walkingWorld.west))
        self.assertEqual(set(seen), {(96, 32)})
        self.assertTrue(h.w.pending)
        h.s.x, h.s.y = 96, 43
        result = h.w.Resolve(h.w, goal)
        self.assertIsNone(result.walkingTurn)
        self.assertGreater(result.walkingWorld.west, 43)
        self.assertEqual(h.ns.char.progress.g.cursor, 21)

    def test_right_turn_and_objective_change_resets_the_indication(self):
        h, _, result = self.follow([(32, 64, 12), (44, 64, 12), (72, 64, 12), (72, 40, 12)])
        self.assertEqual((result.walkingTurn, result.walkingTurnDistance), ("right", 40))
        self.assertEqual((result.walkingWorld.north, result.walkingWorld.west), (72, 64))
        self.assertTrue(h.w.Resolve(h.w, h.point(180, quest=99)).navigationBlocked)
        self.assertIsNone(h.w.turns)
        self.assertIsNone(h.w.steeringIndex)

    def test_lateral_shortcut_needs_dry_single_level_loaded_terrain_and_open_edges(self):
        route = [(32, 32, 12), (48, 32, 12), (64, 32, 12), (96, 32, 12), (96, 80, 12)]
        for hazard in ("t.val[0][j]=0", "t.val[0][j]=2", "t.z[0][j]=24", "t.at[0][-j]=16384",
                       "t.links[0][j]={}", "t.moves[0][j]=0"):
            with self.subTest(hazard=hazard):
                h, goal, _ = self.follow(route, open_road=True)
                h.lua.execute("local t=TEST.terrain; local j=17*128+8+1; " + hazard)
                h.s.x, h.s.y, h.s.now = 40, 39, 1
                result = h.w.Resolve(h.w, goal)
                self.assertEqual(result.walkingTurn, "left")
                self.assertLess(result.walkingWorld.north, 68, "arrow must stage before the hazard")
                self.assertEqual(h.w.requests, 1)
        h, goal, _ = self.follow(route, open_road=True)
        h.w.corridor.val[0] = False
        h.s.x, h.s.y, h.s.now = 40, 39, 1
        result = h.w.Resolve(h.w, goal)
        self.assertTrue(result.navigationBlocked)
        self.assertIsNone(result.walkingWorld)

    # The planned path approaches the south-east corner, follows the building's
    # side, then enters through its east door. Coordinates are synthetic yards.
    door_route = [(38, 62, 12), (70, 62, 12), (70, 86, 12), (54, 86, 12)]
    walls = {(x, y) for x in range(12, 17) for y in range(16, 25)
             if (x in (12, 16) or y in (16, 24)) and not (x == 16 and 20 <= y <= 22)}

    def building(self, terrain, seal_door=False):
        walls = self.walls | {(16, gy) for gy in range(20, 23)} if seal_door else self.walls
        for gx, gy in walls:
            terrain.val[0][gx * terrain.C + gy + 1] = 0
        for gx in range(11, 18):
            for gy in range(15, 26):
                moves = 0
                for bit, dx, dy in ((1, 1, 0), (2, 0, 1), (4, 1, 1), (8, 1, -1)):
                    cells = {(gx, gy), (gx + dx, gy + dy)}
                    if dx and dy:
                        cells.update(((gx + dx, gy), (gx, gy + dy)))
                    if cells.isdisjoint(walls):
                        moves += bit
                terrain.moves[0][gx * terrain.C + gy + 1] = moves

    def assert_ray_clear(self, position, point):
        aim = point.walkingWorld
        self.assertIsNotNone(aim, position)
        self.assert_clear_segment(position, (aim.north, aim.west))

    def assert_clear_segment(self, position, target):
        x, y = position
        dx, dy = target[0] - x, target[1] - y
        # The open intervals between grid-boundary crossings lie in individual
        # cells, including a wall that the ray clips for a fraction of a yard.
        crossings = {0, 1}
        for start, end in zip(position, target):
            for boundary in range(math.floor(min(start, end) / 4) + 1, math.ceil(max(start, end) / 4)):
                crossings.add((4 * boundary - start) / (end - start))
        ordered = sorted(crossings)
        for a, b in zip(ordered, ordered[1:]):
            t = (a + b) / 2
            cell = (math.floor((x + t * dx) / 4), math.floor((y + t * dy) / 4))
            self.assertNotIn(cell, self.walls, f"segment from {position} to {target} crosses wall {cell}")

    def test_arrow_rounds_the_building_and_enters_at_the_door(self):
        h, goal, _ = self.follow(self.door_route, open_road=True, configure_terrain=self.building)
        positions = [(x, 62) for x in (38, 45, 55, 63, 66, 67.2, 68.5, 70)]
        positions += [(70, y) for y in (66, 70, 74, 78, 82, 86)]
        positions += [(66, 86), (60, 86), (54, 86)]
        for position in positions:
            h.s.x, h.s.y, h.s.now = *position, h.s.now + .7
            point = h.w.Resolve(h.w, goal)
            self.assert_ray_clear(position, point)
        self.assertTrue(point.walkingFinal)
        self.assertEqual((point.walkingWorld.north, point.walkingWorld.west), positions[-1])
        self.assertEqual(h.w.requests, 1)

    def routing_grid(self):
        h = WalkingHistoryHost()
        h.ns.PathingNamespace = h.table({})
        h.lua.globals().RutaXPPathData = h.table({0: {"cells": 32, "nx": 1, "ny": 1,
            "cx0": 0, "cy0": 0, "swim": 2, "graph": {}}})
        for name in ("PathGrid", "Path"):
            source = ROOT / "RutaXP" / "Pathing" / "Routing" / f"{name}.lua"
            h.load(source.read_text(encoding="utf-8-sig"), h.ns)
        terrain = h.ns.PathingNamespace.PathGrid.State(0)
        h.lua.globals().terrain = terrain
        h.lua.execute("""
            local t=terrain
            t.cs,t.nodes[0]=4,{}
            t.val[0],t.z[0],t.moves[0],t.at[0],t.links[0]={},{},{},{},{}
            for x=0,t.C-1 do for y=0,t.C-1 do
                local i=x*t.C+y+1
                t.val[0][i],t.z[0][i]=1,12
                t.moves[0][i]=(x<t.C-1 and 1 or 0)+(y<t.C-1 and 2 or 0)
                    +(x<t.C-1 and y<t.C-1 and 4 or 0)+(x<t.C-1 and y>0 and 8 or 0)
            end end
        """)
        return h, terrain

    def test_grid_routes_through_the_door_and_rejects_a_sealed_building(self):
        for seal_door in (False, True):
            with self.subTest(seal_door=seal_door):
                h, terrain = self.routing_grid()
                self.building(terrain, seal_door)
                start = h.table({"x": 38, "y": 62, "z": 12})
                end = h.table({"x": 54, "y": 86, "z": 12})
                path, cost, _ = h.ns.PathingNamespace.Path.FindSync(0, start, end)
                if seal_door:
                    self.assertIsNone(path)
                    self.assertEqual(cost, "unreachable")
                else:
                    self.assertTrue(path.goalOnMesh)
                    self.assertGreater(cost, math.hypot(end.x - start.x, end.y - start.y))
                    for i in range(2, len(path) + 1):
                        a, b = path[i - 1], path[i]
                        self.assert_clear_segment((a.x, a.y), (b.x, b.y))

    def test_exact_endpoint_metadata_uses_the_cell_and_height_the_search_reached(self):
        h, terrain = self.routing_grid()
        grid = h.ns.PathingNamespace.PathGrid
        start = h.table({"x": 38, "y": 62, "z": 12})
        goal = h.table({"x": 54, "y": 86, "z": 12})
        k, cell = grid.locate(terrain, goal.x, goal.y)
        terrain.z[k][cell + 1] = 20
        node, gap = grid.surface(terrain, k, cell, -1, goal.z)
        self.assertEqual(node, cell)
        self.assertLessEqual(gap, grid.ZTOL)
        self.assertNotEqual(grid.snap(terrain, k, cell, goal.x, goal.y, goal.z), cell)
        for height, exact in ((12, False), (20, True), (40, False), (None, True)):
            with self.subTest(height=height):
                goal.z = height
                path, cost, _ = h.ns.PathingNamespace.Path.FindSync(0, start, goal)
                self.assertGreater(cost, 0)
                self.assertEqual((path[len(path)].x, path[len(path)].y), (goal.x, goal.y))
                self.assertEqual(path.goalOnMesh, exact)

    def test_snapped_start_across_a_fence_can_be_joined_after_walking_round_it(self):
        for joined_before_answer in (False, True):
            with self.subTest(joined_before_answer=joined_before_answer):
                h, terrain = self.routing_grid()
                grid = h.ns.PathingNamespace.PathGrid
                k, cell = grid.locate(terrain, 54, 86)
                terrain.z[k][cell + 1] = 20
                for gy in range(17, 25):
                    terrain.moves[0][12 * terrain.C + gy + 1] = 2  # fence at x=52, y=68..100
                start = h.table({"x": 54, "y": 86, "z": 20})
                end = h.table({"x": 38, "y": 86, "z": 12})
                find = h.ns.PathingNamespace.Path.FindSync
                path, _, _ = find(0, start, end)
                self.assertIsNone(path.meshStart)
                self.assertGreater(len(path), 2, "from this surface the real route goes around the fence")
                start.z = 12
                path, cost, _ = find(0, start, end)
                self.assertTrue(path.goalOnMesh)
                self.assertEqual((path[1].x, path[1].y), (54, 86))
                self.assertEqual((path.meshStart.x, path.meshStart.y, path.meshStart.z), (50, 86, 12))
                goal = h.point(end.x)
                goal.y, goal.z = end.y / 1000, end.z
                h.s.x, h.s.y, h.s.z = start.x, start.y, start.z
                h.w.Resolve(h.w, goal)
                first_job = h.s.jobs[1]
                if joined_before_answer:
                    # A legal walk goes round the end of the fence while the engine is busy.
                    positions = [(54, y) for y in (90, 94, 98, 102)]
                    positions += [(50, y) for y in (102, 98, 94, 90, 86)]
                    for position in positions:
                        h.s.x, h.s.y, h.s.now = *position, h.s.now + .6
                        h.w.Resolve(h.w, goal)
                first_job.callback(path, cost)
                point = h.w.Resolve(h.w, goal)
                if joined_before_answer:
                    self.assertTrue(point.walking)
                    self.assertEqual((point.walkingWorld.north, point.walkingWorld.west), (38, 86))
                    self.assertEqual(h.s.finds, 1, "the character already reached the computed route")
                elif point.walkingWorld:
                    aim = point.walkingWorld
                    if aim.north <= 52:
                        crossing = 86 + (aim.west - 86) * (52 - 54) / (aim.north - 54)
                        self.assertFalse(68 <= crossing < 100, "initial direction crosses the fence")
                else:
                    self.assertTrue(point.navigationBlocked)

    def test_legal_lateral_drift_cannot_send_the_arrow_through_a_wall(self):
        h, goal, _ = self.follow(self.door_route, open_road=True, configure_terrain=self.building)
        for position in ((38, 62), (42, 66), (46, 70)):
            h.s.x, h.s.y, h.s.now = *position, h.s.now + .7
            point = h.w.Resolve(h.w, goal)
            if point.walkingWorld:
                self.assert_ray_clear(position, point)
            else:
                self.assertTrue(point.navigationBlocked)
                self.assertTrue(h.w.pending)

    def test_shortcut_at_the_corner_needs_an_open_crossing_even_if_all_cells_are_dry(self):
        def railing(terrain):
            # A thin railing runs along y=64 from x=48 to x=68. Cells on
            # either side remain dry; only the edges crossing the railing close.
            for gx in range(12, 17):
                edge = gx * 128 + 15 + 1
                terrain.moves[0][edge] = 9  # close +y and +x,+y
                terrain.moves[0][edge + 1] = 7  # close +x,-y

        for blocked in (False, True):
            with self.subTest(railing=blocked):
                h, goal, _ = self.follow(self.door_route, open_road=True,
                                         configure_terrain=railing if blocked else None)
                for x in (38, 45, 55, 63, 66, 67.2):
                    h.s.x, h.s.y, h.s.now = x, 62, h.s.now + .7
                    point = h.w.Resolve(h.w, goal)
                aim = point.walkingWorld
                self.assertIsNotNone(aim)
                if blocked and aim.west > 64:
                    crossing_x = x + (aim.north - x) * (64 - 62) / (aim.west - 62)
                    self.assertFalse(48 <= crossing_x < 68, "the diagonal crosses the closed edge")
                if not blocked:
                    self.assertGreater(aim.west, 64, "walkable open ground permits this corner cut")

    def test_long_certified_segment_has_stable_intermediate_targets_before_arrival(self):
        start, end = 32, 352
        h, goal, first = self.follow([(start, 64, 12), (end, 64, 12)], open_road=True)
        first_aim = first.walkingWorld.north
        self.assertGreater(first_aim - start, 44)
        self.assertLessEqual(first_aim - start, 70)
        self.assertFalse(first.walkingFinal)
        targets = [first_aim]
        for x in range(start + 4, end, 4):
            h.s.x, h.s.now = x, h.s.now + .6
            result = h.w.Resolve(h.w, goal)
            aim = result.walkingWorld.north
            self.assertGreater(aim, x, "the arrow must lead me down the segment")
            self.assertLessEqual(aim - x, 70)
            self.assertEqual(result.walkingWorld.west, 64)
            self.assertAlmostEqual(result.walkingDistance, end - x)
            self.assertEqual(bool(result.walkingFinal), aim == end)
            if aim < end:
                self.assertAlmostEqual(result.walkingSegmentDistance, aim - x)
            else:
                self.assertIsNone(result.walkingSegmentDistance)
            if x < start + 20:
                self.assertEqual(aim, first_aim, "the first target should stay fixed")
            if aim != targets[-1]:
                self.assertGreater(aim, targets[-1])
                targets.append(aim)
        self.assertEqual(targets[-1], end)
        self.assertLessEqual(len(targets), 8, "avoid a new arrow target every few yards")
        self.assertEqual(h.ns.char.progress.g.cursor, 21)

    def test_two_sustained_moderate_bends_are_announced_in_order(self):
        # A 26.6-degree change persists for 54 yards and then straightens.
        route = [(x, 64, 12) for x in range(32, 97, 8)]
        route += [(96 + 8 * i, 64 + 4 * i, 12) for i in range(1, 7)]
        route += [(x, 88, 12) for x in range(152, 217, 8)]
        h, goal, _ = self.follow(route, open_road=True)
        turns = []
        for p, q in zip(route, route[1:]):
            for fraction in (0, .5):
                h.s.x, h.s.y = (p[i] + (q[i] - p[i]) * fraction for i in (0, 1))
                h.s.now += .6
                result = h.w.Resolve(h.w, goal)
                if result.walkingTurn and (not turns or turns[-1] != result.walkingTurn):
                    turns.append(result.walkingTurn)
        self.assertEqual(turns, ["left", "right"])

    def test_short_moderate_zigzags_do_not_create_turns(self):
        route = [(32, 64, 12), (48, 64, 12), (64, 64, 12), (72, 68, 12),
                 (80, 68, 12), (88, 64, 12), (104, 64, 12), (120, 64, 12)]
        h, goal, first = self.follow(route, open_road=True)
        self.assertIsNone(first.walkingTurn)
        for x, y, _ in route[1:-1]:
            h.s.x, h.s.y, h.s.now = x, y, h.s.now + 2
            self.assertIsNone(h.w.Resolve(h.w, goal).walkingTurn)

    def test_release_old_leg_when_refresh_has_lost_its_corridor(self):
        h, goal, _ = self.follow([(32, 32, 12), (48, 32, 12), (96, 32, 12), (96, 80, 12)], dynamic=True)
        h.s.x, h.s.y, h.s.now = 41, 45, 3
        goal.y += .010
        result = h.w.Resolve(h.w, goal)
        self.assertTrue(h.w.pending)
        self.assertTrue(result.navigationBlocked)
        self.assertIsNone(result.walkingWorld)
        self.assertIsNone(result.walkingTurn)

    def test_seven_yard_segments_aim_ahead_without_marking_arrival_or_losing_distance(self):
        for mesh in (True, False):
            with self.subTest(mesh=mesh):
                h, _, point = self.follow([(0, 0, 0), (7, 0, 0), (14, 0, 0), (21, 0, 0), (80, 0, 0)], mesh)
                self.assertEqual(point.walkingWorld.north, 36)
                self.assertEqual(point.walkingIndex, 2)
                self.assertEqual(h.w.index, 2)
                self.assertEqual(h.w.progress, 0)
                self.assertEqual(point.walkingDistance, 80)
                self.assertFalse(point.walkingFinal)

    def test_gentle_bend_can_share_a_mesh_corridor_but_not_cut_into_another_cell(self):
        for bend_y, expected in ((2.6, 36), (4.1, 10)):
            with self.subTest(bend_y=bend_y):
                _, _, point = self.follow([(0, 3.8, 0), (10, bend_y, 0), (40, 3.8, 0)])
                if expected == 10:
                    self.assertEqual((point.walkingWorld.north, point.walkingWorld.west), (10, bend_y))
                else:
                    self.assertGreater(point.walkingWorld.north, 35)
                self.assertAlmostEqual(point.walkingDistance,
                                       math.hypot(10, bend_y - 3.8) + math.hypot(30, bend_y - 3.8))

    def test_turns_and_height_changes_keep_the_real_bend(self):
        for nodes in ([(0, 0, 0), (7, 0, 0), (7, 40, 0)],
                      [(0, 0, 0), (7, 0, 0), (30, 0, 15)],
                      [(0, 0, 0), (7, 0, -4), (40, 0, 0)]):
            with self.subTest(nodes=nodes):
                _, _, point = self.follow(nodes)
                self.assertEqual((point.walkingWorld.north, point.walkingWorld.west, point.z), nodes[1])

    def test_aiming_at_the_last_node_does_not_consume_the_last_segment(self):
        h, goal, point = self.follow([(0, 0, 0), (7, 0, 0), (25, 0, 0)])
        self.assertEqual(point.walkingWorld.north, 25)
        self.assertFalse(point.walkingFinal)
        h.s.x, h.s.now = 7, 1
        point = h.w.Resolve(h.w, goal)
        self.assertTrue(point.walkingFinal)
        self.assertEqual(point.walkingIndex, 3)
        self.assertEqual(point.walkingDistance, 18)

    def test_npc_with_unknown_height_uses_mapped_nodes_then_the_exact_final_destination(self):
        h, goal, point = self.follow([(0, 0, 12), (7, 0, 12), (21, 0, 12), (46, 0, None)])
        self.assertEqual(point.walkingWorld.north, 21)
        self.assertEqual(point.walkingDistance, 46)
        self.assertEqual(point.walkingIndex, 2)
        self.assertFalse(point.walkingFinal)
        for x in (7, 14, 21):
            h.s.x, h.s.now = x, x / 7
            point = h.w.Resolve(h.w, goal)
        self.assertTrue(point.walkingFinal)
        self.assertEqual(point.walkingWorld.north, 46)
        self.assertIsNone(point.z)
        self.assertEqual(point.walkingGoal.x, goal.x)


if __name__ == "__main__":
    unittest.main()
