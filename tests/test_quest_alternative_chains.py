"""A closed alternative must not become an impossible required delivery later."""
import unittest

from test_quest_engine import QuestEngineHost


class AlternativeChainTests(unittest.TestCase):
    def test_shipping_alternatives_remain_closed_at_their_delivery(self):
        cases = [
            ('forever/alliance/human/01-elwynn-forest', 3, 2, 5261, 33),
            ('forever/alliance/dwarf-gnome/01-dun-morogh', 56, 6, 415, 413),
            ('forever/horde/50-60/01-un-goro-crater', 56, 3, 5241, 5211),
        ]
        for guide_id, si, gi, quest, alternative in cases:
            for delivered in (False, True):
                with self.subTest(guide=guide_id, delivered=delivered):
                    h = QuestEngineHost(catalog=True)
                    h.initialize()
                    h.ns.char.auto = False
                    h.ns.char.activeGuide = guide_id
                    state = h.call('GetProgress', guide_id)
                    state.cursor, state.placed = si, True
                    h.quest(alternative, onQuest=not delivered, flagged=delivered)
                    if delivered:
                        h.ns.turnedIn[alternative] = True
                    step = h.ns.guides[guide_id].steps[si]
                    self.assertEqual(h.status(step.goals[gi], step, state, gi), 'skip')
                    self.assertFalse(h.call('IsQuestDelivered', quest))
                    self.assertEqual(state.cursor, si)
                    h.quest(quest, onQuest=True, complete=False)
                    self.assertEqual(h.status(step.goals[gi], step, state, gi), 'active')

    def test_open_required_chain_is_still_blocked_if_abandoned(self):
        h = QuestEngineHost()
        guide = h.guide('alternative', steps=[
            {'title': 'Elegir rama', 'goals': [{'t': 'accept', 'quest': 100, 'closedBy': [101]}]},
            {'title': 'Hacer y entregar', 'goals': [{'t': 'complete', 'quest': 100}, {'t': 'turnin', 'quest': 100}]},
        ])
        h.initialize()
        h.ns.char.auto = False
        h.ns.char.activeGuide = 'alternative'
        state = h.call('GetProgress', 'alternative')
        state.cursor = 2
        step = h.ns.guides['alternative'].steps[2]
        self.assertEqual(h.status(step.goals[1], step, state, 1), 'blocked')
        h.quest(101, onQuest=True)
        self.assertEqual(h.status(step.goals[1], step, state, 1), 'skip')
        self.assertEqual(h.status(step.goals[2], step, state, 2), 'skip')
        h.quest(100, onQuest=True)
        self.assertEqual(h.status(step.goals[1], step, state, 1), 'active')
        self.assertFalse(h.call('IsQuestDelivered', 100))

    def test_unrelated_class_or_later_accept_cannot_close_the_current_chain(self):
        h = QuestEngineHost()
        h.guide('scoped', steps=[
            {'title': 'Inicio', 'goals': [{'t': 'accept', 'quest': 100},
                       {'t': 'accept', 'quest': 100, 'closedBy': [101], 'only': {'classes': ['MAGE']}}]},
            {'title': 'Entrega', 'goals': [{'t': 'turnin', 'quest': 100}]},
            {'title': 'Otra visita', 'goals': [{'t': 'accept', 'quest': 100, 'closedBy': [101]}]},
        ])
        h.initialize()
        h.ns.char.auto = False
        h.ns.char.activeGuide = 'scoped'
        state = h.call('GetProgress', 'scoped')
        state.cursor = 2
        h.quest(101, onQuest=True)
        step = h.ns.guides['scoped'].steps[2]
        self.assertEqual(h.status(step.goals[1], step, state, 1), 'blocked')


if __name__ == '__main__':
    unittest.main()
