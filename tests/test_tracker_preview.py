"""Future tracker rows describe sources without changing or completing quests."""
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
STUBS = r'''
TEST={class="WARRIOR",race="Human",faction="Alliance",helper=false,titles={},queries=0}
function UnitClass() return "Clase",TEST.class end
function UnitRace() return "Raza",TEST.race end
function UnitFactionGroup() return TEST.faction end
C_QuestLog={GetTitleForQuestID=function(id) TEST.queries=TEST.queries+1;return TEST.titles[id] end}
function Fingerprint(t)
 if type(t)~="table" then return tostring(t) end
 local keys={};for k in pairs(t) do keys[#keys+1]=k end
 table.sort(keys,function(a,b) return tostring(a)<tostring(b) end)
 local out={};for _,k in ipairs(keys) do out[#out+1]=tostring(k).."="..Fingerprint(t[k]) end
 return "{"..table.concat(out,";").."}"
end
NS={char={activeGuide="route",progress={route={cursor=1,review=true,confirmed={x=true},skipped={y=true}}}},DuoAuto={},Duo={}}
function NS:GetCurrent() error("Preview must not position a cursor") end
function NS:GetActiveGoal() error("Preview must not select a live future objective") end
function NS:GetGoalStatus() error("Preview must not classify future quests from my history") end
function NS:IsStepComplete() error("Preview never marks future rows completed") end
function NS:IsQuestDelivered() error("Preview must not inspect delivered history") end
function NS:Sync() error("Preview must not sync progress") end
function NS:SelectGuide() error("Preview must not select a route") end
function NS.DuoAuto:GetSharedView() return TEST.helper and {following=true,guideID="route"} or nil end
function NS.Duo:GetContext() return {partnerFaction="Alliance"} end
function NS.Duo:AppliesToPartner(conditions)
 for _,key in ipairs({"classes","races","factions"}) do
   local actual=key=="classes" and "PRIEST" or key=="races" and "NightElf" or "Alliance"
   if conditions and conditions[key] then
      local found=false;for _,v in ipairs(conditions[key]) do if v==actual then found=true end end
      if not found then return false end
   end
 end
 return true
end
GUIDE={id="route",faction="Alliance",steps={
 {title="Actual",goals={{t="accept",quest=1}}},
 {title="Centro",goals={{t="accept",quest=2,npcName="Alguacil",title="Título fuente",note="Habla al llegar"},
   {t="kill",quest=2,title="Título fuente"},{t="turnin",quest=2,npcName="Alguacil"}}},
 {title="Próximo destino",action="travel",text="Cruza el puente"},
 {title="Hogar",goals={{t="sethome",npcName="Tabernero"}}}}}
TEST.titles[2]="Una amenaza cercana"
'''


class TrackerPreviewTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(STUBS)
        loader = self.lua.execute("return function(...)\n" + (ROOT / "RutaXP" / "TrackerPreview.lua").read_text(encoding="utf-8") + "\nend")
        loader("RutaXP", self.lua.globals().NS)

    def check(self, code):
        self.lua.execute(code)

    def test_future_actions_have_clear_verbs_readable_notes_and_are_not_clickable(self):
        self.check('''
        local before=Fingerprint(NS.char);local guideBefore=Fingerprint(GUIDE)
        local items=NS:GetTrackerUpcomingItems(GUIDE,1)
        assert(#items==5 and items[1].title=="Acepta: Una amenaza cercana")
        assert(items[1].subtitle=="Después · Paso 2 · Alguacil · Habla al llegar")
        assert(items[2].title=="Derrota: Una amenaza cercana" and items[3].title=="Entrega: Una amenaza cercana")
        assert(items[4].action=="travel" and items[4].title=="Viaja a: Próximo destino")
        for _,item in ipairs(items) do
          assert(item.preview and item.status=="upcoming" and item.index==nil and not item.isCurrent)
          assert(item.stepIndex>1)
        end
        assert(Fingerprint(NS.char)==before and Fingerprint(GUIDE)==guideBefore)
        ''')

    def test_limits_twelve_items_and_twelve_source_steps_even_when_some_are_filtered(self):
        self.check('''
        GUIDE.steps={{title="Actual"}}
        for i=2,30 do GUIDE.steps[i]={title="Paso "..i,goals={{t="accept",quest=i}}} end
        assert(#NS:GetTrackerUpcomingItems(GUIDE,1,100)==12)
        assert(#NS:GetTrackerUpcomingItems(GUIDE,1,3)==3)
        assert(#NS:GetTrackerUpcomingItems(GUIDE,1,0)==0)
        for i=2,13 do GUIDE.steps[i].only={classes={"PRIEST"}} end
        assert(#NS:GetTrackerUpcomingItems(GUIDE,1)==0) -- Do not scan beyond twelve future steps.
        ''')

    def test_local_profile_filters_steps_goals_and_guide_headers(self):
        self.check('''
        GUIDE.steps[2].goals={
          {t="accept",quest=10,only={classes={"PRIEST"}}},
          {t="accept",quest=11,only={classes={"WARRIOR"},races={"Human"}}},
          {t="accept",quest=12,only={races={"!Human"}}}}
        GUIDE.steps[3].only={races={"NightElf"}}
        local items=NS:GetTrackerUpcomingItems(GUIDE,1)
        assert(#items==2 and items[1].questID==11 and items[2].action=="sethome")
        GUIDE.races={"NightElf"};assert(#NS:GetTrackerUpcomingItems(GUIDE,1)==0)
        GUIDE.only={races={"Human"}};assert(#NS:GetTrackerUpcomingItems(GUIDE,1)==0)
        GUIDE.only=nil
        GUIDE.races=nil;GUIDE.faction="Horde";assert(#NS:GetTrackerUpcomingItems(GUIDE,1)==0)
        ''')

    def test_helper_view_uses_partner_profile_and_partner_trainer_candidates(self):
        self.check('''
        TEST.helper=true
        GUIDE.steps[2].goals={
          {t="accept",quest=10,only={classes={"WARRIOR"}}},
          {t="accept",quest=11,only={classes={"PRIEST"}}},
          {t="train",class=true,npcName="Instructor propio",candidates={
            {classes={"WARRIOR"},npcName="Instructor guerrero",faction="A"},
            {classes={"PRIEST"},npcName="Sacerdote Horda",faction="H"},
            {classes={"PRIEST"},npcName="Instructor sacerdote",faction="A"}}}}
        GUIDE.steps[3].only={races={"Human"}}
        local items=NS:GetTrackerUpcomingItems(GUIDE,1)
        assert(#items==3 and items[1].questID==11)
        assert(items[2].title=="Entrena habilidades: Instructor sacerdote")
        assert(items[3].action=="sethome")
        NS.Duo.AppliesToPartner=nil;assert(#NS:GetTrackerUpcomingItems(GUIDE,1)==0)
        ''')

    def test_unrelated_or_equal_cursor_shared_view_keeps_our_local_conditions(self):
        self.check('''
        GUIDE.steps[2].goals={{t="accept",quest=10,only={classes={"WARRIOR"}}},{t="accept",quest=11,only={classes={"PRIEST"}}}}
        function NS.DuoAuto:GetSharedView() return {following=true,guideID="other"} end
        assert(NS:GetTrackerUpcomingItems(GUIDE,1)[1].questID==10)
        function NS.DuoAuto:GetSharedView() return {following=false,guideID="route"} end
        assert(NS:GetTrackerUpcomingItems(GUIDE,1)[1].questID==10)
        ''')

    def test_empty_notes_skipped_and_simple_steps_and_unknown_actions_are_supported(self):
        self.check('''
        GUIDE.steps={
          {title="Actual"},
          {title="Vacío",goals={{t="note"},{t="note",note="  "..string.char(10).."  "},{t="note",note="|cffffffff|r"}}},
          {title="Nota",t="note",text="Compra agua antes de salir"},
          {title="Entrega",action="turnin",questID=99},
          {title="Aviso manual",action="custom",text="Revisa el inventario"},
          {title="Nivel",goals={{t="level",level=14}}}}
        local items=NS:GetTrackerUpcomingItems(GUIDE,1)
        assert(#items==4 and items[1].title=="Nota: Compra agua antes de salir")
        assert(items[2].title=="Entrega: Entrega" and items[2].questID==99)
        assert(items[3].title=="Objetivo: Aviso manual")
        assert(items[4].title=="Sube a nivel: 14")
        ''')

    def test_safe_bad_inputs_and_no_quest_history_queries(self):
        self.check('''
        assert(#NS:GetTrackerUpcomingItems(nil,1)==0)
        assert(#NS:GetTrackerUpcomingItems({},1)==0)
        assert(#NS:GetTrackerUpcomingItems(GUIDE,999)==0)
        assert(#NS:GetTrackerUpcomingItems(GUIDE,-1)==0)
        assert(#NS:GetTrackerUpcomingItems(GUIDE,1,-2)==0)
        GUIDE.steps[2].goals[1].quest=0
        assert(NS:GetTrackerUpcomingItems(GUIDE,1,1)[1].questID==nil)
        NS.char=nil -- Describing a guide does not need saved character state.
        assert(#NS:GetTrackerUpcomingItems(GUIDE,1)>0)
        ''')

    def test_spanish_long_notes_stay_valid_utf8_and_preserve_source_data(self):
        self.check('''
        GUIDE.steps[2].goals={{t="note",note=string.rep("ñ",200)}}
        RESULT=NS:GetTrackerUpcomingItems(GUIDE,1,1)[1].title
        assert(RESULT:find("…",1,true))
        ''')
        self.assertTrue(self.lua.globals().RESULT.endswith("…"))


if __name__ == "__main__":
    unittest.main()
