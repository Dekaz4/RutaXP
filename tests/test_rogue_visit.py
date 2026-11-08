import unittest

from test_quest_engine import QuestEngineHost


class RogueVisitTests(unittest.TestCase):
    def setup_visit(self, goals):
        host = QuestEngineHost()
        host.group(goals, id="forever/alliance/human/test")
        host.initialize()
        host.state.classToken, host.state.raceToken = "ROGUE", "Human"
        host.ns.char.auto = True
        host.lua.execute('function UnitGUID(unit) if unit == "npc" then return "Creature-0-1-2-3-111-ABC" end end')
        host.quest(99, onQuest=True, complete=True)
        return host

    def test_ready_turnin_is_suggested_only_during_same_town_visit(self):
        first = {"t": "accept", "npc": 222, "quest": 44}
        near = {"t": "turnin", "npc": 111, "quest": 99}
        h = self.setup_visit([first, near])
        self.assertEqual(h.active()[1], 2)
        h.quest(99, onQuest=True, complete=False)
        self.assertEqual(h.active()[1], 1)
        h.quest(99, onQuest=True, complete=True)
        h.lua.execute("function IsInGroup() return true end")
        self.assertEqual(h.active()[1], 1)
        h.lua.execute("function IsInGroup() return false end")
        h.state.classToken = "PALADIN"
        self.assertEqual(h.active()[1], 1)
        gate = self.setup_visit([first, {"t": "hearth", "location": "Auberdine"}, near])
        self.assertEqual(gate.active()[1], 1)
