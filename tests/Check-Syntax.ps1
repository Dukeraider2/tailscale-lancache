$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path -Parent $PSScriptRoot
foreach ($file in Get-ChildItem -LiteralPath $sourceRoot -Filter '*.ps1' -Recurse) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count) { throw ($errors | Out-String) }
}
. (Join-Path $sourceRoot 'windows\Common.ps1')
foreach ($address in @('10.20.0.10','172.20.0.10','192.168.50.10')) { Assert-CacheAddress $address }
foreach ($address in @('100.64.0.1','8.8.8.8','127.0.0.1','::1','invalid')) {
    $rejected = $false
    try { Assert-CacheAddress $address } catch { $rejected = $true }
    if (-not $rejected) { throw 'Unsafe cache address accepted.' }
}
& (Join-Path $sourceRoot 'windows\Install.ps1') -CacheIP '192.168.50.10' -TailnetSuffix 'example-tailnet.ts.net' -WhatIf
Write-Output 'PASS: PowerShell syntax, RFC1918 validation and non-mutating installer preview.'
