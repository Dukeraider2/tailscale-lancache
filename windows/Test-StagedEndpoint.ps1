#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ServicePlan,
    [string]$Hostname = 'download.epicgames.com',
    [string]$InterfaceAlias = 'Tailscale'
)
. "$PSScriptRoot\Common.ps1"
$rawPlan = Get-Content -LiteralPath $ServicePlan -Raw | ConvertFrom-Json
Assert-CacheAddress $rawPlan.CacheIP
$plan = Import-ServicePlan $ServicePlan $rawPlan.CacheIP $true
if ($Hostname -notin @($plan.Namespaces) -or $Hostname.StartsWith('.')) {
    throw 'Choose an exact content hostname from the reviewed service plan.'
}
$routes = @(Find-NetRoute -RemoteIPAddress $plan.CacheIP | Where-Object { $_.PSObject.Properties.Name -contains 'DestinationPrefix' })
if (-not @($routes | Where-Object { $_.DestinationPrefix -eq ($plan.CacheIP + '/32') -and $_.InterfaceAlias -eq $InterfaceAlias }).Count) {
    throw 'The staging cache must be reached through its approved Tailscale /32 route.'
}
function Invoke-CurlProbe([string[]]$Arguments) {
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $response = & curl.exe @Arguments 2>$null
        $code = $LASTEXITCODE
        return [pscustomobject]@{ExitCode=$code;Status=([string]($response | Select-Object -Last 1)).Trim()}
    } finally { $ErrorActionPreference = $previous }
}
$baseArgs = @('--noproxy','*','--connect-timeout','5','--max-time','12','--silent','--output','NUL','--write-out','%{http_code}')
$heartbeat = Invoke-CurlProbe ($baseArgs + @('--header','Host: lancache.steamcontent.com',('http://{0}/lancache-heartbeat' -f $plan.CacheIP)))
$http = Invoke-CurlProbe ($baseArgs + @('--head','--resolve',('{0}:80:{1}' -f $Hostname,$plan.CacheIP),('http://{0}/' -f $Hostname)))
$https = Invoke-CurlProbe ($baseArgs + @('--head','--resolve',('{0}:443:{1}' -f $Hostname,$plan.CacheIP),('https://{0}/' -f $Hostname)))
$passed = $heartbeat.ExitCode -eq 0 -and $heartbeat.Status -eq '204' -and $http.ExitCode -eq 0 -and $https.ExitCode -eq 0
[pscustomobject]@{Hostname=$Hostname;TailscaleRoute=$true;Heartbeat=$heartbeat.Status;
    HTTPStatus=$http.Status;HTTPExitCode=$http.ExitCode;HTTPSStatus=$https.Status;HTTPSExitCode=$https.ExitCode;
    TLSCertificateValidated=($https.ExitCode -eq 0);Passed=$passed;CacheHitProven=$false} | ConvertTo-Json
if (-not $passed) { throw 'A staging transport probe failed; no system DNS settings were changed.' }
