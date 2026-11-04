param([string]$FixtureRoot, [string]$Assembly, [string]$Case)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Web.Extensions
Add-Type -Path $Assembly
$temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$FixtureRoot=[IO.Path]::GetFullPath($FixtureRoot)
if (-not $FixtureRoot.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase)) { throw 'Tests require a temporary fixture directory.' }
[IO.Directory]::CreateDirectory($FixtureRoot) | Out-Null

function Assert-True { param($Value,[string]$Message) if (-not $Value) { throw $Message } }
function Assert-Throws { param([scriptblock]$Body) $failed=$false; try { & $Body | Out-Null } catch { $failed=$true }; Assert-True $failed 'Expected rejection.' }
function Put { param([string]$Path,[string]$Text) [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path)) | Out-Null;[IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false))) }
function File-Hash { param([string]$Path) $hash=[Security.Cryptography.SHA256]::Create();$input=[IO.File]::OpenRead($Path);try { return [BitConverter]::ToString($hash.ComputeHash($input)).Replace('-','').ToLowerInvariant() } finally { $input.Dispose();$hash.Dispose() } }
function Seal { param([string]$Root)
    $lines=@('# Fixture')
    foreach($file in [IO.Directory]::GetFiles($Root,'*',[IO.SearchOption]::AllDirectories) | Sort-Object) {
        if ([IO.Path]::GetFileName($file) -eq 'manifest.sha256') { continue }
        $lines += (File-Hash $file)+'  '+$file.Substring($Root.Length+1).Replace('\','/')
    }
    [IO.File]::WriteAllLines((Join-Path $Root 'manifest.sha256'),[string[]]$lines,(New-Object Text.UTF8Encoding($false)))
}
function New-Addon { param([string]$Root,[string]$Version='0.9.0',[string]$Label='old')
    Put (Join-Path $Root 'RutaXP.toc') "## Interface: 16001`n## Version: $Version`nCore.lua`nSub\ui.lua`n"
    Put (Join-Path $Root 'Core.lua') ("-- "+$Label)
    Put (Join-Path $Root 'Sub\ui.lua') '-- fixture ui'
    Put (Join-Path $Root 'Source\guide.json') '{"fixture":true}'
    Seal $Root;return $Root
}
function New-Client { param([string]$Name)
    $client=Join-Path $FixtureRoot ($Name+'\_classic_beta_')
    $addons=Join-Path $client 'Interface\AddOns'
    [IO.Directory]::CreateDirectory($addons) | Out-Null
    Put (Join-Path $client 'WTF\Account\untouched.lua') '-- never touch WTF'
    Put (Join-Path $addons 'OtherAddon\keep.lua') '-- other addon'
    return $addons
}
function Zip-Addon { param([string]$Source,[string]$Extra='')
    $memory=New-Object IO.MemoryStream
    $zip=[IO.Compression.ZipArchive]::new($memory,[IO.Compression.ZipArchiveMode]::Create,$true)
    foreach($file in [IO.Directory]::GetFiles($Source,'*',[IO.SearchOption]::AllDirectories)) {
        $entry=$zip.CreateEntry('RutaXP/'+$file.Substring($Source.Length+1).Replace('\','/'))
        $output=$entry.Open();try { $bytes=[IO.File]::ReadAllBytes($file);$output.Write($bytes,0,$bytes.Length) } finally { $output.Dispose() }
    }
    if($Extra) { $entry=$zip.CreateEntry($Extra);$output=$entry.Open();$output.WriteByte(1);$output.Dispose() }
    $zip.Dispose();$bytes=$memory.ToArray();$memory.Dispose();return ,$bytes
}
function New-Package { param([string]$Source,[string]$Version='0.10.0',[byte[]]$Bytes=$null)
    if ($null -eq $Bytes) { $Bytes=Zip-Addon $Source }
    $name='RutaXP-'+$Version+'-addon.zip';$tag='v'+$Version
    $base='https://github.com/Dekaz4/RutaXP/releases/download/'+$tag+'/'
    $sum=[RutaXPUpdater.UpdaterCore]::Hash($Bytes)+'  '+$name+"`n"
    $meta=@{tag_name=$tag;draft=$false;prerelease=$false;assets=@(
        @{name=$name;size=$Bytes.Length;browser_download_url=$base+$name},
        @{name='SHA256SUMS.txt';size=[Text.Encoding]::UTF8.GetByteCount($sum);browser_download_url=$base+'SHA256SUMS.txt'})}
    $json=(New-Object Web.Script.Serialization.JavaScriptSerializer).Serialize($meta)
    return @{Archive=$Bytes;Sum=$sum;Meta=$json;Name=$name;ZipUrl=$base+$name;SumUrl=$base+'SHA256SUMS.txt';Release=[RutaXPUpdater.UpdaterCore]::ParseRelease($json)}
}
function Use-Package { param($Package)
    $script:Responses=@{}
    $script:Responses[[RutaXPUpdater.UpdaterCore]::LatestUrl]=[Text.Encoding]::UTF8.GetBytes($Package.Meta)
    $script:Responses[$Package.ZipUrl]=$Package.Archive
    $script:Responses[$Package.SumUrl]=[Text.Encoding]::UTF8.GetBytes($Package.Sum)
    $script:FetchCount=0;$script:Offline=$false;$script:Running=$false;$script:StartDuringDownload=$false
    $script:Fetch=[Func[string,long,byte[]]] { param($url,$maximum)
        $script:FetchCount++
        if($script:Offline){throw 'Offline fixture; no network is used.'}
        if($script:StartDuringDownload -and $script:FetchCount -eq 3){$script:Running=$true}
        if(-not $script:Responses.ContainsKey($url)){throw ('Unexpected URL: '+$url)}
        return [byte[]]$script:Responses[$url]
    }
    $script:IsRunning=[Func[bool]] { return $script:Running }
}
function Update { param([string]$Addons,[bool]$Repair=$false,[string]$Floor=$null,[Action]$Before=$null)
    if($Floor -eq ''){$Floor=$null}
    return [RutaXPUpdater.UpdaterCore]::Update($Addons,$Repair,$Floor,$script:Fetch,$script:IsRunning,$Before)
}
function Assert-Old { param([string]$Target) [RutaXPInstaller.InstallerCore]::Manifest($Target) | Out-Null;Assert-True ([IO.File]::ReadAllText((Join-Path $Target 'Core.lua')) -eq '-- old') 'Previous addon was changed.' }
function Assert-Wtf { param([string]$Addons)
    $client=[IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName($Addons))
    Assert-True ([IO.File]::ReadAllText((Join-Path $client 'WTF\Account\untouched.lua')) -eq '-- never touch WTF') 'WTF changed.'
    Assert-True ([IO.File]::ReadAllText((Join-Path $Addons 'OtherAddon\keep.lua')) -eq '-- other addon') 'Another addon changed.'
}
function Patch-ZipLength { param([byte[]]$Bytes,[uint32]$Length)
    $copy=[byte[]]$Bytes.Clone()
    for($i=0;$i -lt $copy.Length-46;$i++) {
        if($copy[$i] -eq 80 -and $copy[$i+1] -eq 75 -and $copy[$i+2] -eq 1 -and $copy[$i+3] -eq 2) {
            [Array]::Copy([BitConverter]::GetBytes($Length),0,$copy,$i+24,4);break
        }
    }
    return ,$copy
}

try {
    $source=New-Addon (Join-Path $FixtureRoot 'source') '0.10.0' 'new'
    $package=New-Package $source
    $addons=New-Client 'Game';$target=New-Addon (Join-Path $addons 'RutaXP') '0.9.0' 'old'
    Use-Package $package
    switch($Case) {
        'metadata' {
            Assert-True ([RutaXPUpdater.UpdaterCore]::CompareVersions('0.10.0','0.9.9') -gt 0) 'Version 10 must sort after 9.'
            Assert-True ([RutaXPUpdater.UpdaterCore]::CompareVersions('1.0.0','0.99.99') -gt 0) 'Major version comparison failed.'
            foreach($tag in @('v01.2.3','v1.2','v1.2.3-beta','v1.2.3/evil')) { Assert-Throws {[RutaXPUpdater.UpdaterCore]::TagVersion($tag)} }
            foreach($url in @('http://github.com/Dekaz4/RutaXP/releases/download/v0.10.0/'+$package.Name,
                'https://github.com/Other/RutaXP/releases/download/v0.10.0/'+$package.Name,
                'https://github.com.evil.test/Dekaz4/RutaXP/releases/download/v0.10.0/'+$package.Name,
                $package.ZipUrl+'?redirect=evil','https://user@github.com/Dekaz4/RutaXP/releases/download/v0.10.0/'+$package.Name)) {
                Assert-Throws {[RutaXPUpdater.UpdaterCore]::ValidateAssetUrl($url,'v0.10.0',$package.Name)}
            }
            Assert-Throws {[RutaXPUpdater.UpdaterCore]::ParseRelease('{"tag_name":"v0.10.0","draft":false,"prerelease":false,"assets":[]}')}
            Assert-Throws {[RutaXPUpdater.UpdaterCore]::ParseRelease($package.Meta.Replace('SHA256SUMS.txt','not-checksums.txt'))}
            Assert-Throws {[RutaXPUpdater.UpdaterCore]::ParseRelease($package.Meta.Replace('"draft":false','"draft":true'))}
        }
        'update' {
            $result=Update $addons
            Assert-True ($result.Changed -and $result.LatestVerified -and $result.Version -eq '0.10.0') 'Update was not verified.'
            Assert-Old $result.Backup
            Assert-True ([RutaXPUpdater.UpdaterCore]::TocVersion($result.Target) -eq '0.10.0') 'Wrong version installed.'
            [RutaXPInstaller.InstallerCore]::Manifest($result.Target) | Out-Null
            Assert-Wtf $addons
        }
        'repair' {
            Update $addons | Out-Null;Use-Package $package
            $result=Update $addons
            Assert-True (-not $result.Changed -and $result.LatestVerified -and $script:FetchCount -eq 1) 'Equal valid version should only check metadata.'
            Use-Package $package;$result=Update $addons $true
            Assert-True ($result.Changed -and $script:FetchCount -eq 3) 'Repair must redownload the same version.'
            [IO.File]::AppendAllText((Join-Path $target 'Core.lua'),'corrupt')
            Use-Package $package;$result=Update $addons
            Assert-True $result.Changed 'A corrupt equal-version install must be repaired.'
            [RutaXPInstaller.InstallerCore]::Manifest($target) | Out-Null
            Assert-Wtf $addons
        }
        'download_failures' {
            $script:Offline=$true;Assert-Throws {Update $addons};Assert-Old $target
            Use-Package $package;$bad=[byte[]]$package.Archive.Clone();$bad[30]=$bad[30] -bxor 1;$script:Responses[$package.ZipUrl]=$bad
            Assert-Throws {Update $addons};Assert-Old $target
            Use-Package $package;Assert-Throws {Update $addons $false '0.11.0'};Assert-Old $target
            $old=New-Package $source '0.8.0';Use-Package $old
            Assert-Throws {Update $addons};Assert-Old $target
            Assert-Wtf $addons
        }
        'packages' {
            foreach($entry in @('RutaXP/../outside.txt','RutaXP/Core.lua','RutaXP/Sub/../../outside.txt','evil.exe','RutaXP/CON.txt')) {
                $p=New-Package $source '0.10.0' (Zip-Addon $source $entry);Use-Package $p
                Assert-Throws {Update $addons};Assert-Old $target
            }
            $p=New-Package $source '0.10.0' ([Text.Encoding]::UTF8.GetBytes('not a zip'));Use-Package $p
            Assert-Throws {Update $addons};Assert-Old $target
            [IO.File]::AppendAllText((Join-Path $source 'Core.lua'),'wrong manifest')
            $p=New-Package $source;Use-Package $p;Assert-Throws {Update $addons};Assert-Old $target
            $source=New-Addon $source '0.9.0' 'new'
            $p=New-Package $source '0.10.0';Use-Package $p;Assert-Throws {Update $addons};Assert-Old $target
            $source=New-Addon $source '0.10.0' 'new'
            Put (Join-Path $source 'Core.lua') ('x'*200000);Seal $source
            $bytes=Zip-Addon $source
            foreach($declared in @([uint32]0,[uint32]([RutaXPUpdater.UpdaterCore]::MaxEntryBytes+1))) {
                $p=New-Package $source '0.10.0' (Patch-ZipLength $bytes $declared);Use-Package $p
                Assert-Throws {Update $addons};Assert-Old $target
            }
            Assert-Wtf $addons
        }
        'rollback' {
            $fail=[Action] {throw 'Simulated failure after old folder was backed up.'}
            Assert-Throws {Update $addons $false $null $fail};Assert-Old $target
            Assert-True (@([IO.Directory]::GetDirectories($addons,'.RutaXP.*')).Count -eq 0) 'Successful rollback left temporary directories.'
            Use-Package $package;$start=[Action] {$script:Running=$true}
            Assert-Throws {Update $addons $false $null $start};Assert-Old $target
            Use-Package $package;$script:StartDuringDownload=$true
            Assert-Throws {Update $addons};Assert-Old $target
            Assert-Wtf $addons
        }
        'restore' {
            $result=Update $addons;$oldBackup=$result.Backup
            $bad=New-Addon (Join-Path $addons ('.RutaXP.backup.'+[guid]::NewGuid().ToString('N'))) '0.8.0' 'broken'
            [IO.File]::AppendAllText((Join-Path $bad 'Core.lua'),'corrupt')
            $copies=[RutaXPUpdater.UpdaterCore]::Backups($addons)
            Assert-True ($copies.Count -eq 1 -and $copies[0].Path -eq $oldBackup) 'Corrupt backup must not be offered.'
            foreach($name in @('..\RutaXP',$oldBackup,'.RutaXP.backup.not-a-guid')) { Assert-Throws {[RutaXPUpdater.UpdaterCore]::Restore($addons,$name,$script:IsRunning,$null)} }
            $foreign=New-Client 'OtherGame';$foreignName='.RutaXP.backup.'+[guid]::NewGuid().ToString('N')
            New-Addon (Join-Path $foreign $foreignName) '0.8.0' 'foreign' | Out-Null
            Assert-Throws {[RutaXPUpdater.UpdaterCore]::Restore($addons,$foreignName,$script:IsRunning,$null)}
            $restored=[RutaXPUpdater.UpdaterCore]::Restore($addons,$null,$script:IsRunning,$null)
            Assert-Old $target;Assert-Old $oldBackup
            Assert-True ([RutaXPUpdater.UpdaterCore]::TocVersion($restored.Backup) -eq '0.10.0') 'Restoring must also back up the current version.'
            [RutaXPInstaller.InstallerCore]::Manifest($restored.Backup) | Out-Null
            Assert-Wtf $addons
        }
        'settings' {
            $script:Running=$true;Assert-Throws {Update $addons}
            Assert-True ($script:FetchCount -eq 0) 'Running WoW should block before downloading.'
            Assert-Old $target
            $settings=Join-Path $FixtureRoot 'LocalAppData\RutaXP'
            [RutaXPUpdater.ClientSettings]::Save($settings,'client',$addons)
            Assert-True ([RutaXPUpdater.ClientSettings]::Load($settings,'client') -eq $addons) 'Client was not remembered.'
            $other=New-Client 'SecondComputer'
            [RutaXPUpdater.ClientSettings]::Save($settings,'client',$other)
            Assert-True ([RutaXPUpdater.ClientSettings]::Load($settings,'client') -eq $other) 'Client path was not changed.'
            Assert-Throws {[RutaXPUpdater.ClientSettings]::Save($settings,'..\WTF','bad')}
            Assert-Throws {[RutaXPUpdater.ClientSettings]::Load($settings,'..\WTF')}
            Assert-Wtf $addons
        }
        'bundled' {
            $stream=[IO.MemoryStream]::new([byte[]]$package.Archive,$false)
            try {$result=[RutaXPUpdater.UpdaterCore]::InstallBundled($stream,$addons,$script:IsRunning,$null)} finally {$stream.Dispose()}
            Assert-True ($result.Changed -and -not $result.LatestVerified -and $script:FetchCount -eq 0) 'Offline install must not claim that latest was verified.'
            Assert-Old $result.Backup
            [IO.File]::AppendAllText((Join-Path $target 'Core.lua'),'corrupt')
            $stream=[IO.MemoryStream]::new([byte[]]$package.Archive,$false)
            try {$result=[RutaXPUpdater.UpdaterCore]::InstallBundled($stream,$addons,$script:IsRunning,$null)} finally {$stream.Dispose()}
            [RutaXPInstaller.InstallerCore]::Manifest($target) | Out-Null
            $older=New-Addon (Join-Path $FixtureRoot 'older bundle') '0.9.0' 'old';$bytes=Zip-Addon $older
            $stream=[IO.MemoryStream]::new([byte[]]$bytes,$false)
            try {Assert-Throws {[RutaXPUpdater.UpdaterCore]::InstallBundled($stream,$addons,$script:IsRunning,$null)}} finally {$stream.Dispose()}
            Assert-True ([RutaXPUpdater.UpdaterCore]::TocVersion($target) -eq '0.10.0') 'Offline bundle downgraded a newer installation.'
            $before=File-Hash (Join-Path $target 'Core.lua')
            $stream=[IO.MemoryStream]::new([byte[]]$package.Archive,$false);$fail=[Action]{throw 'Activation failed.'}
            try {Assert-Throws {[RutaXPUpdater.UpdaterCore]::InstallBundled($stream,$addons,$script:IsRunning,$fail)}} finally {$stream.Dispose()}
            Assert-True ((File-Hash (Join-Path $target 'Core.lua')) -eq $before) 'Offline rollback changed the installed copy.'
            Assert-Wtf $addons
        }
        default {throw ('Unknown case: '+$Case)}
    }
    Write-Output ('PASS '+$Case)
} catch {Write-Error ($_ | Out-String);exit 1}
