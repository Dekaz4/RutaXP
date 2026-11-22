local _, ns = ...
-- Ground routing uses Shortest Path Forever by Cillian Berragan and the
-- pinned Polestar/SendaFH walking maps in Pathing/ (GPL-3.0-or-later).
-- This follower only steers the arrow; it never moves a quest cursor.
local W = { phase="idle", serial=0, requests=0, cancellations=0 }
ns.Walking = W
local TRACE_LIMIT = 512
local SEARCH_SECONDS = 12
local PROGRESSING_SEARCH_SECONDS = 20
local SEARCH_CPU_MS = 600
local TARGET_GAP_SECONDS = 0.75
-- Distances in terrain yards. Renew a reference about two seconds before
-- reaching it at running speed, unless it is the actual turn.
local REFERENCE_SPACING = 56
local REFERENCE_LEAD = 14
local LOOKAHEAD = REFERENCE_SPACING + REFERENCE_LEAD
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
    self.budgetUpdated,self.activeSeconds,self.retryAfter,self.timeoutRetried,self.missingSince=nil,nil,nil,nil,nil
    self.startMap,self.lastRejectedX,self.lastRejectedY=nil,nil,nil
    self.turns,self.turnCursor,self.steeringIndex,self.corridor=nil,nil,nil,nil
    self.phase,self.text="idle","Esperando un destino"
end
local function failed(self,reason,px,py,message)
    self.failure,self.failedAt,self.failedX,self.failedY=reason,now(),px,py
    self.trace,self.traceValid=nil,nil
    self.refreshWanted=true
    self.phase,self.text="failed",message
end
local function checkBudget(self,px,py)
    if not self.pending then return end
    local stamp=now()
    if not combat() and not self.wasPaused then
        self.activeSeconds=self.activeSeconds+math.max(0,stamp-self.budgetUpdated)
    end
    self.budgetUpdated,self.wasPaused=stamp,combat()
    local cpu=type(self.job)=="table" and self.job.cpu or 0
    local frames=type(self.job)=="table" and self.job.frames or 0
    if frames>self.jobFrames then self.jobFrames,self.lastProgressAt=frames,self.activeSeconds end
    local progressing=frames>0 and self.activeSeconds-self.lastProgressAt<2
    local limit=progressing and PROGRESSING_SEARCH_SECONDS or SEARCH_SECONDS
    if self.activeSeconds < limit and cpu < SEARCH_CPU_MS then return end
    -- A scheduler that never pumped may recover. A search already consuming
    -- frames gets no second full budget at the same position and endpoint.
    local stalled=not self.job or type(self.job)~="table" or (self.job.frames or 0)==0
    self:_Cancel("timeout")
    failed(self,"timeout",px,py,"Se agotó el tiempo de cálculo del camino")
    if stalled and not self.timeoutRetried then self.retryAfter=stamp+2 end
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
    if combat() then self.phase,self.text="pending","Sal del combate para calcular el camino"; return end
    if read(IsFalling)==true then self.phase,self.text="pending","Esperando a pisar el suelo para calcular el camino"; return end
    self:_Cancel()
    local token=self.serial
    self.pending,self.lastAsk,self.failure=true,now(),nil
    self.budgetUpdated,self.activeSeconds,self.wasPaused,self.retryAfter=self.lastAsk,0,false,nil
    self.jobFrames,self.lastProgressAt=0,0
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
            failed(self,type(reason)=="string" and reason or "unreachable",px,py,
                "No hay un camino comprobado hasta ese punto; revisa el acceso")
            diagnostic(self,"failed")
            return
        end
        if self:_Adopt(points,requestTravel,requestZ) then
            self.lastRejectedX,self.lastRejectedY,self.timeoutRetried=nil,nil,nil
        else
            -- One new origin can recover after a stale answer. Repeatedly
            -- rejecting the same origin/floor must settle like an offmesh hit.
            if self.lastRejectedX and distance(px,py,self.lastRejectedX,self.lastRejectedY)<20 then
                failed(self,"stale",px,py,"El camino calculado no coincide con tu posición")
            end
            self.lastRejectedX,self.lastRejectedY=px,py
        end
    end,false)
    if not ok then
        self.pending,self.job=nil,nil
        failed(self,"error",px,py,"No se pudo calcular el camino; usa /rutaxp recalcular")
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
    return table.concat({identity(point.targetKey),identity(point.activityKey),identity(source),identity(guideID),identity(stepIndex),identity(goalIndex),
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
-- A shortcut is safe on the path engine's mesh only if it takes the same
-- ordered cell-to-cell moves (including diagonals) as the certified route.
-- This bounded walk only reads the grid scale, never decompresses terrain.
local function cellMoves(ax,ay,bx,by,cell)
    ax,ay,bx,by=ax/cell,ay/cell,bx/cell,by/cell
    local x,y,ex,ey=math.floor(ax),math.floor(ay),math.floor(bx),math.floor(by)
    local dx,dy=bx-ax,by-ay
    local sx,sy=dx>=0 and 1 or -1,dy>=0 and 1 or -1
    local function crossing(v,start,delta,sign)
        if delta==0 then return math.huge end
        return (v+(sign>0 and 1 or 0)-start)/delta
    end
    local moves={}
    while x~=ex or y~=ey do
        local tx=x~=ex and crossing(x,ax,dx,sx) or math.huge
        local ty=y~=ey and crossing(y,ay,dy,sy) or math.huge
        local mx,my=tx<=ty and sx or 0,ty<=tx and sy or 0
        moves[#moves+1]=string.char(5+3*mx+my)
        x,y=x+mx,y+my
    end
    return table.concat(moves)
end

-- PathGrid.Idle releases its decoded pages immediately after the callback.
-- Keep only nearby pages on this route, at most four and 6 MiB in total
-- (PathGrid's own estimates). The HUD never loads or decodes a page.
local function routeCorridor(points,index)
    local grid=ns.PathingNamespace and ns.PathingNamespace.PathGrid
    local st=grid and grid.State and grid.State(points[index].map)
    if not (st and st.val and st.cs and st.C) then return nil end
    local saved={map=points[index].map,C=st.C,ny=st.ny,cs=st.cs,x0=st.x0,y0=st.y0,GX=st.GX,GY=st.GY,
        val={},z={},moves={},at={},links={}}
    local pages,kb,covered=0,0,0
    for i=index,math.min(#points,index+128) do
        local a,b=points[i-1],points[i]
        local length=distance(a.x,a.y,b.x,b.y)
        local step=math.max(1,math.ceil(length/(st.C*st.cs*.35)))
        for s=0,step do
            local u=s/step
            if covered+length*u>1500 then return saved end
            local x,y=a.x+(b.x-a.x)*u,a.y+(b.y-a.y)*u
            local k=math.floor((x-st.x0)/(st.C*st.cs))*st.ny+math.floor((y-st.y0)/(st.C*st.cs))
            local size=st.sizes and st.sizes[k] or 0
            if st.val[k] and not saved.val[k] and kb+size<=6144 then
                saved.val[k],saved.z[k],saved.moves[k],saved.at[k],saved.links[k]=
                    st.val[k],st.z[k],st.moves[k],st.at[k],st.links[k]
                pages,kb=pages+1,kb+size
                if pages==4 then return saved end
            end
        end
        covered=covered+length
    end
    return saved
end

-- A lateral shortcut needs open dry ground on BOTH sides, with no extra
-- floors/links and no rises or drops. The original polyline is always the
-- fallback on narrow bridges, stairs, around walls and in cave entrances.
local function openRoad(continent,px,py,pz,b,corridor)
    if not (corridor and corridor.map==continent and finite(pz) and finite(b.z)) then return false end
    local st=corridor
    local length=distance(px,py,b.x,b.y)
    if length>124 or math.abs(b.z-pz)>3+.20*length then return false end
    local C,cell=st.C,st.cs
    local count=math.max(1,math.ceil(2*length/cell))
    if count>64 then return false end
    local lastX,lastY
    for s=0,count do
        local u=s/count
        local gx=math.floor((px+(b.x-px)*u-st.x0)/cell)
        local gy=math.floor((py+(b.y-py)*u-st.y0)/cell)
        if gx~=lastX or gy~=lastY then
            if gx<1 or gy<1 or gx>=st.GX-1 or gy>=st.GY-1 then return false end
            local x,y=gx%C,gy%C
            if x<1 or y<1 or x>=C-1 or y>=C-1 then return false end
            local k=math.floor(gx/C)*st.ny+math.floor(gy/C)
            local val,heights,moves,floors,links=st.val[k],st.z[k],st.moves[k],st.at[k],st.links[k]
            if not (val and heights and moves and floors and links) then return false end
            local i=x*C+y+1
            local height=heights[i]
            if not finite(height) or math.abs(height-(pz+(b.z-pz)*u))>3 then return false end
            for dx=-1,1 do
                for dy=-1,1 do
                    local j=i+dx*C+dy
                    if val[j]~=1 or floors[-j] or links[j] or not finite(heights[j]) or math.abs(heights[j]-height)>2 then return false end
                    -- Require every cardinal edge inside this 3x3 window.
                    local m=moves[j] or 0
                    if (dx<1 and m%2<1) or (dy<1 and m%4<2) then return false end
                end
            end
            lastX,lastY=gx,gy
        end
    end
    return true
end

-- A mild bend counts only when the road holds its direction on each side.
-- Measuring length rather than counting nodes handles both sparse roads and
-- short, closely spaced mesh edges without announcing their zigzags.
local function holdsDirection(points,index,step,dx,dy)
    local length=0
    for i=index,index+step*7,step do
        local a,b=points[i],points[i+step]
        if not b then break end
        local x,y=b.x-a.x,b.y-a.y
        local edge=math.sqrt(x*x+y*y)
        if edge>0 then
            if x*dx+y*dy<.98*edge then return false end
            length=length+edge
            if length>=16 then return true end
        end
    end
    return false
end

local function findTurns(points)
    local result={}
    local anchorX,anchorY
    for i=2,#points-1 do
        local a,b,c=points[i-1],points[i],points[i+1]
        local ix,iy=b.x-a.x,b.y-a.y
        local ox,oy=c.x-b.x,c.y-b.y
        local il,ol=math.sqrt(ix*ix+iy*iy),math.sqrt(ox*ox+oy*oy)
        if il>=1 and ol>=1 then
            ix,iy,ox,oy=ix/il,iy/il,ox/ol,oy/ol
            anchorX,anchorY=anchorX or ix,anchorY or iy
            local dot=ix*ox+iy*oy
            local localBend=dot<.84 or (dot<.91 and holdsDirection(points,i,-1,-ix,-iy)
                and holdsDirection(points,i,1,ox,oy))
            if localBend or anchorX*ox+anchorY*oy<.72 then
                local cross=anchorX*oy-anchorY*ox
                if localBend then cross=ix*oy-iy*ox end
                -- UnitPosition's axes are north, west: a positive cross turns left.
                result[#result+1]={index=i,side=math.abs(cross)>.08 and (cross>0 and "left" or "right") or nil}
                anchorX,anchorY=ox,oy
            end
        end
    end
    return result
end

local function nextTurn(self,index)
    if not self.turns then self.turns,self.turnCursor=findTurns(self.points),1 end
    local turn=self.turns[self.turnCursor]
    while turn and turn.index<index do
        self.turnCursor=self.turnCursor+1
        turn=self.turns[self.turnCursor]
    end
    return turn
end

-- Certify the whole ray from the actual player position. Same ordered mesh
-- crossings on the path's height profile are sufficient even in a passage.
-- For a different set of crossings we require a wide, walkable mesh corridor.
local function canAim(points,index,last,continent,px,py,pz,corridor,endpoint)
    local b=endpoint or points[last]
    if last-index>24 or distance(px,py,b.x,b.y)>145 then return false end
    local prev,node=points[index-1],points[index]
    local off,_,u,z=projection(px,py,prev,node,pz)
    if off>12 or not finite(z) or (finite(pz) and math.abs(pz-z)>2.5) or not finite(b.z) then return false end
    local origin={x=px,y=py,z=pz or z}
    local ax,ay=prev.x+(node.x-prev.x)*u,prev.y+(node.y-prev.y)*u
    local data=RutaXPPathData and RutaXPPathData[continent]
    local grid=ns.PathingNamespace and ns.PathingNamespace.PathGrid
    local cell=data and grid and grid.TILE/data.cells
    local same=cell and math.floor(px/cell)==math.floor(ax/cell) and math.floor(py/cell)==math.floor(ay/cell)
    if not cell then same=off<.001 end
    local moves={}
    local az=z
    for i=index,last do
        local p=i==last and b or points[i]
        local dist=distance(ax,ay,p.x,p.y)
        if not finite(p.z) or math.abs(p.z-az)>1+.30*dist then return false end
        local gap,_,_,height=projection(p.x,p.y,origin,b)
        if gap>12 or not height or math.abs(p.z-height)>2 then return false end
        if gap>(cell and 1.5 or .00001) then same=false end
        if same and cell then moves[#moves+1]=cellMoves(ax,ay,p.x,p.y,cell) end
        ax,ay,az=p.x,p.y,p.z
    end
    if same and (not cell or cellMoves(px,py,b.x,b.y,cell)==table.concat(moves)) then return true end
    return openRoad(continent,px,py,pz,b,corridor)
end

local function steeringPoint(points,index,continent,px,py,pz)
    local node=points[index]
    if index>=#points or distance(px,py,node.x,node.y)>25 then return node end
    local previous=points[index-1]
    local off,_,u,z=projection(px,py,previous,node,pz)
    if off>1.5 or not finite(z) or (finite(pz) and math.abs(z-pz)>2) then return node end
    local ax,ay=previous.x+(node.x-previous.x)*u,previous.y+(node.y-previous.y)*u
    local grid=ns.PathingNamespace and ns.PathingNamespace.PathGrid
    local data=RutaXPPathData and RutaXPPathData[continent]
    local cell=grid and data and finite(grid.TILE) and finite(data.cells) and data.cells>0 and grid.TILE/data.cells
    -- Tile origins are integer multiples of the cell size on both axes.
    if cell and (math.floor(px/cell)~=math.floor(ax/cell) or math.floor(py/cell)~=math.floor(ay/cell)) then return node end
    local origin={x=px,y=py,z=pz or z}
    local aim=node
    local walked=distance(ax,ay,node.x,node.y)
    local grade=finite(pz) and .35 or .05
    if math.abs(node.z-z)>grade*walked then return node end
    local moves=cell and cellMoves(ax,ay,node.x,node.y,cell) or ""
    for j=index,math.min(#points-1,index+5) do
        local a,b=points[j],points[j+1]
        local dx,dy=b.x-a.x,b.y-a.y
        local length=math.sqrt(dx*dx+dy*dy)
        local incoming=distance(ax,ay,a.x,a.y)
        if length<.01 or incoming<.01 or walked>=36 or not finite(a.z) or not finite(b.z) then break end
        if ((a.x-ax)*dx+(a.y-ay)*dy)<.98*incoming*length or math.abs(b.z-a.z)>grade*length then break end
        local fraction=math.min(1,(36-walked)/length)
        local target=fraction==1 and b or {x=a.x+fraction*dx,y=a.y+fraction*dy,z=a.z+fraction*(b.z-a.z)}
        local safe=true
        for k=index,j do
            local bend=points[k]
            local gap,_,_,height=projection(bend.x,bend.y,origin,target)
            if gap>(cell and 1.5 or .00001) or math.abs(bend.z-height)>1 then safe=false; break end
        end
        if not safe then break end
        if cell then
            moves=moves..cellMoves(a.x,a.y,target.x,target.y,cell)
            if cellMoves(px,py,target.x,target.y,cell)~=moves then break end
        end
        aim=target
        if fraction<1 then break end
        walked,ax,ay=walked+length,a.x,a.y
    end
    return aim
end

local function maneuverPoint(self,index,turn,continent,px,py,pz)
    local points=self.points
    local limit=turn and turn.index or #points
    local node=points[index]
    local previous=points[index-1]
    local length=self.arc[index]-self.arc[index-1]
    if length>LOOKAHEAD and finite(previous.z) and finite(node.z) then
        -- Fixed anchors along the certified edge. Reading the HUD repeatedly
        -- or swaying near an anchor must not move it backwards and forwards.
        local along=self.progress-self.arc[index-1]
        local nextAnchor=(math.floor((along+REFERENCE_LEAD)/REFERENCE_SPACING)+1)*REFERENCE_SPACING
        if nextAnchor<length-REFERENCE_LEAD then
            local u=nextAnchor/length
            local anchor={x=previous.x+(node.x-previous.x)*u,y=previous.y+(node.y-previous.y)*u,
                z=previous.z+(node.z-previous.z)*u}
            if canAim(points,index,index,continent,px,py,pz,self.corridor,anchor) then
                self.steeringIndex=nil
                return anchor
            end
        end
    end
    if limit==index then self.steeringIndex=nil;return points[index] end
    local held=self.steeringIndex
    if held and held>=index and held<=limit and
        (held==limit or distance(px,py,points[held].x,points[held].y)>REFERENCE_LEAD) and
        (held==index or canAim(points,index,held,continent,px,py,pz,self.corridor)) then return points[held] end
    self.steeringIndex=nil
    -- Try the actual corner first. On open ground a nearer mesh vertex has no
    -- meaning to the player. A blind turn still uses its last certified approach.
    local firstLeg=distance(px,py,node.x,node.y)
    for j=math.min(limit,index+24),index+1,-1 do
        if firstLeg+self.arc[j]-self.arc[index]<=LOOKAHEAD and
            (turn or openRoad(continent,px,py,pz,points[j],self.corridor)) and
            canAim(points,index,j,continent,px,py,pz,self.corridor) then
            self.steeringIndex=j
            return points[j]
        end
    end
    return steeringPoint(points,index,continent,px,py,pz)
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
    self.turns,self.turnCursor,self.steeringIndex=nil,nil,nil
    self.corridor=routeCorridor(points,self.index)
    self.refreshWanted=nil
    diagnostic(self,"accepted")
    self.phase,self.text="walking","Siguiendo el camino por el terreno"
    return true
end
local function blockedWaypoint(self, point)
    point.navigationBlocked, point.navigationNotice = true, self.text
    if self.startMap and self.startMap==point.mapID and not combat() and read(IsFalling)~=true then
        point.navigationBearing=true
        point.navigationBearingText=self.pending and "Rumbo orientativo · calculando camino" or "Rumbo orientativo · camino sin confirmar"
    end
    if self.phase == "pending" then
        if combat() then
            point.navigationHint = "Sal de combate"
        elseif not self.pending and read(IsFalling) == true then
            point.navigationHint = "Espera a tocar el suelo"
        end
    elseif self.phase == "failed" then
        point.navigationHint = self.failure == "error" and "Recalcula el camino" or "Revisa el acceso"
    end
    return point
end

function W:Resolve(point)
    if type(point)~="table" then
        if self.key then
            self.missingSince=self.missingSince or now()
            if now()-self.missingSince>=TARGET_GAP_SECONDS then self:Clear("target-lost") end
        end
        return nil
    end
    self.missingSince=nil
    local config=settings()
    if not config then return point end
    local out=copy(point)
    local engine=RutaXPPathEngine
    local continent,gx,gy=ns:GetWaypointWorldPosition(point)
    local here=ns.PlayerPoint and ns:PlayerPoint()
    local pc,px,py
    if here then pc,px,py=ns:GetWaypointWorldPosition(here) end
    if (pc and continent and pc~=continent) or (not (pc and continent) and (not here or here.mapID~=point.mapID)) then
        if self.key then self:Clear("map") end
        self.phase,self.text="unavailable","Esperando un tramo local de viaje"
        out.navigationBlocked,out.navigationNotice=true,self.text
        return out
    end
    if not config.enabled then
        if self.key then self:Clear() end
        self.phase,self.text="disabled","Dirección orientativa; camino por terreno desactivado"
        out.navigationNotice=self.text;return out
    end
    if not engine or not engine.Find or not engine.Available or read(engine.Available,continent)~=true or
        not finite(gx) or not finite(gy) or not finite(px) or not finite(py) then
        if self.key then self:Clear() end
        self.phase,self.text="unavailable","Dirección orientativa: sin datos de terreno para esta zona"
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
    if self.key~=key or self.startMap~=here.mapID then
        self:Clear("key");self.key,self.engine=key,engine
        self.startMap=here.mapID
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
            self.startMap=here.mapID
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
        checkBudget(self,px,py)
        -- NPC/object spawns are alternatives for the same quest objective.
        -- Keep the selected camp while its corridor is valid, even if its
        -- detour makes another camp look closer halfway through the search.
        local newTarget=changed and not self.campCommitted
        local repositioned=self.failure and now()-(self.failedAt or 0)>=15 and
            distance(px,py,self.failedX or px,self.failedY or py)>20
        local retry=self.retryAfter and now()>=self.retryAfter
        if not self.pending and now()-(self.lastAsk or -100)>=2 and
            (newTarget or repositioned or retry or (not self.failure and (self.refreshWanted or not self.points))) then
            if retry then self.timeoutRetried=true
            elseif newTarget or repositioned then self.timeoutRetried=nil end
            self.campCommitted=resourceCandidate and true or nil
            self:_Ask(engine,continent,px,py,pz,latest,newTarget and "destination" or retry and "timeout-retry" or "refresh")
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
        -- During a refresh, only keep the old instruction if we can still
        -- connect to its corridor. Above the lateral allowance even a nearby
        -- road can be on the far side of a wall.
        local stale=self.pending or self.refreshWanted or self.failure
        local lost=off>(stale and 6 or 12) and not canAim(points,index,index,continent,px,py,pz,self.corridor)
        if off>30 or not floorOK or behind or lost then
            self.points,self.left,self.arc,self.index=nil,nil,nil,nil
            self.turns,self.turnCursor,self.steeringIndex,self.corridor=nil,nil,nil,nil
            self.campCommitted=nil
            self.refreshWanted=true
            diagnostic(self,not floorOK and "floor" or behind and "behind" or "drift")
            if not self.pending and now()-(self.lastAsk or -100)>=2 then self:_Ask(engine,continent,px,py,pz,latest,not floorOK and "floor" or behind and "behind" or "drift") end
            self.phase,self.text="pending","Recalculando el camino desde tu posición…"
            return blockedWaypoint(self, out)
        end
        local node=points[index]
        if index==#points and (self.pending or self.refreshWanted) and distance(px,py,node.x,node.y)<=12 then
            if self.failure and not self.pending then
                self.phase,self.text="failed","Falta confirmar el camino desde aquí hasta el nuevo destino"
            else
                self.phase,self.text="pending","Actualizando el camino hasta el nuevo destino…"
            end
            return blockedWaypoint(self, out)
        end
        local turn=nextTurn(self,index)
        local visual=maneuverPoint(self,index,turn,continent,px,py,pz)
        local aim=ns.WorldToWaypoint and ns:WorldToWaypoint(continent,visual.x,visual.y,here.mapID)
        if not aim then
            self.phase,self.text="unavailable","No se puede situar el siguiente giro en este mapa"
            return blockedWaypoint(self, out)
        end
        out.mapID,out.x,out.y,out.z=aim.mapID,aim.x,aim.y,visual.z
        out.walking,out.walkingIndex,out.walkingCount=true,index,#points
        out.walkingWorld={continent=continent,north=visual.x,west=visual.y}
        out.walkingRouteKey=key
        if turn and turn.side then
            out.walkingTurn=turn.side
            out.walkingTurnDistance=distance(px,py,node.x,node.y)+self.arc[turn.index]-self.arc[index]
        end
        out.walkingDistance=distance(px,py,node.x,node.y)+(self.left[index] or 0)
        out.walkingFinal=index==#points and visual==node and not self.pending and not self.refreshWanted
        out.walkingGoal=point
        out.navigationNotice=nil
        self.phase,self.text="walking","Camino por terreno · tramo "..math.max(1,index-1).."/"..(#points-1)
            ..(self.pending and " · actualizando" or self.failure and " · tramo final sin confirmar"
                or self.refreshWanted and " · actualizando" or "")
        return out
    end
    return blockedWaypoint(self, out)
end
