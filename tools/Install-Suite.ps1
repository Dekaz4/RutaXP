# Install a personal RutaXP bundle with WoW closed. PowerShell 5.1 or newer.
[CmdletBinding(DefaultParameterSetName='Zip')]
param(
    [Parameter(Mandatory)][string]$Client,
    [Parameter(Mandatory,ParameterSetName='Zip')][string]$Archive,
    [Parameter(Mandatory,ParameterSetName='Directory')][string]$AddonDirectory,
    [Parameter(Mandatory,ParameterSetName='Restore')][switch]$Restore
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
$modules = @('OpenMap','ForeverDungeonJournal')
$legacyBackupName = '\.RutaXP\.backup\.[0-9a-f]{32}'
# Imported RestedXP guides stay with the separate installation, in its own
# SavedVariables. Only the native map and journal settings enter the suite.
$settingsModules = @('OpenMap','ForeverDungeonJournal')

function Assert-NoLink([string]$path) {
    for ($itemPath = $path; $itemPath; $itemPath = [IO.Path]::GetDirectoryName($itemPath)) {
        if (Test-Path -LiteralPath $itemPath) {
            $item = Get-Item -LiteralPath $itemPath -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'La ruta contiene un enlace o junction.' }
        }
    }
}
function ChildPath([string]$root,[string]$relative) {
    $parts = $relative.Replace('\','/').Split('/')
    foreach ($part in $parts) {
        if (!$part -or $part -match '[. ]$|[:*?"<>|\x00-\x1f]|^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)') {
            throw 'Ruta de archivo no valida.'
        }
    }
    $full = [IO.Path]::GetFullPath([IO.Path]::Combine($root, ($parts -join [IO.Path]::DirectorySeparatorChar)))
    if (!$full.StartsWith($root.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta fuera del destino.' }
    return $full
}
function BackupStore([string]$clientPath) {
    $clientDirectory = Get-Item -LiteralPath $clientPath -Force
    $gameDirectory = $clientDirectory
    $name = $clientDirectory.Name
    if ($clientDirectory.Parent -and ($name -in @('_forever_', '_classic_beta_') -or
        [IO.File]::Exists((Join-Path $clientDirectory.Parent.FullName '.build.info')))) {
        $gameDirectory = $clientDirectory.Parent
    }
    if (!$gameDirectory.Parent) {
        if ($gameDirectory -eq $clientDirectory -or [IO.File]::Exists((Join-Path $gameDirectory.FullName '.build.info'))) {
            throw 'La instalacion ocupa la raiz de la unidad. Usa una carpeta de juego para conservar copias externas en la misma unidad.'
        }
        $gameDirectory = $clientDirectory
    }
    $folder = if ($gameDirectory.Name -eq 'RutaXP-Suite-Backups') { 'RutaXP-Suite-Backups-External' } else { 'RutaXP-Suite-Backups' }
    $result = ChildPath $gameDirectory.Parent.FullName "$folder/$($gameDirectory.Name)"
    if ($gameDirectory.FullName -ne $clientPath) { $result = ChildPath $result $name }
    return $result
}
function MakeDirectory([string]$path) { [void][IO.Directory]::CreateDirectory($path) }
function AllFiles([string]$root) {
    Assert-NoLink $root
    $dirs = [Collections.Generic.Stack[string]]::new()
    $dirs.Push($root)
    while ($dirs.Count) {
        foreach ($item in Get-ChildItem -LiteralPath $dirs.Pop() -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Hay un enlace en los archivos del addon.' }
            if ($item.PSIsContainer) { $dirs.Push($item.FullName) } else { $item.FullName }
        }
    }
}
function FileHash([string]$file) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($file)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','') }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
function ReadPackage([string]$root) {
    $manifest = ChildPath $root 'manifest.sha256'
    Assert-NoLink $manifest
    $expected = @{}
    foreach ($line in [IO.File]::ReadAllLines($manifest)) {
        if ($line -match '^#' -or !$line.Trim()) { continue }
        if ($line -notmatch '^([a-fA-F0-9]{64})  (.+)$') { throw 'Manifiesto invalido.' }
        $file = ChildPath $root $Matches[2]
        if ($expected.ContainsKey($file) -or $file -eq $manifest) { throw 'Archivo duplicado en el manifiesto.' }
        $expected[$file] = $Matches[1]
    }
    foreach ($file in AllFiles $root) {
        if ($file -eq $manifest) { continue }
        if (!$expected.ContainsKey($file) -or (FileHash $file) -ne $expected[$file]) { throw 'Archivo inesperado o alterado.' }
        $expected.Remove($file)
    }
    if ($expected.Count) { throw 'Faltan archivos del paquete.' }
    $toc = [IO.File]::ReadAllText((ChildPath $root 'RutaXP.toc'))
    $header = [regex]::Match($toc,'(?im)^##\s*X-RutaXP-Embedded\s*:\s*([^\r\n]+)')
    $embedded = @($header.Groups[1].Value.Split(',') | ForEach-Object { $_.Trim() })
    # Previous personal ZIPs remain installable and restorable.
    if (!$header.Success -or ((Compare-Object $modules $embedded) -and
        (Compare-Object ($modules + 'RXPGuides') $embedded))) { throw 'El paquete no contiene los modulos de RutaXP esperados.' }
    return FileHash $manifest
}
function StagePackage([string]$target) {
    MakeDirectory $target
    if ($AddonDirectory) {
        $source = (Get-Item -LiteralPath $AddonDirectory).FullName
        if (![IO.File]::Exists((ChildPath $source 'RutaXP.toc')) -or
            $target.StartsWith($source + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
            throw 'Selecciona la carpeta RutaXP extraida del paquete.'
        }
        foreach ($file in AllFiles $source) {
            $dest = ChildPath $target ($file.Substring($source.Length + 1))
            MakeDirectory ([IO.Path]::GetDirectoryName($dest))
            [IO.File]::Copy($file,$dest)
        }
    } else {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead((Get-Item -LiteralPath $Archive).FullName)
        try {
            foreach ($entry in $zip.Entries) {
                $name = $entry.FullName.Replace('\','/')
                if ($name -ceq 'RutaXP/') { continue }
                if (!$name.StartsWith('RutaXP/',[StringComparison]::Ordinal)) { throw 'El ZIP debe contener solo la carpeta RutaXP.' }
                $dest = ChildPath $target $name.Substring(7).TrimEnd('/')
                if ($name.EndsWith('/')) { MakeDirectory $dest; continue }
                MakeDirectory ([IO.Path]::GetDirectoryName($dest))
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$dest,$false)
            }
        } finally { $zip.Dispose() }
    }
    return ReadPackage $target
}
function CheckClosed {
    foreach ($p in Get-Process -Name 'Wow','WowB','Wow-64','WowClassic','WowClassicB','WowT','WowClassicT','WorldOfWarcraft','World of Warcraft' -ErrorAction SilentlyContinue) {
        try { $exe = $p.Path } catch { $exe = $null }
        if (!$exe -or [IO.Path]::GetDirectoryName($exe) -eq $game) { throw 'Cierra WoW para instalar o restaurar RutaXP.' }
    }
}
function SavedDirectories {
    $accounts = ChildPath $game 'WTF/Account'
    Assert-NoLink $accounts
    if (![IO.Directory]::Exists($accounts)) { return }
    foreach ($account in Get-ChildItem -LiteralPath $accounts -Directory -Force) {
        Assert-NoLink $account.FullName
        $shared = ChildPath $account.FullName 'SavedVariables'
        if ([IO.Directory]::Exists($shared)) { Assert-NoLink $shared; $shared }
        foreach ($realm in Get-ChildItem -LiteralPath $account.FullName -Directory -Force) {
            if ($realm.Name -eq 'SavedVariables') { continue }
            Assert-NoLink $realm.FullName
            foreach ($character in Get-ChildItem -LiteralPath $realm.FullName -Directory -Force) {
                Assert-NoLink $character.FullName
                $individual = ChildPath $character.FullName 'SavedVariables'
                if ([IO.Directory]::Exists($individual)) { Assert-NoLink $individual; $individual }
            }
        }
    }
}
function WriteCombined([string[]]$paths,[string]$dest) {
    # WoW writes independent assignments in UTF-8. Keep their exact bytes, with
    # a newline boundary, and put newer RutaXP assignments last on upgrades.
    $output = [IO.File]::Open($dest,'CreateNew','Write','None')
    try {
        foreach ($path in $paths) {
            Assert-NoLink $path
            $inputStream = [IO.File]::OpenRead($path)
            try {
                $prefix = New-Object byte[] 3
                $count = $inputStream.Read($prefix,0,3)
                $bom = $count -eq 3 -and $prefix[0] -eq 239 -and $prefix[1] -eq 187 -and $prefix[2] -eq 191
                if (!$bom) {
                    if (($count -gt 1) -and ($prefix[0] -in @(254,255))) { throw 'Formato de SavedVariables distinto al UTF-8 del juego.' }
                    $inputStream.Position = 0
                }
                $inputStream.CopyTo($output)
                $output.WriteByte(10)
            } finally { $inputStream.Dispose() }
        }
    } finally { $output.Dispose() }
}
function TargetPath([string]$relative) {
    if ($relative -notmatch "^Interface/AddOns/(RutaXP|OpenMap|ForeverDungeonJournal|RXPGuides|Journey|$legacyBackupName)$" -and
        $relative -notmatch '^WTF/Account/[^/\\]+/([^/\\]+/[^/\\]+/)?SavedVariables/RutaXP\.lua$') { throw 'Destino ajeno a RutaXP.' }
    $target = ChildPath $game $relative
    Assert-NoLink $target
    return $target
}
function Transfer([string]$from,[string]$to) {
    Assert-NoLink $from
    Assert-NoLink $to
    if ([IO.Directory]::Exists($from)) { [IO.Directory]::Move($from,$to) }
    else { [IO.File]::Move($from,$to) }
}
function MoveOldTransactions([string]$old,[string]$external) {
    foreach ($item in Get-ChildItem -LiteralPath $old -Force -Directory) {
        if ($item.Name -notmatch '^\d{17}-[0-9a-f]{32}$') { continue }
        Assert-NoLink $item.FullName
        $plan = ChildPath $item.FullName 'plan.json'
        Assert-NoLink $plan
        if (![IO.File]::Exists($plan)) {
            # A crash during extraction predates plan.json and changes no
            # addon. Preserve its partial payload away from the patcher.
            $new = ChildPath $item.FullName 'new'
            Assert-NoLink $new
            if (![IO.Directory]::Exists($new)) { continue }
            $incomplete = ChildPath $external 'Incomplete-transactions'
            Assert-NoLink $incomplete
            MakeDirectory $incomplete
            Transfer $item.FullName (ChildPath $incomplete ($item.Name + '-' + [guid]::NewGuid().ToString('N')))
            continue
        }
        $next = ChildPath $external $item.Name
        if (Test-Path -LiteralPath $next) {
            # A copied (rather than moved) history can contain both versions.
            # Keep both unchanged. Only an identical copy may be taken out of
            # the active history without losing a restore or pending rollback.
            $originalFiles = @(AllFiles $item.FullName)
            if (@(AllFiles $next).Count -ne $originalFiles.Count) { throw 'Hay dos copias distintas de una misma transaccion de RutaXP.' }
            foreach ($file in $originalFiles) {
                $other = ChildPath $next ($file.Substring($item.FullName.Length + 1))
                if (![IO.File]::Exists($other) -or (FileHash $file) -ne (FileHash $other)) {
                    throw 'Hay dos copias distintas de una misma transaccion de RutaXP.'
                }
            }
            $dupes = ChildPath $external 'Archived-duplicates'
            Assert-NoLink $dupes
            MakeDirectory $dupes
            $next = ChildPath $dupes ($item.Name + '-' + [guid]::NewGuid().ToString('N'))
        }
        Transfer $item.FullName $next
    }
}
function Rollback([string]$tx,$rows) {
    [IO.File]::WriteAllText((ChildPath $tx 'restoring'),'')
    MakeDirectory (ChildPath $tx 'after')
    for ($i = $rows.Count - 1; $i -ge 0; $i--) {
        $row = $rows[$i]
        $target = TargetPath $row.dest
        if ($row.dest -match "^Interface/AddOns/($legacyBackupName)$") {
            # Restore an archived updater copy to its new discovery location.
            $target = ChildPath $store $Matches[1]
            Assert-NoLink $target
        }
        $prior = ChildPath $tx "prior/$i"
        $stage = ChildPath $tx "new/$i"
        $replaced = [IO.File]::Exists($prior) -or [IO.Directory]::Exists($prior)
        if ($replaced -or (!$row.old -and $row.add -and !(Test-Path -LiteralPath $stage))) {
            if (Test-Path -LiteralPath $target) { Transfer $target (ChildPath $tx "after/$i") }
            if ($replaced) { Transfer $prior $target }
        }
    }
    [IO.File]::WriteAllText((ChildPath $tx 'restored'),'')
}

$game = (Get-Item -LiteralPath $Client).FullName.TrimEnd('\','/')
if ([IO.Path]::GetFileName($game) -eq 'AddOns' -and [IO.Path]::GetFileName([IO.Path]::GetDirectoryName($game)) -eq 'Interface') {
    $game = [IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName($game))
}
Assert-NoLink $game
$addons = ChildPath $game 'Interface/AddOns'
Assert-NoLink $addons
if (![IO.Directory]::Exists($addons)) { throw 'Elige la carpeta del cliente con Interface\AddOns.' }
$forever = [IO.Path]::GetFileName($game) -in @('_forever_', '_classic_beta_')
if (!$forever) {
    foreach ($name in @('Wow.exe', 'WowB.exe', 'WowClassic.exe', 'WowClassicB.exe')) {
        $exe = ChildPath $game $name
        if ([IO.File]::Exists($exe) -and [Diagnostics.FileVersionInfo]::GetVersionInfo($exe).FileVersion -match '^1\.60\.') {
            $forever = $true
            break
        }
    }
}
if (!$forever) { throw 'Selecciona el cliente de WoW Forever.' }
CheckClosed
$store = BackupStore $game
Assert-NoLink $store
MakeDirectory $store
$lockPath = ChildPath $store 'install.lock'
Assert-NoLink $lockPath
$lock = [IO.File]::Open($lockPath,'OpenOrCreate','Write','None')
$oldLock = $null
try {
    $oldStore = ChildPath $game 'RutaXP-Suite-Backups'
    Assert-NoLink $oldStore
    if ([IO.Directory]::Exists($oldStore)) {
        $oldLockPath = ChildPath $oldStore 'install.lock'
        Assert-NoLink $oldLockPath
        $oldLock = [IO.File]::Open($oldLockPath,'OpenOrCreate','Write','None')
        MoveOldTransactions $oldStore $store
    }
    $active = @()
    $migrated = @{}
    foreach ($txn in @(Get-ChildItem -LiteralPath $store -Directory -Force | Sort-Object Name)) {
        if ($txn.Name -notmatch '^\d{17}-[0-9a-f]{32}$') { continue }
        $tx = $txn.FullName
        Assert-NoLink $tx
        $plan = ChildPath $tx 'plan.json'
        Assert-NoLink $plan
        if (!(Test-Path -LiteralPath $plan) -or (Test-Path -LiteralPath (ChildPath $tx 'restored'))) { continue }
        $rows = @((ConvertFrom-Json ([IO.File]::ReadAllText($plan))).rows)
        if (!(Test-Path -LiteralPath (ChildPath $tx 'committed')) -or (Test-Path -LiteralPath (ChildPath $tx 'restoring'))) {
            Rollback $tx $rows
            continue
        }
        $active += @{root=$tx;rows=$rows}
        foreach ($row in $rows) {
            foreach ($source in $row.sources) { $migrated["$($row.dest)|$source"] = $true }
        }
    }
    if ($Restore) {
        if (!$active.Count) { Write-Output 'No hay una instalacion de la suite para restaurar.'; return }
        for ($i = $active.Count - 1; $i -ge 0; $i--) { Rollback $active[$i].root $active[$i].rows }
        Write-Output 'Instalacion anterior restaurada. Las copias de la suite se conservan en RutaXP-Suite-Backups.'
        return
    }
    $name = [DateTime]::UtcNow.ToString('yyyyMMddHHmmssfff') + '-' + [guid]::NewGuid().ToString('N')
    $tx = ChildPath $store $name
    MakeDirectory (ChildPath $tx 'new')
    $planPath = ChildPath $tx 'plan.json'
    try {
        $staged = ChildPath $tx 'new/0'
        $packageHash = StagePackage $staged
        $rows = [Collections.Generic.List[object]]::new()
        $suite = TargetPath 'Interface/AddOns/RutaXP'
        $rows.Add(@{ dest='Interface/AddOns/RutaXP'; old=[IO.Directory]::Exists($suite); add=$true; sources=@() })
        $replace = $modules
        $newToc = [IO.File]::ReadAllText((ChildPath $staged 'RutaXP.toc'))
        if ($newToc -match '(?im)^##\s*X-RutaXP-Embedded\s*:[^\r\n]*\bRXPGuides\b') {
            $replace += 'RXPGuides'
        }
        if ($newToc -match '(?im)^## X-RutaXP-Journey-UI:\s*\S+') {
            foreach ($component in @('ui/GuideContainer.lua','lib/TomCats/Arrows.lua')) {
                if (![IO.File]::Exists((ChildPath $staged "Modules/Journey/$component"))) { throw 'Faltan componentes de Journey en la nueva suite.' }
            }
            $replace += 'Journey'
        }
        foreach ($module in $replace) {
            $dest = "Interface/AddOns/$module"
            if ([IO.Directory]::Exists((TargetPath $dest))) { $rows.Add(@{dest=$dest;old=$true;add=$false;sources=@()}) }
        }
        # Older updaters kept backups inside AddOns. Move only their named
        # RutaXP copies into the same reversible transaction as the upgrade.
        foreach ($backup in Get-ChildItem -LiteralPath $addons -Directory -Force -Filter '.RutaXP.backup.*') {
            if ($backup.Name -notmatch "^$legacyBackupName$") { continue }
            $dest = "Interface/AddOns/$($backup.Name)"
            $toc = ChildPath (TargetPath $dest) 'RutaXP.toc'
            Assert-NoLink $toc
            if ([IO.File]::Exists($toc)) { $rows.Add(@{dest=$dest;old=$true;add=$false;sources=@()}) }
        }
        foreach ($saved in SavedDirectories) {
            $dest = ($saved.Substring($game.Length + 1).Replace('\','/')) + '/RutaXP.lua'
            $target = TargetPath $dest
            $sources = @($settingsModules | Where-Object {
                !$migrated.ContainsKey("$dest|$_") -and [IO.File]::Exists((ChildPath $saved "$_.lua"))
            })
            if (!$sources.Count) { continue }
            $paths = @($sources | ForEach-Object { ChildPath $saved "$_.lua" })
            $old = [IO.File]::Exists($target)
            if ($old) { $paths += $target }
            WriteCombined $paths (ChildPath $tx "new/$($rows.Count)")
            $rows.Add(@{dest=$dest;old=$old;add=$true;sources=$sources})
        }
        if ($rows.Count -eq 1 -and $active.Count -gt 0) {
            $installed = try { ReadPackage $suite } catch { $null }
            if ($packageHash -eq $installed) { Write-Output 'La suite ya esta instalada y verificada.'; return }
        }
        CheckClosed
        MakeDirectory (ChildPath $tx 'prior')
        [IO.File]::WriteAllText((ChildPath $tx 'plan.tmp'),(ConvertTo-Json -InputObject @{rows=$rows} -Depth 5))
        Transfer (ChildPath $tx 'plan.tmp') $planPath
        try {
            for ($i = 0; $i -lt $rows.Count; $i++) {
                $row = $rows[$i]
                $target = TargetPath $row.dest
                if ($row.old) { Transfer $target (ChildPath $tx "prior/$i") }
                if ($row.add) { Transfer (ChildPath $tx "new/$i") $target }
            }
            [IO.File]::WriteAllText((ChildPath $tx 'committed'),'')
        } catch { Rollback $tx $rows; throw }
        Write-Output 'RutaXP instalado. Abre WoW y escribe /rutaxp.'
    } finally {
        # This transaction has not touched the game before plan.json is written.
        if (!(Test-Path -LiteralPath $planPath) -and ([IO.Path]::GetDirectoryName($tx) -eq $store) -and
            ([IO.Path]::GetFileName($tx) -ceq $name)) {
            Assert-NoLink $tx
            Remove-Item -LiteralPath $tx -Recurse -Force
        }
    }
} finally {
    if ($oldLock) {
        $oldLock.Dispose()
        try {
            # Never recursively remove the legacy root. A concurrently opened
            # legacy lock or an unrecognised file simply keeps it in place.
            if ([IO.Directory]::GetFileSystemEntries($oldStore).Count -eq 1 -and [IO.File]::Exists($oldLockPath)) {
                Assert-NoLink $oldLockPath
                [IO.File]::Delete($oldLockPath)
                [IO.Directory]::Delete($oldStore, $false)
            }
        } catch [IO.IOException] {} catch [UnauthorizedAccessException] {}
    }
    $lock.Dispose()
}
