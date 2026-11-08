import json
import unittest
from unittest.mock import patch

from tools import build_early_quest_offers as builder


class EarlyOfferEvidenceTests(unittest.TestCase):
    def test_shipped_table_matches_offline_witnesses_and_the_current_guides(self):
        guides = json.loads((builder.ROOT / "RutaXP/Source/leveling.json").read_bytes())["guides"]
        with patch.object(builder, "urlopen", side_effect=AssertionError("unexpected download")):
            proofs = builder.snapshot()
            authored = builder.authored_signatures(guides)
            self.assertEqual(builder.render(authored, proofs), builder.OUTPUT.read_text(encoding="utf8"))
        self.assertTrue(all(authored.get(qid) == targets for qid, (_, targets) in proofs.items()))
        self.assertEqual(proofs[109][1], ())  # Direct report to Gryan
        self.assertEqual(proofs[4289][1], (-11480, -11479, -11478))  # Torwa's three samples
        for qid in (89, 1395, 2781, 5321, 91777):
            self.assertNotIn(qid, proofs)

    def test_live_schema_rejects_timer_start_items_unknown_flags_and_unusual_targets(self):
        row = {"questType": 2, "flags": 8,
               "objectives": [{"type": "monster", "objectId": 6, "amount": 10}]}
        self.assertEqual(builder.live_signature(row), {6: 10})
        for special in ({"timeLimitSeconds": 1}, {"startItemId": 1}, {"flags": 8192},
                        {"flagsEx": 1}, {"questInfoId": 1}, {"questType": 0},
                        {"objectives": [{"type": "item", "objectId": 6, "amount": 1}]},
                        {"objectives": [{"type": "gameObject", "objectId": 6, "amount": 2}]}):
            with self.subTest(special=special):
                self.assertIsNone(builder.live_signature(dict(row, **special)))

    def test_authored_changes_suspend_previously_proven_targets(self):
        work = {"t": "kill", "quest": 7, "npc": 6, "spots": [{}, {}]}
        def qualify(goal):
            goals = [{"t": "accept", "quest": 7}, goal, {"t": "turnin", "quest": 7}]
            return builder.authored_signatures([{"steps": [{"goals": goals}]}])
        self.assertEqual(qualify(work), {7: (6,)})
        for change in ({"fromRank": 1}, {"optional": True}, {"spots": [{}, {"alt": True}]},
                       {"t": "escort"}, {"count": 1}):
            with self.subTest(change=change):
                self.assertEqual(qualify(dict(work, **change)), {})
        new_target = qualify(dict(work, npc=100))
        self.assertNotIn("[7] = true", builder.render(new_target, builder.snapshot()))
