<#
.SYNOPSIS
    Audits Automatic/Delayed-Auto Windows services that are currently stopped and queries recent Service Control Manager errors.
.PSSTORE_META
    {
        "title": "Audit Stopped Automatic Services & SCM Errors",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 30,
        "output_mode": "json",
        "params": [
            {"name": "IncludeDelayedAuto", "type": "bool", "default": true},
            {"name": "IncludeTriggerStart", "type": "bool", "default": false},
            {"name": "HoursBack", "type": "int", "default": 24, "min": 1, "max": 168},
            {"name": "MaxEvents", "type": "int", "default": 20, "min": 5, "max": 100}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [bool]$IncludeDelayedAuto = $true,

    [Parameter(Mandatory = $false)]
    [bool]$IncludeTriggerStart = $false,

    [Parameter(Mandatory = $false)]
    [int]$HoursBack = 24,

    [Parameter(Mandatory = $false)]
    [int]$MaxEvents = 20
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

try {
    $HoursBack = [math]::Max(1, [math]::Min(168, $HoursBack))
    $MaxEvents = [math]::Max(5, [math]::Min(100, $MaxEvents))

    # 1. Stopped Automatic Services (CIM/WMI with Get-Service + Registry fallback)
    $stoppedServices = [System.Collections.Generic.List[PSObject]]::new()
    $usedCimServices = $false
    try {
        $cimServices = @(Get-CimInstance -ClassName Win32_Service -Filter "StartMode = 'Auto' AND State <> 'Running'" -ErrorAction Stop)
        foreach ($svc in $cimServices) {
            $stoppedServices.Add([PSCustomObject]@{
                Name                    = [string]$svc.Name
                DisplayName             = [string]$svc.DisplayName
                State                   = [string]$svc.State
                ExitCode                = [string]$svc.ExitCode
                ServiceSpecificExitCode = [string]$svc.ServiceSpecificExitCode
            })
        }
        $usedCimServices = $true
    }
    catch {
        try {
            $wmiServices = @(Get-WmiObject -Class Win32_Service -Filter "StartMode = 'Auto' AND State <> 'Running'" -ErrorAction Stop)
            foreach ($svc in $wmiServices) {
                $stoppedServices.Add([PSCustomObject]@{
                    Name                    = [string]$svc.Name
                    DisplayName             = [string]$svc.DisplayName
                    State                   = [string]$svc.State
                    ExitCode                = [string]$svc.ExitCode
                    ServiceSpecificExitCode = [string]$svc.ServiceSpecificExitCode
                })
            }
            $usedCimServices = $true
        }
        catch {
            $usedCimServices = $false
        }
    }

    if (-not $usedCimServices) {
        try {
            $allSvcs = @(Get-Service -ErrorAction Stop | Where-Object { $_.Status -ne 'Running' })
            foreach ($svc in $allSvcs) {
                $regPath = "HKLM:\SYSTEM\CurrentControlSet\Services\$($svc.Name)"
                try {
                    if (Test-Path -Path $regPath) {
                        $props = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
                        if ($null -ne $props -and $props.Start -eq 2) {
                            $stoppedServices.Add([PSCustomObject]@{
                                Name                    = [string]$svc.Name
                                DisplayName             = [string]$svc.DisplayName
                                State                   = [string]$svc.Status
                                ExitCode                = "N/A"
                                ServiceSpecificExitCode = "RegistryFallback"
                            })
                        }
                    }
                }
                catch {}
            }
        }
        catch {
            $errors.Add("Service enumeration notice: $($_.Exception.Message)")
            $results.Add([PSCustomObject]@{
                RecordType     = "ServiceAudit"
                Name           = "Service Control Manager"
                StateOrEventID = "AccessDenied"
                StartMode      = "Unavailable"
                Timestamp      = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
                Detail         = $_.Exception.Message
            })
        }
    }

    $stoppedAutoCount = 0
    foreach ($svc in $stoppedServices) {
        $svcName = [string]$svc.Name
        $regPath = "HKLM:\SYSTEM\CurrentControlSet\Services\$svcName"
        $isDelayed = $false
        $hasTrigger = $false

        try {
            if (Test-Path -Path $regPath) {
                $props = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
                if ($null -ne $props -and $props.DelayedAutostart -eq 1) {
                    $isDelayed = $true
                }
                if (Test-Path -Path (Join-Path -Path $regPath -ChildPath "TriggerInfo")) {
                    $hasTrigger = $true
                }
            }
        }
        catch {
            # Ignore per-service registry read anomalies
        }

        if ($isDelayed -and -not $IncludeDelayedAuto) { continue }
        if ($hasTrigger -and -not $IncludeTriggerStart) { continue }

        $startLabel = if ($isDelayed) { "Automatic (Delayed)" } else { "Automatic" }
        if ($hasTrigger) { $startLabel = "$startLabel / Trigger" }

        $stoppedAutoCount++
        $results.Add([PSCustomObject]@{
            RecordType     = "StoppedService"
            Name           = "$($svc.DisplayName) ($svcName)"
            StateOrEventID = [string]$svc.State
            StartMode      = $startLabel
            Timestamp      = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
            Detail         = "ExitCode=$($svc.ExitCode) | ServiceSpecific=$($svc.ServiceSpecificExitCode)"
        })
    }

    # 2. Recent Service Control Manager Errors (System log)
    $scmEventIds = @(7000, 7001, 7009, 7023, 7024, 7031, 7034)
    $startTime = (Get-Date).AddHours(-$HoursBack)
    $scmEvents = @()
    try {
        $scmEvents = @(Get-WinEvent -FilterHashtable @{
            LogName      = 'System'
            ProviderName = 'Service Control Manager'
            Id           = $scmEventIds
            StartTime    = $startTime
        } -MaxEvents $MaxEvents -ErrorAction Stop)
    }
    catch {
        if ($_.FullyQualifiedErrorId -notmatch 'NoMatchingEventsFound') {
            $errors.Add("SCM event query warning: $($_.Exception.Message)")
        }
    }

    $scmCount = 0
    foreach ($evt in $scmEvents) {
        $scmCount++
        $cleanMsg = ($evt.Message -replace '\s+', ' ').Trim()
        if ($cleanMsg.Length -gt 140) {
            $cleanMsg = $cleanMsg.Substring(0, 137) + "..."
        }
        $results.Add([PSCustomObject]@{
            RecordType     = "SCMEvent"
            Name           = "Service Control Manager"
            StateOrEventID = [string]$evt.Id
            StartMode      = "EventLog"
            Timestamp      = $evt.TimeCreated.ToString("yyyy-MM-dd HH:mm:ss")
            Detail         = if ($cleanMsg) { $cleanMsg } else { "(No event message)" }
        })
    }

    if ($results.Count -eq 0) {
        $status = "pass"
        $summary = "All matching Automatic services are running and 0 SCM errors were logged in the past $HoursBack hour(s)."
        Write-Output $summary
    }
    else {
        $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
        Write-Output $tableOutput.Trim()
        Write-Output ""

        $status = "warning"
        $summary = "Found $stoppedAutoCount stopped Automatic service(s) and $scmCount SCM error event(s) in the past $HoursBack hour(s)."
    }
}
catch {
    $status = "error"
    $summary = "Failed to audit Automatic services and SCM errors: $($_.Exception.Message)"
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
