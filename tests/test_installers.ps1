param([string]$Workspace, [string]$FixtureRoot, [string]$Assembly, [string]$Case)
$ErrorActionPreference = 'Stop'
. (Join-Path $Workspace 'Instalar.ps1')
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -Path $Assembly

function Assert-True { param($Condition, [string]$Message) if (-not $Condition) { throw $Message } }
function Assert-Throws { param([scriptblock]$Action) $thrown=$false; try { & $Action | Out-Null } catch { $thrown=$true }; Assert-True $thrown 'Expected operation to be rejected.' }
function Put { param([string]$Path, [string]$Text) [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path)) | Out-Null; [IO.File]::WriteAllText($Path, $Text) }
function Seal-Addon {
    param([string]$Root)
    $lines=@('# RutaXP test fixture')
    foreach ($file in @(Get-RutaXPFiles $Root | Sort-Object)) {
        if ([IO.Path]::GetFileName($file) -ieq 'manifest.sha256') { continue }
        $relative=$file.Substring($Root.Length + 1).Replace('\','/')
        $lines += (Get-RutaXPHash $file) + '  ' + $relative
    }
    [IO.File]::WriteAllLines((Join-Path $Root 'manifest.sha256'), [string[]]$lines, (New-Object Text.UTF8Encoding($false)))
}
function New-Addon {
    param([string]$Root, [string]$Label)
    Put (Join-Path $Root 'RutaXP.toc') "## Interface: 16001`nCore.lua`nSub\ui.lua`n"
    Put (Join-Path $Root 'Core.lua') ("-- " + $Label)
    Put (Join-Path $Root 'Sub\ui.lua') '-- ui fixture'
    Put (Join-Path $Root 'Source\editable.json') '{"fixture":true}'
    Put (Join-Path $Root 'Licenses\notice.txt') 'fixture notice'
    Seal-Addon $Root
    return $Root
}
function New-Destination {
    param([string]$Name)
    $path=Join-Path $FixtureRoot ($Name + '\_classic_beta_\Interface\AddOns')
    [IO.Directory]::CreateDirectory($path) | Out-Null
    return $path
}
function Assert-Old {
    param([string]$Target, [hashtable]$Before)
    Assert-RutaXPManifest $Target $Before
    Assert-True ([IO.File]::ReadAllText((Join-Path $Target 'Core.lua')) -eq '-- old') 'The previous version changed.'
}
function Archive-Source {
    param([string]$Source, [string]$Extra)
    $memory=New-Object IO.MemoryStream
    $zip=New-Object IO.Compression.ZipArchive($memory, [IO.Compression.ZipArchiveMode]::Create, $true)
    foreach ($file in @(Get-RutaXPFiles $Source)) {
        $name='RutaXP/' + $file.Substring($Source.Length + 1).Replace('\','/')
        $entry=$zip.CreateEntry($name)
        $output=$entry.Open()
        try { $bytes=[IO.File]::ReadAllBytes($file); $output.Write($bytes,0,$bytes.Length) } finally { $output.Dispose() }
    }
    if ($Extra) { $entry=$zip.CreateEntry($Extra); $output=$entry.Open(); $output.WriteByte(120); $output.Dispose() }
    $zip.Dispose(); $memory.Position=0
    return ,$memory
}

try {
    [IO.Directory]::CreateDirectory($FixtureRoot) | Out-Null
    $source=New-Addon (Join-Path $FixtureRoot 'Source [beta] con espacios') 'new'
    if ($Case -eq 'paths') {
        $base=Join-Path $FixtureRoot 'World of Warcraft [prueba]'
        foreach ($flavor in @('_classic_beta_','_forever_','_classic_era_','_classic_','_retail_')) { [IO.Directory]::CreateDirectory((Join-Path $base ($flavor + '\Interface\AddOns'))) | Out-Null }
        $expected=Join-Path $base '_classic_beta_\Interface\AddOns'
        $one=@(Resolve-RutaXPAddonFolders ('"' + $expected + '\"'))
        Assert-True ($one.Count -eq 1 -and $one[0] -ceq $expected) 'Single path was indexed as a character or nested by trailing slash.'
        $all=@(Resolve-RutaXPAddonFolders $base)
        Assert-True ($all.Count -eq 2 -and $all[0] -eq $expected) 'Only Forever clients may be resolved; beta should be first.'
        $cs=[RutaXPInstaller.InstallerCore]::ResolveDestinations('"' + $expected + '\"')
        Assert-True ($cs.Count -eq 1 -and $cs[0] -eq $expected) 'C# trailing slash/quote normalization failed.'
        $cs=[RutaXPInstaller.InstallerCore]::ResolveDestinations($base)
        Assert-True ($cs.Count -eq 2 -and $cs[0] -eq $expected) 'C# selected an unrelated client.'
        Assert-Throws { Resolve-RutaXPAddonFolders (Join-Path $base '_retail_') }
        Assert-Throws { [RutaXPInstaller.InstallerCore]::ResolveDestinations((Join-Path $base '_retail_')) }
        Assert-Throws { Get-RutaXPFullPath 'E:relative' }
        Assert-Throws { [RutaXPInstaller.InstallerCore]::Normalize('E:relative') }
        function Read-Host { return '2' }
        $selected=Select-RutaXPFolder $all
        Assert-True ($selected -eq $all[1]) 'Manual root must choose exactly one client.'
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $all[0] 'RutaXP'))) 'Selection must not install silently.'
    } elseif ($Case -eq 'update') {
        foreach ($engine in @('PS','CS')) {
            $addons=New-Destination $engine
            $target=New-Addon (Join-Path $addons 'RutaXP') 'old'
            Put (Join-Path $target 'custom-guide.lua') '-- preserve me'
            Seal-Addon $target
            $before=Get-RutaXPManifest $target
            if ($engine -eq 'PS') { $result=Install-RutaXP $source $addons } else { $result=[RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons) }
            Assert-True ([IO.Directory]::Exists($result.Backup)) 'Successful update must preserve the previous folder.'
            Assert-Old $result.Backup $before
            Assert-RutaXPManifest $target (Get-RutaXPManifest $source)
            Assert-True (Test-Path -LiteralPath (Join-Path $target 'Source\editable.json')) 'A non-TOC source file was lost.'
        }
    } elseif ($Case -eq 'failures') {
        foreach ($engine in @('PS','CS')) {
            $addons=New-Destination $engine
            $target=New-Addon (Join-Path $addons 'RutaXP') 'old'
            $before=Get-RutaXPManifest $target
            if ($engine -eq 'PS') {
                Assert-Throws { Install-RutaXP $source $addons -CopyFile { throw 'simulated copy failure' } }
                Assert-Old $target $before
                Assert-Throws { Install-RutaXP $source $addons -CopyFile { param($from,$to) Copy-Item -LiteralPath $from -Destination $to -ErrorAction Stop; if ([IO.Path]::GetFileName($to) -eq 'Core.lua') { [IO.File]::AppendAllText($to,'corrupt') } } }
                Assert-Old $target $before
                Assert-Throws { Install-RutaXP $source $addons -BeforeActivate { throw 'simulated activation failure' } }
            } else {
                $copy=[Action[string,string]] { param($from,$to) throw 'simulated copy failure' }
                Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons,$copy,$null) }
                Assert-Old $target $before
                $copy=[Action[string,string]] { param($from,$to) [IO.File]::Copy($from,$to); if ([IO.Path]::GetFileName($to) -eq 'Core.lua') { [IO.File]::AppendAllText($to,'corrupt') } }
                Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons,$copy,$null) }
                Assert-Old $target $before
                $activate=[Action] { throw 'simulated activation failure' }
                Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons,$null,$activate) }
            }
            Assert-Old $target $before
            Assert-True (@(Get-ChildItem -LiteralPath $addons -Force | Where-Object { $_.Name -like '.RutaXP.*' }).Count -eq 0) 'Failed transaction left a staging or backup folder after successful rollback.'
        }
    } elseif ($Case -eq 'invalid') {
        $addons=New-Destination 'common'
        $target=New-Addon (Join-Path $addons 'RutaXP') 'old'
        $before=Get-RutaXPManifest $target
        Assert-Throws { Install-RutaXP $target $addons }
        Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($target,$addons) }
        Put (Join-Path $source 'RutaXP.toc') "## Interface: 16001`nmissing.lua`n"
        Seal-Addon $source
        Assert-Throws { Install-RutaXP $source $addons }
        Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons) }
        Put (Join-Path $source 'RutaXP.toc') "## Interface: 16001`n..\outside.lua`n"
        Seal-Addon $source
        Assert-Throws { Install-RutaXP $source $addons }
        Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons) }
        $source=New-Addon $source 'new'
        [IO.File]::Delete((Join-Path $source 'Licenses\notice.txt'))
        Assert-Throws { Install-RutaXP $source $addons }
        Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons) }
        Assert-Old $target $before
        $source=New-Addon $source 'new'
        [IO.File]::Delete((Join-Path $source 'manifest.sha256'))
        Assert-Throws { Install-RutaXP $source $addons }
        Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons) }
        Assert-Old $target $before
    } elseif ($Case -eq 'archive') {
        $addons=New-Destination 'embedded'
        $target=New-Addon (Join-Path $addons 'RutaXP') 'old'
        $before=Get-RutaXPManifest $target
        $memory=Archive-Source $source ''
        try { $result=[RutaXPInstaller.InstallerCore]::InstallFromArchive($memory,$addons) } finally { $memory.Dispose() }
        Assert-RutaXPManifest $result.Target (Get-RutaXPManifest $source)
        Assert-Old $result.Backup $before
        $memory=Archive-Source $source 'RutaXP/../../outside.txt'
        try { Assert-Throws { [RutaXPInstaller.InstallerCore]::ExtractArchive($memory,(Join-Path $FixtureRoot 'unpack')) } } finally { $memory.Dispose() }
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $FixtureRoot 'outside.txt'))) 'ZIP escaped its destination.'
        $memory=Archive-Source $source 'RutaXP/Core.lua'
        try { Assert-Throws { [RutaXPInstaller.InstallerCore]::ExtractArchive($memory,(Join-Path $FixtureRoot 'duplicate')) } } finally { $memory.Dispose() }
    } elseif ($Case -eq 'junctions') {
        $addons=New-Destination 'links'
        $other=Join-Path $FixtureRoot 'do not touch'
        [IO.Directory]::CreateDirectory($other) | Out-Null
        Put (Join-Path $other 'sentinel.txt') 'untouched'
        $link=Join-Path $addons 'RutaXP'
        New-Item -ItemType Junction -Path $link -Target $other | Out-Null
        try {
            Assert-Throws { Install-RutaXP $source $addons }
            Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons) }
            Assert-True ([IO.File]::ReadAllText((Join-Path $other 'sentinel.txt')) -eq 'untouched') 'Junction destination was changed.'
        } finally { [IO.Directory]::Delete($link) }
        $link=Join-Path $source 'linked-source'
        New-Item -ItemType Junction -Path $link -Target $other | Out-Null
        try {
            Assert-Throws { Install-RutaXP $source $addons }
            Assert-Throws { [RutaXPInstaller.InstallerCore]::InstallFromDirectory($source,$addons) }
        } finally { [IO.Directory]::Delete($link) }
    } else { throw "Unknown case: $Case" }
    Write-Output ('PASS ' + $Case)
} catch { Write-Error ($_ | Out-String); exit 1 }
