<#
.SYNOPSIS
    Inspects active Kerberos TGT and service tickets via klist along with domain controller discovery and trust state.
.PSSTORE_META
    {
        "title": "Get Kerberos Tickets & Domain Trust Status",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 25,
        "output_mode": "json",
        "params": [
            {"name": "IncludeMachineTickets", "type": "bool", "default": false},
            {"name": "CheckDomainDiscovery", "type": "bool", "default": true}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [bool]$IncludeMachineTickets = $false,

    [Parameter(Mandatory = $false)]
    [bool]$CheckDomainDiscovery = $true
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

function Parse-KlistOutput {
    param(
        [string[]]$Lines,
        [string]$ContextLabel
    )
    $parsed = [System.Collections.Generic.List[PSObject]]::new()
    $current = $null
    foreach ($raw in $Lines) {
        $line = $raw.Trim()
        if ($line -match '^#\d+>\s*(?:Client|Client)\s*:\s*(.+)$') {
            if ($null -ne $current) {
                $parsed.Add([PSCustomObject]$current)
            }
            $current = [ordered]@{
                Context          = $ContextLabel
                TicketOrTarget   = ""
                EncryptionOrSite = "Unknown"
                EndTime          = "N/A"
                Status           = "Cached"
                Detail           = "Client: $($Matches[1].Trim())"
            }
        }
        elseif ($null -ne $current) {
            if ($line -match '^Server:\s*(.+)$') {
                $srv = $Matches[1].Trim()
                $current.TicketOrTarget = $srv
                if ($srv -like 'krbtgt/*') {
                    $current.Status = "TGT"
                }
            }
            elseif ($line -match '^KerbTicket Encryption Type:\s*(.+)$') {
                $current.EncryptionOrSite = $Matches[1].Trim()
            }
            elseif ($line -match '^End Time:\s*(.+)$') {
                $current.EndTime = $Matches[1].Trim()
            }
            elseif ($line -match '^Ticket Flags\s*(.+)$') {
                $current.Detail = "$($current.Detail) | Flags: $($Matches[1].Trim())"
            }
        }
    }
    if ($null -ne $current -and $current.TicketOrTarget) {
        $parsed.Add([PSCustomObject]$current)
    }
    return $parsed
}

try {
    $warnCount = 0
    $partOfDomain = $false
    $domainName = "WORKGROUP"
    try {
        $cs = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
        $partOfDomain = [bool]$cs.PartOfDomain
        $domainName = if ($partOfDomain -and $cs.Domain) { [string]$cs.Domain } else { [string]$cs.Workgroup }
    }
    catch {
        try {
            $ipProps = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
            if ($ipProps -and -not [string]::IsNullOrWhiteSpace($ipProps.DomainName)) {
                $domainName = [string]$ipProps.DomainName
                $partOfDomain = $true
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
                }
            }
            catch {}
        }
    }

    $klistCmd = Get-Command -Name "klist.exe" -ErrorAction SilentlyContinue
    $userTicketCount = 0

    if ($klistCmd) {
        $userKlist = Invoke-NativeCapture -FilePath $klistCmd.Source -Arguments @("tickets")
        $userRows = Parse-KlistOutput -Lines $userKlist.Output -ContextLabel "UserSession"
        foreach ($row in $userRows) {
            $results.Add($row)
            $userTicketCount++
        }

        if ($userTicketCount -eq 0) {
            $results.Add([PSCustomObject]@{
                Context          = "UserSession"
                TicketOrTarget   = "None"
                EncryptionOrSite = "N/A"
                EndTime          = "N/A"
                Status           = if ($partOfDomain) { "Warning" } else { "Info" }
                Detail           = if ($partOfDomain) { "0 Kerberos tickets cached in current user logon session." } else { "Workgroup session; no AD Kerberos tickets expected." }
            })
            if ($partOfDomain) { $warnCount++ }
        }

        if ($IncludeMachineTickets) {
            $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
            $isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
            if (-not $isAdmin) {
                $warnCount++
                $errors.Add("Machine ticket cache (-li 0x3e7) requires Administrator privileges.")
                $results.Add([PSCustomObject]@{
                    Context          = "MachineAccount"
                    TicketOrTarget   = "SYSTEM (0x3e7)"
                    EncryptionOrSite = "N/A"
                    EndTime          = "N/A"
                    Status           = "Warning"
                    Detail           = "Administrator elevation required to inspect SYSTEM Kerberos cache."
                })
            }
            else {
                $sysKlist = Invoke-NativeCapture -FilePath $klistCmd.Source -Arguments @("tickets", "-li", "0x3e7")
                $sysRows = Parse-KlistOutput -Lines $sysKlist.Output -ContextLabel "MachineAccount"
                foreach ($row in $sysRows) {
                    $results.Add($row)
                }
                if ($sysRows.Count -eq 0) {
                    $results.Add([PSCustomObject]@{
                        Context          = "MachineAccount"
                        TicketOrTarget   = "None"
                        EncryptionOrSite = "N/A"
                        EndTime          = "N/A"
                        Status           = "Info"
                        Detail           = "0 cached tickets in SYSTEM (0x3e7) logon session."
                    })
                }
            }
        }
    }
    else {
        $warnCount++
        $errors.Add("klist.exe is unavailable on this host.")
    }

    if ($CheckDomainDiscovery) {
        if (-not $partOfDomain) {
            $results.Add([PSCustomObject]@{
                Context          = "DomainDiscovery"
                TicketOrTarget   = $domainName
                EncryptionOrSite = "Workgroup"
                EndTime          = "N/A"
                Status           = "Skipped"
                Detail           = "Host is not domain-joined."
            })
        }
        else {
            $nltestCmd = Get-Command -Name "nltest.exe" -ErrorAction SilentlyContinue
            if ($nltestCmd) {
                $nlRes = Invoke-NativeCapture -FilePath $nltestCmd.Source -Arguments @("/dsgetdc:$domainName")
                $dcName = ""
                $siteName = ""
                foreach ($line in $nlRes.Output) {
                    if ($line -match '^\s*DC:\s*(\S+)') { $dcName = $Matches[1].Trim() }
                    elseif ($line -match '^\s*Our Site Name:\s*(.+)$') { $siteName = $Matches[1].Trim() }
                }
                if ($nlRes.ExitCode -eq 0 -and $dcName) {
                    $results.Add([PSCustomObject]@{
                        Context          = "DomainDiscovery"
                        TicketOrTarget   = $dcName
                        EncryptionOrSite = if ($siteName) { "Site: $siteName" } else { $domainName }
                        EndTime          = "Online"
                        Status           = "Healthy"
                        Detail           = "Discovered Domain Controller for '$domainName'."
                    })
                }
                else {
                    $warnCount++
                    $errSnippet = (($nlRes.Output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 2) -join " ").Trim()
                    $results.Add([PSCustomObject]@{
                        Context          = "DomainDiscovery"
                        TicketOrTarget   = $domainName
                        EncryptionOrSite = "Unreachable"
                        EndTime          = "N/A"
                        Status           = "Warning"
                        Detail           = if ($errSnippet) { $errSnippet } else { "nltest /dsgetdc failed (Exit $($nlRes.ExitCode))." }
                    })
                }
            }
            else {
                try {
                    $dom = [System.DirectoryServices.ActiveDirectory.Domain]::GetComputerDomain()
                    $dc = $dom.FindDomainController()
                    $results.Add([PSCustomObject]@{
                        Context          = "DomainDiscovery"
                        TicketOrTarget   = [string]$dc.Name
                        EncryptionOrSite = [string]$dc.SiteName
                        EndTime          = "Online"
                        Status           = "Healthy"
                        Detail           = "Discovered DC via .NET DirectoryServices for '$($dom.Name)'."
                    })
                }
                catch {
                    $warnCount++
                    $results.Add([PSCustomObject]@{
                        Context          = "DomainDiscovery"
                        TicketOrTarget   = $domainName
                        EncryptionOrSite = "Unreachable"
                        EndTime          = "N/A"
                        Status           = "Warning"
                        Detail           = $_.Exception.Message
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
        $summary = "Kerberos & trust audit on '$domainName' completed with $warnCount warning(s) ($userTicketCount user ticket(s))."
    }
    else {
        $status = "pass"
        $summary = "Kerberos & trust audit on '$domainName' completed cleanly ($userTicketCount user ticket(s))."
    }
}
catch {
    $status = "error"
    $summary = "Kerberos ticket audit failed: $($_.Exception.Message)"
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
