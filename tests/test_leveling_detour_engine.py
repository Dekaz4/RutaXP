"""The solo itinerary, journal plan and NPC offers must agree on costly errands."""
import unittest

from test_quest_engine import ADDON, QuestEngineHost


class LevelingDetourEngineTests(unittest.TestCase):
    def host(self):
        h = QuestEngineHost()
        for name in ("TrackerPreview", "QuestOfferAdvice"):
            h.load((ADDON / (name + ".lua")).read_text(encoding="utf8"), "RutaXP", h.ns)
        return h

    def test_ready_bundle_rechecks_each_item_and_real_prerequisites(self):
        h = self.host()
        requirements = {"levelingDetour": True, "optional": True, "detourItems": {"12": 3, "13": 2}}
        h.group([{"t": "accept", "quest": 201, "minLevel": 30, "preAll": [199, 200], **requirements},
                 {"t": "turnin", "quest": 201, **requirements}, {"t": "accept", "quest": 202}])
        h.initialize()
        h.lua.execute("bags={[12]=3,[13]=1}; C_Item={GetItemCount=function(id, bank) assert(bank==false); return bags[id] or 0 end}")
        h.quest(199, delivered=True)
        h.state.level = 30
        self.assertEqual(h.active()[0].quest, 202)
        h.lua.execute("bags[13]=2")
        self.assertFalse(h.call("WantsQuest", "accept", 201))
        self.assertEqual(h.active()[0].quest, 202)
        h.quest(200, delivered=True)
        h.state.level = 29
        self.assertEqual(h.active()[0].quest, 202)
        h.state.level = 30
        self.assertEqual(h.active()[0].quest, 201)
        self.assertTrue(h.call("WantsQuest", "accept", 201))
        self.assertEqual(h.call("GetQuestOfferAdvice", 201)[1], "ahora")
        self.assertFalse(h.call("WantsQuest", "turnin", 201))
        h.quest(201, onQuest=True, complete=False)
        self.assertFalse(h.call("WantsQuest", "turnin", 201))
        h.quest(201, onQuest=True, complete=True)
        self.assertTrue(h.call("WantsQuest", "turnin", 201))

    def test_journal_does_not_force_farm_but_a_finished_delivery_is_shown(self):
        h = self.host()
        detour = {"quest": 565, "levelingDetour": True}
        guide = h.group([{"t": "accept", "quest": 110}],
                        next_goals=[{"t": "collect", **detour}, {"t": "turnin", **detour},
                                    {"t": "turnin", "quest": 300}])
        h.quest(565, onQuest=True, complete=False)
        h.initialize()
        preview = lambda: [g for g in h.call("GetTrackerPlannedUpcomingItems", guide, 1, 12).values()
                           if g.questID == 565]
        self.assertEqual(preview(), [])
        self.assertEqual(h.status(guide.steps[2].goals[1], guide.steps[2]), "skip")
        h.quest(565, onQuest=True, complete=True)
        self.assertEqual([g.action for g in preview()], ["turnin"])
        self.assertEqual(h.status(guide.steps[2].goals[2], guide.steps[2]), "active")
        self.assertFalse(h.call("IsQuestDelivered", 565))

    def test_opt_in_duo_and_shared_travel(self):
        h = self.host()
        guide = h.group([{"t":"fly"}, {"t":"accept", "quest": 110, "levelingDetour": True}],
                        next_goals=[{"t":"accept", "quest": 111}])
        h.initialize()
        goal, step = guide.steps[1].goals[2], guide.steps[1]
        self.assertEqual(h.active()[0].t, "fly")
        self.assertEqual(h.status(goal, step), "skip")
        self.assertEqual(h.call("GetQuestOfferAdvice", 110)[1], "opcional")
        h.ns.char.optional = True
        self.assertEqual(h.status(goal, step), "active")
        h.ns.char.optional = False
        h.ns.char.duo = h.table({"enabled": True})
        self.assertEqual(h.status(goal, step), "active")

    def test_auxiliary_flight_does_not_return_after_consumed_handin(self):
        h = self.host()
        guide = h.group([{"t": "fly", "detourQuest": 3501, "levelingDetour": True, "detourItems": {"99": 1}},
                         {"t": "getfp"}])
        h.initialize()
        goal = guide.steps[1].goals[1]
        self.assertEqual(h.status(goal), "skip")
        h.lua.execute("C_Item={GetItemCount=function() return 1 end}")
        self.assertEqual(h.status(goal), "manual")
        h.quest(3501, delivered=True)
        self.assertEqual(h.status(goal), "skip")
        self.assertEqual(h.active()[0].t, "getfp")
