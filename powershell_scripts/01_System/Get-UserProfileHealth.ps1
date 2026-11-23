<#
.SYNOPSIS
    Audits Windows Registry ProfileList entries for .bak temporary profile keys, missing folders, and recent User Profile Service events (1511/1515).
.PSSTORE_META
    {
        "title": "Audit Windows User Profile Health & Temp Profiles",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 25,
        "output_mode": "json",
        "params": [
            {"name": "HoursBack", "type": "int", "default": 72, "min": 1, "max": 720},
            {"name": "IncludeSystemProfiles", "type": "bool", "default": false}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [int]$HoursBack = 72,

    [Parameter(Mandatory = $false)]
    [bool]$IncludeSystemProfiles = $false
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

try {
    $HoursBack = [math]::Max(1, [math]::Min(720, $HoursBack))
    $issueCount = 0

    # 1. Inspect Registry ProfileList
    $profileRoot = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
    if (Test-Path -Path $profileRoot) {
        $subKeys = @(Get-ChildItem -Path $profileRoot -ErrorAction Stop)
        foreach ($sk in $subKeys) {
            $keyName = [string]$sk.PSChildName
            if (-not $IncludeSystemProfiles -and ($keyName -in @('S-1-5-18', 'S-1-5-19', 'S-1-5-20'))) {
                continue
            }

            $props = Get-ItemProperty -Path $sk.PSPath -ErrorAction SilentlyContinue
            $imgPath = if ($props -and $props.ProfileImagePath) { [string]$props.ProfileImagePath } else { "" }
            $stateInt = if ($props -and $null -ne $props.State) { [int]$props.State } else { 0 }
            $hasBak = $keyName.ToLowerInvariant().EndsWith('.bak')
            $isTempPath = ($imgPath -match '(?i)\\Users\\TEMP(\.|$)')
            $folderExists = if ($imgPath) { Test-Path -Path $imgPath } else { $false }
            $tempStateFlag = (($stateInt -band 0x8000) -ne 0) -or (($stateInt -band 0x0080) -ne 0)

            $healthy = (-not $hasBak) -and (-not $isTempPath) -and (-not $tempStateFlag) -and ($folderExists -or [string]::IsNullOrWhiteSpace($imgPath))
            $notes = [System.Collections.Generic.List[string]]::new()
            if ($hasBak) { $notes.Add("Orphaned .bak key") }
            if ($isTempPath) { $notes.Add("TEMP profile path active") }
            if ($tempStateFlag) { $notes.Add("Temp/Backup State flag set") }
            if ($imgPath -and -not $folderExists) { $notes.Add("Profile folder missing on disk") }
            if ($notes.Count -eq 0) { $notes.Add("Healthy profile entry") }
            if (-not $healthy) { $issueCount++ }

            $results.Add([PSCustomObject]@{
                RecordType   = "ProfileKey"
                SIDOrEventID = $keyName
                ProfilePath  = if ($imgPath) { $imgPath } else { "(Empty)" }
                HasBakKey    = $hasBak
                StateFlags   = ("0x{0:X}" -f $stateInt)
                Healthy      = $healthy
                Detail       = ($notes -join "; ")
            })
        }
    }

    # 2. Query Application Event Log for User Profile Service Errors
    $startTime = (Get-Date).AddHours(-$HoursBack)
    $profileEvents = @()
    try {
        $profileEvents = @(Get-WinEvent -FilterHashtable @{
            LogName      = 'Application'
            ProviderName = 'Microsoft-Windows-User Profiles Service'
            Id           = @(1511, 1515, 1508, 1509, 1502)
            StartTime    = $startTime
        } -MaxEvents 20 -ErrorAction Stop)
    }
    catch {
        if ($_.FullyQualifiedErrorId -notmatch 'NoMatchingEventsFound') {
            $errors.Add("Profile event query notice: $($_.Exception.Message)")
        }
    }

    foreach ($evt in $profileEvents) {
        $issueCount++
        $msg = ($evt.Message -replace '\s+', ' ').Trim()
        if ($msg.Length -gt 140) { $msg = $msg.Substring(0, 137) + "..." }
        $results.Add([PSCustomObject]@{
            RecordType   = "ProfileEvent"
            SIDOrEventID = [string]$evt.Id
            ProfilePath  = $evt.TimeCreated.ToString("yyyy-MM-dd HH:mm:ss")
            HasBakKey    = $false
            StateFlags   = "Event"
            Healthy      = $false
            Detail       = if ($msg) { $msg } else { "User Profile Service warning/error" }
        })
    }

    if ($results.Count -eq 0) {
        $status = "pass"
        $summary = "No user profile entries or profile service errors found."
        Write-Output $summary
    }
    else {
        $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
        Write-Output $tableOutput.Trim()
        Write-Output ""

        if ($issueCount -gt 0) {
            $status = "warning"
            $summary = "Audited $($results.Count) profile record(s): $issueCount temp/corrupted profile indicator(s) found."
        }
        else {
            $status = "pass"
            $summary = "Audited $($results.Count) user profile entry(ies): no .bak keys or 1511/1515 temp profile events found."
        }
    }
}
catch {
    $status = "error"
    $summary = "Failed to audit Windows user profile health: $($_.Exception.Message)"
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
