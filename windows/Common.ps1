Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:Product = 'TailscaleLANCache'
$script:Root = Join-Path $env:ProgramData $script:Product
$script:SteamMarker = 'TailscaleLANCache Steam v1'
$script:MagicMarker = 'TailscaleLANCache MagicDNS v1'
$script:ServiceMarker = 'TailscaleLANCache Services v2'
$script:TaskNames = @('TailscaleLANCache DNS', 'TailscaleLANCache Maintenance')
function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this script from PowerShell as Administrator.'
    }
}
function Assert-CacheAddress([string]$Address) {
    $parsed = $null
    if (-not [Net.IPAddress]::TryParse($Address, [ref]$parsed) -or $parsed.AddressFamily -ne 'InterNetwork') { throw 'An IPv4 cache address is required.' }
    $b = $parsed.GetAddressBytes()
    if (-not ($b[0] -eq 10 -or ($b[0] -eq 172 -and $b[1] -ge 16 -and $b[1] -le 31) -or ($b[0] -eq 192 -and $b[1] -eq 168))) {
        throw 'Steam requires an RFC1918 cache address, routed over Tailscale as a /32.'
    }
}
function Import-ServicePlan([string]$Path, [string]$CacheIP, [bool]$AllowExperimental) {
    $plan = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($plan.SchemaVersion -ne 2 -or $plan.CacheIP -ne $CacheIP) { throw 'Service plan version or cache address does not match.' }
    $ids = @($plan.Services)
    if ('steam' -notin $ids) { throw 'Service plan must include the Steam baseline.' }
    foreach ($id in $ids) {
        if ($id -notin @('steam','epic','ea','microsoft-xbox','microsoft-updates')) { throw 'Service plan contains an unsupported service.' }
    }
    if (@($ids | Where-Object { $_ -ne 'steam' }).Count -and -not $AllowExperimental) { throw 'Experimental service plan requires -AllowExperimental.' }
    if ($plan.DomainRevision -notmatch '^[a-f0-9]{40}$') { throw 'Service plan requires a pinned domain-source revision.' }
    $names = @($plan.Namespaces)
    if (-not $names.Count -or $names.Count -gt 512) { throw 'Invalid namespace count in service plan.' }
    foreach ($name in $names) {
        if ($name -isnot [string] -or ($name -ne '.windowsupdate.com' -and $name -notmatch '^\.?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.){2,}[a-z]{2,63}$') -or $name.Length -gt 254) {
            throw 'Service plan contains an invalid or overly broad DNS namespace.'
        }
    }
    return $plan
}
function Set-OwnedRule([string]$Marker, [string[]]$Names) {
    $rules = @(Get-DnsClientNrptRule | Where-Object Comment -eq $Marker)
    if ($rules.Count -eq 1) {
        Set-DnsClientNrptRule -Name $rules[0].Name -Namespace $Names -NameServers '127.0.0.1'
    } else {
        foreach ($rule in $rules) { Remove-DnsClientNrptRule -Name $rule.Name -Force }
        Add-DnsClientNrptRule -Namespace $Names -NameServers '127.0.0.1' -Comment $Marker | Out-Null
    }
}
