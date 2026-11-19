"""Check solo routing against the shipped quests and their auxiliary waypoints."""
import unittest

from test_quest_engine import QuestEngineHost


class UnmatchedSoloNavigationTests(unittest.TestCase):
    def setUp(self):
        self.h = QuestEngineHost(catalog=True)
        self.h.state.faction = "Horde"
        self.h.state.raceToken = "Orc"
        self.h.state.level = 55
        self.h.initialize()
        self.h.ns.char.auto = False
        self.h.lua.execute("TEST.bags = {}; C_Item = {GetItemCount=function(id) return TEST.bags[id] or 0 end}")

    def visit(self, slug, number):
        guide_id = "forever/" + self.h.state.faction.lower() + "/" + slug
        self.h.call("SelectGuide", guide_id)
        state = self.h.call("GetProgress", guide_id)
        state.cursor = number
        step = self.h.ns.guides[guide_id].steps[number]
        return [(goal, self.h.status(goal, step, state, i)) for i, goal in step.goals.items()]

    def status(self, slug, number, **fields):
        return next(status for goal, status in self.visit(slug, number)
                    if all(goal[key] == value for key, value in fields.items()))

    def test_gadgetzan_uses_only_the_five_spare_pouches(self):
        slug = "40-50/02-feralas"
        self.h.quest(1707, onQuest=True, complete=False)
        self.h.state.bags[8483] = 4
        self.assertEqual(self.status(slug, 12, t="collect", quest=1707), "active")
        self.h.state.bags[8483] = 5
        self.assertEqual(self.status(slug, 12, t="collect", quest=None, item=8483), "skip")
        self.h.state.bags[8483] = 0
        self.h.quest(1707, delivered=True)
        self.assertEqual(self.status(slug, 13, t="accept", quest=1878), "skip")
        self.h.state.bags[8483] = 4
        self.assertEqual(self.status(slug, 13, t="accept", quest=1878), "skip")
        self.h.state.bags[8483] = 5
        self.assertEqual(self.status(slug, 13, t="accept", quest=1878), "active")

    def test_noboru_patrol_can_be_bypassed_and_found_cudgel_can_be_used(self):
        slug = "40-50/01-stranglethorn-vale"
        self.assertEqual([status for _, status in self.visit(slug, 34)], ["skip", "skip", "skip"])
        self.h.state.bags[6196] = 1
        self.assertEqual([status for _, status in self.visit(slug, 34)], ["done", "done", "active"])
        self.h.state.bags[6196] = 0
        self.h.quest(1392, onQuest=True, complete=True)
        self.assertEqual(self.status(slug, 37, t="turnin", quest=1392), "active")

    def test_alliance_crystals_share_the_camp_with_the_optional_cudgel(self):
        self.h.state.faction, self.h.state.raceToken = "Alliance", "Human"
        self.h.quest(1389, onQuest=True, complete=False)
        slug = "30-40/05-arathi-highlands"
        self.assertEqual(self.status(slug, 6, t="collect", quest=1389), "active")
        self.assertEqual(self.status(slug, 6, t="collect", item=6196), "skip")
        self.h.state.bags[6196] = 1
        self.assertEqual(self.status(slug, 6, t="collect", item=6196), "done")
        self.assertEqual(self.status(slug, 6, t="accept", quest=1392), "active")

    def test_egg_only_flights_follow_the_quest_but_the_shared_flight_survives(self):
        first = "50-60/05-eastern-plaguelands"
        later = "50-60/06-silithus"
        self.assertNotIn(self.status(first, 26, t="fly", location="Gadgetzan"), ("done", "skip"))
        self.assertEqual(self.status(first, 30, t="fly", location="Campamento Mojache"), "skip")
        self.assertEqual(self.status(later, 23, t="fly", location="Gadgetzan"), "skip")
        self.h.ns.char.optional = True
        self.h.quest(2741, onQuest=True, complete=False)
        self.assertNotIn(self.status(first, 30, t="fly", location="Campamento Mojache"), ("done", "skip"))
        self.h.ns.char.optional = False
        self.h.quest(2741, onQuest=True, complete=True)
        self.assertIn(self.status(first, 30, t="fly", location="Campamento Mojache"), ("skip", "done"))
        self.h.state.bags[8564] = 1
        self.assertIn(self.status(first, 30, t="fly", location="Campamento Mojache"), ("skip", "done"))
        self.assertIn(self.status(first, 30, t="collect", quest=2741), ("skip", "done"))
        self.assertNotIn(self.status(later, 23, t="fly", location="Gadgetzan"), ("done", "skip"))
        self.assertEqual(self.status(later, 23, t="turnin", quest=2741), "active")
        self.h.quest(2741, delivered=True)
        self.assertEqual(self.status(later, 23, t="fly", location="Gadgetzan"), "done")

    def test_two_elixir_beaches_are_skipped_and_still_reachable_by_choice(self):
        slug = "30-40/01-desolace"
        self.h.quest(515, onQuest=True, complete=False)
        for number in (37, 38):
            self.assertEqual(self.status(slug, number, t="goto"), "skip")
            self.assertEqual(self.status(slug, number, t="collect", quest=515), "skip")
        self.h.ns.char.optional = True
        for number in (37, 38):
            self.assertEqual(self.status(slug, number, t="goto"), "active")
            self.assertEqual(self.status(slug, number, t="collect", quest=515), "active")
        self.h.ns.char.optional = False
        self.h.quest(515, onQuest=True, complete=True)
        for number in (37, 38):
            self.assertIn(self.status(slug, number, t="goto"), ("done", "skip"))
        self.assertEqual(self.status(slug, 39, t="turnin", quest=515), "active")
