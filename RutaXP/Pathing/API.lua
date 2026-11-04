-- RutaXP mechanical adaptation, 2026-10-20; tools/vendor_pathing.py.
-- Source: julen92/SendaFH@5d207e28e82e2c529143b21ace74fe88692f0067; original notices follow.
-- SendaFH_Nav's handoff to SendaFH: the global RutaXPPathEngine is Shortest
-- Path Forever's Path table (Routing/), which SendaFH's Nav keeps as
-- ns.Nav.Path. Its calls are upstream's: Find(map, from, to, callback,
-- waterWalking), FindCost, FindMany, Cancel(job), Busy(), with points in
-- UnitPosition's frame (x north, y west, z optional) and map the instance map
-- ID (0 Eastern Kingdoms, 1 Kalimdor, 2991 Zephras Isle). The maps of 0 and 1
-- are SendaFH's own (`nav pack`, PACK.json: 128 cells a tile, 4.17 yd), 2991
-- is his. The engine reads only RutaXPPathData, our own copy of the maps,
-- never an installed Shortest Path Forever's tables (its engine evicts
-- decoded entries while ours may be searching them). Added here:
--
--   Path.Available(map) -> true when walking routes can be found on that map
--
-- Memory ceilings (docs/ARCHITECTURE.md, "In-game walking routes"): his are
-- 24 MB of decoded grids and 4 MB of decoded graph, sized for his 8 yd cells.
-- Our 4.17 yd cells hold 3.7 times as many cells a tile: by the engine's own
-- accounting a cluster decodes to 3.3 MB on average (his: 1.0 MB): Razor
-- Hill to the Valley of Strength (through Orgrimmar, 4 clusters) decodes
-- 28.5 MB of grids, a 7,700 yd walk from the Crossroads to Tanaris 46.4 MB
-- in 17 clusters with 4.9 MB of graph; a continent's whole graph decodes to
-- 4.2 MB (Eastern Kingdoms) and 4.9 MB (Kalimdor). So 48 MB of grids holds
-- such a walk without evicting a cluster mid-search, and 6 MB of graph a
-- continent's whole graph. Both are ceilings: Idle drops the decoded grids
-- when no search is queued.
local _, root = ...
local ns = root.PathingNamespace
local Path = ns.Path

Path.cacheKB = 48 * 1024
Path.graphKB = 6 * 1024

function Path.Available(map)
	return map ~= nil and Path.HasData(map)
end

-- A map is used whole or not at all: one whose packed tables do not hold the
-- entries its `counts` promise (a part file missing from the folder, or one
-- that failed to load) is dropped, and so is every map when the client lacks
-- C_EncodingUtil's DecodeBase64 or DecompressString (the engine would raise
-- a Lua error decoding the first cluster). Path.HasData is then false for
-- that map and SendaFH's arrow points straight. A part's bytes are not
-- checked here: the shipped files are pinned by sha256.
local enc = C_EncodingUtil
local decodes = type(enc) == "table" and type(enc.DecodeBase64) == "function" and type(enc.DecompressString) == "function"
for map, D in pairs(type(RutaXPPathData) == "table" and RutaXPPathData or {}) do
	local whole = decodes and type(D) == "table"
	if whole and type(D.packed) == "table" and type(D.counts) == "table" then
		for field, want in pairs(D.counts) do
			local n = 0
			for _ in pairs(D.packed[field] or {}) do
				n = n + 1
			end
			if n ~= want then
				whole = false
				break
			end
		end
	end
	if not whole then
		RutaXPPathData[map] = nil
	end
end

RutaXPPathEngine = Path
