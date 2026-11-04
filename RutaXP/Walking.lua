local _, ns = ...
-- Ground routing uses Shortest Path Forever by Cillian Berragan and the
-- pinned Polestar/SendaFH walking maps in Pathing/ (GPL-3.0-or-later).
-- This follower only steers the arrow; it never moves a quest cursor.
local W = { phase="idle", serial=0, requests=0, cancellations=0 }
ns.Walking = W
local TRACE_LIMIT = 512
local function finite(n)
    return not (issecretvalue and issecretvalue(n)) and type(n)=="number" and n==n and math.abs(n)<math.huge
end
local function read(fn,...)
    if type(fn)~="function" then return nil end
    local ok,a,b,c,d=pcall(fn,...)
    if ok then return a,b,c,d end
end
local function now() return read(GetTime) or 0 end
local function settings()
    if not ns.char then return nil end
    if type(ns.char.walking)~="table" then ns.char.walking={} end
    if ns.char.walking.enabled==nil then ns.char.walking.enabled=true end
    return ns.char.walking
end
local function copy(point)
    local out={}; for k,v in pairs(point) do out[k]=v end; return out
end
local function distance(ax,ay,bx,by) return math.sqrt((ax-bx)^2+(ay-by)^2) end
local function combat() return read(InCombatLockdown)==true end
local function diagnostic(self,reason)
    self.reasons=self.reasons or {}
    self.reasons[reason]=math.min(99999,(self.reasons[reason] or 0)+1)
    self.lastReason=reason
    local config=settings()
    if config then
        local counts={};for key,value in pairs(self.reasons) do counts[key]=value end
        -- Bounded counters only: no coordinates, quest log, or player names.
        config.diagnostics={requests=self.requests,cancellations=self.cancellations,
            accepted=self.accepted or 0,rejected=self.rejected or 0,lastReason=reason,reasons=counts}
    end
end
function W:_Cancel(reason)
    self.serial=self.serial+1
    local engine=self.engine or RutaXPPathEngine
    if self.job and engine and engine.Cancel then
        self.cancellations=self.cancellations+1
        pcall(engine.Cancel,self.job)
        diagnostic(self,reason or "cancel")
    end
    self.job,self.pending=nil,nil
end
function W:Clear(reason)
    self:_Cancel(reason)
    self.key,self.points,self.left,self.arc,self.index,self.failure,self.target,self.lastAsk=nil,nil,nil,nil,nil,nil,nil,nil
    self.travel,self.seenX,self.seenY,self.requestTravel,self.requestZ,self.progress=0,nil,nil,nil,nil,0
    self.seenZ,self.seenAt,self.pathTravel,self.pathZ,self.trace,self.traceValid=nil,nil,nil,nil,nil,nil
    self.cornerCredit,self.cornerCreditBefore,self.cornerCreditTravel=nil,nil,nil
    self.latestTarget,self.campCommitted,self.refreshWanted=nil,nil,nil
    self.phase,self.text="idle","Esperando un destino"
end
function W:Toggle(enabled)
    local config=settings()
    if not config then return false,"Todavía no hay un personaje cargado" end
    config.enabled=enabled==nil and not config.enabled or enabled==true
    self:Clear()
    if ns.UpdateNavigation then ns:UpdateNavigation() end
    if ns.RefreshUI then ns:RefreshUI() end
    return true,config.enabled and "Camino por terreno activado" or "Camino por terreno desactivado; dirección orientativa"
end
function W:Retry()
    self:Clear()
    if ns.UpdateNavigation then ns:UpdateNavigation() end
    return true,"Recalculando el camino desde tu posición"
end
function W:GetStatus()
    local config=settings()
    return {enabled=config and config.enabled==true or false,phase=self.phase,text=self.text,
        count=self.points and #self.points or 0,index=self.index or 0,reason=self.failure,
        requests=self.requests,cancellations=self.cancellations,
        accepted=self.accepted or 0,rejected=self.rejected or 0,lastReason=self.lastReason,
        updating=self.pending==true and self.points~=nil,
        pendingSeconds=self.pending and math.max(0,now()-(self.lastAsk or now())) or 0}
end
function W:_Ask(engine,continent,px,py,pz,target,reason)
    if self.pending then return false end
    self:_Cancel()
    if combat() then self.phase,self.text="pending","Sal del combate para calcular el camino"; return end
    if read(IsFalling)==true then self.phase,self.text="pending","Esperando a pisar el suelo para calcular el camino"; return end
    local token=self.serial
    self.pending,self.lastAsk,self.failure=true,now(),nil
    self.requestTravel,self.requestZ=self.travel or 0,pz
    self.target={x=target.x,y=target.y,z=target.z}
    target=self.target
    self.trace={{x=px,y=py,z=pz,travel=self.travel or 0,time=now()}}
    self.traceValid=true
    self.phase,self.text="pending","Calculando un camino transitable…"
    self.requests=self.requests+1
    diagnostic(self,reason or "query")
    local requestTravel,requestZ=self.requestTravel,pz
    local ok,job=pcall(engine.Find,continent,{x=px,y=py,z=pz},{x=target.x,y=target.y,z=target.z},function(points,reason)
        if token~=self.serial then return end
        self.pending,self.job=nil,nil
        local valid=type(points)=="table" and #points>=2 and #points<=10000
        if valid then
            for _,p in ipairs(points) do
                if type(p)~="table" or not finite(p.x) or not finite(p.y)
                    or p.map~=continent or (p.z~=nil and not finite(p.z)) then valid=false; break end
            end
        end
        -- Do not silently select a roof or a tunnel on another floor.
        if valid and target.z and #points>2 then
            local floor=points[#points-1].z
            if finite(floor) and math.abs(floor-target.z)>30 then valid=false;reason="floor" end
        end
        if not valid then
            -- A failed background refresh cannot erase a still valid route.
            self.failure,self.failedAt,self.failedX,self.failedY=type(reason)=="string" and reason or "unreachable",now(),px,py
            self.refreshWanted=true
            self.phase,self.text="failed","No hay un camino comprobado hasta ese punto; revisa el acceso"
            diagnostic(self,"failed")
            return
        end
        self:_Adopt(points,requestTravel,requestZ)
    end,false)
    if not ok then
        self.pending,self.job=nil,nil
        self.failure,self.failedAt,self.failedX,self.failedY="error",now(),px,py
        self.phase,self.text="failed","No se pudo calcular el camino; usa /rutaxp recalcular"
    elseif self.pending and token==self.serial then self.job=job end
end
local function identity(value)
    return (type(value)=="string" or type(value)=="number") and tostring(value) or ""
end
local function pointKey(point,continent)
    local goal=point.goal or {}
    local guideID,stepIndex,goalIndex=point.guideID,point.stepIndex,point.goalIndex
    if not guideID and ns.GetCurrent then
        local guide,step,progress=ns:GetCurrent()
        if guide and step and progress then
            for index,candidate in ipairs(step.goals or {}) do
                if candidate==goal then goalIndex=index;break end
            end
            if goalIndex or step==goal or point==step.waypoint then
                guideID,stepIndex=guide.id,progress.cursor
            end
        end
    end
    local source=point.targetSource or point.source or "goal"
    -- game/guide/learned are coordinate providers for the same objective.
    -- Sub-yard marker changes must not cancel an unfinished async search.
    if source=="game" or source=="guide" or source=="learned" then source="goal" end
    return table.concat({identity(point.targetKey),identity(source),identity(guideID),identity(stepIndex),identity(goalIndex),
        identity(point.routeID),identity(point.pointIndex),identity(continent),identity(goal.quest or goal.questID or point.questID),
        identity(goal.t or goal.action),identity(goal.oi or goal.objectiveIndex or goal.objective),
        identity(goal.item),identity(goal.npc),identity(point.candidate and point.candidate.objectiveIndex)},"|")
end
local function targetMoved(target,x,y,z)
    if not target then return true end
    -- Compare with the dispatched endpoint, not the last sample: real gradual
    -- relocation still replans, while marker noise cannot starve the search.
    if distance(target.x,target.y,x,y)>4 then return true end
    return finite(z) and (not finite(target.z) or math.abs(target.z-z)>8)
end
local function projection(px,py,a,b,originZ)
    local dx,dy=b.x-a.x,b.y-a.y
    local length=dx*dx+dy*dy
    local t=length>0 and ((px-a.x)*dx+(py-a.y)*dy)/length or 0
    local u=math.max(0,math.min(1,t))
    local az,bz=finite(a.z) and a.z or originZ,b.z
    local z=finite(az) and finite(bz) and (az+(bz-az)*u) or nil
    return distance(px,py,a.x+dx*u,a.y+dy*u),t,u,z
end
local function sameFloor(pz,z)
    return not finite(pz) or not finite(z) or math.abs(pz-z)<=12
end
function W:_Follow(px,py,pz)
    local points,index=self.points,math.max(2,self.index or 2)
    local originZ=self.pathZ
    if self.pathTravel==nil then originZ=self.requestZ end
    -- Only adjacent segments may be acquired. A nearby return corridor in a
    -- U-shaped path is not proof that its earlier bends have been passed.
    local travel=self.travel or 0
    local travelled=math.max(0,travel-(self.pathTravel or self.requestTravel or 0))
    local credit=self.cornerCredit or 0
    -- A credit just observed at a corner is available after further motion,
    -- never through repeated UI reads of the same position.
    if self.cornerCreditTravel and travel<=self.cornerCreditTravel+.05 then credit=self.cornerCreditBefore or 0 end
    local budget=travelled+credit+12
    local firstIndex=index
    while index<#points do
        local a,b=points[index-1],points[index]
        local off,t,u,z=projection(px,py,a,b,index==2 and originZ or nil)
        local nextOff,nextT,nextU,nextZ=projection(px,py,b,points[index+1])
        local nextArc=self.arc[index]+nextU*(self.arc[index+1]-self.arc[index])
        local atB=distance(px,py,b.x,b.y)<=3 and sameFloor(pz,b.z)
        local ahead=nextT>=0 and nextOff<=12 and (t>=1 or nextOff+1<off)
        if not sameFloor(pz,nextZ) or nextArc>budget or not (atB or ahead) then break end
        index=index+1
    end
    self.index=index
    local off,t,u,z=projection(px,py,points[index-1],points[index],index==2 and originZ or nil)
    local along=self.arc[index-1]+u*(self.arc[index]-self.arc[index-1])
    self.progress=math.max(self.progress or 0,along)
    local behind=t<=.001 and distance(px,py,points[index-1].x,points[index-1].y)>12
    local floorOK=sameFloor(pz,z)
    -- Cutting an observed adjacent corner shortens the walked polyline. Keep
    -- that proved progress for later corners instead of exhausting a single
    -- twelve-yard allowance over the whole route. Do not enlarge this call's
    -- budget inside the loop or acquire a nearby non-adjacent return leg.
    if index>firstIndex and off<=12 and floorOK and not behind
        and travel>(self.cornerCreditTravel or self.pathTravel or self.requestTravel or 0)+.05 then
        local nextCredit=math.max(self.cornerCredit or 0,along-travelled)
        if nextCredit>(self.cornerCredit or 0)+.001 then
            self.cornerCreditBefore=self.cornerCredit or 0
            self.cornerCredit,self.cornerCreditTravel=nextCredit,travel
        end
    end
    return index,off,floorOK,behind
end
function W:_RecordMotion(px,py,pz)
    local trace=self.pending and self.trace
    if not trace then return end
    local previous=trace[#trace]
    local moved=distance(px,py,previous.x,previous.y)
    if moved<.05 and (not finite(pz) or not finite(previous.z) or math.abs(pz-previous.z)<.5) then return end
    local elapsed=math.max(0,now()-previous.time)
    local height=finite(pz) and finite(previous.z) and math.abs(pz-previous.z) or 0
    if elapsed<.09 and moved<2 and height<.75 then return end
    -- A position gap or blink is not evidence of walking a connecting segment.
    if (moved>math.max(3,elapsed*28) or (elapsed>2 and moved>7) or height>12) and self.traceValid then
        self.traceValid=false;diagnostic(self,"trace-gap")
    end
    if #trace>=TRACE_LIMIT then
        if self.traceValid then self.traceValid=false;diagnostic(self,"trace-limit") end
        return
    end
    trace[#trace+1]={x=px,y=py,z=pz,travel=self.travel or 0,time=now()}
end
function W:_Adopt(points,requestTravel,requestZ)
    if self.traceValid==false then
        self.trace,self.traceValid=nil,nil
        self.rejected=(self.rejected or 0)+1
        self.refreshWanted=true
        diagnostic(self,"trace-invalid")
        self.phase,self.text="pending","Actualizando el camino desde tu posición…"
        return false
    end
    local old={points=self.points,left=self.left,arc=self.arc,index=self.index,progress=self.progress,
        pathTravel=self.pathTravel,pathZ=self.pathZ,cornerCredit=self.cornerCredit,
        cornerCreditBefore=self.cornerCreditBefore,cornerCreditTravel=self.cornerCreditTravel}
    self.points,self.left,self.arc,self.index,self.progress=points,{},{[1]=0},2,0
    self.pathTravel,self.pathZ=requestTravel,requestZ
    self.cornerCredit,self.cornerCreditBefore,self.cornerCreditTravel=nil,nil,nil
    for i=2,#points do self.arc[i]=self.arc[i-1]+distance(points[i-1].x,points[i-1].y,points[i].x,points[i].y) end
    self.left[#points]=0
    for i=#points-1,1,-1 do self.left[i]=self.left[i+1]+distance(points[i].x,points[i].y,points[i+1].x,points[i+1].y) end
    local travel=self.travel or 0
    -- Replay what actually happened while the coroutine was working. Looking
    -- only at today's position cannot explain two corners already passed.
    if self.traceValid then
        for _,sample in ipairs(self.trace or {}) do
            self.travel=sample.travel
            self:_Follow(sample.x,sample.y,sample.z)
        end
    end
    self.travel=travel
    local latest=self.trace and self.trace[#self.trace]
    local px,py,pz=self.seenX,self.seenY,self.seenZ
    if not px or not py then px,py,pz=latest and latest.x,latest and latest.y,latest and latest.z end
    local _,off,floorOK,behind
    if px and py then _,off,floorOK,behind=self:_Follow(px,py,pz) end
    self.trace,self.traceValid=nil,nil
    if off and (off>30 or not floorOK or behind) then
        self.points,self.left,self.arc,self.index,self.progress=old.points,old.left,old.arc,old.index,old.progress
        self.pathTravel,self.pathZ=old.pathTravel,old.pathZ
        self.cornerCredit,self.cornerCreditBefore,self.cornerCreditTravel=old.cornerCredit,old.cornerCreditBefore,old.cornerCreditTravel
        self.rejected=(self.rejected or 0)+1
        self.refreshWanted=true
        diagnostic(self,not floorOK and "floor" or behind and "behind" or "drift")
        self.phase,self.text="pending","Actualizando el camino desde tu posición…"
        return false
    end
    self.accepted=(self.accepted or 0)+1
    self.refreshWanted=nil
    diagnostic(self,"accepted")
    self.phase,self.text="walking","Siguiendo el camino por el terreno"
    return true
end
function W:Resolve(point)
    if type(point)~="table" then self:Clear();return nil end
    local config=settings()
    if not config then return point end
    local out=copy(point)
    if not config.enabled then
        if self.key then self:Clear() end
        self.phase,self.text="disabled","Dirección orientativa; camino por terreno desactivado"
        out.navigationNotice=self.text;return out
    end
    local engine=RutaXPPathEngine
    local continent,gx,gy=ns:GetWaypointWorldPosition(point)
    local here=ns.PlayerPoint and ns:PlayerPoint()
    local pc,px,py
    if here then pc,px,py=ns:GetWaypointWorldPosition(here) end
    if not engine or not engine.Find or not engine.Available or read(engine.Available,continent)~=true then
        if self.key then self:Clear() end
        self.phase,self.text="unavailable","Dirección orientativa: sin datos de terreno para esta zona"
        out.navigationNotice=self.text;return out
    end
    if not finite(gx) or not finite(gy) or pc~=continent or not finite(px) or not finite(py) then
        self:Clear();self.phase,self.text="unavailable","El camino necesita posiciones del mismo continente"
        out.navigationNotice=self.text;return out
    end
    local ux,uy,uz,instance=read(UnitPosition,"player")
    local pz
    -- Forever can return 0 for an unread height. Keep it unknown rather than
    -- rejecting real terrain floors while walking (SendaFH Core/Compat.lua).
    if finite(uz) and uz~=0 and instance==pc then pz=uz end
    if finite(ux) and finite(uy) and instance==pc and distance(ux,uy,px,py)>100 then
        self:Clear();self.phase,self.text="unavailable","Dirección orientativa: esta fase no coincide con los datos de terreno"
        out.navigationNotice=self.text;return out
    end
    -- Pathing and its floor samples use the same native coordinate frame.
    -- Map positions remain for the semantic marker and map conversion only.
    if finite(ux) and finite(uy) and instance==pc then px,py=ux,uy end
    if read(IsInInstance)==true then
        self:Clear();self.phase,self.text="unavailable","Dirección orientativa: esta instancia no tiene datos de terreno"
        out.navigationNotice=self.text;return out
    end
    if read(UnitIsDeadOrGhost,"player")==true or read(IsFlying)==true or read(UnitOnTaxi,"player")==true then
        self:Clear();self.phase,self.text="unavailable","Dirección orientativa durante vuelo o viaje de fantasma"
        out.navigationNotice=self.text;return out
    end
    local key=pointKey(point,continent)
    local latest={x=gx,y=gy,z=finite(point.z) and point.z or nil}
    local candidate=point.candidate
    local goal=point.goal or {}
    local resourceCandidate=candidate and candidate.objectiveIndex and (goal.quest or goal.questID)
        and (goal.t=="complete" or goal.t=="objective" or goal.t=="collect" or goal.t=="kill")
    if self.key~=key then
        self:Clear("key");self.key,self.engine=key,engine
        self.seenX,self.seenY,self.seenZ,self.seenAt,self.travel=px,py,pz,now(),0
        self.latestTarget,self.campCommitted=latest,resourceCandidate and true or nil
        self:_Ask(engine,continent,px,py,pz,latest,"key")
    else
        local moved=self.seenX and distance(px,py,self.seenX,self.seenY) or 0
        self.seenX,self.seenY,self.seenZ,self.seenAt=px,py,pz,now()
        self.latestTarget=latest
        if moved>60 then
            -- A teleport or a long position gap cannot justify jumping over
            -- the old path's turns. Start a fresh search at the new position.
            self:Clear("teleport");self.key,self.engine=key,engine
            self.seenX,self.seenY,self.seenZ,self.seenAt,self.travel=px,py,pz,now(),0
            self.latestTarget,self.campCommitted=latest,resourceCandidate and true or nil
            self:_Ask(engine,continent,px,py,pz,latest,"teleport")
        else
            self.travel=(self.travel or 0)+moved
            self:_RecordMotion(px,py,pz)
        end
        if self.campCommitted and self.target and distance(px,py,self.target.x,self.target.y)<=12
            and sameFloor(pz,self.target.z) then self.campCommitted=nil end
        local changed=targetMoved(self.target,gx,gy,point.z)
        if changed and not self.campCommitted then self.refreshWanted=true end
        -- NPC/object spawns are alternatives for the same quest objective.
        -- Keep the selected camp while its corridor is valid, even if its
        -- detour makes another camp look closer halfway through the search.
        if not self.pending and (self.refreshWanted or changed and not self.campCommitted)
            and (changed or not self.failure or now()-(self.failedAt or 0)>=15)
            and now()-(self.lastAsk or -100)>=2 then
            self.campCommitted=resourceCandidate and true or nil
            self:_Ask(engine,continent,px,py,pz,latest,changed and "destination" or "refresh")
        end
        if not self.pending and not self.points and now()-(self.lastAsk or -100)>=2 and (not self.failure
            or (now()-(self.failedAt or 0)>=15 and distance(px,py,self.failedX or px,self.failedY or py)>20)) then
            self:_Ask(engine,continent,px,py,pz,latest,"query")
        end
    end
    if self.pending then
        self.phase="pending"
        self.text=combat() and "Esperando a salir del combate para continuar el cálculo" or "Calculando un camino transitable…"
    end
    local points,index=self.points,self.index or 1
    if points then
        local off,floorOK,behind
        index,off,floorOK,behind=self:_Follow(px,py,pz)
        -- Replan from where the player really is; never skip across a wall
        -- to a later nearby segment or a floor directly above the player.
        if off>30 or not floorOK or behind then
            self.points,self.left,self.arc,self.index=nil,nil,nil,nil
            self.campCommitted=nil
            self.refreshWanted=true
            diagnostic(self,not floorOK and "floor" or behind and "behind" or "drift")
            if not self.pending and now()-(self.lastAsk or -100)>=2 then self:_Ask(engine,continent,px,py,pz,latest,not floorOK and "floor" or behind and "behind" or "drift") end
            self.phase,self.text="pending","Recalculando el camino desde tu posición…"
            out.navigationBlocked,out.navigationNotice=true,self.text;return out
        end
        local node=points[index]
        if index==#points and (self.pending or self.refreshWanted) and distance(px,py,node.x,node.y)<=12 then
            self.phase,self.text="pending","Actualizando el camino hasta el nuevo destino…"
            out.navigationBlocked,out.navigationNotice=true,self.text;return out
        end
        local aim=ns.WorldToWaypoint and ns:WorldToWaypoint(continent,node.x,node.y,here.mapID)
        if not aim then
            self.phase,self.text="unavailable","No se puede situar el siguiente giro en este mapa"
            out.navigationBlocked,out.navigationNotice=true,self.text;return out
        end
        out.mapID,out.x,out.y,out.z=aim.mapID,aim.x,aim.y,node.z
        out.walking,out.walkingIndex,out.walkingCount=true,index,#points
        out.walkingWorld={continent=continent,north=node.x,west=node.y}
        out.walkingDistance=distance(px,py,node.x,node.y)+(self.left[index] or 0)
        out.walkingFinal,out.walkingGoal=index==#points and not self.pending and not self.refreshWanted,point
        out.navigationNotice=nil
        self.phase,self.text="walking","Camino por terreno · tramo "..math.max(1,index-1).."/"..(#points-1)
            ..((self.pending or self.refreshWanted) and " · actualizando" or "")
        return out
    end
    out.navigationBlocked,out.navigationNotice=true,self.text
    return out
end
