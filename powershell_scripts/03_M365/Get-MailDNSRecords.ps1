<#
.SYNOPSIS
    Queries MX, SPF, DMARC, DKIM selector, and Autodiscover DNS records for a mail domain without external PowerShell modules.
.PSSTORE_META
    {
        "title": "Audit Mail DNS Records (MX, SPF, DMARC, DKIM, Autodiscover)",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 30,
        "output_mode": "json",
        "params": [
            {"name": "Domain", "type": "string", "default": "example.com"},
            {"name": "DkimSelector", "type": "string", "default": "selector1"},
            {"name": "DnsServer", "type": "string", "default": "1.1.1.1"},
            {"name": "CheckAutodiscover", "type": "bool", "default": true}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Domain = "example.com",

    [Parameter(Mandatory = $false)]
    [string]$DkimSelector = "selector1",

    [Parameter(Mandatory = $false)]
    [string]$DnsServer = "1.1.1.1",

    [Parameter(Mandatory = $false)]
    [bool]$CheckAutodiscover = $true
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

function Query-DnsSafe {
    param(
        [string]$Name,
        [string]$Type,
        [string]$Server
    )
    $resolveCmd = Get-Command -Name "Resolve-DnsName" -ErrorAction SilentlyContinue
    if ($resolveCmd) {
        $splat = @{
            Name        = $Name
            Type        = $Type
            DnsOnly     = $true
            ErrorAction = 'Stop'
        }
        if (-not [string]::IsNullOrWhiteSpace($Server)) {
            $splat['Server'] = $Server.Trim()
        }
        return @(Resolve-DnsName @splat)
    }
    return @()
}

try {
    $cleanDomain = if ($null -ne $Domain) { $Domain.Trim().TrimEnd('.') } else { "" }
    if ([string]::IsNullOrWhiteSpace($cleanDomain)) {
        $cleanDomain = "example.com"
    }
    $cleanSelector = if ([string]::IsNullOrWhiteSpace($DkimSelector)) { "selector1" } else { $DkimSelector.Trim() }
    $cleanServer = if ($null -ne $DnsServer) { $DnsServer.Trim() } else { "" }
    $warnCount = 0

    $hasResolveDns = [bool](Get-Command -Name "Resolve-DnsName" -ErrorAction SilentlyContinue)
    if (-not $hasResolveDns) {
        $status = "warning"
        $summary = "Resolve-DnsName cmdlet is unavailable on this Windows build."
        $errors.Add("DnsClient module (Resolve-DnsName) not found.")
        $results.Add([PSCustomObject]@{
            RecordType = "Prerequisite"
            QueryName  = $cleanDomain
            Status     = "Unavailable"
            Value      = "Resolve-DnsName missing"
            Notes      = "Install or enable Windows DnsClient module."
        })
    }
    else {
        # 1. MX Records
        try {
            $mxRecs = @(Query-DnsSafe -Name $cleanDomain -Type "MX" -Server $cleanServer | Where-Object { $_.QueryType -eq 'MX' -or $_.NameExchange })
            if ($mxRecs.Count -gt 0) {
                $mxList = ($mxRecs | Sort-Object Preference | ForEach-Object { "$($_.Preference):$($_.NameExchange)" }) -join "; "
                $results.Add([PSCustomObject]@{
                    RecordType = "MX"
                    QueryName  = $cleanDomain
                    Status     = "Found"
                    Value      = $mxList
                    Notes      = "$($mxRecs.Count) MX record(s)"
                })
            }
            else {
                $warnCount++
                $results.Add([PSCustomObject]@{
                    RecordType = "MX"
                    QueryName  = $cleanDomain
                    Status     = "Missing"
                    Value      = "None"
                    Notes      = "No MX records returned"
                })
            }
        }
        catch {
            $warnCount++
            $results.Add([PSCustomObject]@{
                RecordType = "MX"
                QueryName  = $cleanDomain
                Status     = "Error"
                Value      = "LookupFailed"
                Notes      = $_.Exception.Message
            })
        }

        # 2. SPF (TXT on apex domain)
        try {
            $txtRecs = @(Query-DnsSafe -Name $cleanDomain -Type "TXT" -Server $cleanServer)
            $spfVals = [System.Collections.Generic.List[string]]::new()
            foreach ($rec in $txtRecs) {
                $joined = ($rec.Strings -join "")
                if ($joined -like "v=spf1*") {
                    $spfVals.Add($joined)
                }
            }
            if ($spfVals.Count -eq 1) {
                $results.Add([PSCustomObject]@{
                    RecordType = "SPF"
                    QueryName  = $cleanDomain
                    Status     = "Found"
                    Value      = $spfVals[0]
                    Notes      = "Single valid v=spf1 record"
                })
            }
            elseif ($spfVals.Count -gt 1) {
                $warnCount++
                $results.Add([PSCustomObject]@{
                    RecordType = "SPF"
                    QueryName  = $cleanDomain
                    Status     = "Warning"
                    Value      = ($spfVals -join " | ")
                    Notes      = "Multiple SPF records detected ($($spfVals.Count)); RFC 7208 PermError risk"
                })
            }
            else {
                $warnCount++
                $results.Add([PSCustomObject]@{
                    RecordType = "SPF"
                    QueryName  = $cleanDomain
                    Status     = "Missing"
                    Value      = "None"
                    Notes      = "No v=spf1 TXT record found"
                })
            }
        }
        catch {
            $warnCount++
            $results.Add([PSCustomObject]@{
                RecordType = "SPF"
                QueryName  = $cleanDomain
                Status     = "Error"
                Value      = "LookupFailed"
                Notes      = $_.Exception.Message
            })
        }

        # 3. DMARC (_dmarc.<domain>)
        $dmarcHost = "_dmarc.$cleanDomain"
        try {
            $dmarcRecs = @(Query-DnsSafe -Name $dmarcHost -Type "TXT" -Server $cleanServer)
            $dmarcVals = [System.Collections.Generic.List[string]]::new()
            foreach ($rec in $dmarcRecs) {
                $joined = ($rec.Strings -join "")
                if ($joined -like "v=DMARC1*") {
                    $dmarcVals.Add($joined)
                }
            }
            if ($dmarcVals.Count -gt 0) {
                $policy = if ($dmarcVals[0] -match '\bp=([a-zA-Z]+)') { $Matches[1] } else { "unknown" }
                $dStatus = if ($policy -eq 'none') { "Warning" } else { "Found" }
                if ($policy -eq 'none') { $warnCount++ }
                $results.Add([PSCustomObject]@{
                    RecordType = "DMARC"
                    QueryName  = $dmarcHost
                    Status     = $dStatus
                    Value      = $dmarcVals[0]
                    Notes      = "Policy p=$policy"
                })
            }
            else {
                $warnCount++
                $results.Add([PSCustomObject]@{
                    RecordType = "DMARC"
                    QueryName  = $dmarcHost
                    Status     = "Missing"
                    Value      = "None"
                    Notes      = "No v=DMARC1 TXT record found"
                })
            }
        }
        catch {
            $warnCount++
            $results.Add([PSCustomObject]@{
                RecordType = "DMARC"
                QueryName  = $dmarcHost
                Status     = "Missing"
                Value      = "None"
                Notes      = $_.Exception.Message
            })
        }

        # 4. DKIM (<selector>._domainkey.<domain>)
        $dkimHost = "$cleanSelector._domainkey.$cleanDomain"
        try {
            $dkimTxt = @(Query-DnsSafe -Name $dkimHost -Type "TXT" -Server $cleanServer)
            $dkimCname = @($dkimTxt | Where-Object { $_.Type -eq 'CNAME' -or $_.NameHost })
            $dkimKeys = [System.Collections.Generic.List[string]]::new()
            foreach ($rec in $dkimTxt) {
                if ($rec.Strings) {
                    $joined = ($rec.Strings -join "")
                    if ($joined) { $dkimKeys.Add($joined) }
                }
            }
            if ($dkimCname.Count -gt 0 -or $dkimKeys.Count -gt 0) {
                $val = if ($dkimCname.Count -gt 0) { "CNAME -> $($dkimCname[0].NameHost)" } else { $dkimKeys[0] }
                $results.Add([PSCustomObject]@{
                    RecordType = "DKIM"
                    QueryName  = $dkimHost
                    Status     = "Found"
                    Value      = $val
                    Notes      = "Selector '$cleanSelector' resolved"
                })
            }
            else {
                $warnCount++
                $results.Add([PSCustomObject]@{
                    RecordType = "DKIM"
                    QueryName  = $dkimHost
                    Status     = "Missing"
                    Value      = "None"
                    Notes      = "No DKIM record for selector '$cleanSelector'"
                })
            }
        }
        catch {
            $warnCount++
            $results.Add([PSCustomObject]@{
                RecordType = "DKIM"
                QueryName  = $dkimHost
                Status     = "Missing"
                Value      = "None"
                Notes      = $_.Exception.Message
            })
        }

        # 5. Optional Autodiscover
        if ($CheckAutodiscover) {
            $autoHost = "autodiscover.$cleanDomain"
            try {
                $autoRecs = @(Query-DnsSafe -Name $autoHost -Type "A" -Server $cleanServer)
                $cnameTargets = @($autoRecs | Where-Object { $_.NameHost } | ForEach-Object { $_.NameHost })
                $ips = @($autoRecs | Where-Object { $_.IPAddress } | ForEach-Object { $_.IPAddress })
                if ($cnameTargets.Count -gt 0 -or $ips.Count -gt 0) {
                    $val = if ($cnameTargets.Count -gt 0) { "CNAME -> $($cnameTargets[0]) ($(($ips -join ', ')))" } else { ($ips -join ", ") }
                    $results.Add([PSCustomObject]@{
                        RecordType = "Autodiscover"
                        QueryName  = $autoHost
                        Status     = "Found"
                        Value      = $val
                        Notes      = "Autodiscover host resolves"
                    })
                }
                else {
                    $warnCount++
                    $results.Add([PSCustomObject]@{
                        RecordType = "Autodiscover"
                        QueryName  = $autoHost
                        Status     = "Missing"
                        Value      = "None"
                        Notes      = "No CNAME or A record found"
                    })
                }
            }
            catch {
                $warnCount++
                $results.Add([PSCustomObject]@{
                    RecordType = "Autodiscover"
                    QueryName  = $autoHost
                    Status     = "Missing"
                    Value      = "None"
                    Notes      = $_.Exception.Message
                })
            }
        }

        $serverLabel = if ($cleanServer) { $cleanServer } else { "SystemDefault" }
        if ($warnCount -gt 0) {
            $status = "warning"
            $summary = "Mail DNS audit for '$cleanDomain' (DNS: $serverLabel) found $warnCount warning/missing record(s)."
        }
        else {
            $status = "pass"
            $summary = "Mail DNS audit for '$cleanDomain' (DNS: $serverLabel) passed all $($results.Count) record check(s)."
        }
    }

    if ($results.Count -gt 0) {
        $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
        Write-Output $tableOutput.Trim()
        Write-Output ""
    }
}
catch {
    $status = "error"
    $summary = "Mail DNS audit failed: $($_.Exception.Message)"
    $errors.Add($_.Exception.Message)
}
finally {
    $payload = @{
        status  = $status
        summary = $summary
        data    = @($results)
        errors  = @($errors)
    }
    $payload | ConvertTo-Json -Depth 4 -Compress
}
