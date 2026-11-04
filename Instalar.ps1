# Dot-source to load helpers without running the installer. PowerShell 5.1+.
function Get-RutaXPFullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $value = $Path.Trim().Trim('"').Trim()
    if (-not $value -or -not [IO.Path]::IsPathRooted($value) -or ([IO.Path]::GetPathRoot($value).Length -lt 3 -and -not $value.StartsWith('\\'))) { throw 'Introduce una ruta absoluta.' }
    $full = [IO.Path]::GetFullPath($value)
    if ($full.Length -gt [IO.Path]::GetPathRoot($full).Length) { $full = $full.TrimEnd('\', '/') }
    return $full
}

function Assert-RutaXPNoLinks {
    param([string]$Path)
    $current = Get-RutaXPFullPath $Path
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "No se permiten enlaces o junctions: $current" }
        }
        $parent = [IO.Path]::GetDirectoryName($current)
        if ($parent -eq $current) { break }
        $current = $parent
    }
}

function Test-RutaXPForeverClient {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return $false }
    if ([IO.Path]::GetFileName((Get-RutaXPFullPath $Path)) -in @('_classic_beta_', '_forever_')) { return $true }
    foreach ($name in @('Wow.exe', 'WowB.exe', 'WowClassic.exe')) {
        $exe = Join-Path $Path $name
        if (Test-Path -LiteralPath $exe -PathType Leaf) {
            try { if ([Diagnostics.FileVersionInfo]::GetVersionInfo($exe).FileVersion -match '^1\.60\.') { return $true } } catch { }
        }
    }
    return $false
}

function Resolve-RutaXPAddonFolders {
    param([Parameter(Mandatory=$true)][string]$Path)
    $full = Get-RutaXPFullPath $Path
    Assert-RutaXPNoLinks $full
    $client = $full
    if ([IO.Path]::GetFileName($full) -ieq 'AddOns') {
        $interface = [IO.Path]::GetDirectoryName($full)
        if ([IO.Path]::GetFileName($interface) -ine 'Interface') { throw 'AddOns debe estar dentro de Interface.' }
        $client = [IO.Path]::GetDirectoryName($interface)
    } elseif ([IO.Path]::GetFileName($full) -ieq 'Interface') { $client = [IO.Path]::GetDirectoryName($full) }
    $clients = @()
    if (Test-RutaXPForeverClient $client) { $clients = @($client) }
    elseif (Test-Path -LiteralPath $full -PathType Container) {
        foreach ($flavor in @('_classic_beta_', '_forever_')) {
            $candidate = Join-Path $full $flavor
            if (Test-RutaXPForeverClient $candidate) { $clients += $candidate }
        }
    }
    if ($clients.Count -eq 0) { throw 'No se encuentra WoW Forever. Elige _classic_beta_, _forever_ o su Interface\AddOns.' }
    foreach ($item in $clients) {
        $addons = Get-RutaXPFullPath (Join-Path $item 'Interface\AddOns')
        Assert-RutaXPNoLinks $addons
        Write-Output $addons
    }
}

function Get-RutaXPSortedFolders {
    param([string[]]$Paths)
    # Consumers use @(...): one result remains a complete path, never a char.
    $Paths | Sort-Object -Unique | Sort-Object @{Expression={ if ($_ -match '[\\/]_classic_beta_[\\/]') { 0 } else { 1 } }}, @{Expression={$_}}
}

function Find-WoWAddonFolders {
    $roots = [Collections.Generic.List[string]]::new()
    foreach ($process in @(Get-Process -Name 'Wow*', 'WorldOfWarcraft*' -ErrorAction SilentlyContinue)) {
        try {
            if ($process.Path) {
                $folder = [IO.Path]::GetDirectoryName($process.Path)
                $roots.Add($folder); $roots.Add([IO.Path]::GetDirectoryName($folder))
            }
        } catch { }
    }
    foreach ($regPath in @('HKLM:\SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft', 'HKLM:\SOFTWARE\Blizzard Entertainment\World of Warcraft', 'HKCU:\SOFTWARE\Blizzard Entertainment\Battle.net\Default Installations')) {
        if (Test-Path -LiteralPath $regPath) {
            $item = Get-ItemProperty -LiteralPath $regPath -ErrorAction SilentlyContinue
            foreach ($property in @('InstallPath', 'Path', 'Install_Path')) { if ($item.$property) { $roots.Add([string]$item.$property) } }
        }
    }
    $common = @('World of Warcraft', 'Program Files (x86)\World of Warcraft', 'Program Files\World of Warcraft', 'Games\World of Warcraft', 'Juegos\World of Warcraft', 'WOW\World of Warcraft', 'WOW', 'WoW Forever', 'World of Warcraft Forever', 'Forever')
    foreach ($drive in @(Get-PSDrive -PSProvider FileSystem)) { foreach ($sub in $common) { $roots.Add((Join-Path $drive.Root $sub)) } }
    $found = @()
    foreach ($root in $roots) { try { $found += @(Resolve-RutaXPAddonFolders $root) } catch { } }
    Get-RutaXPSortedFolders $found
}

function Get-RutaXPFiles {
    param([string]$Root)
    $full = Get-RutaXPFullPath $Root
    Assert-RutaXPNoLinks $full
    if (-not (Test-Path -LiteralPath $full -PathType Container)) { throw "No existe la carpeta: $full" }
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($full)
    while ($pending.Count -gt 0) {
        foreach ($entry in @(Get-ChildItem -LiteralPath $pending.Pop() -Force -ErrorAction Stop)) {
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "No se permiten enlaces: $($entry.FullName)" }
            if ($entry.PSIsContainer) { $pending.Push($entry.FullName) } else { Write-Output $entry.FullName }
        }
    }
}

function Assert-RutaXPToc {
    param([string]$Root)
    $full = Get-RutaXPFullPath $Root
    $toc = Join-Path $full 'RutaXP.toc'
    if (-not (Test-Path -LiteralPath $toc -PathType Leaf)) { throw 'Falta RutaXP.toc.' }
    $scripts = 0
    foreach ($line in [IO.File]::ReadAllLines($toc)) {
        $entry = $line.Trim()
        if (-not $entry -or $entry.StartsWith('#')) { continue }
        if ([IO.Path]::IsPathRooted($entry)) { throw "Ruta absoluta no permitida en TOC: $entry" }
        $file = Get-RutaXPFullPath (Join-Path $full $entry)
        if (-not $file.StartsWith($full + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Entrada TOC fuera del addon: $entry" }
        Assert-RutaXPNoLinks $file
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Falta un archivo del TOC: $entry" }
        $scripts++
    }
    if ($scripts -eq 0) { throw 'El TOC no contiene archivos del addon.' }
}

function Get-RutaXPManifest {
    param([string]$Root)
    $full = Get-RutaXPFullPath $Root
    Assert-RutaXPToc $full
    $manifestFile = Join-Path $full 'manifest.sha256'
    if (-not (Test-Path -LiteralPath $manifestFile -PathType Leaf)) { throw 'Falta manifest.sha256. Extrae el paquete de publicacion completo.' }
    $expected = @{}
    foreach ($line in [IO.File]::ReadAllLines($manifestFile)) {
        if (-not $line.Trim() -or $line.TrimStart().StartsWith('#')) { continue }
        if ($line -notmatch '^([a-fA-F0-9]{64})  (.+)$') { throw 'Formato de manifest.sha256 no valido.' }
        $hash = $Matches[1].ToLowerInvariant(); $relative = $Matches[2].Replace('/', '\')
        if ([IO.Path]::IsPathRooted($relative) -or $relative.Contains(':')) { throw 'Ruta no valida en manifest.sha256.' }
        $file = Get-RutaXPFullPath (Join-Path $full $relative)
        if (-not $file.StartsWith($full + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta del manifiesto fuera del addon.' }
        $key = $file.Substring($full.Length + 1)
        if ($key -ieq 'manifest.sha256' -or $expected.ContainsKey($key)) { throw 'Entrada duplicada o circular en manifest.sha256.' }
        $expected[$key] = $hash
    }
    $manifest = @{}
    foreach ($file in @(Get-RutaXPFiles $full)) { $manifest[$file.Substring($full.Length + 1)] = Get-RutaXPHash $file }
    if ($manifest.Count -ne $expected.Count + 1) { throw 'El paquete no coincide con la lista de manifest.sha256.' }
    foreach ($key in $expected.Keys) { if (-not $manifest.ContainsKey($key) -or $manifest[$key] -ne $expected[$key]) { throw "Archivo ausente o alterado: $key" } }
    return $manifest
}

function Get-RutaXPHash {
    param([string]$Path)
    $hash = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $hash.Dispose() }
}

function Assert-RutaXPManifest {
    param([string]$Root, [hashtable]$Manifest)
    $actual = Get-RutaXPManifest $Root
    if ($actual.Count -ne $Manifest.Count) { throw 'La copia esta incompleta o contiene archivos inesperados.' }
    foreach ($key in $Manifest.Keys) { if (-not $actual.ContainsKey($key) -or $actual[$key] -ne $Manifest[$key]) { throw "La copia no coincide: $key" } }
}

function Assert-RutaXPChild {
    param([string]$Parent, [string]$Child, [string]$ExpectedName)
    $parentPath = Get-RutaXPFullPath $Parent
    $childPath = Get-RutaXPFullPath $Child
    if ([IO.Path]::GetDirectoryName($childPath) -ine $parentPath -or [IO.Path]::GetFileName($childPath) -ine $ExpectedName) { throw 'Destino fuera de la carpeta elegida.' }
    Assert-RutaXPNoLinks $childPath
}

function Remove-RutaXPStage {
    param([string]$Parent, [string]$Stage)
    $name = [IO.Path]::GetFileName($Stage)
    if ($name -notmatch '^\.RutaXP\.(stage|failed)\.[a-f0-9]{32}$') { throw 'Nombre temporal no valido.' }
    Assert-RutaXPChild $Parent $Stage $name
    if (Test-Path -LiteralPath $Stage) {
        @(Get-RutaXPFiles $Stage) | Out-Null
        Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction Stop
    }
}

function Install-RutaXP {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$AddOns,
        [scriptblock]$CopyFile = { param($From, $To) Copy-Item -LiteralPath $From -Destination $To -Force -ErrorAction Stop },
        [scriptblock]$BeforeActivate = { }
    )
    $sourcePath = Get-RutaXPFullPath $Source
    $resolved = @(Resolve-RutaXPAddonFolders $AddOns)
    if ($resolved.Count -ne 1 -or $resolved[0] -ine (Get-RutaXPFullPath $AddOns)) { throw 'Selecciona una sola carpeta Interface\AddOns de Forever.' }
    $parent = $resolved[0]
    $target = Join-Path $parent 'RutaXP'
    Assert-RutaXPChild $parent $target 'RutaXP'
    if ($sourcePath -ieq $target -or $sourcePath.StartsWith($target + '\', [StringComparison]::OrdinalIgnoreCase) -or $target.StartsWith($sourcePath + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Origen y destino deben ser distintos y no contenerse entre si.' }
    $manifest = Get-RutaXPManifest $sourcePath
    if (Test-Path -LiteralPath $target) { @(Get-RutaXPFiles $target) | Out-Null }
    Assert-RutaXPNoLinks $parent
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $token = [guid]::NewGuid().ToString('N')
    $stage = Join-Path $parent ('.RutaXP.stage.' + $token)
    $backup = Join-Path $parent ('.RutaXP.backup.' + $token)
    $failed = Join-Path $parent ('.RutaXP.failed.' + $token)
    $oldMoved = $false; $activated = $false
    try {
        Assert-RutaXPChild $parent $stage ('.RutaXP.stage.' + $token)
        [IO.Directory]::CreateDirectory($stage) | Out-Null
        foreach ($relative in $manifest.Keys) {
            $from = Join-Path $sourcePath $relative; $to = Join-Path $stage $relative
            Assert-RutaXPNoLinks $from
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($to)) | Out-Null
            & $CopyFile $from $to | Out-Null
        }
        Assert-RutaXPManifest $stage $manifest
        Assert-RutaXPChild $parent $target 'RutaXP'
        Assert-RutaXPChild $parent $backup ('.RutaXP.backup.' + $token)
        if (Test-Path -LiteralPath $target) {
            @(Get-RutaXPFiles $target) | Out-Null
            # Exact literal rename: unlike Move-Item, never nest in an existing destination.
            [IO.Directory]::Move($target, $backup)
            $oldMoved = $true
        }
        & $BeforeActivate | Out-Null
        Assert-RutaXPChild $parent $stage ('.RutaXP.stage.' + $token)
        Assert-RutaXPChild $parent $target 'RutaXP'
        [IO.Directory]::Move($stage, $target)
        $activated = $true
        Assert-RutaXPManifest $target $manifest
        return [pscustomobject]@{ Target=$target; Backup=$(if ($oldMoved) { $backup } else { $null }) }
    } catch {
        $problem = $_.Exception.Message
        try {
            if ($activated -and (Test-Path -LiteralPath $target)) {
                Assert-RutaXPChild $parent $target 'RutaXP'; Assert-RutaXPChild $parent $failed ('.RutaXP.failed.' + $token)
                [IO.Directory]::Move($target, $failed)
            }
            if ($oldMoved) {
                Assert-RutaXPChild $parent $backup ('.RutaXP.backup.' + $token); Assert-RutaXPChild $parent $target 'RutaXP'
                [IO.Directory]::Move($backup, $target)
            }
        } catch { throw "Fallo: $problem. Restauracion automatica imposible; tu copia anterior se conserva en $backup. $($_.Exception.Message)" }
        throw "Instalacion cancelada; se conserva la version anterior. $problem"
    } finally {
        foreach ($temporary in @($stage, $failed)) { try { Remove-RutaXPStage $parent $temporary } catch { Write-Warning "Carpeta temporal conservada: $temporary. $($_.Exception.Message)" } }
    }
}

function Select-RutaXPFolder {
    param([string[]]$Folders)
    $choices = @(Get-RutaXPSortedFolders $Folders)
    if ($choices.Count -eq 1) {
        Write-Host "Cliente Forever: $($choices[0])" -ForegroundColor Green
        $answer = Read-Host 'Instalar aqui (S/N; Enter = S)'
        if (-not $answer -or $answer.Trim() -match '^(?i:s|si)$') { return $choices[0] }
        return $null
    }
    for ($index=0; $index -lt $choices.Count; $index++) { Write-Host "  [$($index + 1)] $($choices[$index])" }
    if ($choices.Count -gt 0) {
        $answer = Read-Host 'Elige UN cliente (numero; M = otra carpeta; Enter = 1)'
        if (-not $answer) { $answer='1' }
        if ($answer.Trim() -ieq 'M') { return $null }
        $number=0
        if (-not [int]::TryParse($answer, [ref]$number) -or $number -lt 1 -or $number -gt $choices.Count) { throw 'Opcion no valida; no se ha instalado nada.' }
        return $choices[$number - 1]
    }
    return $null
}

function Invoke-RutaXPInstaller {
    [Console]::OutputEncoding = [Text.Encoding]::UTF8
    try { $Host.UI.RawUI.WindowTitle='Instalador de RutaXP' } catch { }
    Write-Host "`nINSTALADOR DE RUTAXP PARA WOW FOREVER`n" -ForegroundColor Cyan
    try {
        $source=Join-Path $PSScriptRoot 'RutaXP'
        if (-not (Test-Path -LiteralPath (Join-Path $source 'RutaXP.toc') -PathType Leaf)) { $source=$PSScriptRoot }
        Assert-RutaXPToc $source
        Write-Host 'Buscando clientes de Forever...' -ForegroundColor Cyan
        $detected=@(Find-WoWAddonFolders)
        $target=Select-RutaXPFolder $detected
        if (-not $target) { $manual=Read-Host 'Ruta de WoW Forever, carpeta principal de WoW o Interface\AddOns'; $target=Select-RutaXPFolder @(Resolve-RutaXPAddonFolders $manual) }
        if (-not $target) { Write-Host 'Instalacion cancelada.'; return 1 }
        $result=Install-RutaXP -Source $source -AddOns $target
        Write-Host "Instalado correctamente en: $($result.Target)" -ForegroundColor Green
        if ($result.Backup) { Write-Host "Copia anterior conservada en: $($result.Backup)" }
        Write-Host 'Cierra WoW completamente y vuelve a abrirlo; /reload no descubre addons nuevos.'
        Write-Host 'Activa RutaXP en Accesorios. Usa /rutaxp para las guias y N para los talentos.'
        return 0
    } catch { Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red; return 1 }
}

if ($MyInvocation.InvocationName -ne '.') {
    $code=Invoke-RutaXPInstaller
    Read-Host 'Presiona Enter para salir' | Out-Null
    exit $code
}
