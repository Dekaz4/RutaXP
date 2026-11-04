"""Tracker sizing through real WoW-style resize events and the shipping TOC."""

import math
import unittest

from test_duo import DUO_STUBS
from test_duo_journey import primitive_copy
import test_talent_trainer_regressions as full


GEOMETRY_STUBS = r'''
local create = CreateFrame
local function attach(frame,parent)
    frame.geometryParent,frame.points=parent,{}
    function frame:SetPoint(anchor,relative,relativeAnchor,x,y)
        if type(relative)=="number" then x,y,relative,relativeAnchor=relative,relativeAnchor,self.geometryParent or UIParent,anchor end
        relative,relativeAnchor=relative or self.geometryParent or UIParent,relativeAnchor or anchor
        local point={anchor,relative,relativeAnchor,x or 0,y or 0}
        for i,old in ipairs(self.points) do if old[1]==anchor then self.points[i]=point;return end end
        self.points[#self.points+1]=point
    end
    function frame:ClearAllPoints() self.points={} end
    function frame:GetPoint(index)
        local p=self.points[index or 1]
        if p then return unpack(p) end
        return "CENTER",UIParent,"CENTER",0,0
    end
    function frame:SetSize(width,height)
        if self.sizing and self.resizeBounds then
            local b=self.resizeBounds
            width=math.max(b[1],math.min(b[3] or math.huge,width))
            height=math.max(b[2],math.min(b[4] or math.huge,height))
        end
        local changed=self.width~=width or self.height~=height
        self.width,self.height=width,height
        if changed and self.scripts.OnSizeChanged then
            TEST.sizeCallbacks=(TEST.sizeCallbacks or 0)+1
            assert(TEST.sizeCallbacks<2000,"Size handlers recursively resize or refresh forever")
            self.scripts.OnSizeChanged(self,width,height)
        end
    end
    function frame:SetWidth(width) self:SetSize(width,self.height or 0) end
    function frame:SetHeight(height) self:SetSize(self.width or 0,height) end
    function frame:SetResizable(value) self.resizable=value end
    function frame:SetResizeBounds(...) self.resizeBounds={...} end
    function frame:SetMinResize(width,height)
        self.resizeBounds=self.resizeBounds or {};self.resizeBounds[1],self.resizeBounds[2]=width,height
    end
    function frame:SetMaxResize(width,height)
        self.resizeBounds=self.resizeBounds or {};self.resizeBounds[3],self.resizeBounds[4]=width,height
    end
    function frame:StartSizing(anchor) self.sizing=anchor;TEST.sizingAnchor=anchor end
    function frame:StopMovingOrSizing() self.sizing=nil;TEST.stoppedSizing=true end
    function frame:SetFrameLevel(level) self.frameLevel=level end
    function frame:GetFrameLevel() return self.frameLevel or 1 end
    function frame:SetScale(scale) self.scale=scale end
    function frame:GetScale() return self.scale or 1 end
    function frame:GetEffectiveScale()
        local parent=self.geometryParent
        return self:GetScale()*(parent and parent.GetEffectiveScale and parent:GetEffectiveScale() or 1)
    end
    function frame:SetScrollChild(child) self.scrollChild=child;child.geometryParent=self end
    function frame:GetStringHeight()
        local value=(self.text or ""):gsub("|c%x%x%x%x%x%x%x%x",""):gsub("|r","")
        if value=="" then return 0 end
        local columns=math.max(1,math.floor((self.width or 300)/6))
        local lines=0
        for line in (value.."\n"):gmatch("(.-)\n") do lines=lines+math.max(1,math.ceil(#line/columns)) end
        return lines*15
    end
    local createFont,createTexture=frame.CreateFontString,frame.CreateTexture
    function frame:CreateFontString(...) local item=createFont(self,...);item.geometryParent=self;return item end
    function frame:CreateTexture(...) local item=createTexture(self,...);item.geometryParent=self;return item end
    return frame
end
CreateFrame=function(kind,name,parent,...) return attach(create(kind,name,parent,...),parent) end
function TrackerRect(item,tracker,depth)
    depth=depth or 0;assert(depth<25,"Cyclic geometry anchor")
    if item==tracker then return 0,0,item:GetWidth(),item:GetHeight() end
    local anchor,relative,relativeAnchor,x,y=item:GetPoint()
    if relative==UIParent then relative=item.geometryParent end
    if not relative then return 0,0,item:GetWidth(),item:GetHeight() end
    local left,top,width,height=TrackerRect(relative,tracker,depth+1)
    local function offset(point,w,h)
        local ox=point:find("LEFT") and 0 or point:find("RIGHT") and w or w/2
        local oy=point:find("TOP") and 0 or point:find("BOTTOM") and h or h/2
        return ox,oy
    end
    local rx,ry=offset(relativeAnchor,width,height)
    local ownWidth,ownHeight=item:GetWidth(),item:GetHeight()
    local ax,ay=offset(anchor,ownWidth,ownHeight)
    return left+rx+x-ax,top+ry-y-ay,ownWidth,ownHeight
end
'''


class ResizableTrackerHost:
    def __init__(self, saved=None, legacy_bounds=False, screen_size=None):
        self.h = full.TalentTrainerHost(full_toc=True)
        self.h.lua.execute(DUO_STUBS)
        self.h.lua.execute(GEOMETRY_STUBS)
        self.ns, self.s = self.h.ns, self.h.state
        self.s.members, self.s.level = 0, 10
        if screen_size:
            self.h.g.UIParent.width, self.h.g.UIParent.height = screen_size
        if legacy_bounds:
            self.h.lua.execute('''
                local original=CreateFrame
                CreateFrame=function(...)
                    local frame=original(...);frame.SetResizeBounds=false;return frame
                end
            ''')
        self.ns.RegisterGuide(self.ns, self.h.table({
            "id": "resize", "title": "Una ruta con un título lo bastante largo para adaptar la cabecera",
            "faction": "Alliance", "steps": [
                {"title": "Varias tareas con texto extenso", "goals": [
                    {"t": "train", "title": "Consulta habilidades nuevas con tu instructor", "note": "Comprueba las habilidades disponibles y conserva tus monedas para las que vayas a utilizar."},
                    {"t": "vendor", "title": "Vende los objetos que ya no necesitas", "note": "Deja espacio suficiente en las bolsas antes de volver al camino."},
                    {"t": "note", "text": "Recuerda revisar el registro de misiones y prepararte antes de salir."},
                ]},
                {"title": "Recorrido terminado", "text": "Texto simple de otro paso para probar cambios de contenido."},
            ],
        }))
        if saved is None:
            saved = {"seen": True, "activeGuide": "resize", "auto": False,
                     "tracker": True, "duo": {"enabled": False, "autoPair": False},
                     "progress": {"resize": {"cursor": 1, "review": True, "confirmed": {"keep": True}}}}
        self.h.g.RutaXPCharDB = self.h.table(saved)
        self.h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        self.h.g.EmitAddonEvent("PLAYER_LOGIN")
        self.tracker = self.ns.tracker

    def refresh(self):
        self.ns.RefreshUI(self.ns)

    def point(self, frame):
        return frame.GetPoint(frame)

    def saved(self):
        return primitive_copy(self.ns.char)

    def resize(self, width, height, orientation="BOTTOMRIGHT", finish=True):
        handle = self.tracker.resizeHandles[orientation]
        handle.scripts.OnMouseDown(handle, "LeftButton")
        self.tracker.SetSize(self.tracker, width, height)
        if finish:
            handle.scripts.OnMouseUp(handle, "LeftButton")

    def rect(self, frame):
        return self.h.g.TrackerRect(frame, self.tracker)


class TrackerResizeTests(unittest.TestCase):
    def test_drag_corner_preserves_live_size_and_only_saves_on_mouse_release(self):
        h = ResizableTrackerHost()
        self.assertTrue(h.tracker.resizable)
        self.assertIsNone(h.ns.char.trackerSize)
        before = primitive_copy(h.ns.char.progress)
        h.resize(560, 420, finish=False)
        self.assertEqual(h.s.sizingAnchor, "BOTTOMRIGHT")
        self.assertEqual((h.tracker.width, h.tracker.height), (560, 420))
        self.assertIsNone(h.ns.char.trackerSize)
        h.refresh()
        self.assertEqual((h.tracker.width, h.tracker.height), (560, 420))
        handle = h.tracker.resizeHandles.BOTTOMRIGHT
        handle.scripts.OnMouseUp(handle, "LeftButton")
        self.assertTrue(h.s.stoppedSizing)
        self.assertEqual((h.ns.char.trackerSize.width, h.ns.char.trackerSize.height), (560, 420))
        self.assertEqual(primitive_copy(h.ns.char.progress), before)

    def test_all_edges_and_corners_start_their_native_sizing_direction(self):
        h = ResizableTrackerHost()
        expected = {"TOP", "BOTTOM", "LEFT", "RIGHT", "TOPLEFT", "TOPRIGHT", "BOTTOMLEFT", "BOTTOMRIGHT"}
        self.assertEqual(set(h.tracker.resizeHandles.keys()), expected)
        for orientation in expected:
            h.resize(450, 350, orientation)
            self.assertEqual(h.s.sizingAnchor, orientation)
            self.assertEqual((h.ns.char.trackerSize.width, h.ns.char.trackerSize.height), (450, 350))

    def test_right_click_does_not_begin_or_persist_a_resize(self):
        h = ResizableTrackerHost()
        handle = h.tracker.resizeHandles.BOTTOMRIGHT
        handle.scripts.OnMouseDown(handle, "RightButton")
        handle.scripts.OnMouseUp(handle, "RightButton")
        self.assertIsNone(h.tracker.sizing)
        self.assertIsNone(h.ns.char.trackerSize)

    def test_rows_titles_and_footer_adapt_to_width_and_remain_inside_the_panel(self):
        h = ResizableTrackerHost()
        row = h.ns.trackerRows[1]
        initial = (row.width, row.title.width, h.ns.trackerTitle.width, h.ns.trackerNext.width)
        h.resize(620, 500)
        self.assertGreater(row.width, initial[0])
        self.assertGreater(row.title.width, initial[1])
        self.assertGreater(h.ns.trackerTitle.width, initial[2])
        self.assertGreater(h.ns.trackerNext.width, initial[3])
        for item in (row, row.title, h.ns.trackerTitle, h.ns.trackerText, h.ns.trackerBar):
            self.assertGreater(item.width, 0)
            self.assertLessEqual(item.width, h.tracker.width)
        buttons = [h.ns.trackerPrevious, h.ns.trackerNext, h.ns.trackerSkip, h.ns.trackerMap]
        previous_right = 0
        for item in buttons:
            left, top, width, height = h.rect(item)
            self.assertGreaterEqual(left, previous_right)
            self.assertGreaterEqual(top, 0)
            self.assertLessEqual(left + width, h.tracker.width)
            self.assertLessEqual(top + height, h.tracker.height)
            previous_right = left + width

    def test_small_manual_height_uses_scrolling_instead_of_overwriting_the_size(self):
        h = ResizableTrackerHost()
        h.resize(324, 160)
        self.assertEqual(h.tracker.height, 160)
        self.assertIsNotNone(h.ns.trackerScroll)
        self.assertIsNotNone(h.ns.trackerContent)
        self.assertGreater(h.ns.trackerContent.height, h.ns.trackerScroll.height)
        self.assertLessEqual(h.ns.trackerScroll.height, h.tracker.height)
        self.assertTrue(h.ns.trackerRows[1].shown)
        for _ in range(3):
            h.refresh()
            self.assertEqual(h.tracker.height, 160)

    def test_text_reflows_when_narrowed_without_changing_the_saved_manual_height(self):
        h = ResizableTrackerHost()
        h.resize(620, 400)
        wide_height = h.ns.trackerRows[1].height
        h.resize(324, 400)
        self.assertGreater(h.ns.trackerRows[1].height, wide_height)
        self.assertEqual(h.tracker.height, 400)
        self.assertEqual(h.ns.char.trackerSize.height, 400)

    def test_resize_bounds_and_saved_size_survive_reloading_this_character(self):
        h = ResizableTrackerHost()
        h.resize(10000, 10000)
        maximum = (h.tracker.width, h.tracker.height)
        self.assertLessEqual(maximum[0], 900)
        self.assertLessEqual(maximum[1], 850)
        h.resize(-10, -20)
        self.assertEqual((h.tracker.width, h.tracker.height), (324, 160))
        h.resize(515, 377)
        saved = h.saved()
        other = ResizableTrackerHost(saved=saved)
        self.assertEqual((other.tracker.width, other.tracker.height), (515, 377))
        self.assertEqual((other.ns.char.trackerSize.width, other.ns.char.trackerSize.height), (515, 377))
        fresh = ResizableTrackerHost()
        self.assertEqual(fresh.tracker.width, 324)
        self.assertIsNone(fresh.ns.char.trackerSize)

    def test_finish_resize_keeps_the_position_and_size_as_separate_preferences(self):
        h = ResizableTrackerHost()
        h.resize(500, 350, "TOPLEFT", finish=False)
        h.tracker.ClearAllPoints(h.tracker)
        h.tracker.SetPoint(h.tracker, "TOPLEFT", h.h.g.UIParent, "TOPLEFT", 71, -109)
        h.tracker.resizeHandles.TOPLEFT.scripts.OnMouseUp(h.tracker.resizeHandles.TOPLEFT, "LeftButton")
        self.assertEqual((h.ns.char.trackerPosition.x, h.ns.char.trackerPosition.y), (71, -109))
        self.assertEqual((h.ns.char.trackerSize.width, h.ns.char.trackerSize.height), (500, 350))
        other = ResizableTrackerHost(saved=h.saved())
        self.assertEqual(other.point(other.tracker)[3:], (71, -109))

    def test_duo_footer_and_repeated_content_refreshes_keep_the_manual_dimensions(self):
        h = ResizableTrackerHost()
        h.resize(550, 390)
        for enabled in (True, False, True, True, False):
            h.ns.Duo.SetEnabled(h.ns.Duo, enabled)
            for _ in range(3):
                h.refresh()
                self.assertEqual((h.tracker.width, h.tracker.height), (550, 390))
                self.assertEqual((h.ns.char.trackerSize.width, h.ns.char.trackerSize.height), (550, 390))
            if enabled:
                self.assertTrue(h.ns.duoTracker.shown)
                left, top, width, height = h.rect(h.ns.duoTracker)
                self.assertGreaterEqual(left, 0)
                self.assertGreaterEqual(top, 0)
                self.assertLessEqual(left + width, 550)
                self.assertLessEqual(top + height, 390)
        h.ns.char.progress.resize.cursor = 2
        h.refresh()
        self.assertEqual((h.tracker.width, h.tracker.height), (550, 390))

    def test_invalid_saved_sizes_never_reach_frame_geometry_as_nan_or_negative(self):
        base = ResizableTrackerHost().saved()
        for value in ("broken", {"width": -50, "height": 0}, {"width": math.nan, "height": 300},
                      {"width": 500, "height": math.inf}, {"width": "wide", "height": 300},
                      {"width": 20000, "height": 20000}):
            with self.subTest(value=value):
                saved = {**base, "trackerSize": value}
                h = ResizableTrackerHost(saved=saved)
                self.assertTrue(math.isfinite(h.tracker.width))
                self.assertTrue(math.isfinite(h.tracker.height))
                self.assertGreaterEqual(h.tracker.width, 324)
                self.assertGreaterEqual(h.tracker.height, 160)
                self.assertLessEqual(h.tracker.width, 900)
                self.assertLessEqual(h.tracker.height, 850)

    def test_bounds_respect_a_smaller_screen_and_legacy_client_size_methods(self):
        h = ResizableTrackerHost(screen_size=(500, 400))
        h.resize(900, 850)
        self.assertLessEqual(h.tracker.width, 500)
        self.assertLessEqual(h.tracker.height, 400)
        old = ResizableTrackerHost(legacy_bounds=True)
        old.resize(2000, 2000)
        self.assertLessEqual(old.tracker.width, 900)
        self.assertLessEqual(old.tracker.height, 850)
        self.assertEqual((old.ns.char.trackerSize.width, old.ns.char.trackerSize.height),
                         (old.tracker.width, old.tracker.height))

    def test_mouse_wheel_scrolls_only_content_and_clamps_to_available_rows(self):
        h = ResizableTrackerHost()
        h.resize(324, 160)
        scroll = h.ns.trackerScroll
        footer = h.rect(h.ns.trackerNext)
        before = primitive_copy(h.ns.char.progress)
        scroll.scripts.OnMouseWheel(scroll, -10000)
        self.assertEqual(scroll.GetVerticalScroll(scroll), h.ns.trackerScrollMax)
        self.assertEqual(h.rect(h.ns.trackerNext), footer)
        scroll.scripts.OnMouseWheel(scroll, 10000)
        self.assertEqual(scroll.GetVerticalScroll(scroll), 0)
        self.assertEqual(primitive_copy(h.ns.char.progress), before)
        self.assertEqual(h.tracker.height, 160)

    def test_releasing_outside_handle_or_hiding_panel_finishes_native_resize(self):
        h = ResizableTrackerHost()
        h.resize(480, 330, finish=False)
        h.h.g.IsMouseButtonDown = h.h.lua.eval("function() return false end")
        h.tracker.scripts.OnUpdate(h.tracker, .1)
        self.assertEqual((h.ns.char.trackerSize.width, h.ns.char.trackerSize.height), (480, 330))
        self.assertFalse(h.tracker.isResizing)
        h.resize(520, 370, finish=False)
        h.tracker.scripts.OnHide(h.tracker)
        self.assertEqual((h.ns.char.trackerSize.width, h.ns.char.trackerSize.height), (520, 370))
        self.assertFalse(h.tracker.isResizing)

    def test_large_current_steps_and_preview_share_the_dynamic_pool_without_mutating_progress(self):
        h = ResizableTrackerHost()
        h.ns.guides.resize.steps[1].goals = h.h.table([
            {"t": "train", "title": f"Revisa la habilidad {index}"} for index in range(1, 10)
        ])
        h.refresh()
        self.assertEqual(h.ns.trackerCurrentCount, 9)
        self.assertEqual(h.ns.trackerPreviewCount, 0)
        for index in range(1, 10):
            row = h.ns.trackerRows[index]
            self.assertTrue(row.shown)
            self.assertFalse(row.preview)
            self.assertEqual(row.goalIndex, index)

        progress = primitive_copy(h.ns.char.progress)
        sources = primitive_copy(h.ns.guides.resize.steps)
        h.resize(550, 500)
        self.assertEqual(h.ns.trackerCurrentCount, 9)
        self.assertEqual(h.ns.trackerPreviewCount, 1)
        self.assertTrue(h.ns.trackerUpcomingLabel.shown)
        preview = h.ns.trackerRows[10]
        self.assertTrue(preview.shown)
        self.assertTrue(preview.preview)
        self.assertIsNone(preview.goalIndex)
        h.ns.Navigate = h.h.lua.eval("function() TEST.navigateCalls=(TEST.navigateCalls or 0)+1 end")
        for button in ("LeftButton", "RightButton"):
            preview.scripts.OnClick(preview, button)
        self.assertIsNone(h.s.navigateCalls)
        self.assertEqual(primitive_copy(h.ns.char.progress), progress)
        self.assertEqual(primitive_copy(h.ns.guides.resize.steps), sources)

        h.ns.char.progress.resize.cursor = 2
        h.refresh()
        self.assertEqual(h.ns.trackerPreviewCount, 0)
        self.assertFalse(h.ns.trackerUpcomingLabel.shown)
        self.assertFalse(preview.shown)
        self.assertEqual(h.tracker.height, 500)

    def test_increasing_height_shows_more_rows_and_resets_scroll_when_everything_fits(self):
        h = ResizableTrackerHost()
        h.ns.guides.resize.steps[1].goals = h.h.table([
            {"t": "train", "title": f"Habilidad {index}"} for index in range(1, 10)
        ])
        h.refresh()

        def fully_visible_rows():
            _, viewport_top, _, viewport_height = h.rect(h.ns.trackerScroll)
            position = h.ns.trackerScroll.GetVerticalScroll(h.ns.trackerScroll)
            visible = 0
            for _, row in h.ns.trackerRows.items():
                if not row.shown:
                    continue
                _, top, _, height = h.rect(row)
                if top - position >= viewport_top and top - position + height <= viewport_top + viewport_height:
                    visible += 1
            return visible

        progress = primitive_copy(h.ns.char.progress)
        h.resize(550, 260)
        small_visible = fully_visible_rows()
        self.assertGreater(small_visible, 0)
        self.assertLess(small_visible, 9)
        scroll = h.ns.trackerScroll
        scroll.scripts.OnMouseWheel(scroll, -10000)
        self.assertGreater(scroll.GetVerticalScroll(scroll), 0)
        h.resize(550, 700)
        self.assertGreater(fully_visible_rows(), small_visible)
        self.assertEqual(fully_visible_rows(), 10)
        self.assertEqual(h.ns.trackerScrollMax, 0)
        self.assertEqual(scroll.GetVerticalScroll(scroll), 0)
        self.assertFalse(h.ns.trackerScrollThumb.shown)
        self.assertEqual(primitive_copy(h.ns.char.progress), progress)


if __name__ == "__main__":
    unittest.main()
