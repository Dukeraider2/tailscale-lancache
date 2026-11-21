#Requires -Version 5.1
param([Parameter(Mandatory)][string]$CacheIP, [string]$MagicDNSName)
. "$PSScriptRoot\Common.ps1"
Assert-CacheAddress $CacheIP
$answers = @([Net.Dns]::GetHostAddresses('lancache.steamcontent.com') | ForEach-Object IPAddressToString)
if ($CacheIP -notin $answers) { throw 'Steam discovery did not resolve to the cache.' }
if (-not @([Net.Dns]::GetHostAddresses('example.com')).Count) { throw 'Ordinary DNS failed.' }
if ($MagicDNSName -and -not @([Net.Dns]::GetHostAddresses($MagicDNSName)).Count) { throw 'MagicDNS resolution failed.' }
$request = [Net.HttpWebRequest]::Create("http://$CacheIP/lancache-heartbeat")
$request.Proxy = $null
$request.Host = 'lancache.steamcontent.com'
$request.Timeout = 8000
$response = $request.GetResponse()
try { if ([int]$response.StatusCode -ne 204) { throw 'Cache heartbeat did not return 204.' } } finally { $response.Dispose() }
Write-Output 'PASS: Steam DNS, ordinary DNS and cache heartbeat. VPN state was not changed.'
