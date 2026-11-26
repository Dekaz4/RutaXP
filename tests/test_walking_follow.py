"""Whole walks at 7 yd/s reveal follower faults missed by a first-point test."""

import math
import unittest

from test_access_navigation import AccessHost, DWARF


def length(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def blend(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def samples(points, speed=7, interval=.1):
    """A constant-speed walk, retaining the direction of the current segment."""
    remainder = 0.0
    for a, b in zip(points, points[1:]):
        distance = length(a, b)
        if distance < .001:
            continue
        along = remainder
        while along < distance:
            yield blend(a, b, along / distance), ((b[0] - a[0]) / distance, (b[1] - a[1]) / distance)
            along += speed * interval
        remainder = along - distance
    yield points[-1], (0, 0)


def cut_corners(points, radius):
    out = [points[0]]
    for a, b, c in zip(points, points[1:], points[2:]):
        before = min(radius, length(a, b) * .4)
        after = min(radius, length(b, c) * .4)
        out.append(blend(b, a, before / length(a, b)))
        out.append(blend(b, c, after / length(b, c)))
    return out + [points[-1]]


def lateral_drift(points, offset):
    out = [points[0]]
    for a, b, c in zip(points, points[1:], points[2:]):
        ux, uy = (b[0] - a[0]) / length(a, b), (b[1] - a[1]) / length(a, b)
        vx, vy = (c[0] - b[0]) / length(b, c), (c[1] - b[1]) / length(b, c)
        nx, ny = -(uy + vy), ux + vx
        scale = offset / math.hypot(nx, ny)
        out.append((b[0] + nx * scale, b[1] + ny * scale, b[2]))
    return out + [points[-1]]


class FollowHost:
    def __init__(self):
        self.host = AccessHost(DWARF, 13, 2, x=.312, y=.679, terrain=True)
        self.h, self.ns, self.s = self.host.h, self.host.ns, self.host.s
        self.w = self.ns.Walking
        self.semantic = self.host.point()
        self.ns.GetArrowWaypoint(self.ns, self.host.step)
        self.host.pump()
        native = self.w.points
        self.route = []
        last_height = native[2].z
        for index in range(1, len(native) + 1):
            node = native[index]
            last_height = node.z if node.z is not None else last_height
            self.route.append((node.x, node.y, last_height))
        self.before = self.host.progress()
        self.h.g.FOLLOW_PATH = self.host.engine
        self.h.lua.execute('''
            TEST.walkSearches=0
            local find=FOLLOW_PATH.Find
            FOLLOW_PATH.Find=function(...)
              TEST.walkSearches=TEST.walkSearches+1;return find(...)
            end
        ''')

    def place(self, position):
        point = self.ns.WorldToWaypoint(self.ns, 0, position[0], position[1], 1426)
        assert point is not None
        self.s.x, self.s.y, self.s.height = point.x, point.y, position[2]

    def observe(self, position, motion=(0, 0), height_noise=0, interval=.1):
        self.place((position[0], position[1], position[2] + height_noise))
        self.s.now += interval
        arrow = self.ns.GetArrowWaypoint(self.ns, self.host.step)
        if not arrow or not arrow.walking:
            return {"phase": self.w.GetStatus(self.w).phase, "arrow": arrow}
        _, north, west = self.ns.GetWaypointWorldPosition(self.ns, arrow)
        dx, dy = north - position[0], west - position[1]
        distance = math.hypot(dx, dy)
        dot = (dx * motion[0] + dy * motion[1]) / distance if distance > .001 else 1
        return {"phase": "walking", "index": arrow.walkingIndex, "distance": distance,
                "dot": dot, "position": position, "target": (north, west), "arrow": arrow}

    def walk(self, route, noise=False):
        observations = []
        for index, (position, motion) in enumerate(samples(route)):
            observations.append(self.observe(position, motion, 3 * math.sin(index * .19) if noise else 0))
            self.host.pump()
        return observations

    def synthetic(self, route):
        """Adversarial contiguous corridors; only the terrain answer is a fixture."""
        self.w.Clear(self.w)
        self.route = route
        self.h.g.FOLLOW_CORRIDOR = self.h.table([
            {"map": 0, "x": x, "y": y, "z": z} for x, y, z in route
        ])
        self.h.lua.execute('''
            FOLLOW_PATH.Find=function(map,from,to,callback)
              TEST.walkSearches=TEST.walkSearches+1
              local job={}
              C_Timer.After(0,function()
                if not job.cancelled then callback(FOLLOW_CORRIDOR,500,job) end
              end)
              return job
            end
        ''')
        self.place(route[0])
        self.ns.GetArrowWaypoint(self.ns, self.host.step)
        self.host.pump()
        self.s.walkSearches = 0


class CompleteWalkingFollowTests(unittest.TestCase):
    def test_entire_real_gozwin_polyline_with_height_noise_reaches_the_final_target(self):
        f = FollowHost()
        observations = f.walk(f.route, noise=True)
        bad = [o for o in observations if o.get("distance", 0) > 7 and o.get("dot", 1) < -.25]
        self.assertEqual(bad, [], str(bad[:2]))
        self.assertEqual(f.s.walkSearches, 0)
        self.assertTrue(observations[-1]["arrow"].walkingFinal)
        self.assertEqual(f.host.progress(), f.before)

    def test_normal_corner_cuts_do_not_make_the_arrow_point_back_for_seconds(self):
        for radius in (6, 8, 12):
            with self.subTest(radius=radius):
                f = FollowHost()
                observations = f.walk(cut_corners(f.route, radius), noise=True)
                backward = [o for o in observations if o.get("distance", 0) > 7 and o.get("dot", 1) < -.25]
                self.assertLessEqual(len(backward), 3, str(backward[:2]))
                self.assertLessEqual(f.s.walkSearches, 1)
                self.assertTrue(observations[-1]["arrow"].walkingFinal)
                self.assertEqual(f.host.progress(), f.before)

    def test_moving_during_async_search_does_not_send_the_player_back_to_its_old_origin(self):
        f = FollowHost()
        f.w.Clear(f.w)
        f.observe(f.route[0])
        trajectory = list(samples(f.route, interval=1 / 30))
        # A search can take 35 frames. The character keeps walking while its
        # callbacks are queued; publishing the old origin must not turn them back.
        for position, motion in trajectory[:35]:
            f.observe(position, motion, interval=1 / 30)
        f.host.pump()
        position, motion = trajectory[35]
        answer = f.observe(position, motion, interval=1 / 30)
        self.assertTrue(answer["arrow"].navigationBlocked or answer.get("dot", 1) >= -.25, str(answer))
        self.assertEqual(f.host.progress(), f.before)

    def test_small_lateral_drift_on_the_real_route_does_not_aim_at_a_missed_vertex(self):
        f = FollowHost()
        observations = f.walk(lateral_drift(f.route, 7), noise=True)
        backward = [o for o in observations if o.get("distance", 0) > 7 and o.get("dot", 1) < -.25]
        self.assertLessEqual(len(backward), 3, str(backward[:2]))
        self.assertLessEqual(f.s.walkSearches, 2)
        self.assertTrue(observations[-1]["arrow"].walkingFinal)
        self.assertEqual(f.host.progress(), f.before)

    def test_twelve_yard_corner_cut_in_a_right_angle_corridor_does_not_hold_an_old_vertex(self):
        f = FollowHost()
        x, y, z = f.route[0]
        route = [(x, y, z), (x + 80, y, z), (x + 80, y + 80, z), f.route[-1]]
        f.synthetic(route)
        observations = f.walk(cut_corners(route, 12))
        backward = [o for o in observations if o.get("distance", 0) > 7 and o.get("dot", 1) < -.25]
        self.assertLessEqual(len(backward), 3, str(backward[:2]))
        self.assertLessEqual(f.s.walkSearches, 1)
        self.assertEqual(f.host.progress(), f.before)

    def test_nearby_return_corridor_of_a_u_shape_does_not_become_the_next_segment(self):
        f = FollowHost()
        x, y, z = f.route[0]
        f.synthetic([(x, y, z), (x + 100, y, z), (x + 100, y + 10, z),
                     (x, y + 10, z), f.route[-1]])
        # The later return corridor is only one yard away. A nearest-segment
        # search would cross its separating wall and discard the whole U.
        for distance in range(1, 9):
            answer = f.observe((x + distance, y + 9, z), (1, 0))
            if answer["phase"] == "walking":
                self.assertLessEqual(answer["index"], 2, str(answer))
        self.assertEqual(f.host.progress(), f.before)

    def test_parallel_corridor_on_a_higher_floor_is_not_reached_by_matching_xy(self):
        f = FollowHost()
        x, y, z = f.route[0]
        f.synthetic([(x, y, z), (x + 40, y, z), (x + 40, y + 8, z + 40),
                     (x, y + 8, z + 40), f.route[-1]])
        for distance in range(0, 40):
            answer = f.observe((x + distance, y, z), (1, 0))
        answer = f.observe((x + 40, y + 8, z))
        if answer["phase"] == "walking":
            self.assertLessEqual(answer["index"], 3)
        self.assertFalse(bool(answer["arrow"].walkingFinal))
        self.assertEqual(f.host.progress(), f.before)

    def test_falling_defers_the_search_until_landing_on_the_real_gozwin_route(self):
        f = FollowHost()
        f.w.Clear(f.w)
        f.h.g.IsFalling = f.h.lua.eval("function() return TEST.falling==true end")
        f.s.falling = True
        for _ in range(5):
            answer = f.observe(f.route[0], height_noise=20)
            self.assertEqual(answer["phase"], "pending")
            self.assertTrue(answer["arrow"].navigationBlocked)
        self.assertEqual(f.s.walkSearches, 0)
        self.assertIsNone(f.w.job)
        f.s.falling = False
        f.observe(f.route[0])
        self.assertEqual(f.s.walkSearches, 1)
        f.host.pump()
        landed = f.observe(f.route[0])
        self.assertTrue(landed["arrow"].walking)
        self.assertEqual(landed["phase"], "walking")
        self.assertEqual(f.host.progress(), f.before)

    def test_returning_behind_a_passed_corner_replans_instead_of_cutting_across_it(self):
        f = FollowHost()
        x, y, z = f.route[0]
        f.synthetic([(x, y, z), (x + 100, y, z), (x + 100, y + 100, z)])
        f.walk([(x, y, z), (x + 100, y, z), (x + 100, y + 20, z)])
        self.assertEqual(f.w.index, 3)
        f.s.walkSearches = 0
        f.s.now += 3
        f.observe((x + 100, y + 5, z), (0, -1))
        answer = f.observe((x + 80, y, z), (-1, 0))
        self.assertTrue(answer["arrow"].navigationBlocked)
        self.assertEqual(f.s.walkSearches, 1)
        self.assertIsNotNone(f.w.job)
        self.assertEqual(f.host.progress(), f.before)


if __name__ == "__main__":
    unittest.main()
