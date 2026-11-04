local _, ns = ...

local MIN_WIDTH, MIN_HEIGHT = 324, 160
-- Forever APIs and Blizzard's resize pattern:
-- https://github.com/Gethe/wow-ui-source/blob/172a387e3ab85b26e6640d3058d5ec1e6ccd4c63/Interface/AddOns/Blizzard_SharedXML/Mainline/SharedUIPanelTemplates.lua#L1681
local function finite(value)
    return type(value) == "number" and value == value and value > -math.huge and value < math.huge
end
local function clamp(value, low, high, fallback)
    return math.max(low, math.min(high, finite(value) and value or fallback or low))
end

function ns:GetTrackerSizeLimits()
    local frame = self.tracker
    local scale = frame and frame.GetScale and frame:GetScale() or 1
    if not finite(scale) or scale <= 0 then scale = 1 end
    local width, height = UIParent:GetWidth() / scale, UIParent:GetHeight() / scale
    return MIN_WIDTH, MIN_HEIGHT, math.max(MIN_WIDTH, math.min(900, width - 16)),
        math.max(MIN_HEIGHT, math.min(850, height - 16))
end

function ns:UpdateTrackerScroll()
    local scroll, thumb = self.trackerScroll, self.trackerScrollThumb
    if not scroll or not thumb then return end
    local maximum = self.trackerScrollMax or 0
    local position = clamp(scroll:GetVerticalScroll(), 0, maximum)
    if position ~= scroll:GetVerticalScroll() then scroll:SetVerticalScroll(position) end
    if maximum <= 0 then thumb:Hide(); return end
    local viewport = self.trackerViewportHeight or 1
    local height = math.max(18, viewport * viewport / math.max(viewport, self.trackerContentHeight or 1))
    thumb:SetHeight(math.min(viewport, height))
    thumb:ClearAllPoints()
    thumb:SetPoint("TOPRIGHT", scroll, "TOPRIGHT", -2, -(viewport - height) * position / maximum)
    thumb:Show()
end

-- Geometry only: resizing must not run quest automation or move the real cursor.
function ns:LayoutTracker()
    local frame = self.tracker
    if not frame or not self.trackerContent or self.trackerLayoutBusy then return end
    self.trackerLayoutBusy = true
    local minW, minH, maxW, maxH = self:GetTrackerSizeLimits()
    local saved = type(self.char.trackerSize) == "table" and self.char.trackerSize or nil
    local width = clamp(frame.isResizing and frame:GetWidth() or (saved and saved.width) or frame:GetWidth(), minW, maxW, MIN_WIDTH)
    frame:SetWidth(width)
    if frame.SetResizeBounds then frame:SetResizeBounds(minW, minH, maxW, maxH)
    else
        if frame.SetMinResize then frame:SetMinResize(minW, minH) end
        if frame.SetMaxResize then frame:SetMaxResize(maxW, maxH) end
    end

    self.trackerTitle:SetWidth(width - 146)
    for _, entry in ipairs({ {self.trackerTalentBtn, 131}, {self.trackerZoneBtn, 106},
        {self.trackerGuidesBtn, 62}, {self.trackerCloseBtn, 17} }) do
        entry[1]:ClearAllPoints(); entry[1]:SetPoint("TOPLEFT", width - entry[2], -7)
    end
    self.trackerBar:SetWidth(width - 2)
    self.trackerStep:SetWidth(width - 110)
    self.trackerProgress:ClearAllPoints(); self.trackerProgress:SetPoint("TOPLEFT", width - 100, -45)
    self.trackerProgress:SetWidth(90)
    self.trackerContent:SetWidth(width)
    self.trackerText:SetWidth(width - 20)

    local y, upcoming = 0, false
    for _, row in ipairs(self.trackerRows) do
        if row:IsShown() then
            if row.preview and not upcoming then
                upcoming = true
                self.trackerUpcomingLabel:ClearAllPoints()
                self.trackerUpcomingLabel:SetPoint("TOPLEFT", 10, -y - 10)
                self.trackerUpcomingLabel:SetWidth(width - 20)
                y = y + 34
            end
            row:SetWidth(width - 16)
            row.title:SetWidth(width - 56); row.sub:SetWidth(width - 56)
            local titleH = math.max(14, row.title:GetStringHeight() or 14)
            local subH = row.sub:IsShown() and math.max(13, row.sub:GetStringHeight() or 13) or 0
            row:SetHeight(math.max(subH > 0 and 40 or 28, titleH + subH + (subH > 0 and 17 or 14)))
            row:ClearAllPoints(); row:SetPoint("TOPLEFT", 8, -y)
            y = y + row:GetHeight() + 5
        end
    end
    self.trackerUpcomingLabel:SetShown(upcoming)
    if self.trackerText:IsShown() then
        self.trackerText:ClearAllPoints(); self.trackerText:SetPoint("TOPLEFT", 10, 0)
        y = math.max(y, self.trackerText:GetStringHeight() + 8)
    end
    self.trackerContentHeight = math.max(1, y)
    self.trackerContent:SetHeight(self.trackerContentHeight)
    local duo = self.trackerDuoVisible and 30 or 0
    local height = frame.isResizing and frame:GetHeight() or (saved and saved.height) or (math.max(minH, 66 + y + 38) + duo)
    height = clamp(height, minH, maxH, MIN_HEIGHT)
    frame:SetHeight(height)
    if saved and not frame.isResizing then saved.width, saved.height = width, height end

    local bottom = 8 + duo
    local function place(button, x, buttonWidth)
        button:ClearAllPoints(); button:SetPoint("BOTTOMLEFT", x, bottom)
        if buttonWidth then button:SetWidth(buttonWidth) end
    end
    place(self.trackerPrevious, 8)
    place(self.trackerNext, 44, width - 198)
    place(self.trackerSkip, width - 150)
    place(self.trackerMap, width - 74)
    if self.duoTracker then
        self.duoTracker:SetWidth(width - 16)
        self.duoTracker:ClearAllPoints(); self.duoTracker:SetPoint("BOTTOMLEFT", 8, 6)
    end
    self.trackerViewportHeight = math.max(1, height - 66 - 38 - duo)
    self.trackerScroll:ClearAllPoints(); self.trackerScroll:SetPoint("TOPLEFT", 0, -66)
    self.trackerScroll:SetSize(width, self.trackerViewportHeight)
    self.trackerScrollMax = math.max(0, self.trackerContentHeight - self.trackerViewportHeight)
    self:UpdateTrackerScroll()
    self.trackerLayoutBusy = nil
end

function ns:FinishTrackerResize(noRefresh)
    local frame = self.tracker
    if not frame or not frame.isResizing then return end
    frame:StopMovingOrSizing()
    local minW, minH, maxW, maxH = self:GetTrackerSizeLimits()
    self.char.trackerSize = { width = clamp(frame:GetWidth(), minW, maxW), height = clamp(frame:GetHeight(), minH, maxH) }
    local point, _, relativePoint, x, y = frame:GetPoint()
    if type(point) == "string" and type(relativePoint) == "string" and finite(x) and finite(y) then
        self.char.trackerPosition = { point=point, relativePoint=relativePoint, x=x, y=y }
    end
    frame.isResizing = nil
    frame:SetScript("OnUpdate", nil)
    if self.trackerResizeCursor and ResetCursor then ResetCursor() end
    self.trackerResizeCursor = nil
    self:LayoutTracker()
    if not noRefresh and self.RefreshUI then self:RefreshUI() end
end

function ns:CreateTrackerLayout()
    local frame = self.tracker
    if not frame then return end
    local saved = self.char.trackerSize
    if type(saved) == "table" and finite(saved.width) and finite(saved.height) then
        local minW, minH, maxW, maxH = self:GetTrackerSizeLimits()
        saved.width, saved.height = clamp(saved.width, minW, maxW), clamp(saved.height, minH, maxH)
        frame:SetSize(saved.width, saved.height)
    else self.char.trackerSize = nil end
    if frame.SetResizable then frame:SetResizable(true) end
    frame.resizeHandles = {}
    local function cursor()
        if SetCursor and SetCursor("UI_RESIZE_CURSOR") then self.trackerResizeCursor = true end
    end
    local function release()
        if not frame.isResizing and self.trackerResizeCursor then
            if ResetCursor then ResetCursor() end
            self.trackerResizeCursor = nil
        end
    end
    local function add(direction, first, second, width, height)
        local handle = CreateFrame("Frame", nil, frame)
        handle:EnableMouse(true)
        handle:SetFrameLevel(frame:GetFrameLevel() + (second and 20 or 21))
        handle:SetPoint(first, frame, first, 0, 0)
        if second then handle:SetPoint(second, frame, second, 0, 0) end
        if width then handle:SetWidth(width) end
        if height then handle:SetHeight(height) end
        handle:SetScript("OnEnter", cursor)
        handle:SetScript("OnLeave", release)
        handle:SetScript("OnMouseDown", function(_, button)
            if button ~= "LeftButton" or frame.isResizing or not frame.StartSizing then return end
            cursor()
            frame.isResizing = true
            -- Populate the preview before the first native size callback.
            if self.RefreshUI then self:RefreshUI() end
            frame:StartSizing(direction, true)
            frame:SetScript("OnUpdate", function()
                if IsMouseButtonDown and not IsMouseButtonDown("LeftButton") then self:FinishTrackerResize() end
            end)
        end)
        handle:SetScript("OnMouseUp", function(_, button)
            if button == "LeftButton" then self:FinishTrackerResize() end
        end)
        frame.resizeHandles[direction] = handle
    end
    add("TOP", "TOPLEFT", "TOPRIGHT", nil, 4)
    add("BOTTOM", "BOTTOMLEFT", "BOTTOMRIGHT", nil, 4)
    add("LEFT", "TOPLEFT", "BOTTOMLEFT", 4)
    add("RIGHT", "TOPRIGHT", "BOTTOMRIGHT", 4)
    for _, point in ipairs({"TOPLEFT", "TOPRIGHT", "BOTTOMLEFT", "BOTTOMRIGHT"}) do add(point, point, nil, 8, 8) end
    local grip = frame:CreateTexture(nil, "OVERLAY")
    if grip.SetTexture then grip:SetTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Up") end
    grip:SetSize(12, 12); grip:SetPoint("BOTTOMRIGHT", -1, 1)
    frame:SetScript("OnSizeChanged", function() self:LayoutTracker() end)
    frame:SetScript("OnHide", function()
        if not frame.isResizing then frame:StopMovingOrSizing() end
        self:FinishTrackerResize(true)
        if frame.isMoving then
            local point, _, relativePoint, x, y = frame:GetPoint()
            if finite(x) and finite(y) then self.char.trackerPosition = {point=point,relativePoint=relativePoint,x=x,y=y} end
            frame.isMoving = nil
        end
        release()
    end)
    if self.trackerScroll.EnableMouseWheel then self.trackerScroll:EnableMouseWheel(true) end
    self.trackerScroll:SetScript("OnMouseWheel", function(scroll, delta)
        scroll:SetVerticalScroll(clamp(scroll:GetVerticalScroll() - delta * 36, 0, self.trackerScrollMax or 0))
        self:UpdateTrackerScroll()
    end)
    self.trackerScroll:SetScript("OnVerticalScroll", function() self:UpdateTrackerScroll() end)
    self:LayoutTracker()
end
