<#
.SYNOPSIS
    Audits Microsoft Teams client installation/version, cache sizes, local audio endpoints, and optional TLS 443 endpoint reachability.
.PSSTORE_META
    {
        "title": "Get Microsoft Teams Client, Cache, Audio & Endpoint Diagnostics",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 35,
        "output_mode": "json",
        "params": [
            {"name": "TestEndpoints", "type": "bool", "default": true},
            {"name": "TimeoutMs", "type": "int", "default": 3000, "min": 500, "max": 15000},
            {"name": "WarnCacheSizeMB", "type": "int", "default": 500, "min": 50, "max": 5000}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [bool]$TestEndpoints = $true,

    [Parameter(Mandatory = $false)]
    [int]$TimeoutMs = 3000,

    [Parameter(Mandatory = $false)]
    [int]$WarnCacheSizeMB = 500
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

function Test-Tcp443 {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$WaitMs
    )
    $client = $null
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($WaitMs, $false)
        $sw.Stop()
        if ($ok -and $client.Connected) {
            $client.EndConnect($iar)
            return @{
                Reachable = $true
                LatencyMs = [int]$sw.ElapsedMilliseconds
                Message   = "TCP/$Port connected in $([int]$sw.ElapsedMilliseconds) ms"
            }
        }
        return @{
            Reachable = $false
            LatencyMs = [int]$sw.ElapsedMilliseconds
            Message   = "Timed out after $WaitMs ms"
        }
    }
    catch {
        $sw.Stop()
        return @{
            Reachable = $false
            LatencyMs = [int]$sw.ElapsedMilliseconds
            Message   = $_.Exception.Message
        }
    }
    finally {
        if ($null -ne $client) {
            $client.Close()
        }
    }
}

try {
    $TimeoutMs = [math]::Max(500, [math]::Min(15000, $TimeoutMs))
    $WarnCacheSizeMB = [math]::Max(50, [math]::Min(5000, $WarnCacheSizeMB))
    $warnCount = 0

    # 1. Client Installation & Running Processes
    $newTeamsPkg = $null
    try {
        $newTeamsPkg = Get-AppxPackage -Name "MSTeams" -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    catch {
        $newTeamsPkg = $null
    }
    $newRunning = @(Get-Process -Name "ms-teams" -ErrorAction SilentlyContinue)
    $results.Add([PSCustomObject]@{
        Category  = "Client"
        CheckName = "NewTeams (MSTeams)"
        Status    = if ($newTeamsPkg) { "Installed" } else { "NotInstalled" }
        Value     = if ($newTeamsPkg) { [string]$newTeamsPkg.Version } else { "N/A" }
        Detail    = "Running instances: $($newRunning.Count)"
    })

    $classicExe = Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Teams\current\Teams.exe"
    $classicInstalled = Test-Path -Path $classicExe
    $classicVer = "N/A"
    if ($classicInstalled) {
        try {
            $classicVer = [string](Get-Item -Path $classicExe -ErrorAction Stop).VersionInfo.ProductVersion
        }
        catch {
            $classicVer = "Installed"
        }
    }
    $classicRunning = @(Get-Process -Name "Teams" -ErrorAction SilentlyContinue)
    $results.Add([PSCustomObject]@{
        Category  = "Client"
        CheckName = "ClassicTeams"
        Status    = if ($classicInstalled) { "Installed" } else { "NotInstalled" }
        Value     = $classicVer
        Detail    = "Running instances: $($classicRunning.Count)"
    })

    # 2. Cache Size Inspection (Read-Only)
    $cachePaths = @(
        @{ Name = "NewTeamsCache"; Path = "$env:LOCALAPPDATA\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams" },
        @{ Name = "ClassicTeamsCache"; Path = "$env:APPDATA\Microsoft\Teams" }
    )
    foreach ($cp in $cachePaths) {
        try {
            if (Test-Path -Path $cp.Path -ErrorAction Stop) {
                $files = @(Get-ChildItem -Path $cp.Path -Recurse -File -ErrorAction SilentlyContinue)
                $totalBytes = ($files | Measure-Object -Property Length -Sum).Sum
                if ($null -eq $totalBytes) { $totalBytes = 0 }
                $sizeMb = [math]::Round(($totalBytes / 1MB), 2)
                $cacheStatus = if ($sizeMb -ge $WarnCacheSizeMB) { "Warning" } else { "Healthy" }
                if ($cacheStatus -eq "Warning") { $warnCount++ }
                $results.Add([PSCustomObject]@{
                    Category  = "Cache"
                    CheckName = $cp.Name
                    Status    = $cacheStatus
                    Value     = "$sizeMb MB"
                    Detail    = "$($files.Count) file(s) under $($cp.Path)"
                })
            }
            else {
                $results.Add([PSCustomObject]@{
                    Category  = "Cache"
                    CheckName = $cp.Name
                    Status    = "NotPresent"
                    Value     = "0 MB"
                    Detail    = "Path not found: $($cp.Path)"
                })
            }
        }
        catch {
            $results.Add([PSCustomObject]@{
                Category  = "Cache"
                CheckName = $cp.Name
                Status    = "AccessDenied"
                Value     = "N/A"
                Detail    = "Cannot inspect $($cp.Path): $($_.Exception.Message)"
            })
        }
    }

    # 3. Audio Devices / Endpoints (CIM with read-only Registry fallback)
    $audioItems = @()
    try {
        $audioItems = @(Get-CimInstance -ClassName Win32_SoundDevice -ErrorAction Stop)
    }
    catch {
        $audioItems = @()
    }
    if ($audioItems.Count -gt 0) {
        foreach ($snd in $audioItems) {
            $sndStatus = [string]$snd.Status
            $rowStatus = if ($sndStatus -eq 'OK' -or -not $sndStatus) { "Healthy" } else { "Warning" }
            if ($rowStatus -eq "Warning") { $warnCount++ }
            $results.Add([PSCustomObject]@{
                Category  = "Audio"
                CheckName = [string]$snd.Name
                Status    = $rowStatus
                Value     = if ($sndStatus) { $sndStatus } else { "Detected" }
                Detail    = "Manufacturer: $($snd.Manufacturer)"
            })
        }
    }
    else {
        $regMediaCount = 0
        try {
            $mediaClass = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e96c-e325-11ce-bfc1-08002be10318}"
            if (Test-Path -Path $mediaClass) {
                $subKeys = @(Get-ChildItem -Path $mediaClass -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match '^\d{4}$' })
                foreach ($sk in $subKeys) {
                    $props = Get-ItemProperty -Path $sk.PSPath -ErrorAction SilentlyContinue
                    if ($props -and $props.DriverDesc) {
                        $regMediaCount++
                        $results.Add([PSCustomObject]@{
                            Category  = "Audio"
                            CheckName = [string]$props.DriverDesc
                            Status    = "Healthy"
                            Value     = "Registry"
                            Detail    = "DriverVersion: $(if ($props.DriverVersion) { $props.DriverVersion } else { 'N/A' })"
                        })
                    }
                }
            }
        }
        catch {}

        if ($regMediaCount -eq 0) {
            $warnCount++
            $results.Add([PSCustomObject]@{
                Category  = "Audio"
                CheckName = "SoundDevices"
                Status    = "Warning"
                Value     = "0 devices"
                Detail    = "No Win32_SoundDevice or registry audio drivers detected."
            })
        }
    }

    # 4. Optional Teams Endpoint Reachability (TCP 443)
    if ($TestEndpoints) {
        $endpoints = @(
            "teams.microsoft.com",
            "login.microsoftonline.com",
            "worldaz.tr.teams.microsoft.com"
        )
        foreach ($ep in $endpoints) {
            $probe = Test-Tcp443 -HostName $ep -Port 443 -WaitMs $TimeoutMs
            if (-not $probe.Reachable) { $warnCount++ }
            $results.Add([PSCustomObject]@{
                Category  = "Connectivity"
                CheckName = $ep
                Status    = if ($probe.Reachable) { "Reachable" } else { "Unreachable" }
                Value     = "$($probe.LatencyMs) ms"
                Detail    = $probe.Message
            })
        }
    }

    $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
    Write-Output $tableOutput.Trim()
    Write-Output ""

    if ($warnCount -gt 0) {
        $status = "warning"
        $summary = "Teams diagnostics completed ($($results.Count) checks) with $warnCount warning(s)."
    }
    else {
        $status = "pass"
        $summary = "Teams diagnostics passed all $($results.Count) check(s)."
    }
}
catch {
    $status = "error"
    $summary = "Teams diagnostics failed: $($_.Exception.Message)"
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
