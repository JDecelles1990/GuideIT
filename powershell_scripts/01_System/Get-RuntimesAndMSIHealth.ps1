<#
.SYNOPSIS
    Audits installed .NET Framework/Desktop Runtimes, Visual C++ Redistributables, Java JRE/JDK, Windows Installer (MSI) lock/errors, and accounting LOB database services.
.PSSTORE_META
    {
        "title": "Audit .NET/Java/VC++ Runtimes, Windows Installer (MSI) & Accounting LOB Services",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 35,
        "output_mode": "json",
        "params": [
            {"name": "IncludeLOBServices", "type": "bool", "default": true},
            {"name": "HoursBack", "type": "int", "default": 72, "min": 1, "max": 720},
            {"name": "MaxEvents", "type": "int", "default": 20, "min": 5, "max": 100}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [bool]$IncludeLOBServices = $true,

    [Parameter(Mandatory = $false)]
    [int]$HoursBack = 72,

    [Parameter(Mandatory = $false)]
    [int]$MaxEvents = 20
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

try {
    $HoursBack = [math]::Max(1, [math]::Min(720, $HoursBack))
    $MaxEvents = [math]::Max(5, [math]::Min(100, $MaxEvents))
    $warnCount = 0

    # 1. .NET Framework 4.x Release
    $ndpKey = "HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"
    if (Test-Path -Path $ndpKey) {
        $ndp = Get-ItemProperty -Path $ndpKey -ErrorAction SilentlyContinue
        $rel = if ($null -ne $ndp.Release) { [int]$ndp.Release } else { 0 }
        $netVer = switch ($true) {
            ($rel -ge 533320) { "4.8.1 ($rel)"; break }
            ($rel -ge 528040) { "4.8 ($rel)"; break }
            ($rel -ge 461808) { "4.7.2 ($rel)"; break }
            ($rel -ge 461308) { "4.7.1 ($rel)"; break }
            ($rel -ge 394802) { "4.6.2 ($rel)"; break }
            default { "Release $rel" }
        }
        $results.Add([PSCustomObject]@{
            Category       = "DotNetFramework"
            Component      = ".NET Framework 4.x"
            VersionOrState = $netVer
            Status         = if ($rel -ge 461808) { "Installed" } else { "Outdated" }
            Details        = "RegistryRelease=$rel"
        })
        if ($rel -lt 461808) { $warnCount++ }
    }

    # 2. .NET Desktop Runtime (x64 & x86)
    foreach ($archLabel in @(
        @{ Arch = "x64"; Root = "$env:ProgramFiles\dotnet\shared\Microsoft.WindowsDesktop.App" },
        @{ Arch = "x86"; Root = "${env:ProgramFiles(x86)}\dotnet\shared\Microsoft.WindowsDesktop.App" }
    )) {
        if ($archLabel.Root -and (Test-Path -Path $archLabel.Root)) {
            $vers = @(Get-ChildItem -Path $archLabel.Root -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name | Sort-Object)
            if ($vers.Count -gt 0) {
                $results.Add([PSCustomObject]@{
                    Category       = "DotNetDesktop"
                    Component      = ".NET Desktop Runtime ($($archLabel.Arch))"
                    VersionOrState = ($vers -join "; ")
                    Status         = "Installed"
                    Details        = "Path=$($archLabel.Root)"
                })
            }
        }
    }

    # 3. Visual C++ Redistributables (x64 & x86)
    $vcList = [System.Collections.Generic.List[string]]::new()
    foreach ($uninstPath in @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )) {
        $vcItems = @(Get-ItemProperty -Path $uninstPath -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -like "Microsoft Visual C++*Redistributable*" })
        foreach ($vc in $vcItems) {
            $entry = "$($vc.DisplayName) ($($vc.DisplayVersion))"
            if (-not $vcList.Contains($entry)) {
                $vcList.Add($entry)
                $results.Add([PSCustomObject]@{
                    Category       = "VisualCppRedist"
                    Component      = [string]$vc.DisplayName
                    VersionOrState = [string]$vc.DisplayVersion
                    Status         = "Installed"
                    Details        = if ($vc.DisplayName -match 'x86') { "Architecture=x86" } elseif ($vc.DisplayName -match 'x64') { "Architecture=x64" } else { "Architecture=Other" }
                })
            }
        }
    }
    if ($vcList.Count -eq 0) {
        $warnCount++
        $results.Add([PSCustomObject]@{
            Category       = "VisualCppRedist"
            Component      = "Visual C++ Redistributable"
            VersionOrState = "None"
            Status         = "Missing"
            Details        = "No Visual C++ Redistributable entries found in Uninstall registry"
        })
    }

    # 4. Java JRE / JDK Inventory
    $javaFound = $false
    foreach ($jKey in @(
        "HKLM:\SOFTWARE\JavaSoft\Java Runtime Environment",
        "HKLM:\SOFTWARE\WOW6432Node\JavaSoft\Java Runtime Environment",
        "HKLM:\SOFTWARE\JavaSoft\JDK",
        "HKLM:\SOFTWARE\Eclipse Adoptium\JRE",
        "HKLM:\SOFTWARE\Eclipse Adoptium\JDK"
    )) {
        if (Test-Path -Path $jKey) {
            $jp = Get-ItemProperty -Path $jKey -ErrorAction SilentlyContinue
            $jVer = if ($jp.CurrentVersion) { [string]$jp.CurrentVersion } else { "Present" }
            $results.Add([PSCustomObject]@{
                Category       = "JavaRuntime"
                Component      = (Split-Path -Path $jKey -Leaf)
                VersionOrState = $jVer
                Status         = "Installed"
                Details        = $jKey
            })
            $javaFound = $true
        }
    }
    $javaExe = Get-Command -Name "java.exe" -ErrorAction SilentlyContinue
    if ($javaExe) {
        $results.Add([PSCustomObject]@{
            Category       = "JavaRuntime"
            Component      = "java.exe (PATH)"
            VersionOrState = "Available"
            Status         = "Installed"
            Details        = [string]$javaExe.Source
        })
        $javaFound = $true
    }
    if (-not $javaFound) {
        $results.Add([PSCustomObject]@{
            Category       = "JavaRuntime"
            Component      = "Java JRE/JDK"
            VersionOrState = "NotInstalled"
            Status         = "Info"
            Details        = "No system JavaSoft/Adoptium runtime or java.exe on PATH"
        })
    }

    # 5. Windows Installer Service, Active MSI Lock & Pending Reboot Check
    $msiStateStr = "Unknown"
    $msiDisabled = $false
    try {
        $msiSvc = Get-Service -Name "msiserver" -ErrorAction Stop
        if ($msiSvc) {
            $msiStateStr = "$($msiSvc.Status) / $($msiSvc.StartType)"
            $msiDisabled = ($msiSvc.StartType -eq 'Disabled')
        }
    }
    catch {
        $msiReg = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\msiserver" -ErrorAction SilentlyContinue
        if ($msiReg) {
            $startNum = [int]$msiReg.Start
            $startLbl = switch ($startNum) { 2 { "Auto" } 3 { "Manual" } 4 { "Disabled" } default { "Start=$startNum" } }
            $msiStateStr = "RegistryFallback ($startLbl)"
            $msiDisabled = ($startNum -eq 4)
        }
    }

    $msiInProgress = Test-Path -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\InProgress"
    $wuReboot = Test-Path -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
    $cbsReboot = Test-Path -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"
    $msiBlocked = ($msiInProgress -or $wuReboot -or $cbsReboot -or $msiDisabled)
    if ($msiBlocked) { $warnCount++ }
    $results.Add([PSCustomObject]@{
        Category       = "WindowsInstaller"
        Component      = "msiserver & MSI Lock"
        VersionOrState = $msiStateStr
        Status         = if ($msiBlocked) { "Warning" } else { "OK" }
        Details        = "InProgressLock=$msiInProgress; RebootPending=$($wuReboot -or $cbsReboot)"
    })

    # 6. Recent MsiInstaller Failure Events
    $since = (Get-Date).AddHours(-1 * $HoursBack)
    $msiErrorCount = 0
    $logQueryNote = ""
    try {
        $events = @(
            Get-WinEvent -FilterHashtable @{ LogName = 'Application'; ProviderName = 'MsiInstaller'; StartTime = $since } -ErrorAction Stop |
                Where-Object { $_.Id -in @(1033, 1034, 11708, 1603, 1618) -or $_.Level -le 2 -or $_.Message -match 'Error status:\s*(1603|1618)' } |
                Select-Object -First $MaxEvents
        )
        foreach ($ev in $events) {
            if ($ev.Message -match 'Error status:\s*0\b' -and $ev.Level -gt 2) { continue }
            $msiErrorCount++
            $warnCount++
            $msgLine = (($ev.Message -split "\r?\n")[0]).Trim()
            if ($msgLine.Length -gt 140) { $msgLine = $msgLine.Substring(0, 140) + "..." }
            $results.Add([PSCustomObject]@{
                Category       = "MsiEventLog"
                Component      = "Event $($ev.Id)"
                VersionOrState = $ev.TimeCreated.ToString("yyyy-MM-dd HH:mm")
                Status         = "Failure"
                Details        = $msgLine
            })
        }
    }
    catch {
        if ($_.Exception.Message -notmatch 'No events were found') {
            $logQueryNote = $_.Exception.Message
        }
    }
    if ($msiErrorCount -eq 0) {
        $results.Add([PSCustomObject]@{
            Category       = "MsiEventLog"
            Component      = "MsiInstaller (${HoursBack}h)"
            VersionOrState = if ($logQueryNote) { "LogRestricted" } else { "0 errors" }
            Status         = if ($logQueryNote) { "Info" } else { "OK" }
            Details        = if ($logQueryNote) { "Event log query skipped in restricted context: $logQueryNote" } else { "No failed MsiInstaller installation events in the last $HoursBack hour(s)" }
        })
    }

    # 7. Optional Accounting / LOB Multi-User Database Services (with Registry fallback)
    if ($IncludeLOBServices) {
        $lobLoaded = $false
        $lobServices = @()
        try {
            $lobServices = @(
                Get-Service -ErrorAction Stop |
                    Where-Object {
                        $_.Name -like "QuickBooksDB*" -or
                        $_.Name -eq "QBCFMonitorService" -or
                        $_.Name -like "*Sage*" -or
                        $_.Name -like "*Simply*" -or
                        $_.Name -like "*Acomba*" -or
                        $_.Name -like "MSSQL*"
                    }
            )
            $lobLoaded = $true
        }
        catch {
            $lobLoaded = $false
        }

        if ($lobLoaded) {
            if ($lobServices.Count -eq 0) {
                $results.Add([PSCustomObject]@{
                    Category       = "AccountingLOBService"
                    Component      = "QuickBooks/Sage50/Acomba/SQL"
                    VersionOrState = "NoneDetected"
                    Status         = "Info"
                    Details        = "No local accounting or MSSQL database services installed on this endpoint"
                })
            }
            else {
                foreach ($ls in $lobServices) {
                    $isStopped = ($ls.StartType -match 'Automatic' -and $ls.Status -ne 'Running')
                    if ($isStopped) { $warnCount++ }
                    $results.Add([PSCustomObject]@{
                        Category       = "AccountingLOBService"
                        Component      = [string]$ls.Name
                        VersionOrState = "$($ls.Status) / $($ls.StartType)"
                        Status         = if ($isStopped) { "StoppedAuto" } else { [string]$ls.Status }
                        Details        = [string]$ls.DisplayName
                    })
                }
            }
        }
        else {
            $svcRoot = "HKLM:\SYSTEM\CurrentControlSet\Services"
            $lobRegKeys = @(
                Get-ChildItem -Path $svcRoot -ErrorAction SilentlyContinue |
                    Where-Object {
                        $_.PSChildName -like "QuickBooksDB*" -or
                        $_.PSChildName -eq "QBCFMonitorService" -or
                        $_.PSChildName -like "*Sage*" -or
                        $_.PSChildName -like "*Simply*" -or
                        $_.PSChildName -like "*Acomba*" -or
                        $_.PSChildName -like "MSSQL*"
                    }
            )
            if ($lobRegKeys.Count -eq 0) {
                $results.Add([PSCustomObject]@{
                    Category       = "AccountingLOBService"
                    Component      = "QuickBooks/Sage50/Acomba/SQL"
                    VersionOrState = "NoneDetected"
                    Status         = "Info"
                    Details        = "No local accounting/MSSQL services found (RegistryFallback)"
                })
            }
            else {
                foreach ($rk in $lobRegKeys) {
                    $rp = Get-ItemProperty -Path $rk.PSPath -ErrorAction SilentlyContinue
                    $results.Add([PSCustomObject]@{
                        Category       = "AccountingLOBService"
                        Component      = [string]$rk.PSChildName
                        VersionOrState = "Start=$($rp.Start)"
                        Status         = "Registered"
                        Details        = "$([string]$rp.DisplayName) (RegistryFallback)"
                    })
                }
            }
        }
    }

    if ($results.Count -gt 0) {
        $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
        Write-Output $tableOutput.Trim()
        Write-Output ""
    }

    if ($warnCount -gt 0) {
        $status = "warning"
        $summary = "Audited $($results.Count) runtime/MSI/LOB check(s): $warnCount item(s) flagged."
    }
    else {
        $status = "pass"
        $summary = "Audited $($results.Count) runtime/MSI/LOB check(s): all healthy."
    }
}
catch {
    $status = "error"
    $summary = "Runtimes and MSI health audit failed: $($_.Exception.Message)"
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
