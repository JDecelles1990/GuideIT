<#
.SYNOPSIS
    Audits local SMB shares, active inbound SMB sessions/open files, and outbound SMB client connections with graceful unelevated fallback.
.PSSTORE_META
    {
        "title": "Audit SMB Shares, Open Sessions & Client Connections",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": true,
        "timeout_seconds": 30,
        "output_mode": "json",
        "params": [
            {"name": "IncludeDefaultShares", "type": "bool", "default": false},
            {"name": "IncludeSessions", "type": "bool", "default": true},
            {"name": "IncludeClientConnections", "type": "bool", "default": true}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [bool]$IncludeDefaultShares = $false,

    [Parameter(Mandatory = $false)]
    [bool]$IncludeSessions = $true,

    [Parameter(Mandatory = $false)]
    [bool]$IncludeClientConnections = $true
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

try {
    $warnCount = 0

    # 1. Local SMB Shares (Get-SmbShare -> Win32_Share -> Registry LanmanServer\Shares fallback)
    $sharesLoaded = $false
    if (Get-Command -Name "Get-SmbShare" -ErrorAction SilentlyContinue) {
        try {
            $shares = @(Get-SmbShare -ErrorAction Stop)
            foreach ($sh in $shares) {
                $name = [string]$sh.Name
                if (-not $IncludeDefaultShares -and $name.EndsWith('$')) { continue }
                $results.Add([PSCustomObject]@{
                    RecordType       = "LocalShare"
                    NameOrTarget     = $name
                    PathOrClient     = if ($sh.Path) { [string]$sh.Path } else { "-" }
                    AccountOrDialect = "Encrypt=$([bool]$sh.EncryptData)"
                    OpenCount        = [int]$sh.CurrentUsers
                    Status           = if ($sh.AvailabilityType) { [string]$sh.AvailabilityType } else { "Active" }
                })
            }
            $sharesLoaded = $true
        }
        catch {
            $errors.Add("Get-SmbShare unavailable: $($_.Exception.Message)")
        }
    }

    if (-not $sharesLoaded) {
        try {
            $wmiShares = @(Get-CimInstance -ClassName Win32_Share -ErrorAction Stop)
            foreach ($sh in $wmiShares) {
                $name = [string]$sh.Name
                if (-not $IncludeDefaultShares -and $name.EndsWith('$')) { continue }
                $results.Add([PSCustomObject]@{
                    RecordType       = "LocalShare"
                    NameOrTarget     = $name
                    PathOrClient     = if ($sh.Path) { [string]$sh.Path } else { "-" }
                    AccountOrDialect = "Type=$($sh.Type)"
                    OpenCount        = 0
                    Status           = if ($sh.Status) { [string]$sh.Status } else { "OK" }
                })
            }
            $sharesLoaded = $true
        }
        catch {
            $sharesLoaded = $false
        }
    }

    if (-not $sharesLoaded) {
        $regSharesPath = "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Shares"
        if (Test-Path -Path $regSharesPath) {
            try {
                $regItem = Get-Item -Path $regSharesPath -ErrorAction Stop
                foreach ($valName in $regItem.GetValueNames()) {
                    if (-not $IncludeDefaultShares -and $valName.EndsWith('$')) { continue }
                    $rawLines = @($regItem.GetValue($valName))
                    $sharePath = "-"
                    foreach ($rl in $rawLines) {
                        if ($rl -match '^Path=(.+)$') { $sharePath = $Matches[1].Trim() }
                    }
                    $results.Add([PSCustomObject]@{
                        RecordType       = "LocalShare"
                        NameOrTarget     = [string]$valName
                        PathOrClient     = $sharePath
                        AccountOrDialect = "RegistryShare"
                        OpenCount        = 0
                        Status           = "Configured"
                    })
                }
            }
            catch {
                $warnCount++
                $errors.Add("Registry share read error: $($_.Exception.Message)")
            }
        }
    }

    # 2. Inbound SMB Sessions & Open Files (requires Admin on most hosts)
    if ($IncludeSessions) {
        if (Get-Command -Name "Get-SmbSession" -ErrorAction SilentlyContinue) {
            try {
                $sessions = @(Get-SmbSession -ErrorAction Stop)
                $openFilesCount = 0
                try {
                    $openFilesCount = @(Get-SmbOpenFile -ErrorAction Stop).Count
                }
                catch {
                    $openFilesCount = 0
                }
                foreach ($sess in $sessions) {
                    $dialect = [string]$sess.Dialect
                    $sessStatus = if ($dialect -like "1.*") { "Warning_SMB1" } else { "Active" }
                    if ($sessStatus -ne "Active") { $warnCount++ }
                    $results.Add([PSCustomObject]@{
                        RecordType       = "InboundSession"
                        NameOrTarget     = [string]$sess.SessionId
                        PathOrClient     = [string]$sess.ClientComputerName
                        AccountOrDialect = "$($sess.ClientUserName) (SMB $dialect)"
                        OpenCount        = [int]$sess.NumOpens
                        Status           = $sessStatus
                    })
                }
                if ($sessions.Count -eq 0 -and $openFilesCount -gt 0) {
                    $results.Add([PSCustomObject]@{
                        RecordType       = "OpenFilesSummary"
                        NameOrTarget     = "TotalOpenFiles"
                        PathOrClient     = $env:COMPUTERNAME
                        AccountOrDialect = "Server"
                        OpenCount        = $openFilesCount
                        Status           = "Active"
                    })
                }
            }
            catch {
                $warnCount++
                $errors.Add("Inbound SMB session query requires Administrator privileges: $($_.Exception.Message)")
                $results.Add([PSCustomObject]@{
                    RecordType       = "InboundSession"
                    NameOrTarget     = "ElevationRequired"
                    PathOrClient     = $env:COMPUTERNAME
                    AccountOrDialect = "N/A"
                    OpenCount        = 0
                    Status           = "AccessDenied"
                })
            }
        }
    }

    # 3. Outbound SMB Client Connections
    if ($IncludeClientConnections) {
        $clientLoaded = $false
        if (Get-Command -Name "Get-SmbConnection" -ErrorAction SilentlyContinue) {
            try {
                $conns = @(Get-SmbConnection -ErrorAction Stop)
                foreach ($c in $conns) {
                    $dialect = [string]$c.Dialect
                    $cStatus = if ($dialect -like "1.*") { "Warning_SMB1" } else { "Connected" }
                    if ($cStatus -ne "Connected") { $warnCount++ }
                    $results.Add([PSCustomObject]@{
                        RecordType       = "ClientConnection"
                        NameOrTarget     = "\\$($c.ServerName)\$($c.ShareName)"
                        PathOrClient     = $env:COMPUTERNAME
                        AccountOrDialect = "$($c.UserName) (SMB $dialect)"
                        OpenCount        = [int]$c.NumOpens
                        Status           = $cStatus
                    })
                }
                $clientLoaded = $true
            }
            catch {
                $errors.Add("Get-SmbConnection fallback triggered: $($_.Exception.Message)")
            }
        }

        if (-not $clientLoaded) {
            try {
                $mapped = @(Get-CimInstance -ClassName Win32_MappedLogicalDisk -ErrorAction Stop)
                foreach ($m in $mapped) {
                    $results.Add([PSCustomObject]@{
                        RecordType       = "MappedDrive"
                        NameOrTarget     = [string]$m.DeviceID
                        PathOrClient     = [string]$m.ProviderName
                        AccountOrDialect = "MappedDisk"
                        OpenCount        = 0
                        Status           = "Mapped"
                    })
                }
            }
            catch {
                # Ignore mapped disk fallback error
            }
        }
    }

    if ($results.Count -eq 0) {
        $status = if ($warnCount -gt 0 -or $errors.Count -gt 0) { "warning" } else { "pass" }
        $summary = "Audited SMB shares/sessions: 0 non-default shares, sessions, or active SMB connections found."
        Write-Output $summary
    }
    else {
        $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
        Write-Output $tableOutput.Trim()
        Write-Output ""

        if ($warnCount -gt 0) {
            $status = "warning"
            $summary = "Audited $($results.Count) SMB item(s) with $warnCount warning(s) (SMB1 or elevation needed for sessions)."
        }
        else {
            $status = "pass"
            $summary = "Audited $($results.Count) SMB share, session, and client connection record(s)."
        }
    }
}
catch {
    $status = "error"
    $summary = "Failed to audit SMB shares and sessions: $($_.Exception.Message)"
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
