"""Drive the same library buttons, slash commands and login hooks used by the game."""
import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1] / "RutaXP"


class GuideLibraryTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("""
            frames, UISpecialFrames = {}, {}
            local function noop() end
            function CreateFrame(kind, name, parent)
                local f=setmetatable({kind=kind,shown=true,scripts={},text="",parent=parent}, {__index=function() return noop end})
                if name then _G[name]=f end
                function f:SetText(text) self.text=text end
                function f:GetText() return self.text end
                function f:SetScript(event, action) self.scripts[event]=action end
                f.HookScript=f.SetScript
                function f:CreateFontString() return CreateFrame("Font") end
                function f:CreateTexture() return CreateFrame("Texture") end
                function f:SetShown(b) self.shown=b end
                function f:Hide() self.shown=false end
                function f:Show() self.shown=true end
                function f:IsShown() return self.shown end
                function f:RegisterEvent(e) self.event=e end
                if name=="RutaXPGuideLibrary" then f.TitleText=CreateFrame("Font") end
                table.insert(frames,f)
                return f
            end
            guides = {}
            for i=1,12 do guides[i]={key=tostring(i),group="Leveo",name="Tramo "..i} end
            guides[12].displayname="Páramos de Poniente"
            ns={char={}, Print=noop}
            ns.GuideEngine = {Catalog=function() return guides end, Current=function() return selected end,
                Subscribe=function(fn) update=fn end, Ready=function() return true end,
                PresentWithJourney=function(v) nativeSuppressed=v end}
            ns.GuideResume = {SelectManually=function(g) selected=g; return true end,
                UseZone=function() zoneRequested=true; return state, "Aviso", state~="unavailable" end,
                Status=function() return state or "auto", "Aviso" end}
            ns.GuideJourney = {Available=function() return true end, IsShown=function() return visible end,
                Show=function() visible=true end, Hide=function() visible=false end, Refresh=noop}
            visible=true
        """)
        for name in ("Suite.lua", "GuideLibrary.lua"):
            self.lua.execute((ROOT/name).read_text("utf-8-sig"), "RutaXP", self.lua.globals().ns)
        self.lua.execute("""
            RutaXPModuleContext("RXPGuides")
            for _,f in ipairs(frames) do
                if f.event=="PLAYER_LOGIN" then f.scripts.OnEvent(f) end
            end
        """)

    def test_library_opens_from_suite_and_selects_filtered_guide(self):
        self.lua.execute("""
            assert(visible)
            assert(ns:HandleSuiteCommand("guías"))
            local p=RutaXPGuideLibrary
            assert(#p.rows == 8 and p.rows[1].title.text=="Tramo 1")
            p.next.scripts.OnClick()
            assert(p.rows[8].guide==guides[12])
            p.search:SetText("paramos")
            p.search.scripts.OnTextChanged()
            assert(p.rows[1].guide==guides[12] and not p.rows[2]:IsShown())
            p.rows[1].scripts.OnClick(p.rows[1])
            assert(selected==guides[12] and not p:IsShown() and visible)
        """)

    def test_toggle_and_zone_command_preserve_local_choice_until_requested(self):
        self.lua.execute("""
            ns:HandleSuiteCommand("guía")
            assert(not visible)
            update()
            assert(not visible)
            ns:HandleSuiteCommand("guía")
            assert(visible)
            state="unavailable"
            ns.OpenGuideLibrary()
            ns:HandleSuiteCommand("zona")
            assert(zoneRequested and RutaXPGuideLibrary:IsShown() and RutaXPGuideLibrary.status.text=="Aviso")
        """)
