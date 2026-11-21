import unittest

from test_quest_engine import QuestEngineHost


class GnomeWarlockPetRoute(unittest.TestCase):
    def setUp(self):
        h = self.host = QuestEngineHost(catalog=True)
        h.globals.TEST.classToken, h.globals.TEST.raceToken = "WARLOCK", "Gnome"
        h.globals.TEST.level = 40
        h.initialize()
        h.ns.char.auto = False

    def find(self, chapter, quest, action):
        h = self.host
        guide_id = "forever/alliance/" + chapter
        h.ns.char.activeGuide = guide_id
        state = h.call("GetProgress", guide_id)
        for si, step in h.ns.guides[guide_id].steps.items():
            for gi, goal in step.goals.items():
                if goal.quest == quest and goal.t == action:
                    state.cursor = si
                    return goal, step, state, gi
        self.fail((chapter, quest, action))

    def test_solo_skips_takar_and_all_later_branches_without_advancing_quests(self):
        h = self.host
        for chapter, quest, action in (
            ("04-redridge-mountains", 1716, "accept"),
            ("07-thousand-needles", 1716, "turnin"),
            ("07-thousand-needles", 1738, "accept"),
            ("07-thousand-needles", 65602, "accept"),
            ("30-40/02-desolace", 1738, "collect"),
            ("30-40/05-arathi-highlands", 1739, "accept"),
            ("30-40/05-arathi-highlands", 1739, "turnin"),
            ("30-40/05-arathi-highlands", 65603, "accept"),
        ):
            with self.subTest(quest=quest, action=action):
                self.assertEqual(h.status(*self.find(chapter, quest, action)), "skip")
                self.assertFalse(h.call("IsQuestDelivered", quest))

    def test_a_started_chain_or_incubus_in_the_log_keeps_its_objectives(self):
        h = self.host
        h.quest(1716, onQuest=True, complete=True)
        self.assertEqual(h.status(*self.find("07-thousand-needles", 1716, "turnin")), "active")
        h.quest(1716, delivered=True)
        self.assertEqual(h.status(*self.find("07-thousand-needles", 1738, "accept")), "active")
        for quest in (1738, 65602):
            h.quest(quest, onQuest=True)
            self.assertEqual(h.status(*self.find("30-40/02-desolace", quest, "collect")), "active")

    def test_optional_toggle_duo_and_other_warlock_races_keep_the_pickup(self):
        h = self.host
        args = self.find("04-redridge-mountains", 1716, "accept")
        h.ns.char.optional = True
        self.assertEqual(h.status(*args), "active")
        h.ns.char.optional = False
        h.ns.char.duo = h.table({"enabled": True})
        self.assertEqual(h.status(*args), "active")
        h.ns.char.duo.enabled = False
        h.globals.TEST.raceToken = "Human"
        self.assertEqual(h.status(*args), "active")

    def test_gakin_summons_only_point_to_stormwind(self):
        for chapter, quest in (("dwarf-gnome/01-dun-morogh", 1689),
                               ("human/01-elwynn-forest", 1689),
                               ("30-40/05-arathi-highlands", 1739)):
            goal, *_ = self.find(chapter, quest, "complete")
            self.assertEqual([point.map for point in goal.candidates.values()], [1453])
