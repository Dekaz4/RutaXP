import json
import unittest
from unittest.mock import patch

from tools import build_early_quest_offers as builder


class EarlyOfferCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guides = json.loads((builder.ROOT / "RutaXP/Source/leveling.json").read_bytes())["guides"]
        cls.timing = json.loads(builder.EVIDENCE.read_bytes())
        cls.allowed, cls.deferred, cls.alternatives = builder.classify(cls.guides, cls.timing)

    def test_every_npc_offer_in_every_shipped_chapter_has_one_decision_offline(self):
        with patch.object(builder, "urlopen", side_effect=AssertionError("unexpected network access")):
            self.assertEqual(builder.render(self.allowed, self.deferred, self.alternatives),
                             builder.OUTPUT.read_text(encoding="utf8"))
        self.assertTrue(self.allowed.isdisjoint(self.deferred))
        self.assertEqual(self.allowed | self.deferred.keys(), builder.npc_quests(self.guides))
        self.assertEqual(len(self.guides), 57)
        for guide in self.guides:
            with self.subTest(guide=guide["id"]):
                ids = builder.npc_quests([guide])
                self.assertTrue(ids & self.allowed)
                self.assertLessEqual(ids, self.allowed | self.deferred.keys())

    def test_normal_npc_quests_do_not_require_old_or_cached_objective_signatures(self):
        # Multiple givers, recipe, unique watch, ordinary exploration, taming
        # item, a #3381 transport offered *after* bringing feathers, and a
        # contact introducing (but not starting) a future escort.
        for quest in (109, 36, 64, 151, 89, 62, 6064, 3381, 979, 87318):
            self.assertIn(quest, self.allowed)
        self.assertNotIn(2781, self.allowed)  # Wanted poster, not an NPC offer.
        self.assertNotIn(91777, self.allowed)  # Separate explicitly optional off-route errand.

    def test_immediate_escorts_scenes_duels_timers_and_decaying_items_are_deferred(self):
        for q in (219, 665, 836, 994, 5321, 6641, 99144, 99053):
            self.assertEqual(self.deferred[q], "escort")
        for q in (1090, 1640, 4966):
            self.assertEqual(self.deferred[q], "event")
        self.assertEqual(self.deferred[1395], "perishable")
        self.assertEqual(self.deferred[3364], "timer")
        self.assertEqual(self.deferred[1149], "transport")
        self.assertTrue(any(reason == "pvp" for reason in self.deferred.values()))

    def test_real_live_flags_are_distinct_from_count_group_and_item_on_acceptance(self):
        row = {"questInfoId": 1, "startItemId": 1234, "flags": 8,
               "objectives": [{"type": "gameObject", "objectId": 32, "amount": 1}]}
        self.assertEqual(list(builder.live_reasons(row)), [])
        for extra, reason in (({"timeLimitSeconds": 60}, "timer"), ({"questInfoId": 84}, "escort"),
                              ({"flags": 0x2000}, "pvp"), ({"flags": 1}, "survival"),
                              ({"flags": 0x1000}, "repeatable")):
            self.assertIn(reason, builder.live_reasons(dict(row, **extra)))

    def test_ordinary_future_quests_from_new_npcs_do_not_need_an_individual_exception(self):
        guide = {"steps": [{"goals": [{"t": "accept", "quest": 120000, "npc": 12, "optional": True},
                                      {"t": "accept", "quest": 120001, "object": 83, "closedBy": [120000]},
                                      {"t": "accept", "quest": 120002, "npc": 11}]}]}
        facts = {"sources": {}, "positiveExclusiveGroups": [[120002, 120001, 17]]}
        allowed, deferred, alternatives = builder.classify([guide], facts)
        self.assertEqual(allowed, {120000, 120002})
        self.assertEqual(deferred, {})
        self.assertEqual(alternatives[120000], {120001})  # Directional, not the reverse.
        self.assertEqual(alternatives[120002], {120001})  # A planned object victim counts too.
        self.assertNotIn(17, alternatives)

    def test_all_conditional_alternatives_refer_to_an_actual_acceptance(self):
        all_planned = {r["quest"] for g in self.guides for r in builder.pickups(g)}
        for q, victims in self.alternatives.items():
            self.assertNotIn(q, victims)
            self.assertLessEqual(victims, all_planned)
        self.assertIn(4641, self.alternatives[788])  # Preserve the starter breadcrumb if it comes first.
