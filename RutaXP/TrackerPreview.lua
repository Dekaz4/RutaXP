local _, ns = ...
-- Source-only previews: no quest history, live objective selection, cursor
-- placement or automation is needed to describe the following actions.
local verbs = {accept="Acepta",turnin="Entrega",complete="Completa",objective="Completa",
    kill="Derrota",collect="Reúne",goto="Ve a",travel="Viaja a",talk="Habla con",
    interact="Interactúa con",use="Usa",sethome="Fija tu hogar en",hearth="Usa la piedra de hogar hacia",
    getfp="Descubre la ruta de vuelo en",fly="Vuela a",train="Entrena habilidades",
    buy="Compra",vendor="Vende y repara",level="Sube a nivel",note="Nota"}

local function read(fn,...)
    if type(fn)~="function" then return nil end
    local ok,a,b=pcall(fn,...)
    if not ok then return nil end
    if issecretvalue then
        if issecretvalue(a) then a=nil end
        if issecretvalue(b) then b=nil end
    end
    return a,b
end
local function number(n)
    if issecretvalue and issecretvalue(n) then return nil end
    n=tonumber(n)
    return n and n==n and math.abs(n)<math.huge and n or nil
end
local function clean(value)
    if type(value)~="string" or issecretvalue and issecretvalue(value) then return nil end
    value=value:gsub("|c%x%x%x%x%x%x%x%x",""):gsub("|r",""):gsub("|T.-|t","")
        :gsub("|H.-|h(.-)|h","%1"):gsub("%s+"," "):gsub("^%s+",""):gsub("%s+$","")
    return value~="" and value or nil
end
local function short(value,maximum)
    local out={}
    -- Do not cut an accented UTF-8 character while shortening source notes.
    for character in value:gmatch("[%z\1-\127\194-\244][\128-\191]*") do
        if #out==maximum then return table.concat(out).."…" end
        out[#out+1]=character
    end
    return table.concat(out)
end
local function token(value)
    value=tostring(value or ""):lower():gsub("[%s_%-]","")
    if value=="undead" then value="scourge" end
    if value:find("skyborne",1,true) then value="skyborne" end
    return value
end
local function matches(values,actual)
    if values==nil then return true end
    if type(values)~="table" then values={values} end
    local positive,found=false,false
    for _,value in ipairs(values) do
        value=tostring(value)
        local excluded=value:sub(1,1)=="!"
        local name=token(excluded and value:sub(2) or value)
        if excluded and name==token(actual) then return false end
        if not excluded then positive=true;if actual and name==token(actual) then found=true end end
    end
    return not positive or found
end
local function predicate(self,guide)
    local view=self.DuoAuto and read(self.DuoAuto.GetSharedView,self.DuoAuto)
    local helper=type(view)=="table" and view.following==true and view.guideID==guide.id
    if helper then
        if not(self.Duo and self.Duo.AppliesToPartner) then return function() return false end,nil end
        local ctx=read(self.Duo.GetContext,self.Duo) or {}
        return function(only)
            return only==nil or read(self.Duo.AppliesToPartner,self.Duo,only)==true
        end,ctx.partnerFaction
    end
    if self.MatchesConditions then
        return function(only) return only==nil or read(self.MatchesConditions,self,only)==true end,read(UnitFactionGroup,"player")
    end
    local _,class=read(UnitClass,"player")
    local _,race=read(UnitRace,"player")
    local faction=read(UnitFactionGroup,"player")
    return function(only)
        return only==nil or (matches(only.classes,class) and matches(only.races,race) and matches(only.factions,faction))
    end,faction
end
local function conditions(value)
    local class=value.class
    if type(class)=="string" then class={class} elseif type(class)~="table" then class=nil end
    return {classes=value.classes or class,races=value.races,factions=value.factions}
end
local function npc(goal,applies,faction)
    local name
    local code=faction=="Alliance" and "A" or faction=="Horde" and "H" or nil
    for _,candidate in ipairs(type(goal.candidates)=="table" and goal.candidates or {}) do
        local side=candidate.faction
        if (not side or side=="AH" or side==faction or side==code) and applies(conditions(candidate)) and applies(candidate.only) then
            name=clean(candidate.npcName) or clean(candidate.objName)
            if name then return name end
        end
    end
    if not goal.candidates or #goal.candidates==0 then return clean(goal.npcName) or clean(goal.objName) or clean(goal.objectName) end
end
local function describe(goal,step,stepIndex,applies,faction)
    local action=goal.t or goal.action or "manual"
    local note=clean(goal.note) or clean(goal.text)
    if action=="note" and not note then return nil end
    local id=number(goal.quest or goal.questID)
    if id and (id<=0 or id~=math.floor(id)) then id=nil end
    local name=npc(goal,applies,faction)
    local target
    if id then target=clean(read(C_QuestLog and C_QuestLog.GetTitleForQuestID,id)) or clean(goal.title) or ("Misión "..id)
    elseif action=="level" then target=tostring(goal.level or goal.n or "indicado")
    elseif action=="note" then target=short(note,110)
    elseif action=="train" or action=="talk" or action=="vendor" or action=="sethome" or action=="getfp" then
        target=name or clean(goal.title) or clean(goal.location)
    else target=clean(goal.title) or clean(goal.itemName) or clean(goal.target) or name or clean(goal.location) or clean(step.title) end
    local verb=clean(goal.instructionVerb) or verbs[action] or "Objetivo"
    local title=verb..(target and (": "..short(target,130)) or "")
    local subtitle="Después · Paso "..stepIndex
    if name and name~=target then subtitle=subtitle.." · "..short(name,70) end
    local detail=ns.GetGoalHint and ns:GetGoalHint(goal) or note
    if detail and detail~=target and detail~=name then subtitle=subtitle.." · "..short(detail,110) end
    return {action=action,title=title,subtitle=subtitle,status="upcoming",preview=true,isCurrent=false,
        stepIndex=stepIndex,questID=id,details=ns.GetGoalInstruction and ns:GetGoalInstruction(goal,step)}
end

function ns:GetTrackerUpcomingItems(guide,fromCursor,limit)
    if type(guide)~="table" or type(guide.steps)~="table" then return {} end
    local count=math.max(0,math.min(12,math.floor(number(limit) or 12)))
    local from=number(fromCursor) or 0
    if count==0 or from<0 then return {} end
    from=math.floor(from)
    local applies,faction=predicate(self,guide)
    if not applies(conditions(guide)) or not applies(guide.only) or guide.faction and guide.faction~=faction then return {} end
    local items={}
    for si=from+1,math.min(#guide.steps,from+12) do
        local step=guide.steps[si]
        if type(step)=="table" and applies(conditions(step)) and applies(step.only) then
            local goals=type(step.goals)=="table" and step.goals or {step}
            for _,goal in ipairs(goals) do
                if type(goal)=="table" and applies(conditions(goal)) and applies(goal.only) then
                    local item=describe(goal,step,si,applies,faction)
                    if item then items[#items+1]=item;if #items>=count then return items end end
                end
            end
        end
    end
    return items
end

-- A read-only journal plan sits beside the source-only preview above. It
-- never uses GetProgress/GetGoalStatus, selects a goal or changes navigation.
local workActions={complete=true,objective=true,kill=true,collect=true,buy=true,
    talk=true,interact=true,use=true,goto=true,travel=true}
local function questID(goal)
    local id=number(goal.quest or goal.questID)
    return id and id>0 and id==math.floor(id) and id or nil
end

function ns:GetTrackerPlannedUpcomingItems(guide,fromCursor,limit)
    if type(guide)~="table" or type(guide.steps)~="table" then return {} end
    local count=math.max(0,math.min(12,math.floor(number(limit) or 12)))
    local from=number(fromCursor) or 0
    if count==0 or from<0 then return {} end
    from=math.floor(from)
    local view=self.DuoAuto and read(self.DuoAuto.GetSharedView,self.DuoAuto)
    if type(view)=="table" and view.following==true and view.guideID==guide.id then
        -- Own delivery flags say nothing about the partner's future route.
        return self:GetTrackerUpcomingItems(guide,from,count)
    end
    local applies,faction=predicate(self,guide)
    if not applies(conditions(guide)) or not applies(guide.only) or guide.faction and guide.faction~=faction then return {} end
    local char=type(self.char)=="table" and self.char or {}
    local states=type(char.progress)=="table" and char.progress or {}
    local state=type(states[guide.id])=="table" and states[guide.id] or {}
    local journal,closedBranches={},{}
    for si,sourceStep in ipairs(guide.steps) do
        if type(sourceStep)=="table" and applies(conditions(sourceStep)) and applies(sourceStep.only) then
            for gi,goal in ipairs(type(sourceStep.goals)=="table" and sourceStep.goals or {sourceStep}) do
                if type(goal)=="table" and (goal.t or goal.action)=="accept" and questID(goal)
                    and applies(conditions(goal)) and applies(goal.only) then
                    local id=questID(goal)
                    closedBranches[id]=closedBranches[id] or {}
                    closedBranches[id][#closedBranches[id]+1]={step=si,goal=gi,closedBy=goal.closedBy}
                end
            end
        end
    end
    local function status(id)
        if not journal[id] then
            local delivered=read(self.IsQuestDelivered,self,id)
            if delivered==nil then delivered=read(C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted,id) end
            local active=read(self.IsQuestActive,self,id)
            if active==nil then active=read(C_QuestLog and C_QuestLog.IsOnQuest,id) end
            local objectives=read(C_QuestLog and C_QuestLog.GetQuestObjectives,id)
            journal[id]={active=active==true,delivered=delivered==true,
                complete=read(C_QuestLog and C_QuestLog.IsComplete,id)==true,
                objectives=type(objectives)=="table" and objectives or {}}
        end
        return journal[id]
    end
    local function allowed(step,goal,si,gi)
        if not applies(conditions(step)) or not applies(step.only)
            or not applies(conditions(goal)) or not applies(goal.only) then return false end
        local key=si..":"..gi
        if type(state.skipped)=="table" and state.skipped[key]
            or type(state.confirmed)=="table" and state.confirmed[key] then return false end
        local id=questID(goal)
        if goal.optional and not char.optional and not (id and status(id).active) then return false end
        if not (id and status(id).active) then
            for _,closed in ipairs(type(goal.closedBy)=="table" and goal.closedBy or {}) do
                if number(closed) and (status(closed).active or status(closed).delivered) then return false end
            end
            local inherited
            for _,entry in ipairs(id and closedBranches[id] or {}) do
                if entry.step<si or entry.step==si and entry.goal<=gi then inherited=entry.closedBy end
            end
            for _,closed in ipairs(type(inherited)=="table" and inherited or {}) do
                if number(closed) and (status(closed).active or status(closed).delivered) then return false end
            end
        end
        return true
    end
    local function finished(goal,id)
        local q=status(id)
        if q.complete then return true end
        local oi=number(goal.oi or goal.objectiveIndex or goal.objective)
        if oi and type(q.objectives[oi])=="table" then
            return read(function() return q.objectives[oi].finished end)==true
        end
        if (goal.t or goal.action)=="collect" and number(goal.item) and number(goal.count) then
            local have=number(read(C_Item and C_Item.GetItemCount,goal.item,false))
                or number(read(GetItemCount,goal.item,false))
            return have~=nil and have>=goal.count
        end
        return false
    end
    local current={}
    local step=guide.steps[from]
    if type(step)=="table" then
        for gi,goal in ipairs(type(step.goals)=="table" and step.goals or {step}) do
            if type(goal)=="table" and allowed(step,goal,from,gi) then
                local id=questID(goal);if id then current[id]=true end
            end
        end
    end
    local plans,ordered={},{}
    for si=from+1,#guide.steps do
        local future=guide.steps[si]
        if type(future)=="table" then
            for gi,goal in ipairs(type(future.goals)=="table" and future.goals or {future}) do
                local id=type(goal)=="table" and questID(goal)
                if id and not current[id] and allowed(future,goal,si,gi) then
                    local q=status(id)
                    if q.active and not q.delivered then
                        local action=goal.t or goal.action
                        local work=workActions[action] and not finished(goal,id)
                        if work or action=="turnin" then
                            local plan=plans[id]
                            if not plan then
                                plan={questID=id,order=si,source=goal,step=future}
                                plans[id]=plan;ordered[#ordered+1]=plan
                            end
                            if work and not plan.workStep then
                                plan.workStep,plan.workGoal,plan.workContext=si,goal,future
                            elseif action=="turnin" and not plan.turninStep then plan.turninStep=si end
                        end
                    end
                end
            end
        end
    end
    local items,scheduled={},{}
    for _,plan in ipairs(ordered) do
        if #items>=math.min(6,count) then break end
        local id,q=plan.questID,status(plan.questID)
        local title=clean(read(C_QuestLog and C_QuestLog.GetTitleForQuestID,id)) or clean(plan.source.title) or ("Misión "..id)
        local parts={"En tu diario"}
        if plan.workStep then parts[#parts+1]="Hacer: paso "..plan.workStep end
        if plan.turninStep then parts[#parts+1]="Entregar: "..plan.turninStep end
        if not q.complete then
            local counters={}
            for _,objective in ipairs(q.objectives) do
                local have,total
                if type(objective)=="table" then have,total=number(objective.numFulfilled),number(objective.numRequired) end
                if have and total and have>=0 and total>0 then
                    counters[#counters+1]=math.floor(have).."/"..math.floor(total)
                    if #counters==2 then break end
                end
            end
            if #counters>0 then parts[#parts+1]=table.concat(counters," · ") end
        end
        local explanation="Esta misión ya está en tu diario. El plan indica cuándo hacerla y entregarla en este recorrido. "
            .."Los contadores proceden del juego; esta fila no cambia el paso, la flecha ni tus marcas manuales."
        local goal,context=plan.workGoal or plan.source,plan.workContext or plan.step
        local detail=self.GetGoalInstruction and read(self.GetGoalInstruction,self,goal,context)
        if detail then explanation=explanation.."\n"..detail end
        items[#items+1]={action=plan.workStep and (goal.t or goal.action) or "turnin",title=title,
            subtitle=table.concat(parts," · "),details=explanation,status="upcoming",preview=true,questPlan=true,
            isCurrent=false,questID=id,stepIndex=plan.workStep or plan.turninStep,
            workStep=plan.workStep,turninStep=plan.turninStep}
        scheduled[id]=true
    end
    -- Keep the usual twelve-step horizon, but apply filters before the item
    -- limit so completed/accepted rows cannot crowd out useful future rows.
    for si=from+1,math.min(#guide.steps,from+12) do
        local future=guide.steps[si]
        if type(future)=="table" then
            for gi,goal in ipairs(type(future.goals)=="table" and future.goals or {future}) do
                if #items>=count then return items end
                if type(goal)=="table" and allowed(future,goal,si,gi) then
                    local id,action=questID(goal),goal.t or goal.action
                    local q=id and status(id)
                    if not id or not scheduled[id] and not q.delivered
                        and not (action=="accept" and q.active) and not (workActions[action] and finished(goal,id)) then
                        local item=describe(goal,future,si,applies,faction)
                        if item then items[#items+1]=item end
                    end
                end
            end
        end
    end
    return items
end
