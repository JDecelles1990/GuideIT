<#
.SYNOPSIS
    Audits Active Directory time synchronization (W32Time), machine secure channel health, and optional repadmin replication summary.
.PSSTORE_META
    {
        "title": "Get AD Replication, Secure Channel & Time Health",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 45,
        "output_mode": "json",
        "params": [
            {"name": "IncludeRepadmin", "type": "bool", "default": true},
            {"name": "MaxSkewSeconds", "type": "int", "default": 60, "min": 1, "max": 300}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [bool]$IncludeRepadmin = $true,

    [Parameter(Mandatory = $false)]
    [int]$MaxSkewSeconds = 60
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
    $MaxSkewSeconds = [math]::Max(1, [math]::Min(300, $MaxSkewSeconds))
    $warningCount = 0

    # 1. Domain join & role detection via CIM with .NET / Registry fallback
    $partOfDomain = $false
    $domainName = "WORKGROUP"
    $domainRole = 0
    $isDc = $false
    try {
        $cs = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
        $partOfDomain = [bool]$cs.PartOfDomain
        $domainName = if ($partOfDomain -and $cs.Domain) { [string]$cs.Domain } else { [string]$cs.Workgroup }
        $domainRole = [int]$cs.DomainRole
        $isDc = ($domainRole -eq 4 -or $domainRole -eq 5)
    }
    catch {
        try {
            $ipProps = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
            if ($ipProps -and -not [string]::IsNullOrWhiteSpace($ipProps.DomainName)) {
                $domainName = [string]$ipProps.DomainName
                $partOfDomain = $true
                $domainRole = 1
            }
        }
        catch {}

        if (-not $partOfDomain) {
            try {
                $tcpParams = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" -ErrorAction Stop
                $nvDom = if ($tcpParams.'NV Domain') { [string]$tcpParams.'NV Domain' } else { [string]$tcpParams.Domain }
                if (-not [string]::IsNullOrWhiteSpace($nvDom)) {
                    $domainName = $nvDom
                    $partOfDomain = $true
                    $domainRole = 1
                }
            }
            catch {}
        }

        if ($partOfDomain) {
            try {
                $ntOpts = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\ProductOptions" -ErrorAction SilentlyContinue
                if ($ntOpts -and [string]$ntOpts.ProductType -eq 'LanmanNT') {
                    $isDc = $true
                    $domainRole = 4
                }
            }
            catch {}
        }
        elseif (-not [string]::IsNullOrWhiteSpace($env:USERDOMAIN) -and $env:USERDOMAIN -ne $env:COMPUTERNAME) {
            $domainName = $env:USERDOMAIN
        }
    }

    $results.Add([PSCustomObject]@{
        Component = "DomainMembership"
        Status    = if ($partOfDomain) { "Healthy" } else { "Workgroup" }
        Metric    = if ($isDc) { "DomainController" } elseif ($partOfDomain) { "DomainMember" } else { "Workgroup" }
        Detail    = "Domain/Workgroup: $domainName (DomainRole=$domainRole)"
    })

    # 2. Windows Time (W32Time) service & w32tm /query /status
    $w32Svc = Get-Service -Name "W32Time" -ErrorAction SilentlyContinue
    if ($null -eq $w32Svc) {
        $warningCount++
        $results.Add([PSCustomObject]@{
            Component = "W32TimeService"
            Status    = "Warning"
            Metric    = "Missing"
            Detail    = "W32Time service was not found."
        })
    }
    elseif ($w32Svc.Status -ne 'Running') {
        $warningCount++
        $results.Add([PSCustomObject]@{
            Component = "W32TimeService"
            Status    = "Warning"
            Metric    = [string]$w32Svc.Status
            Detail    = "Windows Time service is $($w32Svc.Status); Kerberos clock skew risk."
        })
    }
    else {
        $w32Cmd = Get-Command -Name "w32tm.exe" -ErrorAction SilentlyContinue
        if ($w32Cmd) {
            $tmRes = Invoke-NativeCapture -FilePath $w32Cmd.Source -Arguments @("/query", "/status")
            $tmText = ($tmRes.Output -join "`n")
            if ($tmRes.ExitCode -eq 0 -and $tmText) {
                $sourceLine = ""
                $stratumLine = ""
                $offsetSec = $null

                foreach ($line in $tmRes.Output) {
                    if ($line -match '^\s*(Source|Source)\s*:\s*(.+)$') {
                        $sourceLine = $Matches[2].Trim()
                    }
                    elseif ($line -match '^\s*(Stratum|Couche)\s*:\s*(.+)$') {
                        $stratumLine = $Matches[2].Trim()
                    }
                    elseif ($line -match '([-+]?\d+(?:[.,]\d+)?)\s*s\b' -and $line -match 'Phase Offset|D.calage de phase') {
                        $numText = $Matches[1].Replace(',', '.')
                        $parsedOffset = 0.0
                        if ([double]::TryParse($numText, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsedOffset)) {
                            $offsetSec = $parsedOffset
                        }
                    }
                }

                if (-not $sourceLine) {
                    foreach ($line in $tmRes.Output) {
                        if ($line -match '^[^:]+:\s*(.+)$' -and $line -match 'CMOS|VM IC|time\.|pool|DC|NT5DS|Free-running') {
                            $sourceLine = $Matches[1].Trim()
                            break
                        }
                    }
                }

                $skewStatus = "Healthy"
                $metricText = if ($null -ne $offsetSec) { "{0:N3}s" -f $offsetSec } else { "Running" }
                if ($null -ne $offsetSec -and [math]::Abs($offsetSec) -gt $MaxSkewSeconds) {
                    $skewStatus = "Warning"
                    $warningCount++
                }
                if ($sourceLine -match 'Local CMOS|Free-running' -and $partOfDomain) {
                    $skewStatus = "Warning"
                    $warningCount++
                }

                $results.Add([PSCustomObject]@{
                    Component = "TimeSync"
                    Status    = $skewStatus
                    Metric    = $metricText
                    Detail    = "Source: $(if ($sourceLine) { $sourceLine } else { 'N/A' }) | Stratum: $(if ($stratumLine) { $stratumLine } else { 'N/A' }) | Threshold: +/-${MaxSkewSeconds}s"
                })
            }
            else {
                $warningCount++
                $results.Add([PSCustomObject]@{
                    Component = "TimeSync"
                    Status    = "Warning"
                    Metric    = "Exit $($tmRes.ExitCode)"
                    Detail    = (($tmRes.Output | Select-Object -First 2) -join " ").Trim()
                })
            }
        }
    }

    # 3. Domain Secure Channel Check
    if (-not $partOfDomain) {
        $results.Add([PSCustomObject]@{
            Component = "SecureChannel"
            Status    = "Skipped"
            Metric    = "Workgroup"
            Detail    = "Machine is in a workgroup; Test-ComputerSecureChannel not applicable."
        })
    }
    elseif ($isDc) {
        $results.Add([PSCustomObject]@{
            Component = "SecureChannel"
            Status    = "Skipped"
            Metric    = "DomainController"
            Detail    = "Host is a Domain Controller; member secure channel check not applicable."
        })
    }
    else {
        try {
            $scOk = Test-ComputerSecureChannel -ErrorAction Stop
            if (-not $scOk) { $warningCount++ }
            $results.Add([PSCustomObject]@{
                Component = "SecureChannel"
                Status    = if ($scOk) { "Healthy" } else { "Failed" }
                Metric    = if ($scOk) { "True" } else { "False" }
                Detail    = if ($scOk) { "Computer account trust channel to '$domainName' verified." } else { "Secure channel broken; machine trust reset required." }
            })
        }
        catch {
            $warningCount++
            $msg = $_.Exception.Message
            $errors.Add("SecureChannel check notice: $msg")
            $results.Add([PSCustomObject]@{
                Component = "SecureChannel"
                Status    = "Warning"
                Metric    = "Unavailable"
                Detail    = $msg
            })
        }
    }

    # 4. Optional repadmin /replsummary (graceful fallback on workstations without RSAT)
    if ($IncludeRepadmin) {
        $repCmd = Get-Command -Name "repadmin.exe" -ErrorAction SilentlyContinue
        if (-not $repCmd) {
            $results.Add([PSCustomObject]@{
                Component = "ADReplication"
                Status    = "NotAvailable"
                Metric    = "NoRSAT"
                Detail    = "repadmin.exe not installed on this machine (RSAT AD DS tools required)."
            })
        }
        elseif (-not $partOfDomain) {
            $results.Add([PSCustomObject]@{
                Component = "ADReplication"
                Status    = "Skipped"
                Metric    = "Workgroup"
                Detail    = "repadmin.exe present, but host is not domain-joined."
            })
        }
        else {
            $repRes = Invoke-NativeCapture -FilePath $repCmd.Source -Arguments @("/replsummary")
            $repLines = @($repRes.Output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
            $repErrors = 0
            foreach ($rl in $repLines) {
                if ($rl -match '^\s*\S+\s+\d+\s+(\d+)\s*/\s*(\d+)') {
                    $fails = [int]$Matches[1]
                    if ($fails -gt 0) { $repErrors += $fails }
                }
            }
            if ($repRes.ExitCode -ne 0 -or $repErrors -gt 0) {
                $warningCount++
                $snippet = (($repLines | Select-Object -Last 3) -join " | ")
                $results.Add([PSCustomObject]@{
                    Component = "ADReplication"
                    Status    = "Warning"
                    Metric    = "Exit $($repRes.ExitCode) / Fails $repErrors"
                    Detail    = if ($snippet) { $snippet } else { "repadmin /replsummary reported replication errors." }
                })
            }
            else {
                $results.Add([PSCustomObject]@{
                    Component = "ADReplication"
                    Status    = "Healthy"
                    Metric    = "0 Failures"
                    Detail    = "repadmin /replsummary completed with zero reported replication failures."
                })
            }
        }
    }

    $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
    Write-Output $tableOutput.Trim()
    Write-Output ""

    if ($warningCount -gt 0) {
        $status = "warning"
        $summary = "Completed AD/Time audit on '$domainName' with $warningCount warning(s)."
    }
    else {
        $status = "pass"
        $summary = "Completed AD/Time audit on '$domainName': all available checks healthy."
    }
}
catch {
    $status = "error"
    $summary = "AD replication and time audit failed: $($_.Exception.Message)"
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
