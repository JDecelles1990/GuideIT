<#
.SYNOPSIS
    Inspects Windows DHCP Server scopes/utilization, DNS Server forwarders, and related event errors (1020, 1342, 4013) with clean workstation fallback.
.PSSTORE_META
    {
        "title": "Get Windows DHCP & DNS Server Health",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 35,
        "output_mode": "json",
        "params": [
            {"name": "ScopeUtilizationWarnPercent", "type": "int", "default": 85, "min": 50, "max": 99},
            {"name": "HoursBack", "type": "int", "default": 24, "min": 1, "max": 168}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [int]$ScopeUtilizationWarnPercent = 85,

    [Parameter(Mandatory = $false)]
    [int]$HoursBack = 24
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

try {
    $ScopeUtilizationWarnPercent = [math]::Max(50, [math]::Min(99, $ScopeUtilizationWarnPercent))
    $HoursBack = [math]::Max(1, [math]::Min(168, $HoursBack))
    $startTime = (Get-Date).AddHours(-$HoursBack)
    $warnCount = 0

    # 1. DHCP Server Role & Scopes
    $dhcpSvc = Get-Service -Name "DHCPServer" -ErrorAction SilentlyContinue
    if ($null -eq $dhcpSvc) {
        $results.Add([PSCustomObject]@{
            Component = "DHCPServer"
            ItemName  = "DHCPServer Service"
            Status    = "NotInstalled"
            Metric    = "N/A"
            Detail    = "DHCP Server role is not installed on this machine."
        })
    }
    else {
        $dhcpHealthy = ($dhcpSvc.Status -eq 'Running')
        if (-not $dhcpHealthy) { $warnCount++ }
        $results.Add([PSCustomObject]@{
            Component = "DHCPServer"
            ItemName  = "DHCPServer Service"
            Status    = if ($dhcpHealthy) { "Running" } else { [string]$dhcpSvc.Status }
            Metric    = [string]$dhcpSvc.StartType
            Detail    = "Windows DHCP Server service status"
        })

        if ($dhcpHealthy -and (Get-Command -Name "Get-DhcpServerv4Scope" -ErrorAction SilentlyContinue)) {
            try {
                $scopes = @(Get-DhcpServerv4Scope -ErrorAction Stop)
                $statsByScope = @{}
                if (Get-Command -Name "Get-DhcpServerv4ScopeStatistics" -ErrorAction SilentlyContinue) {
                    try {
                        foreach ($st in @(Get-DhcpServerv4ScopeStatistics -ErrorAction Stop)) {
                            $statsByScope[[string]$st.ScopeId] = $st
                        }
                    }
                    catch {
                        $errors.Add("DHCP scope statistics warning: $($_.Exception.Message)")
                    }
                }

                foreach ($sc in $scopes) {
                    $sid = [string]$sc.ScopeId
                    $stat = $statsByScope[$sid]
                    $pct = if ($null -ne $stat) { [math]::Round([double]$stat.PercentageInUse, 1) } else { 0.0 }
                    $free = if ($null -ne $stat) { [int]$stat.Free } else { 0 }
                    $inUse = if ($null -ne $stat) { [int]$stat.InUse } else { 0 }
                    $scStatus = if ($sc.State -ne 'Active') { "Inactive" } elseif ($pct -ge $ScopeUtilizationWarnPercent) { "Warning_HighUtil" } else { "Healthy" }
                    if ($scStatus -eq "Warning_HighUtil") { $warnCount++ }

                    $results.Add([PSCustomObject]@{
                        Component = "DHCPScope"
                        ItemName  = "$($sc.Name) ($sid)"
                        Status    = $scStatus
                        Metric    = "${pct}% used"
                        Detail    = "State=$($sc.State) | InUse=$inUse | Free=$free | WarnAt=${ScopeUtilizationWarnPercent}%"
                    })
                }
            }
            catch {
                $warnCount++
                $errors.Add("DHCP scope query notice: $($_.Exception.Message)")
            }
        }
    }

    # 2. DNS Server Role & Forwarders
    $dnsSvc = Get-Service -Name "DNS" -ErrorAction SilentlyContinue
    if ($null -eq $dnsSvc) {
        $results.Add([PSCustomObject]@{
            Component = "DNSServer"
            ItemName  = "DNS Service"
            Status    = "NotInstalled"
            Metric    = "N/A"
            Detail    = "Windows DNS Server role is not installed on this machine."
        })
    }
    else {
        $dnsHealthy = ($dnsSvc.Status -eq 'Running')
        if (-not $dnsHealthy) { $warnCount++ }
        $results.Add([PSCustomObject]@{
            Component = "DNSServer"
            ItemName  = "DNS Service"
            Status    = if ($dnsHealthy) { "Running" } else { [string]$dnsSvc.Status }
            Metric    = [string]$dnsSvc.StartType
            Detail    = "Windows DNS Server service status"
        })

        if ($dnsHealthy -and (Get-Command -Name "Get-DnsServerForwarder" -ErrorAction SilentlyContinue)) {
            try {
                $fwd = Get-DnsServerForwarder -ErrorAction Stop
                $ipList = @($fwd.IPAddress | ForEach-Object { [string]$_ })
                $results.Add([PSCustomObject]@{
                    Component = "DNSForwarders"
                    ItemName  = "ConfiguredForwarders"
                    Status    = if ($ipList.Count -gt 0) { "Configured" } else { "RootHintsOnly" }
                    Metric    = "$($ipList.Count) server(s)"
                    Detail    = if ($ipList.Count -gt 0) { ($ipList -join ", ") } else { "No forwarders configured (using Root Hints)" }
                })
            }
            catch {
                $warnCount++
                $errors.Add("DNS forwarder query notice: $($_.Exception.Message)")
            }
        }
    }

    # 3. DHCP / DNS Critical Event Check (1020, 1342, 4013) when either role exists
    if ($null -ne $dhcpSvc -or $null -ne $dnsSvc) {
        $logQueries = @(
            @{ LogName = 'System'; Ids = @(1020, 1342) },
            @{ LogName = 'DNS Server'; Ids = @(4013, 4015) },
            @{ LogName = 'Microsoft-Windows-DHCP-Server/Operational'; Ids = @(1020, 1342) }
        )
        foreach ($lq in $logQueries) {
            try {
                $evts = @(Get-WinEvent -FilterHashtable @{
                    LogName   = $lq.LogName
                    Id        = $lq.Ids
                    StartTime = $startTime
                } -MaxEvents 10 -ErrorAction Stop)
                foreach ($evt in $evts) {
                    $warnCount++
                    $msg = ($evt.Message -replace '\s+', ' ').Trim()
                    if ($msg.Length -gt 120) { $msg = $msg.Substring(0, 117) + "..." }
                    $results.Add([PSCustomObject]@{
                        Component = "RoleEvent"
                        ItemName  = "$($lq.LogName) [$($evt.Id)]"
                        Status    = "Warning"
                        Metric    = $evt.TimeCreated.ToString("yyyy-MM-dd HH:mm")
                        Detail    = $msg
                    })
                }
            }
            catch {
                # Ignore missing logs or NoMatchingEventsFound on non-role hosts
            }
        }
    }

    $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
    Write-Output $tableOutput.Trim()
    Write-Output ""

    if ($warnCount -gt 0) {
        $status = "warning"
        $summary = "DHCP/DNS server audit completed with $warnCount warning(s)."
    }
    else {
        $status = "pass"
        $summary = "DHCP/DNS server audit completed cleanly ($($results.Count) check(s))."
    }
}
catch {
    $status = "error"
    $summary = "Failed to inspect DHCP/DNS server health: $($_.Exception.Message)"
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
