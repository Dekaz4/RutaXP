"""Observed adjacent corner cuts must not exhaust a whole-route arc budget."""

import unittest

from test_walking_follow import FollowHost, cut_corners, samples


class WalkingCornerBudgetTests(unittest.TestCase):
    def test_repeated_twelve_yard_corner_cuts_keep_the_next_turn_ahead(self):
        f = FollowHost()
        x, y, z = f.route[0]
        route = [(x, y, z)]
        for index in range(8):
            if index % 2:
                y += 60
            else:
                x += 60
            route.append((x, y, z))
        # The supplied corridor is a topology fixture; the real runtime,
        # coordinate conversion, follower and progress engine are unchanged.
        f.synthetic(route)
        semantic_target = (f.w.target.x, f.w.target.y, f.w.target.z)
        backwards, blocked = [], []
        last = None
        for frame, (position, motion) in enumerate(samples(cut_corners(route, 12))):
            last = f.observe(position, motion)
            if last["phase"] != "walking":
                blocked.append((frame / 10, last["phase"]))
                break  # Do not fabricate a replan answer from the old origin.
            if last["distance"] > 3 and last["dot"] < -.25:
                backwards.append((frame / 10, last["index"], last["distance"], last["dot"]))
        self.assertEqual(blocked, [], str(backwards[:3]))
        self.assertEqual(backwards, [])
        self.assertEqual(f.s.walkSearches, 0)
        self.assertTrue(last["arrow"].walkingFinal)
        self.assertEqual((f.w.target.x, f.w.target.y, f.w.target.z), semantic_target)
        self.assertEqual(f.host.progress(), f.before)

    def test_stationary_refreshes_do_not_create_more_corner_travel_credit(self):
        f = FollowHost()
        x, y, z = f.route[0]
        f.synthetic([(x, y, z), (x + 60, y, z), (x + 60, y + 10, z),
                     (x, y + 10, z)])
        # Adjacent return corridor is close in XY but the first end has not
        # been reached. Repeated UI reads must not march the budget forward.
        for offset in range(1, 10):
            f.observe((x + offset, y + 9, z), (1, 0))
        index = f.w.index
        for _ in range(50):
            arrow = f.observe((x + 9, y + 9, z), (0, 0))
            self.assertEqual(arrow["index"], index)
            self.assertLessEqual(arrow["index"], 2)
        self.assertEqual(f.host.progress(), f.before)


if __name__ == "__main__":
    unittest.main()
