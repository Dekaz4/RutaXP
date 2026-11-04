-- RutaXP's private walking namespace; keep installed pathing addons isolated.
local _, root = ...
root.PathingNamespace = {}
local enc = C_EncodingUtil
local method = Enum and Enum.CompressionMethod
RutaXPPathingSupported = type(enc)=="table" and type(enc.DecodeBase64)=="function"
    and type(enc.DecompressString)=="function" and type(method)=="table" and method.Zlib~=nil
    and type(C_Timer)=="table" and type(C_Timer.After)=="function"
root.PathingNamespace.supported = RutaXPPathingSupported
root.PathingNamespace.unsupportedReason = not RutaXPPathingSupported
    and "El cliente no ofrece decodificación Zlib o temporizadores para las rutas terrestres." or nil
-- These are private copies: neither SendaFH nor Shortest Path Forever data is reused.
RutaXPPathData = {}
RutaXPPathChokepoints = {}
