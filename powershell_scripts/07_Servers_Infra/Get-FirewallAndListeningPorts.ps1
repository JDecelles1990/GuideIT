<#
.SYNOPSIS
    Audits Windows Firewall profile states alongside active TCP listening ports mapped to owning processes and matching inbound Allow rules.
.PSSTORE_META
    {
        "title": "Get Firewall Profiles & Listening TCP Ports Matrix",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 30,
        "output_mode": "json",
        "params": [
            {"name": "PortFilter", "type": "int", "default": 0, "min": 0, "max": 65535},
            {"name": "IncludeLoopback", "type": "bool", "default": false},
            {"name": "CheckInboundRules", "type": "bool", "default": true}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [int]$PortFilter = 0,

    [Parameter(Mandatory = $false)]
    [bool]$IncludeLoopback = $false,

    [Parameter(Mandatory = $false)]
    [bool]$CheckInboundRules = $true
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

try {
    $PortFilter = [math]::Max(0, [math]::Min(65535, $PortFilter))
    $warnCount = 0

    # 1. Windows Firewall Profile States (NetSecurity cmdlet with HKLM fallback)
    $fwLoaded = $false
    try {
        $profiles = @(Get-NetFirewallProfile -ErrorAction Stop)
        foreach ($p in $profiles) {
            $enabled = [bool]$p.Enabled
            if (-not $enabled) { $warnCount++ }
            $results.Add([PSCustomObject]@{
                RecordType        = "FirewallProfile"
                ProfileOrAddress  = [string]$p.Name
                Port              = 0
                ProcessOrAction   = "In:$($p.DefaultInboundAction) Out:$($p.DefaultOutboundAction)"
                PID               = 0
                FirewallRuleMatch = "Profile"
                Status            = if ($enabled) { "Enabled" } else { "Disabled" }
            })
        }
        $fwLoaded = ($profiles.Count -gt 0)
    }
    catch {
        $fwLoaded = $false
    }

    if (-not $fwLoaded) {
        $regRoot = "HKLM:\SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy"
        $map = @{ "DomainProfile" = "Domain"; "StandardProfile" = "Private"; "PublicProfile" = "Public" }
        foreach ($kv in $map.GetEnumerator()) {
            $pKey = Join-Path -Path $regRoot -ChildPath $kv.Key
            if (Test-Path -Path $pKey) {
                $props = Get-ItemProperty -Path $pKey -ErrorAction SilentlyContinue
                $enabled = ($props.EnableFirewall -eq 1 -or $props.EnableFirewall -eq "1")
                if (-not $enabled) { $warnCount++ }
                $results.Add([PSCustomObject]@{
                    RecordType        = "FirewallProfile"
                    ProfileOrAddress  = $kv.Value
                    Port              = 0
                    ProcessOrAction   = "RegistryFallback"
                    PID               = 0
                    FirewallRuleMatch = "Profile"
                    Status            = if ($enabled) { "Enabled" } else { "Disabled" }
                })
            }
        }
    }

    # 2. Optional Enabled Inbound Allow TCP Port Rules Lookup
    $allowedPortsMap = @{}
    $rulesScanned = $false
    if ($CheckInboundRules) {
        try {
            $allowRules = @(Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -ErrorAction Stop)
            if ($allowRules.Count -gt 0) {
                $portFilters = @($allowRules | Get-NetFirewallPortFilter -ErrorAction Stop)
                foreach ($pf in $portFilters) {
                    if ($pf.Protocol -notin @('TCP', 'Any')) { continue }
                    foreach ($lp in @($pf.LocalPort)) {
                        $lpStr = [string]$lp
                        if ($lpStr -eq 'Any') {
                            $allowedPortsMap['Any'] = $true
                        }
                        elseif ($lpStr -match '^(\d+)$') {
                            $allowedPortsMap[[int]$Matches[1]] = $true
                        }
                        elseif ($lpStr -match '^(\d+)-(\d+)$') {
                            $lo = [int]$Matches[1]
                            $hi = [int]$Matches[2]
                            if (($hi - $lo) -le 500) {
                                for ($n = $lo; $n -le $hi; $n++) { $allowedPortsMap[$n] = $true }
                            }
                        }
                    }
                }
                $rulesScanned = $true
            }
        }
        catch {
            $errors.Add("Inbound firewall rule scan skipped: $($_.Exception.Message)")
        }
    }

    # 3. Listening TCP Ports Mapped to Owning Process
    $procNames = @{}
    Get-Process -ErrorAction SilentlyContinue | ForEach-Object { $procNames[$_.Id] = $_.ProcessName }

    $tcpEntries = [System.Collections.Generic.List[PSObject]]::new()
    $usedNetTcp = $false
    try {
        $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Sort-Object LocalPort, LocalAddress)
        foreach ($tcp in $listeners) {
            $addr = [string]$tcp.LocalAddress
            $port = [int]$tcp.LocalPort
            if ($PortFilter -gt 0 -and $port -ne $PortFilter) { continue }
            if (-not $IncludeLoopback -and ($addr -eq '127.0.0.1' -or $addr -eq '::1')) { continue }

            $procId = [int]$tcp.OwningProcess
            $pName = if ($procNames.ContainsKey($procId)) { $procNames[$procId] } else { "PID_$procId" }
            $ruleMatch = "NotChecked"
            if ($CheckInboundRules) {
                if (-not $rulesScanned) {
                    $ruleMatch = "Unavailable"
                }
                elseif ($addr -eq '127.0.0.1' -or $addr -eq '::1') {
                    $ruleMatch = "LoopbackOnly"
                }
                elseif ($allowedPortsMap.ContainsKey($port) -or $allowedPortsMap.ContainsKey('Any')) {
                    $ruleMatch = "InboundAllowRule"
                }
                else {
                    $ruleMatch = "NoExplicitAllow"
                }
            }

            $tcpEntries.Add([PSCustomObject]@{
                RecordType        = "ListeningTCP"
                ProfileOrAddress  = $addr
                Port              = $port
                ProcessOrAction   = $pName
                PID               = $procId
                FirewallRuleMatch = $ruleMatch
                Status            = "Listening"
            })
        }
        $usedNetTcp = $true
    }
    catch {
        $usedNetTcp = $false
    }

    if (-not $usedNetTcp) {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $netLines = @(& netstat.exe -ano 2>$null)
        $ErrorActionPreference = $prev
        foreach ($line in $netLines) {
            $trimmed = $line.Trim()
            if ($trimmed -match '^TCP\s+(\S+):(\d+)\s+\S+\s+LISTENING\s+(\d+)$') {
                $addr = $Matches[1].Trim('[]')
                $port = [int]$Matches[2]
                $procId = [int]$Matches[3]
                if ($PortFilter -gt 0 -and $port -ne $PortFilter) { continue }
                if (-not $IncludeLoopback -and ($addr -eq '127.0.0.1' -or $addr -eq '::1')) { continue }
                $pName = if ($procNames.ContainsKey($procId)) { $procNames[$procId] } else { "PID_$procId" }
                $tcpEntries.Add([PSCustomObject]@{
                    RecordType        = "ListeningTCP"
                    ProfileOrAddress  = $addr
                    Port              = $port
                    ProcessOrAction   = $pName
                    PID               = $procId
                    FirewallRuleMatch = "NetstatFallback"
                    Status            = "Listening"
                })
            }
        }
    }

    foreach ($entry in $tcpEntries) {
        $results.Add($entry)
    }

    $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
    Write-Output $tableOutput.Trim()
    Write-Output ""

    if ($warnCount -gt 0) {
        $status = "warning"
        $summary = "Firewall & ports matrix: $warnCount disabled firewall profile(s); $($tcpEntries.Count) listening TCP socket(s) matched."
    }
    else {
        $status = "pass"
        $summary = "Firewall & ports matrix: all firewall profiles enabled; $($tcpEntries.Count) listening TCP socket(s) audited."
    }
}
catch {
    $status = "error"
    $summary = "Failed to inspect firewall and listening ports: $($_.Exception.Message)"
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
