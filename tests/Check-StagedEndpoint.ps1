$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path -Parent $PSScriptRoot
$fixture = Join-Path ([IO.Path]::GetTempPath()) (([guid]::NewGuid().ToString()) + '.json')
$global:StageProbeWrongRoute = $false
$global:StageProbeTLSFailure = $false
$global:StageProbeCalls = New-Object 'System.Collections.Generic.List[object]'
function Find-NetRoute {
    param([string]$RemoteIPAddress)
    $alias = if ($global:StageProbeWrongRoute) { 'Ethernet' } else { 'Tailscale' }
    [pscustomobject]@{DestinationPrefix=($RemoteIPAddress + '/32');InterfaceAlias=$alias}
}
function curl.exe {
    $arguments = @($args)
    $global:StageProbeCalls.Add($arguments)
    $global:LASTEXITCODE = 0
    if ($arguments -contains 'https://download.epicgames.com/' -and $global:StageProbeTLSFailure) {
        $global:LASTEXITCODE = 60
        return '000'
    }
    if ($arguments -contains 'http://172.28.80.10/lancache-heartbeat') { return '204' }
    return '403'
}
try {
    @{SchemaVersion=2;CacheIP='172.28.80.10';Services=@('steam','epic');
        Namespaces=@('download.epicgames.com');DomainRevision=('a'*40)} |
        ConvertTo-Json | Set-Content -LiteralPath $fixture -Encoding UTF8
    $scriptPath = Join-Path $sourceRoot 'windows\Test-StagedEndpoint.ps1'
    $report = & $scriptPath -ServicePlan $fixture | ConvertFrom-Json
    if (-not $report.Passed -or $report.CacheHitProven -or -not $report.TLSCertificateValidated) { throw 'Incorrect transport result.' }
    foreach ($call in $global:StageProbeCalls) {
        if ('--insecure' -in $call -or '-k' -in $call) { throw 'TLS validation was bypassed.' }
        if ('--resolve' -notin $call -and 'Host: lancache.steamcontent.com' -notin $call) { throw 'Expected direct request routing.' }
    }
    foreach ($mode in @('route','tls','hostname')) {
        $global:StageProbeWrongRoute = $mode -eq 'route'
        $global:StageProbeTLSFailure = $mode -eq 'tls'
        $hostToProbe = if ($mode -eq 'hostname') { 'accounts.epicgames.com' } else { 'download.epicgames.com' }
        $rejected = $false
        try { & $scriptPath -ServicePlan $fixture -Hostname $hostToProbe | Out-Null } catch { $rejected = $true }
        if (-not $rejected) { throw "Unsafe probe accepted: $mode" }
    }
    Write-Output 'PASS: staged transport probes require the Tailscale route and valid TLS, preserve DNS, and never claim a cache HIT.'
} finally {
    Remove-Item -LiteralPath $fixture -Force -ErrorAction SilentlyContinue
    Remove-Variable -Name StageProbeWrongRoute,StageProbeTLSFailure,StageProbeCalls -Scope Global -ErrorAction SilentlyContinue
}
