<#
.SYNOPSIS
    Audits WinINET/WinHTTP web proxies, hosts file overrides, split-DNS vs public DNS, TLS 443 inspection issuers, and Ethernet link speeds.
.PSSTORE_META
    {
        "title": "Get Web Proxy, DNS Split-Brain, TLS Inspection & Ethernet Link Diagnostics",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 35,
        "output_mode": "json",
        "params": [
            {"name": "TargetHost", "type": "string", "default": "login.microsoftonline.com"},
            {"name": "PublicDnsServer", "type": "string", "default": "1.1.1.1"},
            {"name": "TestTlsHandshake", "type": "bool", "default": true},
            {"name": "IncludeAdapterLink", "type": "bool", "default": true}
        ]
    }
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$TargetHost = "login.microsoftonline.com",

    [Parameter(Mandatory = $false)]
    [string]$PublicDnsServer = "1.1.1.1",

    [Parameter(Mandatory = $false)]
    [bool]$TestTlsHandshake = $true,

    [Parameter(Mandatory = $false)]
    [bool]$IncludeAdapterLink = $true
)

$ErrorActionPreference = 'Stop'

$status = "pass"
$summary = ""
$results = [System.Collections.Generic.List[PSObject]]::new()
$errors = [System.Collections.Generic.List[string]]::new()

try {
    $warnCount = 0

    $cleanHost = if ([string]::IsNullOrWhiteSpace($TargetHost)) { "login.microsoftonline.com" } else { $TargetHost.Trim() }
    $cleanHost = $cleanHost -replace '^https?://', ''
    $cleanHost = ($cleanHost -split '/')[0]
    $cleanHost = ($cleanHost -split ':')[0]
    if ([string]::IsNullOrWhiteSpace($cleanHost)) {
        $cleanHost = "login.microsoftonline.com"
    }

    $cleanDns = if ([string]::IsNullOrWhiteSpace($PublicDnsServer)) { "1.1.1.1" } else { $PublicDnsServer.Trim() }

    # 1. WinINET User Proxy Settings
    $inetKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    if (Test-Path -Path $inetKey) {
        $inetProps = Get-ItemProperty -Path $inetKey -ErrorAction SilentlyContinue
        $proxyEnabled = ($inetProps.ProxyEnable -eq 1 -or $inetProps.ProxyEnable -eq "1")
        $proxyServer = if ($inetProps.ProxyServer) { [string]$inetProps.ProxyServer } else { "(none)" }
        $pacUrl = if ($inetProps.AutoConfigURL) { [string]$inetProps.AutoConfigURL } else { "(none)" }
        $proxyOverride = if ($inetProps.ProxyOverride) { [string]$inetProps.ProxyOverride } else { "(none)" }
        $proxyState = if ($proxyEnabled -or $pacUrl -ne "(none)") { "Configured" } else { "Direct" }
        $results.Add([PSCustomObject]@{
            CheckArea = "WinINETProxy"
            Item      = "HKCU Internet Settings"
            Status    = $proxyState
            Details   = "ProxyEnable=$proxyEnabled; ProxyServer=$proxyServer; PAC=$pacUrl; Bypass=$proxyOverride"
        })
    }

    # 2. WinHTTP System Proxy Settings (netsh with Registry Connections fallback)
    try {
        $winhttpOut = @(& netsh.exe winhttp show proxy 2>&1)
        $winhttpLine = ($winhttpOut | ForEach-Object { [string]$_ } | Where-Object { $_ -and $_ -notmatch '^Current WinHTTP' }) -join " | "
        if ($winhttpLine -match 'Direct access') {
            $results.Add([PSCustomObject]@{
                CheckArea = "WinHTTPProxy"
                Item      = "System WinHTTP"
                Status    = "Direct"
                Details   = $winhttpLine
            })
        }
        elseif ($winhttpLine -match 'Proxy Server\s*:') {
            $results.Add([PSCustomObject]@{
                CheckArea = "WinHTTPProxy"
                Item      = "System WinHTTP"
                Status    = "Configured"
                Details   = $winhttpLine
            })
        }
        else {
            $connReg = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings\Connections" -Name "WinHttpSettings" -ErrorAction SilentlyContinue
            $whBytes = $connReg.WinHttpSettings
            $whStatus = "Direct"
            $whDetail = "RegistryFallback: direct access / default"
            if ($whBytes -and $whBytes.Length -ge 9) {
                $flagByte = [int]$whBytes[8]
                if ($flagByte -eq 1) {
                    $whStatus = "Direct"
                    $whDetail = "WinHttpSettings flag=1 (Direct access)"
                }
                else {
                    $whStatus = "Configured"
                    $whDetail = "WinHttpSettings flag=$flagByte (proxy or auto-detect bytes present)"
                }
            }
            $results.Add([PSCustomObject]@{
                CheckArea = "WinHTTPProxy"
                Item      = "System WinHTTP"
                Status    = $whStatus
                Details   = $whDetail
            })
        }
    }
    catch {
        $errors.Add("WinHTTP check skipped: $($_.Exception.Message)")
    }

    # 3. Hosts File Overrides
    $hostsPath = Join-Path -Path $env:SystemRoot -ChildPath "System32\drivers\etc\hosts"
    if (Test-Path -Path $hostsPath) {
        $activeHosts = @(
            Get-Content -Path $hostsPath -ErrorAction Stop |
                ForEach-Object { $_.Trim() } |
                Where-Object { $_ -and -not $_.StartsWith('#') }
        )
        $targetMatch = @($activeHosts | Where-Object { $_ -match ("\b" + [regex]::Escape($cleanHost) + "\b") })
        $hostStatus = if ($targetMatch.Count -gt 0) { "Warning" } else { "OK" }
        if ($targetMatch.Count -gt 0) { $warnCount++ }
        $results.Add([PSCustomObject]@{
            CheckArea = "HostsFile"
            Item      = "etc\hosts"
            Status    = $hostStatus
            Details   = "ActiveEntries=$($activeHosts.Count); MatchesTarget=$($targetMatch.Count)"
        })
    }

    # 4. Local DNS vs Public DNS Split-Brain Check
    $localIps = @()
    try {
        $dnsLocal = @(Resolve-DnsName -Name $cleanHost -Type A -ErrorAction Stop | Where-Object { $_.IPAddress })
        $localIps = @($dnsLocal | Select-Object -ExpandProperty IPAddress)
    }
    catch {
        try {
            $netDns = [System.Net.Dns]::GetHostAddresses($cleanHost) | Where-Object { $_.AddressFamily -eq 'InterNetwork' }
            $localIps = @($netDns | ForEach-Object { $_.IPAddressToString })
        }
        catch {
            $localIps = @()
        }
    }

    $pubIps = @()
    try {
        $dnsPub = @(Resolve-DnsName -Name $cleanHost -Type A -Server $cleanDns -DnsOnly -ErrorAction Stop | Where-Object { $_.IPAddress })
        $pubIps = @($dnsPub | Select-Object -ExpandProperty IPAddress)
    }
    catch {
        $pubIps = @()
    }

    $localSet = ($localIps | Sort-Object) -join ", "
    $pubSet = ($pubIps | Sort-Object) -join ", "
    $dnsStatus = "OK"
    if ($localIps.Count -eq 0) {
        $dnsStatus = "Warning"
        $warnCount++
    }
    elseif ($pubIps.Count -gt 0) {
        $overlap = @($localIps | Where-Object { $pubIps -contains $_ })
        if ($overlap.Count -eq 0) {
            $dnsStatus = "Divergent"
            $warnCount++
        }
    }

    $results.Add([PSCustomObject]@{
        CheckArea = "DNSComparison"
        Item      = $cleanHost
        Status    = $dnsStatus
        Details   = "Local=[$(if ($localSet) { $localSet } else { 'Unresolved' })]; Public($cleanDns)=[$(if ($pubSet) { $pubSet } else { 'Unavailable/Offline' })]"
    })

    # 5. Optional TLS 443 Handshake & Corporate Proxy CA Detection
    if ($TestTlsHandshake) {
        $tcp = $null
        $ssl = $null
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $tcp = New-Object System.Net.Sockets.TcpClient
            $iar = $tcp.BeginConnect($cleanHost, 443, $null, $null)
            $connected = $iar.AsyncWaitHandle.WaitOne(4000, $false)
            if (-not $connected -or -not $tcp.Connected) {
                $warnCount++
                $results.Add([PSCustomObject]@{
                    CheckArea = "TLSInspection"
                    Item      = "${cleanHost}:443"
                    Status    = "Warning"
                    Details   = "TCP 443 connect timed out (4000ms) or blocked by firewall/offline sandbox"
                })
            }
            else {
                $tcp.EndConnect($iar) | Out-Null
                $cb = [System.Net.Security.RemoteCertificateValidationCallback]{ param($sender, $cert, $chain, $sslPolicyErrors) return $true }
                $ssl = New-Object System.Net.Security.SslStream($tcp.GetStream(), $false, $cb)
                $ssl.ReadTimeout = 4000
                $ssl.AuthenticateAsClient($cleanHost, $null, [System.Security.Authentication.SslProtocols]::Tls12, $false)
                $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($ssl.RemoteCertificate)
                $issuer = [string]$cert.Issuer
                $subject = [string]$cert.Subject
                $expires = $cert.NotAfter.ToString("yyyy-MM-dd")
                $proxySuspected = ($issuer -match '(Zscaler|Fortinet|FortiGate|Sophos|Palo Alto|Netskope|Umbrella|BlueCoat|SonicWall|WatchGuard|Smoothwall|Securly|Filter|Proxy|Root CA)')
                $expired = ($cert.NotAfter -lt (Get-Date))
                $tlsStatus = if ($expired) { "Fail" } elseif ($proxySuspected) { "SSLInspection" } else { "OK" }
                if ($expired -or $proxySuspected) { $warnCount++ }
                $results.Add([PSCustomObject]@{
                    CheckArea = "TLSInspection"
                    Item      = "${cleanHost}:443"
                    Status    = $tlsStatus
                    Details   = "Issuer=$issuer; Expires=$expires; Subject=$subject"
                })
            }
        }
        catch {
            $warnCount++
            $results.Add([PSCustomObject]@{
                CheckArea = "TLSInspection"
                Item      = "${cleanHost}:443"
                Status    = "Warning"
                Details   = "TLS handshake skipped/failed: $($_.Exception.Message)"
            })
        }
        finally {
            if ($ssl) { try { $ssl.Dispose() } catch {} }
            if ($tcp) { try { $tcp.Close() } catch {} }
        }
    }

    # 6. Optional Ethernet / Physical NIC Link Speed Check
    if ($IncludeAdapterLink) {
        $nicLoaded = $false
        try {
            $nics = @(Get-NetAdapter -Physical -ErrorAction Stop)
            foreach ($nic in $nics) {
                $speedStr = [string]$nic.LinkSpeed
                $nicState = [string]$nic.Status
                $linkWarn = $false
                if ($nicState -ne 'Up') {
                    $linkWarn = $true
                }
                elseif ($nic.LinkSpeed -match '^(\d+)\s*Mbps' -and [int]$Matches[1] -le 100) {
                    $linkWarn = $true
                }
                if ($linkWarn) { $warnCount++ }
                $results.Add([PSCustomObject]@{
                    CheckArea = "AdapterLink"
                    Item      = [string]$nic.Name
                    Status    = if ($nicState -ne 'Up') { $nicState } elseif ($linkWarn) { "SlowLink" } else { "OK" }
                    Details   = "Desc=$($nic.InterfaceDescription); LinkSpeed=$speedStr; Media=$($nic.MediaType)"
                })
            }
            $nicLoaded = $true
        }
        catch {
            $nicLoaded = $false
        }

        if (-not $nicLoaded) {
            $allNics = @([System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() |
                Where-Object { $_.NetworkInterfaceType -eq 'Ethernet' -or $_.NetworkInterfaceType -eq 'Wireless80211' })
            foreach ($nic in $allNics) {
                $mbps = if ($nic.Speed -gt 0) { [math]::Round($nic.Speed / 1000000, 0) } else { 0 }
                $op = [string]$nic.OperationalStatus
                $linkWarn = ($op -ne 'Up' -or ($mbps -gt 0 -and $mbps -le 100))
                if ($linkWarn) { $warnCount++ }
                $results.Add([PSCustomObject]@{
                    CheckArea = "AdapterLink"
                    Item      = [string]$nic.Name
                    Status    = if ($op -ne 'Up') { $op } elseif ($linkWarn) { "SlowLink" } else { "OK" }
                    Details   = "Type=$($nic.NetworkInterfaceType); SpeedMbps=$mbps"
                })
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
        $summary = "Completed $($results.Count) web/proxy/link check(s) for '$cleanHost': $warnCount item(s) need attention."
    }
    else {
        $status = "pass"
        $summary = "Completed $($results.Count) web/proxy/link check(s) for '$cleanHost': all healthy."
    }
}
catch {
    $status = "error"
    $summary = "Web proxy & TLS diagnostics failed: $($_.Exception.Message)"
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
