<#
.SYNOPSIS
    Queries Windows Security Event Log for Account Lockout (4740) and Failed Logon (4625) events to identify lockout source workstations and substatus codes.
.PSSTORE_META
    {
        "title": "Get Account Lockout & Bad Password Events",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": true,
        "timeout_seconds": 30,
        "output_mode": "json",
        "params": [
            {"name": "Username", "type": "string", "default": ""},
            {"name": "HoursBack", "type": "int", "default": 24, "min": 1, "max": 168},
            {"name": "IncludeFailedLogons", "type": "bool", "default": true},
            {"name": "MaxEvents", "type": "int", "default": 30, "min": 5, "max": 100}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Username = "",

    [Parameter(Mandatory = $false)]
    [int]$HoursBack = 24,

    [Parameter(Mandatory = $false)]
    [bool]$IncludeFailedLogons = $true,

    [Parameter(Mandatory = $false)]
    [int]$MaxEvents = 30
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

function Resolve-LogonSubStatus {
    param([string]$Code)
    if ([string]::IsNullOrWhiteSpace($Code)) { return "" }
    switch ($Code.ToLowerInvariant()) {
        "0xc000006a" { return "0xC000006A (Bad password)" }
        "0xc0000234" { return "0xC0000234 (Account locked out)" }
        "0xc0000071" { return "0xC0000071 (Password expired)" }
        "0xc0000072" { return "0xC0000072 (Account disabled)" }
        "0xc0000064" { return "0xC0000064 (User does not exist)" }
        "0xc000006f" { return "0xC000006F (Logon hour restriction)" }
        "0xc0000070" { return "0xC0000070 (Workstation restriction)" }
        "0xc0000193" { return "0xC0000193 (Account expired)" }
        "0xc0000224" { return "0xC0000224 (Must change password)" }
        default { return $Code }
    }
}

try {
    $HoursBack = [math]::Max(1, [math]::Min(168, $HoursBack))
    $MaxEvents = [math]::Max(5, [math]::Min(100, $MaxEvents))
    $cleanUser = if ($null -ne $Username) { $Username.Trim() } else { "" }
    if ($cleanUser -match '\\([^\\]+)$') {
        $cleanUser = $Matches[1]
    }
    elseif ($cleanUser -match '^([^@]+)@') {
        $cleanUser = $Matches[1]
    }

    $eventIds = if ($IncludeFailedLogons) { @(4740, 4625) } else { @(4740) }
    $startTime = (Get-Date).AddHours(-$HoursBack)
    $fetchLimit = if ([string]::IsNullOrWhiteSpace($cleanUser)) { $MaxEvents } else { [math]::Min(500, $MaxEvents * 10) }

    $filter = @{
        LogName   = 'Security'
        Id        = $eventIds
        StartTime = $startTime
    }

    $rawEvents = @()
    $accessDenied = $false
    try {
        $rawEvents = @(Get-WinEvent -FilterHashtable $filter -MaxEvents $fetchLimit -ErrorAction Stop)
    }
    catch {
        $fqid = [string]$_.FullyQualifiedErrorId
        $msg = $_.Exception.Message
        if ($fqid -match 'NoMatchingEventsFound') {
            $rawEvents = @()
        }
        elseif ($fqid -match 'UnauthorizedAccess' -or $msg -match 'unauthorized|access is denied|privilege') {
            $accessDenied = $true
            $errors.Add("Security event log access denied. Run elevated (Administrator) to read Event IDs 4740/4625.")
        }
        else {
            throw
        }
    }

    if ($accessDenied) {
        $status = "warning"
        $summary = "Security log requires Administrator elevation to inspect 4740/4625 lockout events."
        $results.Add([PSCustomObject]@{
            TimeCreated  = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
            EventID      = 0
            EventType    = "AccessDenied"
            TargetUser   = if ($cleanUser) { $cleanUser } else { "All" }
            Domain       = $env:USERDOMAIN
            CallerSource = $env:COMPUTERNAME
            SourceIP     = "N/A"
            Detail       = "Cannot read Security log without Administrator privileges."
        })
    }
    else {
        $lockoutCount = 0
        $failedLogonCount = 0

        foreach ($evt in $rawEvents) {
            if ($results.Count -ge $MaxEvents) { break }

            $dataMap = @{}
            try {
                $xmlDoc = [xml]$evt.ToXml()
                foreach ($node in $xmlDoc.Event.EventData.Data) {
                    if ($node.Name) {
                        $dataMap[$node.Name] = [string]$node.'#text'
                    }
                }
            }
            catch {
                $dataMap = @{}
            }

            $targetUser = if ($dataMap.ContainsKey('TargetUserName') -and $dataMap['TargetUserName']) { $dataMap['TargetUserName'] } else { "Unknown" }
            if ($cleanUser -and ($targetUser -notlike "*$cleanUser*")) {
                continue
            }

            $targetDomain = if ($dataMap.ContainsKey('TargetDomainName') -and $dataMap['TargetDomainName']) { $dataMap['TargetDomainName'] } else { "-" }
            $callerSource = "-"
            $sourceIp = "-"
            $detail = ""

            if ($evt.Id -eq 4740) {
                $lockoutCount++
                $eventType = "AccountLockout"
                $callerSource = if ($dataMap.ContainsKey('CallerComputerName') -and $dataMap['CallerComputerName']) { $dataMap['CallerComputerName'] } else { "Unknown" }
                $detail = "Account locked out (Caller: $callerSource)"
            }
            else {
                $failedLogonCount++
                $eventType = "FailedLogon"
                $callerSource = if ($dataMap.ContainsKey('WorkstationName') -and $dataMap['WorkstationName']) { $dataMap['WorkstationName'] } else { "-" }
                $sourceIp = if ($dataMap.ContainsKey('IpAddress') -and $dataMap['IpAddress']) { $dataMap['IpAddress'] } else { "-" }
                $logonType = if ($dataMap.ContainsKey('LogonType') -and $dataMap['LogonType']) { "LogonType $($dataMap['LogonType'])" } else { "LogonType ?" }
                $subDesc = Resolve-LogonSubStatus -Code $dataMap['SubStatus']
                if (-not $subDesc) {
                    $subDesc = Resolve-LogonSubStatus -Code $dataMap['Status']
                }
                $detail = if ($subDesc) { "$logonType | $subDesc" } else { $logonType }
            }

            $results.Add([PSCustomObject]@{
                TimeCreated  = $evt.TimeCreated.ToString("yyyy-MM-dd HH:mm:ss")
                EventID      = [int]$evt.Id
                EventType    = $eventType
                TargetUser   = $targetUser
                Domain       = $targetDomain
                CallerSource = $callerSource
                SourceIP     = $sourceIp
                Detail       = $detail
            })
        }

        if ($results.Count -eq 0) {
            $status = "pass"
            $filterNote = if ($cleanUser) { " for user filter '$cleanUser'" } else { "" }
            $summary = "No lockout (4740) or matching failed logon events found in the last $HoursBack hour(s)$filterNote."
            Write-Output $summary
        }
        else {
            if ($lockoutCount -gt 0) {
                $status = "warning"
            }
            else {
                $status = "warning"
            }
            $summary = "Found $($results.Count) Security event(s) in past $HoursBack h ($lockoutCount lockout [4740], $failedLogonCount failed logon [4625])."
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
    $summary = "Failed to query account lockout events: $($_.Exception.Message)"
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
