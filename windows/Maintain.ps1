. "$PSScriptRoot\Common.ps1"
$config = Get-Content -LiteralPath (Join-Path $Root 'client-config.json') -Raw | ConvertFrom-Json
$adapter = Get-NetIPInterface -InterfaceAlias $config.InterfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue
if ($null -eq $adapter) { return }
if ($config.LanSubnet) {
    $direct = @(Get-NetRoute -DestinationPrefix $config.LanSubnet -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.InterfaceIndex -ne $adapter.InterfaceIndex -and $_.NextHop -eq '0.0.0.0' })
    $metric = if ($direct.Count) { 500 } else { 5 }
    Set-NetIPInterface -InterfaceIndex $adapter.InterfaceIndex -AddressFamily IPv4 -AutomaticMetric Disabled -InterfaceMetric $metric
}
$raw = & $config.TailscalePath status --json
if ($LASTEXITCODE -ne 0) { throw 'Tailscale status failed.' }
$status = $raw | ConvertFrom-Json
if ($status.BackendState -ne 'Running') { return }
$names = @($status.Self.DNSName)
$peerProperty = $status.PSObject.Properties['Peer']
if ($null -ne $peerProperty -and $null -ne $peerProperty.Value) {
    foreach ($peer in $peerProperty.Value.PSObject.Properties) { $names += $peer.Value.DNSName }
}
$names = @($names | Where-Object { $_ -and $_.TrimEnd('.').EndsWith('.' + $config.TailnetSuffix) } |
    ForEach-Object { $_.TrimEnd('.') } | Sort-Object -Unique)
if ($names.Count) { Set-OwnedRule $MagicMarker $names }
$suffixes = @((Get-DnsClientGlobalSetting).SuffixSearchList)
if ($config.TailnetSuffix -notin $suffixes) {
    $connectionSuffixes = @(Get-DnsClient | Where-Object ConnectionSpecificSuffix | Select-Object -ExpandProperty ConnectionSpecificSuffix)
    Set-DnsClientGlobalSetting -SuffixSearchList @($suffixes + @($config.TailnetSuffix) + $connectionSuffixes | Where-Object { $_ } | Select-Object -Unique)
}
