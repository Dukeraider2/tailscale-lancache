$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $sourceRoot 'windows\Common.ps1')
$fixture = Join-Path ([IO.Path]::GetTempPath()) (([guid]::NewGuid().ToString()) + '.json')
try {
    $plan = @{ SchemaVersion=2; CacheIP='192.168.50.10'; Services=@('steam','epic');
        Namespaces=@('download.epicgames.com','lancache.steamcontent.com','steam.cache.lancache.net');
        DomainRevision=('a' * 40) }
    $plan | ConvertTo-Json | Set-Content -LiteralPath $fixture -Encoding UTF8
    $imported = Import-ServicePlan $fixture '192.168.50.10' $true
    if ($imported.Namespaces.Count -ne 3) { throw 'Expected content names were lost.' }
    & (Join-Path $sourceRoot 'windows\Install.ps1') -CacheIP '192.168.50.10' -TailnetSuffix 'example-tailnet.ts.net' -ServicePlan $fixture -AllowExperimental -WhatIf
    foreach ($scenario in @('opt-in','wrong-ip','broad-domain','research-only','wrong-version')) {
        $bad = $plan.Clone()
        $expectedIP = '192.168.50.10'
        $allowed = $true
        switch ($scenario) {
            'opt-in' { $allowed = $false }
            'wrong-ip' { $expectedIP = '192.168.50.11' }
            'broad-domain' { $bad.Namespaces = @('.microsoft.com') }
            'research-only' { $bad.Services = @('steam','loverslab') }
            'wrong-version' { $bad.SchemaVersion = 1 }
        }
        $bad | ConvertTo-Json | Set-Content -LiteralPath $fixture -Encoding UTF8
        $rejected = $false
        try { Import-ServicePlan $fixture $expectedIP $allowed | Out-Null } catch { $rejected = $true }
        if (-not $rejected) { throw "Unsafe plan accepted: $scenario" }
    }
    $plan.Services = @('steam','microsoft-updates')
    $plan.Namespaces = @('.windowsupdate.com')
    $plan | ConvertTo-Json | Set-Content -LiteralPath $fixture -Encoding UTF8
    Import-ServicePlan $fixture '192.168.50.10' $true | Out-Null
    Write-Output 'PASS: service-plan validation, experimental opt-in and installer preview.'
} finally {
    Remove-Item -LiteralPath $fixture -Force -ErrorAction SilentlyContinue
}
