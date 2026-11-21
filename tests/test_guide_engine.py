import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime

from tools.suite_rested import transform_lua


ROOT = Path(__file__).resolve().parents[1]


class GuideEngineTests(unittest.TestCase):
    def test_quest_automation_and_sharing_wait_for_the_old_duo_journal(self):
        lua = LuaRuntime()
        lua.execute("addon={comms={grouping={}},rutaXPManualQuesting=function() return waiting end}")
        for path, method, args, invoke in [
            ("RXPGuides.lua", "addon:QuestAutomation", "event, arg1, arg2, arg3", "addon:QuestAutomation()"),
            ("Communications.lua", "addon.comms.grouping:ShareQuest", "questId", "addon.comms.grouping:ShareQuest(968)"),
        ]:
            source = f"function {method}({args})\n changed=true\nend"
            lua.execute(transform_lua("RXPGuides", path, source))
            lua.execute(f"waiting=true; changed=false; {invoke}; assert(not changed)")
            lua.execute(f"waiting=false; {invoke}; assert(changed)")

    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("""
            ns, timers, hooks, dbCallbacks = {}, {}, {}, {}
            local frames = {}
            function CreateFrame(_, name, parent)
                local f = {name=name, parent=parent, shown=true, scripts={}, events={}}
                function f:RegisterEvent(e) self.events[e]=true end
                function f:SetParent(p) self.parent=p end
                function f:GetParent() return self.parent end
                function f:SetScript(k,v) self.scripts[k]=v end
                function f:SetShown(v) self.shown=v end
                function f:Show() self.shown=true end
                function f:SetSize() end
                function f:SetPoint() end
                function f:SetAlpha(a) self.alpha=a end
                function f:SetClipsChildren(c) self.clips=c end
                frames[#frames+1]=f
                return f
            end
            UIParent=CreateFrame()
            function fire(e,...)
                for _,f in ipairs(frames) do
                    if f.events[e] then f.scripts.OnEvent(f,e,...) end
                end
            end
            C_Timer={After=function(_,f) timers[#timers+1]=f end}
            function flush()
                local n=0
                while #timers>0 do
                    n=n+1; assert(n<50,'recursive notification')
                    table.remove(timers,1)()
                end
            end
            function InCombatLockdown() return combat or false end
            function hooksecurefunc(t,k,cb)
                local f=assert(t[k])
                t[k]=function(...) f(...); cb(...) end
            end
            local function noop() end
            broker={OnClick=noop}
            local ldb={GetDataObjectByName=function(_,n) assert(n=='RXPGuides'); return broker end}
            function LibStub(name) if name=='LibDataBroker-1.1' then return ldb end end
            r={guides={}, embeddedGuides={}, addonLoaded=true, player={name='Player'},
                settings={profile={showEnabled=false,hideGuideWindow=true},ToggleActive=noop},
                arrowFrame=CreateFrame(nil,nil,UIParent), RXPFrame=CreateFrame(nil,nil,UIParent),
                itemFrame=CreateFrame(nil,nil,UIParent), v2={ShowGuideSelectionMenu=noop,state={
                    guideWindow={frame=CreateFrame(nil,nil,UIParent)},
                    player={Player={activeStepFrame={frame=CreateFrame(nil,nil,UIParent)}}}}}}
            function ns.GetEmbeddedModule(k) if k=='RXPGuides' then return r end end
            ns.ToggleGuidePanel=function() toggled=true end
            ns.OpenGuideLibrary=function() library=true end
            function r.GetMapId(zone) if zone=='Dun Morogh' then return 1426 end end
            function r.IsGuideActive(g) return not g.wrongFaction end
            function r.IsGuideSelectable(g, _, includeUnused) return not g.lowPrio or includeUnused end
            function r.GetGuideTable(group,name) return r.guides[group..'||'..name] end
            function r.GetGuideProgress() return cursor or 1 end
            function r.ProcessGuideTable(g) processed=true; return g end
            function r:FetchGuide(g)
                self.currentGuideName=g.name
                local parsed={key=g.key, group=g.group, name=g.name, steps={{},{},{}}}
                self.guides[g.group..'||'..g.name]=parsed
                return parsed
            end
            function r:LoadGuide(g)
                loads=(loads or 0)+1
                self.currentGuide=g
                cursor=2
                self.RXPFrame.activeSteps={}
            end
            function r.SetStep(n) cursor=n end
            r.UpdateMap=noop; r.UpdateGotoSteps=noop; r.LoadEmbeddedGuides=noop
            function r:RegisterMessage(name,fn) dbCallbacks[name]=fn end
            function r.ReplaceNpcIds(text) return text:gsub('NPC_1','Thundris') end
            function r.ActiveStepElementPostClick(button)
                local e=button:GetParent().element
                e.skip=button:GetChecked()
                toggles=(toggles or 0)+1
            end
            r.emptyGuide={empty=true}
            function guide(name, opts)
                local g=opts or {}; g.group='Forever'; g.name=name; g.key='Forever||'..name
                r.guides[g.key]=g
                return g
            end
        """)
        self.lua.execute((ROOT / "RutaXP/GuideEngine.lua").read_text(encoding="utf8"),
                         "RutaXP", self.lua.globals().ns)
        self.lua.execute("e=ns.GuideEngine")

    def check(self, code):
        self.lua.execute(code)

    def test_native_catalog_filters_and_lazy_character_guide(self):
        self.check("""
            default=guide('02 quest', {steps={{},{},{}}}); r.guides[1]=default
            alt=guide('01 zone',{lowPrio='secondary'})
            guide('private',{imported=true}); guide('disabled',{disabled=true})
            guide('chapter',{chapter=true}); guide('other faction',{wrongFaction=true})
            assert(e.Ready() and #e.Catalog()==2 and e.Catalog()[1]==alt)
            assert(e.Select(default) and loads==1 and select(2,e.Current())==2)
            r.currentGuideName=default.name
            assert(#e.Preview(alt).steps==3 and processed and r.currentGuideName==default.name and loads==1)
            assert(e.Select(default,3) and loads==1 and cursor==3)
            assert(not e.SetStep(0) and not e.SetStep(4))
            assert(e.Advance(1) and cursor==4)
            assert(not e.Select(r.guides['Forever||private']))
            assert(e.Clear() and not e.Current() and e.Clear() and loads==2)
            r.embeddedGuides={true}; assert(not e.Ready() and #e.Catalog()==0)
        """)

    def test_live_tasks_waypoints_and_stale_clicks(self):
        self.check("""
            local g=guide('01',{steps={{},{}}})
            assert(e.Select(g))
            local a,b={text='Talk to NPC_1', tag='accept'}, {text='Read',textOnly=true}
            local step={index=2,active=true,elements={a,b}}
            r.RXPFrame.activeSteps={step,{active=false,index=1,elements={{text='Old'}}}}
            local rows=e.Tasks()
            assert(#rows==2 and rows[1].text=='Talk to Thundris' and rows[1].manual)
            assert(not rows[2].manual and not e.ToggleTask(rows[2]))
            assert(e.ToggleTask(rows[1]) and toggles==1 and e.Tasks()[1].checked)
            assert(e.ToggleTask(rows[1]) and not e.Tasks()[1].checked)
            r.rutaXPWaypoint={zone='Dun Morogh',x=.50,y=70,step=step,title='Anvilmar'}
            local id,x,y,label=e.Waypoint()
            assert(id==1426 and x==.005 and y==.7 and label=='Anvilmar')
            step.active=false
            assert(not e.Waypoint() and not e.ToggleTask(rows[1]))
            r.RXPFrame.activeSteps={}; assert(#e.Tasks()==0)
        """)

    def test_ui_replacement_preserves_secure_buttons_and_native_preferences(self):
        self.check("""
            local oldMouse,oldToggle=broker.OnClick,r.settings.ToggleActive
            r.currentGuide=guide('private', {imported=true})
            e.PresentWithJourney(true)
            assert(r.currentGuide.empty and not e.Current())
            local clip=r.RXPFrame.parent
            assert(clip~=UIParent and clip.clips and clip.shown and clip.alpha==0)
            assert(r.RXPFrame.shown and not r.isHidden and r.rutaXPJourney)
            assert(r.arrowFrame.parent==clip and r.v2.state.player.Player.activeStepFrame.frame.parent==clip)
            assert(r.itemFrame.parent==UIParent and r.settings.profile.showEnabled==false)
            broker.OnClick(nil,'LeftButton'); assert(toggled)
            broker.OnClick(nil,'RightButton'); assert(library)
            combat=true; e.PresentWithJourney(false); assert(r.rutaXPJourney)
            combat=false; fire('PLAYER_REGEN_ENABLED');flush()
            assert(not r.rutaXPJourney and r.RXPFrame.parent==UIParent and r.arrowFrame.parent==UIParent)
            assert(r.settings.ToggleActive==oldToggle and broker.OnClick==oldMouse)
            assert(not r.RXPFrame.shown and r.isHidden and r.settings.profile.hideGuideWindow)
        """)

    def test_saved_selection_captured_once_and_native_events_coalesce(self):
        self.check("""
            count=0; e.Subscribe(function() count=count+1 end)
            RXPCData={currentGuideGroup='G', currentGuideName='Grizzly',currentStep=9}
            fire('ADDON_LOADED','RutaXP'); fire('PLAYER_LOGIN'); flush()
            RXPCData.currentGuideName='Default'
            fire('ADDON_LOADED','OtherAddon')
            local grp,name,n=e.SavedSelection()
            assert(grp=='G' and name=='Grizzly' and n==9 and count==1)
            dbCallbacks.RXPGuidesV2_GuideStepsChanged(); dbCallbacks.RXP_GUIDE_LOADED()
            r.SetStep(4); flush(); assert(count==2)
            r.rutaXPWaypoint={}; r.UpdateMap(true); r.UpdateGotoSteps();flush(); assert(count==3)
            r.UpdateGotoSteps();flush(); assert(count==3)
        """)

    def test_personal_builder_exposes_real_native_arrow_choice(self):
        source = ("local function updateArrowData()\n"
                  "    af.dist, af.orientation, af.element = 0, 0, element\nend\n"
                  "if #addon.activeWaypoints == 0 and not forceArrowUpdate then\nend")
        text = transform_lua("RXPGuides", "map.lua", source)
        self.assertEqual(text.count("addon.rutaXPWaypoint = nil"), 2)
        self.assertIn("addon.rutaXPWaypoint = element", text)
        self.assertEqual(transform_lua("RXPGuides", "Guides/forever/map.lua", source), source)

    def test_first_login_uses_the_installed_presentation(self):
        text = transform_lua("RXPGuides", "RXPGuides.lua", "addon.ui.v2.configurator:Open(true)")
        lua = LuaRuntime()
        lua.execute("""opened=0
            C_AddOns={GetAddOnMetadata=function() return journey end}
            addon={ui={v2={configurator={Open=function() opened=opened+1 end}}}}
        """)
        lua.globals().journey = "4.00.13"
        lua.execute(text)
        self.assertEqual(lua.globals().opened, 0)
        lua.globals().journey = None
        lua.execute(text)
        self.assertEqual(lua.globals().opened, 1)


if __name__ == "__main__":
    unittest.main()
