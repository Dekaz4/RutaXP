local _, ns = ...

local humanRogue = { classes = { "ROGUE" }, races = { "Human" } }
local labels = { dps = "DPS", agi = "agilidad", str = "fuerza", ap = "poder de ataque",
    crit = "% de crítico", hit = "% de golpe" }
-- The catalog uses percentage points for hit and crit. A client rating uses
-- a different scale, so only the four like-for-like stats are compared.
local itemStatKeys = { dps = "ITEM_MOD_DAMAGE_PER_SECOND_SHORT", agi = "ITEM_MOD_AGILITY_SHORT",
    str = "ITEM_MOD_STRENGTH_SHORT", ap = "ITEM_MOD_ATTACK_POWER_SHORT" }
-- Inventory types on rewards and equipped slot IDs differ for weapons and paired slots.
local equipmentSlots = {
    [1]={1}, [2]={2}, [3]={3}, [5]={5}, [6]={6}, [7]={7}, [8]={8}, [9]={9}, [10]={10},
    [11]={11,12}, [12]={13,14}, [13]={16,17}, [15]={18}, [16]={15}, [20]={5},
    [21]={16}, [22]={17}, [25]={18}, [26]={18},
}
local slotLabels = { [2]="cuello", [11]="anillo 1", [12]="anillo 2", [13]="abalorio 1",
    [14]="abalorio 2", [15]="capa equipada", [16]="mano principal", [17]="mano secundaria", [18]="arma a distancia" }
local waitingForName = {}
local lastRewardDialogQuest

local function readable(api, ...)
    if type(api) ~= "function" then return nil end
    local ok, value = pcall(api, ...)
    if ok and not (issecretvalue and issecretvalue(value)) then return value end
end

local function itemStats(link)
    if link then return readable(C_Item and C_Item.GetItemStats or GetItemStats, link) end
end

local function statValue(stats, key)
    if not key or type(stats) ~= "table" then return nil end
    local value = stats[key]
    if (not issecretvalue or not issecretvalue(value)) and type(value) == "number" then return value end
end

local function numberText(value)
    return (string.format("%.1f", value):gsub("%.0$", ""):gsub("%.", ","))
end

local function equippedDifference(slot, label, reward, candidateValue)
    local link = readable(GetInventoryItemLink, "player", slot)
    local equipped = statValue(itemStats(link), itemStatKeys[reward.stat])
    if equipped == nil then return nil end
    local tenths = math.floor((candidateValue - equipped) * 10 + 0.5)
    local diff = (tenths > 0 and "+" or "") .. numberText(tenths / 10)
    return label .. " " .. diff .. " " .. labels[reward.stat]
end

local function compareEquipment(reward, clientValue)
    local slots = equipmentSlots[reward.inv]
    if not slots or not clientValue then return nil end
    local comparisons = {}
    for _, slot in ipairs(slots) do
        local diff = equippedDifference(slot, slotLabels[slot] or "ranura equipada", reward, clientValue)
        if diff then comparisons[#comparisons + 1] = diff end
    end
    if #comparisons > 0 then return table.concat(comparisons, ", ") end
end

local function offeredItemID(kind, index)
    local link = readable(GetQuestItemLink, kind, index)
    local id = type(link) == "string" and tonumber(link:match("item:(%d+)"))
    if not id and type(GetQuestItemInfo) == "function" then
        local ok, _, _, _, _, _, itemID = pcall(GetQuestItemInfo, kind, index)
        if ok and not (issecretvalue and issecretvalue(itemID)) then id = itemID end
    end
    if type(id) == "number" and id > 0 then return id end
end

local function addOfferedItems(result, catalog, kind, count)
    for index = 1, count do
        local id = offeredItemID(kind, index)
        if not id then return false end
        for _, reward in ipairs(catalog) do
            if reward.id == id then
                -- The same item can be fixed in the guide and a choice in the
                -- client's dialog. Leave the shared catalog intact when it closes.
                local row = {}
                for key, value in pairs(reward) do row[key] = value end
                row.choice = kind == "choice"
                result[#result + 1] = row
                break
            end
        end
    end
    return true
end

local function rewardsAtTurnin(questID, catalog)
    local panel = QuestFrameRewardPanel
    if not panel or not readable(panel.IsVisible, panel) or readable(GetQuestID) ~= questID then return catalog end
    lastRewardDialogQuest = questID
    local choices, fixed = readable(GetNumQuestChoices), readable(GetNumQuestRewards)
    if type(choices) ~= "number" or type(fixed) ~= "number" or choices < 0 or fixed < 0
        or choices % 1 ~= 0 or fixed % 1 ~= 0 or choices + fixed == 0 then return catalog end
    local result = {}
    if addOfferedItems(result, catalog, "reward", fixed) and addOfferedItems(result, catalog, "choice", choices) then
        return result
    end
    return catalog
end

function ns:GetRogueQuestRewardInfo(questID, action)
    local rewards = self.rogueQuestRewards and self.rogueQuestRewards[questID]
    if not rewards or not rewards[1] then
        if questID == 65 and self:MatchesConditions(humanRogue) then
            return "Cadena opcional · Túnica de cuero",
                "Al entregar a Wiley el Negro en Villa del Lago, acepta su respuesta para Gryan Mantorrecio en la Colina del Centinela. Sigue la cadena hasta escoltar al Traidor Defias.\n" ..
                "En el último encargo de Gryan, forma un grupo para Las Minas de la Muerte. Devuélvele la cabeza de VanCleef y podrás elegir la Túnica de Páramos de Poniente (+11 agilidad, +5 aguante)."
        end
        return nil
    end
    if not self:MatchesConditions(humanRogue) then return nil end
    if action == "turnin" then
        rewards = rewardsAtTurnin(questID, rewards)
        if not rewards[1] then return nil end
    end
    local details, kinds, seen = {}, {}, {}
    local choices, fixed, firstSummary = false, false, nil
    for _, reward in ipairs(rewards) do
        local name = readable(C_Item and C_Item.GetItemInfo or GetItemInfo, reward.id)
        if type(name) ~= "string" or name == "" then
            name = reward.name
            waitingForName[reward.id] = questID
        end
        local kind = reward.kind
        if not seen[kind] then
            seen[kind] = true
            kinds[#kinds + 1] = kind
        end
        choices = choices or reward.choice == true
        fixed = fixed or not reward.choice
        local link = "item:" .. reward.id
        local key = itemStatKeys[reward.stat]
        local stats = key and itemStats(link)
        local clientValue = statValue(stats, key)
        local value = clientValue or reward.value
        local line = (reward.choice and "A elegir · " or "Fija · ") .. name .. " (" .. kind .. ")"
        local summary = kind
        if type(value) == "number" and labels[reward.stat] then
            local amount = numberText(value) .. " " .. labels[reward.stat]
            summary = kind .. " (" .. amount .. ")"
            line = line .. " · " .. amount
            local comparison = compareEquipment(reward, clientValue)
            if comparison then line = line .. " (" .. comparison .. ")" end
        end
        if reward.stat == "dps" then
            local agility = statValue(stats, itemStatKeys.agi) or reward.agility
            if agility and agility > 0 then line = line .. " · +" .. numberText(agility) .. " agilidad" end
        end
        firstSummary = firstSummary or summary
        if reward.level and reward.level > 1 then line = line .. " · nivel " .. reward.level end
        details[#details + 1] = line
    end
    local prefix = fixed and choices and "Recompensas" or (choices and "A elegir" or "Recompensa fija")
    return prefix .. " · " .. (#rewards == 1 and firstSummary or table.concat(kinds, ", ")),
        table.concat(details, "\n")
end

local events = CreateFrame("Frame")
pcall(events.RegisterEvent, events, "ITEM_DATA_LOAD_RESULT")
events:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")
events:RegisterEvent("QUEST_COMPLETE")
pcall(events.RegisterEvent, events, "QUEST_ITEM_UPDATE")
events:RegisterEvent("QUEST_FINISHED")

local function refreshReward(questID, turninOnly)
    if not ns.initialized or not ns.RefreshUI or not ns:MatchesConditions(humanRogue) then return end
    local goal = ns:GetActiveGoal()
    local current = goal and (goal.quest or goal.questID)
    local action = goal and (goal.t or goal.action)
    if (action == "turnin" or not turninOnly and action == "accept") and ns.rogueQuestRewards and ns.rogueQuestRewards[current]
        and (not questID or questID == current) then ns:RefreshUI() end
end

events:SetScript("OnEvent", function(_, event, id, success)
    if event == "QUEST_COMPLETE" or event == "QUEST_ITEM_UPDATE" or event == "QUEST_FINISHED" then
        local questID
        if event == "QUEST_FINISHED" then
            questID, lastRewardDialogQuest = lastRewardDialogQuest, nil
        else
            questID = readable(GetQuestID)
        end
        if questID and ns.rogueQuestRewards and ns.rogueQuestRewards[questID] then
            -- Blizzard updates panel visibility during this same event.
            if C_Timer and C_Timer.After then C_Timer.After(0, function() refreshReward(questID, true) end)
            else refreshReward(questID, true) end
        end
        return
    end
    local waiting = event == "ITEM_DATA_LOAD_RESULT" and waitingForName[id]
    if event == "ITEM_DATA_LOAD_RESULT" then
        if not waiting then return end
        waitingForName[id] = nil
        if not success then return end
    end
    refreshReward(waiting)
end)
