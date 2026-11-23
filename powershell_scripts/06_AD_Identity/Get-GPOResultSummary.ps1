<#
.SYNOPSIS
    Generates a read-only Resultant Set of Policy (RSOP) GPO summary via gpresult XML parsing with unelevated fallback.
.PSSTORE_META
    {
        "title": "Get Applied GPO & RSOP Summary",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 45,
        "output_mode": "json",
        "params": [
            {"name": "Scope", "type": "string", "default": "Both"},
            {"name": "IncludeDenied", "type": "bool", "default": true}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Scope = "Both",

    [Parameter(Mandatory = $false)]
    [bool]$IncludeDenied = $true
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()
$tempXml = Join-Path -Path $env:TEMP -ChildPath ("guideit_rsop_" + [System.Guid]::NewGuid().ToString("N") + ".xml")

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
    if ($Scope -notmatch '^(Both|User|Computer)$') {
        $Scope = "Both"
    }

    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    $isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    $gpCmd = Get-Command -Name "gpresult.exe" -ErrorAction SilentlyContinue
    if (-not $gpCmd) {
        $status = "warning"
        $summary = "gpresult.exe was not found on this host."
        $results.Add([PSCustomObject]@{
            Scope        = $Scope
            GPOName      = "N/A"
            Applied      = $false
            LinkOrder    = 0
            FilterReason = "gpresult.exe unavailable"
        })
    }
    elseif ($Scope -eq "Computer" -and -not $isAdmin) {
        $status = "warning"
        $summary = "Computer-scope RSOP inspection requires Administrator privileges."
        $errors.Add("Elevated session required for Computer-scope gpresult.")
        $results.Add([PSCustomObject]@{
            Scope        = "Computer"
            GPOName      = "ElevationRequired"
            Applied      = $false
            LinkOrder    = 0
            FilterReason = "Run elevated to query Computer RSOP policies"
        })
    }
    else {
        $effectiveScope = $Scope
        if ($Scope -eq "Both" -and -not $isAdmin) {
            $effectiveScope = "User"
            $errors.Add("Not running elevated; falling back from Both to User RSOP scope.")
        }

        $gpArgs = @("/X", $tempXml, "/F")
        if ($effectiveScope -eq "User") {
            $gpArgs = @("/SCOPE", "USER", "/X", $tempXml, "/F")
        }
        elseif ($effectiveScope -eq "Computer") {
            $gpArgs = @("/SCOPE", "COMPUTER", "/X", $tempXml, "/F")
        }

        $gpRes = Invoke-NativeCapture -FilePath $gpCmd.Source -Arguments $gpArgs
        if ($gpRes.ExitCode -eq 0 -and (Test-Path -Path $tempXml)) {
            [xml]$rsopXml = Get-Content -Path $tempXml -Encoding UTF8 -Raw -ErrorAction Stop
            $appliedCount = 0
            $deniedCount = 0

            $collectGpos = {
                param($SectionNode, [string]$SectionLabel)
                if ($null -eq $SectionNode) { return }
                foreach ($gpo in @($SectionNode.GPO)) {
                    if ($null -eq $gpo) { continue }
                    $isApplied = ([string]$gpo.FilterAllowed -eq 'true') -and ([string]$gpo.AccessDenied -ne 'true') -and ([string]$gpo.Enabled -ne 'false')
                    if (-not $IncludeDenied -and -not $isApplied) {
                        continue
                    }
                    $reason = "Applied"
                    if (-not $isApplied) {
                        if ([string]$gpo.AccessDenied -eq 'true') { $reason = "Security Filtering / Access Denied" }
                        elseif ([string]$gpo.Enabled -eq 'false') { $reason = "Disabled in GPO" }
                        elseif ([string]$gpo.FilterName) { $reason = "WMI/Filter Denied ($($gpo.FilterName))" }
                        else { $reason = "Filtered Out" }
                    }

                    $orderNum = 0
                    [void][int]::TryParse([string]$gpo.Link.AppliedOrder, [ref]$orderNum)
                    $results.Add([PSCustomObject]@{
                        Scope        = $SectionLabel
                        GPOName      = [string]$gpo.Name
                        Applied      = $isApplied
                        LinkOrder    = $orderNum
                        FilterReason = $reason
                    })
                }
            }

            if ($effectiveScope -in @("Both", "Computer")) {
                & $collectGpos $rsopXml.Rsop.ComputerResults "Computer"
            }
            if ($effectiveScope -in @("Both", "User")) {
                & $collectGpos $rsopXml.Rsop.UserResults "User"
            }

            foreach ($r in $results) {
                if ($r.Applied) { $appliedCount++ } else { $deniedCount++ }
            }

            if ($results.Count -eq 0) {
                $status = "warning"
                $summary = "RSOP XML parsed cleanly ($effectiveScope scope), but 0 GPO entries matched."
                Write-Output $summary
            }
            else {
                $status = if ($errors.Count -gt 0) { "warning" } else { "pass" }
                $summary = "Audited $($results.Count) GPO(s) in $effectiveScope scope ($appliedCount applied, $deniedCount denied/filtered)."
            }
        }
        else {
            # Fallback to gpresult /R text summary (e.g., Windows editions without /X XML flag)
            $rArgs = @("/R")
            if ($effectiveScope -eq "User") {
                $rArgs = @("/SCOPE", "USER", "/R")
            }
            elseif ($effectiveScope -eq "Computer") {
                $rArgs = @("/SCOPE", "COMPUTER", "/R")
            }

            $rRes = Invoke-NativeCapture -FilePath $gpCmd.Source -Arguments $rArgs
            if ($rRes.ExitCode -ne 0) {
                $rawMsg = (($rRes.Output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join " ").Trim()
                $status = "warning"
                $summary = if ($rawMsg) { "No RSOP policy data available: $rawMsg" } else { "gpresult /R did not return RSOP data (workgroup or local-only session)." }
                $results.Add([PSCustomObject]@{
                    Scope        = $effectiveScope
                    GPOName      = "NoRSOPData"
                    Applied      = $false
                    LinkOrder    = 0
                    FilterReason = $summary
                })
            }
            else {
                $curScope = $effectiveScope
                $mode = ""
                $orderCounter = 0
                foreach ($rawLn in $rRes.Output) {
                    $ln = $rawLn.Trim()
                    if (-not $ln) { continue }
                    if ($ln -match '^COMPUTER SETTINGS') { $curScope = "Computer"; $mode = ""; continue }
                    if ($ln -match '^USER SETTINGS') { $curScope = "User"; $mode = ""; continue }
                    if ($ln -match '^Applied Group Policy Objects') { $mode = "Applied"; $orderCounter = 0; continue }
                    if ($ln -match '^The following GPOs were not applied') { $mode = "Denied"; continue }
                    if ($ln -match '^[-]+$' -or $ln -match '^The user|^Resultant Set|^Last time') { continue }
                    if ($mode -in @("Applied", "Denied")) {
                        if ($ln -match '^(None|N/A)$') { $mode = ""; continue }
                        if ($ln -match '^Filtering:') { continue }
                        if ($mode -eq "Denied" -and -not $IncludeDenied) { continue }
                        $orderCounter++
                        $results.Add([PSCustomObject]@{
                            Scope        = $curScope
                            GPOName      = $ln
                            Applied      = ($mode -eq "Applied")
                            LinkOrder    = if ($mode -eq "Applied") { $orderCounter } else { 0 }
                            FilterReason = if ($mode -eq "Applied") { "Applied" } else { "Filtered / Not Applied" }
                        })
                    }
                }
                if ($results.Count -eq 0) {
                    $status = "warning"
                    $summary = "gpresult /R completed ($effectiveScope scope) with 0 GPOs applied (workgroup or no domain GPOs)."
                    $results.Add([PSCustomObject]@{
                        Scope        = $effectiveScope
                        GPOName      = "None"
                        Applied      = $false
                        LinkOrder    = 0
                        FilterReason = $summary
                    })
                }
                else {
                    $appliedCount = @($results | Where-Object { $_.Applied }).Count
                    $deniedCount = $results.Count - $appliedCount
                    $status = if ($errors.Count -gt 0) { "warning" } else { "pass" }
                    $summary = "Audited $($results.Count) GPO(s) via gpresult /R ($appliedCount applied, $deniedCount filtered)."
                }
            }
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
    $summary = "Failed to inspect GPO RSOP summary: $($_.Exception.Message)"
    $errors.Add($_.Exception.Message)
}
finally {
    if (Test-Path -Path $tempXml) {
        Remove-Item -Path $tempXml -Force -ErrorAction SilentlyContinue
    }
    $payload = @{
        status  = $status
        summary = $summary
        data    = @($results)
        errors  = @($errors)
    }
    $payload | ConvertTo-Json -Depth 4 -Compress
}
