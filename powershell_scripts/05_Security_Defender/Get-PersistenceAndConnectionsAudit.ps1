<#
.SYNOPSIS
    Audits Windows Run/Startup persistence entries, non-Microsoft Scheduled Tasks, and active non-loopback outbound TCP connections.
.PSSTORE_META
    {
        "title": "Audit Endpoint Persistence (Run Keys/Tasks) & Active Outbound Connections",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 35,
        "output_mode": "json",
        "params": [
            {"name": "IncludeScheduledTasks", "type": "bool", "default": true},
            {"name": "IncludeOutboundConnections", "type": "bool", "default": true},
            {"name": "MaxConnections", "type": "int", "default": 25, "min": 5, "max": 200}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [bool]$IncludeScheduledTasks = $true,

    [Parameter(Mandatory = $false)]
    [bool]$IncludeOutboundConnections = $true,

    [Parameter(Mandatory = $false)]
    [int]$MaxConnections = 25
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

function Test-SuspiciousCommandTarget {
    param([string]$CommandText)
    if ([string]::IsNullOrWhiteSpace($CommandText)) { return $false }
    $pat = '(\\AppData\\Local\\Temp\\|\\Users\\Public\\|\\ProgramData\\[^\\]+\.(vbs|js|ps1|bat|exe)|\b(powershell|pwsh|mshta|wscript|cscript)\b|\s-enc\s|cmd\.exe\s+/c)'
    return ($CommandText -match $pat)
}

try {
    $MaxConnections = [math]::Max(5, [math]::Min(200, $MaxConnections))
    $suspiciousCount = 0

    # 1. Registry Run & RunOnce Keys
    try {
        $runPaths = @(
            "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
            "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
            "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
            "HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
            "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
        )
        foreach ($rk in $runPaths) {
            if (-not (Test-Path -Path $rk)) { continue }
            $item = Get-Item -Path $rk -ErrorAction SilentlyContinue
            if (-not $item) { continue }
            $props = Get-ItemProperty -Path $rk -ErrorAction SilentlyContinue
            foreach ($valName in $item.GetValueNames()) {
                $target = [string]$props.$valName
                $isSuspect = Test-SuspiciousCommandTarget -CommandText $target
                if ($isSuspect) { $suspiciousCount++ }
                $results.Add([PSCustomObject]@{
                    Category = "RegistryRun"
                    Name     = [string]$valName
                    Target   = $target
                    Status   = if ($isSuspect) { "Review" } else { "OK" }
                    Details  = $rk
                })
            }
        }
    }
    catch {
        $errors.Add("Registry Run audit note: $($_.Exception.Message)")
    }

    # 2. Startup Folder Shortcuts & Scripts
    try {
        $startupFolders = @(
            (Join-Path -Path $env:APPDATA -ChildPath "Microsoft\Windows\Start Menu\Programs\Startup"),
            (Join-Path -Path $env:ProgramData -ChildPath "Microsoft\Windows\Start Menu\Programs\Startup")
        )
        foreach ($sf in $startupFolders) {
            if (-not (Test-Path -Path $sf)) { continue }
            $files = @(Get-ChildItem -Path $sf -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'desktop.ini' })
            foreach ($f in $files) {
                $isSuspect = ($f.Extension -in @('.vbs', '.js', '.ps1', '.bat', '.cmd', '.hta'))
                if ($isSuspect) { $suspiciousCount++ }
                $results.Add([PSCustomObject]@{
                    Category = "StartupFolder"
                    Name     = [string]$f.Name
                    Target   = [string]$f.FullName
                    Status   = if ($isSuspect) { "Review" } else { "OK" }
                    Details  = "Modified=$($f.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))"
                })
            }
        }
    }
    catch {
        $errors.Add("Startup folder audit note: $($_.Exception.Message)")
    }

    # 3. Optional Non-Microsoft Scheduled Tasks
    if ($IncludeScheduledTasks) {
        $tasksLoaded = $false
        try {
            $tasks = @(Get-ScheduledTask -ErrorAction Stop | Where-Object { $_.TaskPath -notlike '\Microsoft\*' -and $_.State -ne 'Disabled' } | Select-Object -First 40)
            foreach ($t in $tasks) {
                $actionCmd = (@($t.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)".Trim() }) -join " | ")
                $isSuspect = Test-SuspiciousCommandTarget -CommandText $actionCmd
                if ($isSuspect) { $suspiciousCount++ }
                $results.Add([PSCustomObject]@{
                    Category = "ScheduledTask"
                    Name     = [string]$t.TaskName
                    Target   = if ($actionCmd) { $actionCmd } else { "(non-exec action)" }
                    Status   = if ($isSuspect) { "Review" } else { [string]$t.State }
                    Details  = "Path=$($t.TaskPath)"
                })
            }
            $tasksLoaded = $true
        }
        catch {
            $tasksLoaded = $false
        }

        if (-not $tasksLoaded) {
            try {
                $csvLines = @(& schtasks.exe /Query /FO CSV /NH 2>$null | Where-Object { $_ -and $_ -notmatch '^"\\Microsoft\\' } | Select-Object -First 30)
                foreach ($line in $csvLines) {
                    $cols = $line -split '","'
                    if ($cols.Count -ge 3) {
                        $tName = $cols[0].Trim('"')
                        $tState = $cols[2].Trim('"')
                        $results.Add([PSCustomObject]@{
                            Category = "ScheduledTask"
                            Name     = $tName
                            Target   = "(schtasks summary)"
                            Status   = $tState
                            Details  = "Source=schtasks fallback"
                        })
                    }
                }
                $tasksLoaded = ($csvLines.Count -gt 0)
            }
            catch {
                $tasksLoaded = $false
            }
        }

        if (-not $tasksLoaded) {
            try {
                $treePath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\Tree"
                if (Test-Path -Path $treePath) {
                    $rootItems = @(Get-ChildItem -Path $treePath -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -ne 'Microsoft' } | Select-Object -First 25)
                    foreach ($ri in $rootItems) {
                        $results.Add([PSCustomObject]@{
                            Category = "ScheduledTask"
                            Name     = [string]$ri.PSChildName
                            Target   = "(TaskCache tree entry)"
                            Status   = "Registered"
                            Details  = "Source=RegistryFallback"
                        })
                    }
                }
            }
            catch {
                $errors.Add("Scheduled tasks enumeration skipped: $($_.Exception.Message)")
            }
        }
    }

    # 4. Optional Established Non-Loopback Outbound TCP Connections
    if ($IncludeOutboundConnections) {
        $procMap = @{}
        try {
            foreach ($p in @(Get-Process -ErrorAction SilentlyContinue)) {
                $procMap[[int]$p.Id] = $p
            }
        }
        catch {
            $procMap = @{}
        }

        $connLoaded = $false
        try {
            $conns = @(
                Get-NetTCPConnection -State Established -ErrorAction Stop |
                    Where-Object { $_.RemoteAddress -notin @('127.0.0.1', '::1', '0.0.0.0', '::') } |
                    Select-Object -First $MaxConnections
            )
            foreach ($c in $conns) {
                $procObj = if ($procMap.ContainsKey([int]$c.OwningProcess)) { $procMap[[int]$c.OwningProcess] } else { $null }
                $pName = if ($procObj) { [string]$procObj.ProcessName } else { "PID:$($c.OwningProcess)" }
                $pPath = ""
                if ($procObj) {
                    try { $pPath = [string]$procObj.Path } catch { $pPath = "" }
                }
                $isSuspect = ($pPath -match '(\\AppData\\Local\\Temp\\|\\Users\\Public\\)')
                if ($isSuspect) { $suspiciousCount++ }
                $results.Add([PSCustomObject]@{
                    Category = "OutboundTCP"
                    Name     = "$pName ($($c.OwningProcess))"
                    Target   = "$($c.RemoteAddress):$($c.RemotePort)"
                    Status   = if ($isSuspect) { "Review" } else { "Established" }
                    Details  = "Local=$($c.LocalAddress):$($c.LocalPort); Path=$(if ($pPath) { $pPath } else { 'N/A' })"
                })
            }
            $connLoaded = $true
        }
        catch {
            $connLoaded = $false
        }

        if (-not $connLoaded) {
            try {
                $active = @(
                    [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpConnections() |
                        Where-Object {
                            $_.State -eq 'Established' -and
                            $_.RemoteEndPoint.Address.ToString() -notin @('127.0.0.1', '::1')
                        } |
                        Select-Object -First $MaxConnections
                )
                foreach ($c in $active) {
                    $results.Add([PSCustomObject]@{
                        Category = "OutboundTCP"
                        Name     = "TCPConnection"
                        Target   = "$($c.RemoteEndPoint.Address):$($c.RemoteEndPoint.Port)"
                        Status   = "Established"
                        Details  = "Local=$($c.LocalEndPoint.Address):$($c.LocalEndPoint.Port); Source=.NET Fallback"
                    })
                }
            }
            catch {
                $errors.Add("Outbound connection scan skipped: $($_.Exception.Message)")
            }
        }
    }

    if ($results.Count -gt 0) {
        $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
        Write-Output $tableOutput.Trim()
        Write-Output ""
    }
    else {
        Write-Output "No matching persistence entries or active outbound connections were found."
    }

    if ($suspiciousCount -gt 0) {
        $status = "warning"
        $summary = "Audited $($results.Count) persistence/connection item(s): $suspiciousCount item(s) flagged for Review."
    }
    else {
        $status = "pass"
        $summary = "Audited $($results.Count) persistence/connection item(s): no suspicious temp/script indicators found."
    }
}
catch {
    $status = "error"
    $summary = "Persistence and connections audit failed: $($_.Exception.Message)"
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
