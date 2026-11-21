#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot\Common.ps1"
if (-not $PSCmdlet.ShouldProcess($Root, 'Remove owned tasks and DNS rules; restore original network preferences')) { return }
Assert-Administrator
if (-not (Test-Path -LiteralPath (Join-Path $Root 'original-state.json'))) { throw 'No original-state backup found; no changes made.' }
$state = Get-Content -LiteralPath (Join-Path $Root 'original-state.json') -Raw | ConvertFrom-Json
foreach ($name in $TaskNames) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($task) { Stop-ScheduledTask -TaskName $name; Unregister-ScheduledTask -TaskName $name -Confirm:$false }
}
foreach ($rule in @(Get-DnsClientNrptRule | Where-Object { $_.Comment -in @($SteamMarker,$MagicMarker) })) {
    Remove-DnsClientNrptRule -Name $rule.Name -Force
}
Set-DnsClientGlobalSetting -SuffixSearchList @($state.Suffixes)
$adapter = Get-NetIPInterface -InterfaceAlias $state.InterfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue
if ($adapter) {
    Set-NetIPInterface -InterfaceIndex $adapter.InterfaceIndex -AddressFamily IPv4 -InterfaceMetric $state.InterfaceMetric -AutomaticMetric $state.AutomaticMetric
}
Clear-DnsClientCache
# Only the fixed product directory is removed. Cache data and Tailscale enrollment remain.
$expectedRoot = Join-Path $env:ProgramData 'TailscaleLANCache'
if ([IO.Path]::GetFullPath($Root) -ne [IO.Path]::GetFullPath($expectedRoot)) { throw 'Unexpected runtime path.' }
Start-Sleep -Seconds 1
Remove-Item -LiteralPath $Root -Recurse -Force
Write-Output 'Client removed. Mullvad exclusions and server deployment are managed separately.'
