Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:Product = 'TailscaleLANCache'
$script:Root = Join-Path $env:ProgramData $script:Product
$script:SteamMarker = 'TailscaleLANCache Steam v1'
$script:MagicMarker = 'TailscaleLANCache MagicDNS v1'
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
function Set-OwnedRule([string]$Marker, [string[]]$Names) {
    $rules = @(Get-DnsClientNrptRule | Where-Object Comment -eq $Marker)
    if ($rules.Count -eq 1) {
        Set-DnsClientNrptRule -Name $rules[0].Name -Namespace $Names -NameServers '127.0.0.1'
    } else {
        foreach ($rule in $rules) { Remove-DnsClientNrptRule -Name $rule.Name -Force }
        Add-DnsClientNrptRule -Namespace $Names -NameServers '127.0.0.1' -Comment $Marker | Out-Null
    }
}
