#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$CacheIP,
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9-]+\.ts\.net$')][string]$TailnetSuffix,
    [string]$LanSubnet,
    [string]$InterfaceAlias = 'Tailscale',
    [string]$ServicePlan,
    [switch]$AllowExperimental,
    [string]$TailscalePath = "$env:ProgramFiles\Tailscale\tailscale.exe"
)
. "$PSScriptRoot\Common.ps1"
Assert-CacheAddress $CacheIP
$serviceNamespaces = @()
if ($ServicePlan) {
    $plan = Import-ServicePlan $ServicePlan $CacheIP $AllowExperimental.IsPresent
    $serviceNamespaces = @($plan.Namespaces | Where-Object { $_ -notin @('lancache.steamcontent.com','steam.cache.lancache.net') } | Sort-Object -Unique)
}
if ($LanSubnet -and $LanSubnet -notmatch '^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$') { throw 'Invalid LAN subnet CIDR.' }
if (-not $PSCmdlet.ShouldProcess($Root, 'Install local DNS proxy, owned NRPT rules and SYSTEM startup tasks')) { return }
Assert-Administrator
if (Test-Path -LiteralPath $Root) { throw 'Already installed or a previous install remains. Uninstall first; existing state is never overwritten.' }
foreach ($name in $TaskNames) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { throw 'A product task already exists. Resolve the previous installation before proceeding.' }
}
if (@(Get-DnsClientNrptRule | Where-Object { $_.Comment -in @($SteamMarker,$MagicMarker,$ServiceMarker) }).Count) {
    throw 'Product DNS rules already exist. Resolve the previous installation before proceeding.'
}
if (-not (Test-Path -LiteralPath $TailscalePath)) { throw 'Install and sign in to Tailscale first.' }
if (Get-NetTCPConnection -LocalPort 53 -State Listen -ErrorAction SilentlyContinue) { throw 'TCP port 53 is already in use.' }
if (Get-NetUDPEndpoint -LocalPort 53 -ErrorAction SilentlyContinue) { throw 'UDP port 53 is already in use.' }
$adapter = Get-NetIPInterface -InterfaceAlias $InterfaceAlias -AddressFamily IPv4
$raw = & $TailscalePath status --json
if ($LASTEXITCODE -ne 0 -or ($raw | ConvertFrom-Json).BackendState -ne 'Running') { throw 'Tailscale must be connected.' }
$route = Find-NetRoute -RemoteIPAddress $CacheIP | Where-Object { $_.PSObject.Properties.Name -contains 'DestinationPrefix' }
if (-not @($route | Where-Object { $_.DestinationPrefix -eq "$CacheIP/32" -and $_.InterfaceIndex -eq $adapter.InterfaceIndex }).Count) {
    throw 'The approved cache /32 route must be active on the Tailscale adapter. Approve it and enable route acceptance first.'
}
$probe = New-Object Net.Sockets.TcpClient
try {
    $pending = $probe.BeginConnect($CacheIP, 8053, $null, $null)
    if (-not $pending.AsyncWaitHandle.WaitOne(5000)) { throw 'Cache DNS transport is unreachable on TCP 8053.' }
    $probe.EndConnect($pending)
} finally { $probe.Dispose() }
$temp = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $temp | Out-Null
try {
    $archive = Join-Path $temp 'dnsproxy.zip'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/AdguardTeam/dnsproxy/releases/download/v0.86.0/dnsproxy-windows-amd64-v0.86.0.zip' -OutFile $archive
    $expected = 'dedc186ddd4b96bf92474f91d972f67da0824e0141d09e3102fd96db9f8a0dbc'
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Download checksum mismatch.' }
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $temp 'expanded')
    $exe = @(Get-ChildItem (Join-Path $temp 'expanded') -Recurse -Filter dnsproxy.exe)
    if ($exe.Count -ne 1) { throw 'Unexpected release archive layout.' }
    New-Item -ItemType Directory -Path $Root | Out-Null
    & icacls.exe $Root /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' /C | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not protect runtime directory.' }
    $state = @{ Suffixes = @((Get-DnsClientGlobalSetting).SuffixSearchList); InterfaceAlias = $InterfaceAlias;
        InterfaceMetric = $adapter.InterfaceMetric; AutomaticMetric = [string]$adapter.AutomaticMetric }
    $state | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Root 'original-state.json') -Encoding UTF8
    @{ CacheIP=$CacheIP; TailnetSuffix=$TailnetSuffix; LanSubnet=$LanSubnet; InterfaceAlias=$InterfaceAlias; TailscalePath=$TailscalePath; ServiceNamespaces=$serviceNamespaces } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Root 'client-config.json') -Encoding UTF8
    Copy-Item -LiteralPath $exe[0].FullName -Destination (Join-Path $Root 'dnsproxy.exe')
    foreach ($name in @('Common.ps1','Maintain.ps1','Uninstall.ps1','Test.ps1')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $Root }
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $action = New-ScheduledTaskAction -Execute (Join-Path $Root 'dnsproxy.exe') -Argument "--listen=127.0.0.1 --port=53 --upstream=tcp://${CacheIP}:8053 --timeout=5s"
    Register-ScheduledTask -TaskName $TaskNames[0] -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $principal -Settings $settings | Out-Null
    Start-ScheduledTask -TaskName $TaskNames[0]
    Start-Sleep -Seconds 2
    Set-OwnedRule $SteamMarker @('lancache.steamcontent.com','steam.cache.lancache.net')
    if ($serviceNamespaces.Count) { Set-OwnedRule $ServiceMarker $serviceNamespaces }
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
    $action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -File "' + (Join-Path $Root 'Maintain.ps1') + '"')
    Register-ScheduledTask -TaskName $TaskNames[1] -Action $action -Trigger @((New-ScheduledTaskTrigger -AtStartup),$trigger) -Principal $principal -Settings $settings | Out-Null
    & (Join-Path $Root 'Maintain.ps1')
    Clear-DnsClientCache
    & (Join-Path $Root 'Test.ps1') -CacheIP $CacheIP
    Write-Output 'Installed and tested. Restart Steam when no download is active. Test once in each VPN state.'
} catch {
    $failure = $_
    if (Test-Path -LiteralPath (Join-Path $Root 'original-state.json')) {
        try { & "$PSScriptRoot\Uninstall.ps1" -Confirm:$false } catch { Write-Warning 'Rollback incomplete. Run Uninstall.ps1 as Administrator.' }
    }
    throw $failure
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force
}
