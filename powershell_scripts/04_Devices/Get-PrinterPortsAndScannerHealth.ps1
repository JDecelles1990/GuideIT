<#
.SYNOPSIS
    Audits printer ports (TCP vs WSD), Windows default-printer auto-management policy, printer drivers, WIA/Print services, and Scan-to-SMB configuration.
.PSSTORE_META
    {
        "title": "Audit Printer Ports (TCP/WSD), Default Policy, WIA Scanner & Scan-to-SMB",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 30,
        "output_mode": "json",
        "params": [
            {"name": "IncludeSMBServerConfig", "type": "bool", "default": true},
            {"name": "IncludePrinterDrivers", "type": "bool", "default": true}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [bool]$IncludeSMBServerConfig = $true,

    [Parameter(Mandatory = $false)]
    [bool]$IncludePrinterDrivers = $true
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

try {
    $warnCount = 0

    # 1. Windows Default Printer Management Policy
    $winPrnKey = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Windows"
    if (Test-Path -Path $winPrnKey) {
        $props = Get-ItemProperty -Path $winPrnKey -ErrorAction SilentlyContinue
        $legacyMode = $props.LegacyDefaultPrinterMode
        $defaultDev = if ($props.Device) { ([string]$props.Device -split ',')[0] } else { "(none)" }
        $autoManaged = ($null -eq $legacyMode -or [int]$legacyMode -eq 0)
        if ($autoManaged) { $warnCount++ }
        $results.Add([PSCustomObject]@{
            CheckArea = "DefaultPrinterPolicy"
            Item      = $defaultDev
            Status    = if ($autoManaged) { "AutoManaged" } else { "LockedManual" }
            Details   = "LegacyDefaultPrinterMode=$(if ($null -eq $legacyMode) { 'NotSet (0=Windows auto-changes default)' } else { $legacyMode })"
        })
    }

    # 2. Installed Printers & Port Types (TCP vs WSD)
    $printersLoaded = $false
    try {
        $printers = @(Get-Printer -ErrorAction Stop)
        $portMap = @{}
        try {
            foreach ($pt in @(Get-PrinterPort -ErrorAction Stop)) {
                $portMap[[string]$pt.Name] = $pt
            }
        }
        catch {
            $portMap = @{}
        }

        foreach ($p in $printers) {
            $portName = [string]$p.PortName
            $isWsd = ($portName -match '^WSD' -or ($portMap.ContainsKey($portName) -and [string]$portMap[$portName].Description -match 'WSD'))
            $hostIp = if ($portMap.ContainsKey($portName) -and $portMap[$portName].PrinterHostAddress) { [string]$portMap[$portName].PrinterHostAddress } else { "N/A" }
            $pStatus = [string]$p.PrinterStatus
            $rowStatus = "OK"
            if ($pStatus -match 'Offline|Error|Paper|Door') {
                $rowStatus = "Warning"
                $warnCount++
            }
            elseif ($isWsd) {
                $rowStatus = "WSDPort"
                $warnCount++
            }
            $results.Add([PSCustomObject]@{
                CheckArea = "PrinterPort"
                Item      = [string]$p.Name
                Status    = $rowStatus
                Details   = "Port=$portName; HostIP=$hostIp; Driver=$($p.DriverName); State=$pStatus"
            })
        }
        $printersLoaded = $true
    }
    catch {
        $printersLoaded = $false
    }

    if (-not $printersLoaded) {
        $regPrintersPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Print\Printers"
        if (Test-Path -Path $regPrintersPath) {
            foreach ($sub in @(Get-ChildItem -Path $regPrintersPath -ErrorAction SilentlyContinue)) {
                $rp = Get-ItemProperty -Path $sub.PSPath -ErrorAction SilentlyContinue
                $pName = [string]$sub.PSChildName
                $pPort = [string]$rp.Port
                $isWsd = ($pPort -match '^WSD')
                if ($isWsd) { $warnCount++ }
                $results.Add([PSCustomObject]@{
                    CheckArea = "PrinterPort"
                    Item      = $pName
                    Status    = if ($isWsd) { "WSDPort" } else { "OK" }
                    Details   = "Port=$pPort; Driver=$($rp.'Printer Driver'); Source=RegistryFallback"
                })
            }
        }
    }

    # 3. Optional Printer Drivers Inventory (Type 3 vs Type 4)
    if ($IncludePrinterDrivers) {
        try {
            $drivers = @(Get-PrinterDriver -ErrorAction Stop)
            $t3 = @($drivers | Where-Object { $_.MajorVersion -eq 3 }).Count
            $t4 = @($drivers | Where-Object { $_.MajorVersion -eq 4 }).Count
            $results.Add([PSCustomObject]@{
                CheckArea = "PrinterDrivers"
                Item      = "Installed Drivers ($($drivers.Count))"
                Status    = "OK"
                Details   = "Type3Count=$t3; Type4Count=$t4"
            })
        }
        catch {
            $drvRoot = "HKLM:\SYSTEM\CurrentControlSet\Control\Print\Environments\Windows x64\Drivers"
            $t3Count = if (Test-Path "$drvRoot\Version-3") { @(Get-ChildItem "$drvRoot\Version-3" -ErrorAction SilentlyContinue).Count } else { 0 }
            $t4Count = if (Test-Path "$drvRoot\Version-4") { @(Get-ChildItem "$drvRoot\Version-4" -ErrorAction SilentlyContinue).Count } else { 0 }
            $results.Add([PSCustomObject]@{
                CheckArea = "PrinterDrivers"
                Item      = "Installed Drivers Registry"
                Status    = "OK"
                Details   = "Type3Count=$t3Count; Type4Count=$t4Count; Source=RegistryFallback"
            })
        }
    }

    # 4. Print & WIA Scanner Core Services
    foreach ($svcName in @("Spooler", "stisvc", "FDResPub", "fdPHost")) {
        $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
        if ($svc) {
            $isCritical = ($svcName -in @("Spooler", "stisvc"))
            $svcStatus = if ($svc.Status -eq 'Running') { "Running" } elseif ($isCritical) { "Stopped" } else { [string]$svc.Status }
            if ($isCritical -and $svc.Status -ne 'Running') { $warnCount++ }
            $results.Add([PSCustomObject]@{
                CheckArea = "PrintScanService"
                Item      = "$($svc.Name) ($($svc.DisplayName))"
                Status    = $svcStatus
                Details   = "State=$($svc.Status); StartType=$($svc.StartType)"
            })
        }
    }

    # 5. Optional Scan-to-SMB Protocol & NTLM Compatibility Audit
    if ($IncludeSMBServerConfig) {
        $smbLoaded = $false
        try {
            $smbCfg = Get-SmbServerConfiguration -ErrorAction Stop
            $smb1 = [bool]$smbCfg.EnableSMB1Protocol
            $smb2 = [bool]$smbCfg.EnableSMB2Protocol
            $sigReq = [bool]$smbCfg.RequireSecuritySignature
            $results.Add([PSCustomObject]@{
                CheckArea = "ScanToSMBConfig"
                Item      = "SMB Server Protocol"
                Status    = if ($smb2) { "OK" } else { "Warning" }
                Details   = "EnableSMB1=$smb1; EnableSMB2=$smb2; RequireSigning=$sigReq"
            })
            if (-not $smb2) { $warnCount++ }
            $smbLoaded = $true
        }
        catch {
            $smbLoaded = $false
        }

        if (-not $smbLoaded) {
            $lanReg = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters" -ErrorAction SilentlyContinue
            $smb1Val = if ($null -ne $lanReg.SMB1) { $lanReg.SMB1 } else { "Default" }
            $smb2Val = if ($null -ne $lanReg.SMB2) { $lanReg.SMB2 } else { "Enabled(1)" }
            $reqSigVal = if ($null -ne $lanReg.RequireSecuritySignature) { $lanReg.RequireSecuritySignature } else { 0 }
            $results.Add([PSCustomObject]@{
                CheckArea = "ScanToSMBConfig"
                Item      = "LanmanServer Parameters"
                Status    = "OK"
                Details   = "SMB1=$smb1Val; SMB2=$smb2Val; RequireSigning=$reqSigVal; Source=RegistryFallback"
            })
        }

        $lsaProps = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -ErrorAction SilentlyContinue
        $lmLevel = if ($null -ne $lsaProps.LmCompatibilityLevel) { [int]$lsaProps.LmCompatibilityLevel } else { -1 }
        $lmDesc = switch ($lmLevel) {
            -1 { "OS Default (Send NTLMv2 response only)" }
            3  { "3 - Send NTLMv2 response only" }
            4  { "4 - Send NTLMv2 only, refuse LM" }
            5  { "5 - Send NTLMv2 only, refuse LM & NTLM (legacy MFPs may fail)" }
            default { "Level $lmLevel" }
        }
        $results.Add([PSCustomObject]@{
            CheckArea = "ScanToSMBAuth"
            Item      = "Lsa LmCompatibilityLevel"
            Status    = if ($lmLevel -eq 5) { "StrictNTLMv2" } else { "OK" }
            Details   = $lmDesc
        })
    }

    if ($results.Count -gt 0) {
        $tableOutput = $results | Format-Table -AutoSize | Out-String -Width 4096
        Write-Output $tableOutput.Trim()
        Write-Output ""
    }

    if ($warnCount -gt 0) {
        $status = "warning"
        $summary = "Audited $($results.Count) printer/scanner/SMB check(s): $warnCount item(s) flagged (WSD/auto-default/offline/stopped)."
    }
    else {
        $status = "pass"
        $summary = "Audited $($results.Count) printer/scanner/SMB check(s): all healthy."
    }
}
catch {
    $status = "error"
    $summary = "Printer & scanner audit failed: $($_.Exception.Message)"
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
