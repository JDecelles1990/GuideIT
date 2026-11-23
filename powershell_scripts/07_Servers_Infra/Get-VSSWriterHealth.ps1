<#
.SYNOPSIS
    Audits Volume Shadow Copy Service (VSS) writer health and shadow storage allocation statistics with graceful fallback if unelevated.
.PSSTORE_META
    {
        "title": "Get VSS Writer Health & Shadow Storage Stats",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": true,
        "timeout_seconds": 30,
        "output_mode": "json",
        "params": [
            {"name": "OnlyFailedWriters", "type": "bool", "default": false},
            {"name": "IncludeShadowStorage", "type": "bool", "default": true}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [bool]$OnlyFailedWriters = $false,

    [Parameter(Mandatory = $false)]
    [bool]$IncludeShadowStorage = $true
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

function Invoke-NativeCapture {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $FilePath @Arguments 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                $_.Exception.Message
            }
            else {
                $_.ToString()
            }
        }
        $rc = $LASTEXITCODE
        return @{
            Output   = @($out)
            ExitCode = $rc
        }
    }
    finally {
        $ErrorActionPreference = $prev
    }
}

try {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    $isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    $vssSvc = Get-Service -Name "VSS" -ErrorAction SilentlyContinue
    $vssCmd = Get-Command -Name "vssadmin.exe" -ErrorAction SilentlyContinue

    if (-not $vssCmd) {
        $status = "warning"
        $summary = "vssadmin.exe is unavailable on this host."
        $errors.Add("vssadmin.exe not found.")
        $results.Add([PSCustomObject]@{
            RecordType       = "Prerequisite"
            NameOrVolume     = "vssadmin.exe"
            State            = "NotAvailable"
            LastErrorOrUsage = if ($vssSvc) { "VSS Service: $($vssSvc.Status)" } else { "VSS service missing" }
            Healthy          = $false
        })
    }
    elseif (-not $isAdmin) {
        $status = "warning"
        $summary = "vssadmin requires Administrator elevation; returning VSS service status only."
        $errors.Add("Run elevated (Administrator) to inspect VSS writers and shadow storage.")
        $results.Add([PSCustomObject]@{
            RecordType       = "ServiceStatus"
            NameOrVolume     = "Volume Shadow Copy (VSS)"
            State            = if ($vssSvc) { [string]$vssSvc.Status } else { "NotFound" }
            LastErrorOrUsage = "Elevation required for vssadmin list writers"
            Healthy          = $false
        })
    }
    else {
        # 1. Parse vssadmin list writers
        $writerRes = Invoke-NativeCapture -FilePath $vssCmd.Source -Arguments @("list", "writers")
        $writerCount = 0
        $failedWriters = 0

        $currentName = ""
        $currentState = ""
        $currentLastErr = ""

        $flushWriter = {
            if (-not $currentName) { return }
            $isStable = ($currentState -match '\[1\]') -and ($currentLastErr -match '^(No error|Aucune erreur|0x0+\b)?$' -or $currentLastErr -match 'No error|Aucune erreur')
            $script:writerCount++
            if (-not $isStable) { $script:failedWriters++ }
            if (-not $OnlyFailedWriters -or -not $isStable) {
                $results.Add([PSCustomObject]@{
                    RecordType       = "VSSWriter"
                    NameOrVolume     = $currentName
                    State            = if ($currentState) { $currentState } else { "Unknown" }
                    LastErrorOrUsage = if ($currentLastErr) { $currentLastErr } else { "No error" }
                    Healthy          = $isStable
                })
            }
        }

        foreach ($rawLine in $writerRes.Output) {
            $line = $rawLine.Trim()
            if (-not $line) { continue }
            if ($line -match '^(?:Writer name|Nom du r.dacteur)\s*:\s*[''"]?(.+?)[''"]?\s*$') {
                & $flushWriter
                $currentName = $Matches[1].Trim()
                $currentState = ""
                $currentLastErr = ""
            }
            elseif ($currentName -and $line -match '^(?:State|.tat)\s*:\s*(.+)$') {
                $currentState = $Matches[1].Trim()
            }
            elseif ($currentName -and $line -match '^(?:Last error|Derni.re erreur)\s*:\s*(.+)$') {
                $currentLastErr = $Matches[1].Trim()
            }
        }
        & $flushWriter

        if ($writerRes.ExitCode -ne 0 -and $writerCount -eq 0) {
            $errText = (($writerRes.Output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join " ").Trim()
            $errors.Add("vssadmin list writers exited $($writerRes.ExitCode): $errText")
        }

        # 2. Optional Shadow Storage stats
        if ($IncludeShadowStorage) {
            $ssRes = Invoke-NativeCapture -FilePath $vssCmd.Source -Arguments @("list", "shadowstorage")
            $volName = ""
            $usedStr = ""
            $allocStr = ""
            $maxStr = ""

            $flushStorage = {
                if (-not $volName) { return }
                $results.Add([PSCustomObject]@{
                    RecordType       = "ShadowStorage"
                    NameOrVolume     = $volName
                    State            = if ($allocStr) { "Allocated: $allocStr" } else { "Configured" }
                    LastErrorOrUsage = "Used: $usedStr | Max: $maxStr"
                    Healthy          = $true
                })
            }

            foreach ($rawLine in $ssRes.Output) {
                $line = $rawLine.Trim()
                if (-not $line) { continue }
                if ($line -match '^(?:For volume|Pour le volume)\s*:\s*(.+)$') {
                    & $flushStorage
                    $volName = $Matches[1].Trim()
                    $usedStr = "N/A"
                    $allocStr = "N/A"
                    $maxStr = "N/A"
                }
                elseif ($volName -and $line -match '^(?:Used Shadow Copy Storage space|Espace utilis.*)\s*:\s*(.+)$') {
                    $usedStr = $Matches[1].Trim()
                }
                elseif ($volName -and $line -match '^(?:Allocated Shadow Copy Storage space|Espace allou.*)\s*:\s*(.+)$') {
                    $allocStr = $Matches[1].Trim()
                }
                elseif ($volName -and $line -match '^(?:Maximum Shadow Copy Storage space|Espace maximal.*)\s*:\s*(.+)$') {
                    $maxStr = $Matches[1].Trim()
                }
            }
            & $flushStorage
        }

        if ($results.Count -eq 0) {
            $status = "pass"
            $summary = "Inspected $writerCount VSS writer(s): 0 failed writers found."
            Write-Output $summary
        }
        elseif ($failedWriters -gt 0 -or $errors.Count -gt 0) {
            $status = "warning"
            $summary = "Audited $writerCount VSS writer(s): $failedWriters failed/non-stable writer(s) detected."
        }
        else {
            $status = "pass"
            $summary = "Audited $writerCount VSS writer(s): all writers are [1] Stable with no errors."
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
    $summary = "Failed to query VSS writer health: $($_.Exception.Message)"
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
