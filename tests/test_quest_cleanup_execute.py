import unittest

from test_addon import ADDON, LuaRuntime


CLIENT = """
ns, StaticPopupDialogs, C_QuestLog = {}, {}, {}
ns.events = { HookScript = function(_, _, fn) onEvent = fn end }
selected, target, guide, step = 99, 0, "test", 12
present = {[1]=true, [2]=true, [3]=true, [99]=true}
offered, items, calls, messages, timers = {1, 2}, {}, {}, {}, {}
function ns:GetQuestCleanupPlan()
    local candidates = {}
    for _, id in ipairs(offered) do
        if present[id] then
            table.insert(candidates, {id=id, title='Quest '..id, reason='Grupo opcional'})
        end
    end
    return {guideID=guide, step=step, candidates=candidates,
        kept={{id=97,title='Misión útil',reason='Entrega pendiente'}},
        review={{id=98,title='Misión desconocida',reason='Sin clasificación'}}}
end
function ns:Print(s) table.insert(messages, s) end
function StaticPopup_Visible(name) return nativePopup and name == 'ABANDON_QUEST' or nil end
function StaticPopup_Show(name, n, list, data)
    popup, count, listing, snapshot = StaticPopupDialogs[name], n, list, data
    return {}
end
function InCombatLockdown() return combat end
function C_QuestLog.IsOnQuest(id) return present[id] == true end
function C_QuestLog.CanAbandonQuest(id) return id ~= denied end
function C_QuestLog.GetSelectedQuest() return selected end
function C_QuestLog.SetSelectedQuest(id) selected = id end
function C_QuestLog.SetAbandonQuest() target = wrongTarget or selected end
function C_QuestLog.GetAbandonQuest() return target end
function C_QuestLog.GetAbandonQuestItems() return items[target] end
function C_QuestLog.AbandonQuest() table.insert(calls, target) end
C_Timer = {After=function(_, fn) table.insert(timers, fn) end}
function tick() table.remove(timers, 1)() end
"""


class QuestCleanupExecutionTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(CLIENT)
        self.lua.execute((ADDON / "QuestCleanup.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.lua.globals().ns)
        self.run_lua = self.lua.execute
        self.eval = self.lua.eval

    def test_preview_lists_only_snapshot_and_cancel_makes_no_changes(self):
        self.run_lua("ns:ShowQuestCleanup()")
        self.assertEqual(self.eval("listing"), "Quest 1\nQuest 2")
        self.assertIn("Grupo opcional", self.eval("table.concat(messages, ' ' )"))
        self.run_lua("popup.OnCancel(nil, snapshot); popup.OnAccept(nil, snapshot)")
        self.assertEqual(self.eval("#calls"), 0)
        self.assertEqual(self.eval("selected"), 99)

    def test_one_confirmation_waits_for_each_server_ack_and_restores_selection(self):
        self.run_lua("ns:ShowQuestCleanup(); popup.OnAccept(nil, snapshot); popup.OnAccept(nil, snapshot); ns:ShowQuestCleanup(); tick()")
        self.assertEqual(self.eval("table.concat(calls, ',')"), "1")
        self.assertEqual(self.eval("selected"), 99)
        self.run_lua("present[1] = nil; table.insert(offered, 3); tick()")
        self.assertEqual(self.eval("table.concat(calls, ',')"), "1,2")
        self.run_lua("present[2] = nil; tick()")
        self.assertIn("2 de 2", self.eval("messages[#messages]"))
        self.assertEqual(self.eval("#timers"), 0)

    def test_reclassification_and_changes_to_guide_stop_stale_requests(self):
        self.run_lua("ns:ShowQuestCleanup(); offered = {2,3}; popup.OnAccept(nil,snapshot)")
        self.assertEqual(self.eval("table.concat(calls, ',')"), "2")
        self.run_lua("present[2]=nil; tick(); ns:ShowQuestCleanup(); step=13; popup.OnAccept(nil,snapshot)")
        self.assertEqual(self.eval("#calls"), 1)

    def test_protects_items_restrictions_and_mismatched_native_selection(self):
        self.run_lua("ns:ShowQuestCleanup(); items[1]={12345}; denied=2; popup.OnAccept(nil,snapshot)")
        self.assertEqual(self.eval("#calls"), 0)
        self.run_lua("ns:ShowQuestCleanup(); items[1]=nil; denied=nil; wrongTarget=99; popup.OnAccept(nil,snapshot)")
        self.assertEqual(self.eval("#calls"), 0)
        self.assertEqual(self.eval("selected"), 99)

    def test_stops_on_timeout_and_does_not_consume_another_pending_confirmation(self):
        self.run_lua("ns:ShowQuestCleanup(); nativePopup=true; popup.OnAccept(nil,snapshot)")
        self.assertEqual(self.eval("#calls"), 0)
        self.run_lua("nativePopup=false; ns:ShowQuestCleanup(); popup.OnAccept(nil,snapshot); while #timers>0 do tick() end")
        self.assertEqual(self.eval("#calls"), 1)
        self.assertIn("Limpieza detenida", self.eval("messages[#messages-1]"))

    def test_combat_unavailable_api_or_empty_results_make_no_changes(self):
        self.run_lua("combat=true; ns:ShowQuestCleanup(); combat=false; offered={}; ns:ShowQuestCleanup()")
        self.run_lua("offered={1}; C_QuestLog.GetAbandonQuestItems=nil; ns:ShowQuestCleanup()")
        self.assertIsNone(self.eval("popup"))
        self.assertEqual(self.eval("#calls"), 0)

    def test_read_only_explains_every_classification_even_without_abandon_api(self):
        self.run_lua("C_QuestLog.AbandonQuest=nil; ns:ShowQuestCleanup(true)")
        reports = self.eval("table.concat(messages, '\\n')")
        self.assertIn('2 para abandonar y 2 para conservar (1 de revisión manual)', reports)
        for name in ('Misión útil', 'Sin clasificación', 'Quest 1', 'Quest 2'):
            self.assertIn(name, reports)
        self.assertIsNone(self.eval('snapshot'))
        self.assertEqual(self.eval('#calls'), 0)

    def test_reaccepted_quest_with_same_id_is_preserved(self):
        self.run_lua("ns:ShowQuestCleanup(); onEvent(nil, 'QUEST_REMOVED', 1); popup.OnAccept(nil,snapshot)")
        self.assertEqual(self.eval("table.concat(calls, ',')"), '2')


if __name__ == '__main__':
    unittest.main()
