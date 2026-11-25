<#
.SYNOPSIS
    Cross-PowerShell (5.1 & 7+) verification and PyInstaller packaging pipeline for GuideIT Master.
#>
[CmdletBinding()]
param(
    [switch]$VerifyOnly,
    [switch]$Package,
    [switch]$SkipTests,
    [switch]$NoZip,
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = $PSScriptRoot
$SpecPath = Join-Path $RepoRoot "guideit_master.spec"
$VenvPython = Join-Path (Join-Path (Join-Path $RepoRoot ".venv") "Scripts") "python.exe"

if (-not $VerifyOnly -and -not $Package) {
    $VerifyOnly = $true
    Write-Host "No mode flag specified; defaulting to -VerifyOnly." -ForegroundColor Yellow
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if (Test-Path -LiteralPath $VenvPython) {
        $PythonExe = $VenvPython
    }
    elseif ($Package) {
        throw (
            "Project virtual environment Python not found at '{0}'. Create .venv and install dependencies first:`n" +
            "  python -m venv --system-site-packages .venv`n" +
            "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt`n" +
            "Or pass -PythonExe explicitly."
        ) -f $VenvPython
    }
    else {
        $PythonExe = "python"
    }
}
else {
    $cmdFound = Get-Command -Name $PythonExe -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $PythonExe) -and $null -eq $cmdFound) {
        throw ("Specified Python executable not found: '{0}'" -f $PythonExe)
    }
}

function Get-AppVersion {
    param([string]$RootDir)
    $pyproject = Join-Path $RootDir "pyproject.toml"
    if (Test-Path -LiteralPath $pyproject) {
        $raw = Get-Content -LiteralPath $pyproject -Raw -Encoding UTF8
        if ($raw -match '(?m)^version\s*=\s*"([^"]+)"') {
            return $Matches[1]
        }
    }
    return "1.0.0"
}

function Get-PlaybookFileCount {
    param([string]$PlaybooksRoot)
    if (-not (Test-Path -LiteralPath $PlaybooksRoot)) {
        return 0
    }
    $count = 0
    $domainDirs = Get-ChildItem -LiteralPath $PlaybooksRoot -Directory
    foreach ($dir in $domainDirs) {
        $files = @(Get-ChildItem -LiteralPath $dir.FullName -File -Filter "*.md" | Where-Object { $_.Name.ToLowerInvariant() -ne "readme.md" })
        $count += $files.Count
    }
    return $count
}

function Get-PsScriptFileCount {
    param([string]$ScriptsRoot)
    if (-not (Test-Path -LiteralPath $ScriptsRoot)) {
        return 0
    }
    return @(Get-ChildItem -LiteralPath $ScriptsRoot -Recurse -File -Filter "*.ps1").Count
}

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host ("=== {0} ===" -f $Label) -ForegroundColor Cyan
    Write-Host ("> {0} {1}" -f $Executable, ($Arguments -join " ")) -ForegroundColor DarkGray

    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $exitCode = 1
    try {
        & $Executable @Arguments
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prevPref
    }

    if ($exitCode -ne 0) {
        throw ("Step '{0}' failed with exit code {1}." -f $Label, $exitCode)
    }
}

function Invoke-SpecAudit {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SpecFile
    )

    Write-Host ""
    Write-Host "=== Auditing PyInstaller Spec (guideit_master.spec) ===" -ForegroundColor Cyan

    if (-not (Test-Path -LiteralPath $SpecFile)) {
        throw ("Spec file not found: {0}" -f $SpecFile)
    }

    $auditCode = @'
import ast
import sys
from pathlib import Path

spec_path = Path(sys.argv[1]).resolve()
repo_root = spec_path.parent
source = spec_path.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(spec_path))

assignments = {}
call_names = []
collect_name = None
exe_console = None
exe_exclude_binaries = None

for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = node.value

for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        call_names.append(node.func.id)
        if node.func.id == "COLLECT":
            for kw in node.keywords:
                if kw.arg == "name":
                    collect_name = ast.literal_eval(kw.value)
        elif node.func.id == "EXE":
            for kw in node.keywords:
                if kw.arg == "console":
                    exe_console = ast.literal_eval(kw.value)
                elif kw.arg == "exclude_binaries":
                    exe_exclude_binaries = ast.literal_eval(kw.value)

if "BUNDLED_DATA_DIRS" not in assignments:
    raise AssertionError("guideit_master.spec must define BUNDLED_DATA_DIRS")
if "EXCLUDED_ROOT_DIRS" not in assignments:
    raise AssertionError("guideit_master.spec must define EXCLUDED_ROOT_DIRS")

bundled = ast.literal_eval(assignments["BUNDLED_DATA_DIRS"])
excluded = set(ast.literal_eval(assignments["EXCLUDED_ROOT_DIRS"]))

required_dirs = {"playbooks", "powershell_scripts", "taxonomy", "templates", "docs"}
forbidden_dirs = {"data", "_ref_GuideIT", "_ref_PowerShellStore", "tests"}

bundled_srcs = {src for src, _ in bundled}
bundled_dsts = {dst for _, dst in bundled}

if bundled_srcs != required_dirs or bundled_dsts != required_dirs:
    raise AssertionError(
        f"BUNDLED_DATA_DIRS mismatch: expected {sorted(required_dirs)}, got srcs={sorted(bundled_srcs)} dsts={sorted(bundled_dsts)}"
    )

if not forbidden_dirs.issubset(excluded):
    raise AssertionError(
        f"EXCLUDED_ROOT_DIRS missing required exclusions: {sorted(forbidden_dirs - excluded)}"
    )

for src, dst in bundled:
    if src in forbidden_dirs or dst in forbidden_dirs:
        raise AssertionError(f"Forbidden directory included in BUNDLED_DATA_DIRS: {(src, dst)}")
    if not (repo_root / src).is_dir():
        raise AssertionError(f"Bundled directory does not exist on disk: {repo_root / src}")

if "COLLECT" not in call_names or collect_name != "GuideIT_Master":
    raise AssertionError(f"Expected onedir COLLECT(name='GuideIT_Master'), got {collect_name!r}")
if exe_exclude_binaries is not True or exe_console is not False:
    raise AssertionError(
        f"Expected EXE(exclude_binaries=True, console=False), got exclude_binaries={exe_exclude_binaries!r}, console={exe_console!r}"
    )

print(
    f"Spec audit passed: bundled={sorted(bundled_srcs)}, excluded={sorted(excluded)}, bundle_name={collect_name}"
)
'@

    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $exitCode = 1
    try {
        $auditCode | & $PythonExe - $SpecFile
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prevPref
    }

    if ($exitCode -ne 0) {
        throw ("Spec audit failed with exit code {0}." -f $exitCode)
    }
}

function Invoke-VerificationSuite {
    Invoke-NativeStep -Label "Python Environment Check" -Executable $PythonExe -Arguments @("--version")
    Invoke-NativeStep -Label "Validate GuideIT Playbooks (--strict)" -Executable $PythonExe -Arguments @((Join-Path $RepoRoot (Join-Path "tools" "validate_playbooks.py")), "--strict")
    Invoke-NativeStep -Label "Lint PowerShellStore Scripts" -Executable $PythonExe -Arguments @((Join-Path $RepoRoot (Join-Path "tools" "lint_scripts.py")))
    if (-not $SkipTests) {
        Invoke-NativeStep -Label "Run Unified Pytest Suite" -Executable $PythonExe -Arguments @("-m", "pytest", (Join-Path $RepoRoot "tests"), "-v")
    }
    else {
        Write-Host ""
        Write-Host "Skipping pytest suite (-SkipTests specified)." -ForegroundColor Yellow
    }
    Invoke-SpecAudit -SpecFile $SpecPath
}

function Get-FileTimestampSnapshot {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        return (Get-Item -LiteralPath $Path).LastWriteTimeUtc
    }
    return $null
}

function Invoke-PackageBuildAndSmokeTest {
    Write-Host ""
    Write-Host "=== Checking PyInstaller Availability ===" -ForegroundColor Cyan
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $pyiVersion = & $PythonExe -m PyInstaller --version 2>&1
        $pyiExit = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prevPref
    }
    if ($pyiExit -ne 0) {
        throw ("PyInstaller is not installed in '{0}'. Install it first with: {0} -m pip install -r requirements.txt" -f $PythonExe)
    }
    Write-Host ("PyInstaller version: {0}" -f $pyiVersion) -ForegroundColor Green

    $liveDataDir = Join-Path $RepoRoot "data"
    $liveGuideItDb = Join-Path $liveDataDir "guideit.db"
    $livePsStoreDb = Join-Path $liveDataDir "powershell_store.db"
    $preGuideItTime = Get-FileTimestampSnapshot -Path $liveGuideItDb
    $prePsStoreTime = Get-FileTimestampSnapshot -Path $livePsStoreDb

    $buildDir = Join-Path $RepoRoot "build"
    $distDir = Join-Path $RepoRoot "dist"
    foreach ($staleDir in @($buildDir, $distDir)) {
        if (Test-Path -LiteralPath $staleDir) {
            Write-Host ("Cleaning stale output directory: {0}" -f $staleDir) -ForegroundColor DarkGray
            Remove-Item -LiteralPath $staleDir -Recurse -Force
        }
    }

    Push-Location $RepoRoot
    try {
        Invoke-NativeStep -Label "PyInstaller Onedir Build" -Executable $PythonExe -Arguments @("-m", "PyInstaller", "--noconfirm", "--clean", $SpecPath)
    }
    finally {
        Pop-Location
    }

    $distBundleDir = Join-Path $distDir "GuideIT_Master"
    $exePath = Join-Path $distBundleDir "GuideIT_Master.exe"
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw ("Expected packaged executable not found: {0}" -f $exePath)
    }

    $internalDir = Join-Path $distBundleDir "_internal"
    $assetRoot = $distBundleDir
    if (Test-Path -LiteralPath $internalDir) {
        $assetRoot = $internalDir
    }

    $requiredAssets = @("playbooks", "powershell_scripts", "taxonomy", "templates", "docs")
    foreach ($dirName in $requiredAssets) {
        $candidate = Join-Path $assetRoot $dirName
        if (-not (Test-Path -LiteralPath $candidate)) {
            throw ("Missing bundled asset directory in compiled output: {0}" -f $candidate)
        }
    }

    $forbiddenDirs = @("data", "_ref_GuideIT", "_ref_PowerShellStore", "tests")
    foreach ($forbidden in $forbiddenDirs) {
        $inRoot = Join-Path $distBundleDir $forbidden
        $inInternal = Join-Path $assetRoot $forbidden
        if ((Test-Path -LiteralPath $inRoot) -or (Test-Path -LiteralPath $inInternal)) {
            throw ("Forbidden directory '{0}' found inside compiled distribution!" -f $forbidden)
        }
    }

    $webEngineDll = @(Get-ChildItem -LiteralPath $distBundleDir -Recurse -File -Filter "Qt6WebEngine*.dll" -ErrorAction SilentlyContinue)
    if ($webEngineDll.Count -gt 0) {
        throw ("Excluded QtWebEngine DLL leaked into bundle: {0}" -f $webEngineDll[0].FullName)
    }

    $expectedPlaybooks = Get-PlaybookFileCount -PlaybooksRoot (Join-Path $RepoRoot "playbooks")
    $bundledPlaybooks = Get-PlaybookFileCount -PlaybooksRoot (Join-Path $assetRoot "playbooks")
    if ($bundledPlaybooks -ne $expectedPlaybooks) {
        throw ("Bundled playbook count mismatch: expected {0}, found {1}" -f $expectedPlaybooks, $bundledPlaybooks)
    }

    $expectedScripts = Get-PsScriptFileCount -ScriptsRoot (Join-Path $RepoRoot "powershell_scripts")
    $bundledScripts = Get-PsScriptFileCount -ScriptsRoot (Join-Path $assetRoot "powershell_scripts")
    if ($bundledScripts -ne $expectedScripts) {
        throw ("Bundled PowerShell script count mismatch: expected {0}, found {1}" -f $expectedScripts, $bundledScripts)
    }

    Write-Host ""
    Write-Host "=== Running Isolated Out-of-Repo Frozen Smoke Test ===" -ForegroundColor Cyan
    $appSandbox = Join-Path ([System.IO.Path]::GetTempPath()) ("GuideIT_App_" + [System.Guid]::NewGuid().ToString("N"))
    $copiedBundleDir = Join-Path $appSandbox "GuideIT_Master"
    $copiedExe = Join-Path $copiedBundleDir "GuideIT_Master.exe"

    $smokeTemp = Join-Path ([System.IO.Path]::GetTempPath()) ("GuideIT_Smoke_" + [System.Guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $appSandbox -Force
    $null = New-Item -ItemType Directory -Path $smokeTemp -Force
    Copy-Item -LiteralPath $distBundleDir -Destination $copiedBundleDir -Recurse -Force

    $smokeUserScripts = Join-Path $smokeTemp "user_scripts"
    $null = New-Item -ItemType Directory -Path $smokeUserScripts -Force
    $smokeScriptPath = Join-Path $smokeUserScripts "Smoke-CustomOverlay.ps1"
    $smokeScriptBody = @'
<#
.SYNOPSIS
    Smoke test user overlay diagnostic script.
.PSSTORE_META
    {
        "title": "Smoke Custom Overlay Script",
        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 15,
        "output_mode": "json",
        "params": []
    }
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$status = 'pass'
$errors = @()
$results = @()
try {
    $results = @([PSCustomObject]@{ Check = 'SmokeOverlay'; Status = 'OK' })
    $results | Format-Table -AutoSize | Out-String -Width 4096 | Write-Output
}
catch {
    $status = 'error'
    $errors += $_.Exception.Message
}
finally {
    [PSCustomObject]@{
        status = $status
        summary = 'Smoke overlay verified'
        data = @($results)
        errors = @($errors)
    } | ConvertTo-Json -Depth 4 -Compress
}
'@
    Set-Content -LiteralPath $smokeScriptPath -Value $smokeScriptBody -Encoding UTF8

    $hadDataDir = Test-Path Env:GUIDEIT_DATA_DIR
    $origDataDir = if ($hadDataDir) { $env:GUIDEIT_DATA_DIR } else { $null }
    $hadBundleDir = Test-Path Env:GUIDEIT_BUNDLE_DIR
    $origBundleDir = if ($hadBundleDir) { $env:GUIDEIT_BUNDLE_DIR } else { $null }
    $hadQtPlatform = Test-Path Env:QT_QPA_PLATFORM
    $origQtPlatform = if ($hadQtPlatform) { $env:QT_QPA_PLATFORM } else { $null }

    try {
        $env:GUIDEIT_DATA_DIR = $smokeTemp
        $env:QT_QPA_PLATFORM = "offscreen"
        if ($hadBundleDir) {
            Remove-Item Env:GUIDEIT_BUNDLE_DIR
        }

        $proc = Start-Process -FilePath $copiedExe -WorkingDirectory $appSandbox -ArgumentList @("--smoke-test") -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            throw ("Frozen smoke test exited with code {0}." -f $proc.ExitCode)
        }

        $smokeGuideItDb = Join-Path $smokeTemp "guideit.db"
        $smokePsDb = Join-Path $smokeTemp "powershell_store.db"
        $smokeLogFile = Join-Path (Join-Path $smokeTemp "logs") "guideit_master.log"
        $smokeJsonFile = Join-Path $smokeTemp "smoke_test_result.json"

        foreach ($expectedFile in @($smokeGuideItDb, $smokePsDb, $smokeLogFile, $smokeJsonFile)) {
            if (-not (Test-Path -LiteralPath $expectedFile)) {
                throw ("Frozen smoke test did not generate expected file: {0}" -f $expectedFile)
            }
        }

        $payload = Get-Content -LiteralPath $smokeJsonFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $payload.ok) {
            throw ("Frozen smoke test reported failure: {0}" -f ($payload.errors -join "; "))
        }
        if (-not $payload.frozen) {
            throw "Frozen smoke test did not report frozen=true."
        }
        $resolvedBundlePath = [System.IO.Path]::GetFullPath([string]$payload.bundle_dir)
        $expectedSandboxPrefix = [System.IO.Path]::GetFullPath($copiedBundleDir)
        if (-not $resolvedBundlePath.StartsWith($expectedSandboxPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw ("Frozen bundle resolved outside sandbox! bundle_dir={0}, expected prefix={1}" -f $resolvedBundlePath, $expectedSandboxPrefix)
        }
        if ([int]$payload.playbook_count -ne $expectedPlaybooks) {
            throw ("Expected {0} playbooks in frozen bundle, got {1}" -f $expectedPlaybooks, $payload.playbook_count)
        }
        if ([int]$payload.script_count -ne ($expectedScripts + 1)) {
            throw ("Expected {0} scripts ({1} bundled + 1 smoke overlay), got {2}" -f ($expectedScripts + 1), $expectedScripts, $payload.script_count)
        }
        if ([int]$payload.user_script_count -lt 1) {
            throw ("Expected >= 1 user_scripts overlay entry, got {0}" -f $payload.user_script_count)
        }
        if (-not $payload.unified_search_ok -or -not $payload.split_view_ok) {
            throw "Frozen smoke test search or Split View check failed."
        }
        if (-not $payload.markdown_render_ok -or -not $payload.rmm_clipboard_ok) {
            throw "Frozen smoke test Markdown rendering or RMM clipboard check failed."
        }

        $postGuideItTime = Get-FileTimestampSnapshot -Path $liveGuideItDb
        $postPsStoreTime = Get-FileTimestampSnapshot -Path $livePsStoreDb
        if ($preGuideItTime -ne $postGuideItTime) {
            throw "Live data/guideit.db was modified during frozen smoke test!"
        }
        if ($prePsStoreTime -ne $postPsStoreTime) {
            throw "Live data/powershell_store.db was modified during frozen smoke test!"
        }

        Write-Host ("Out-of-repo smoke test passed: playbooks={0}, scripts={1} (user={2}), bundle_dir={3}" -f $payload.playbook_count, $payload.script_count, $payload.user_script_count, $payload.bundle_dir) -ForegroundColor Green
    }
    finally {
        if ($hadDataDir) { $env:GUIDEIT_DATA_DIR = $origDataDir } else { Remove-Item Env:GUIDEIT_DATA_DIR -ErrorAction SilentlyContinue }
        if ($hadBundleDir) { $env:GUIDEIT_BUNDLE_DIR = $origBundleDir } else { Remove-Item Env:GUIDEIT_BUNDLE_DIR -ErrorAction SilentlyContinue }
        if ($hadQtPlatform) { $env:QT_QPA_PLATFORM = $origQtPlatform } else { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
        if (Test-Path -LiteralPath $appSandbox) {
            Remove-Item -LiteralPath $appSandbox -Recurse -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $smokeTemp) {
            Remove-Item -LiteralPath $smokeTemp -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    $bundleBytes = (Get-ChildItem -LiteralPath $distBundleDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
    $bundleSizeMB = [math]::Round(($bundleBytes / 1MB), 2)

    $appVersion = Get-AppVersion -RootDir $RepoRoot
    $zipPath = Join-Path $distDir ("GuideIT_Master-v{0}-win64.zip" -f $appVersion)
    $shaPath = "$zipPath.sha256"
    $zipSizeMB = 0
    if (-not $NoZip) {
        if (Test-Path -LiteralPath $zipPath) {
            Remove-Item -LiteralPath $zipPath -Force
        }
        if (Test-Path -LiteralPath $shaPath) {
            Remove-Item -LiteralPath $shaPath -Force
        }
        Add-Type -AssemblyName System.IO.Compression
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory(
            $distBundleDir,
            $zipPath,
            [System.IO.Compression.CompressionLevel]::Optimal,
            $true
        )
        $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        Set-Content -LiteralPath $shaPath -Value ("{0}  {1}" -f $zipHash, (Split-Path -Leaf $zipPath)) -Encoding ASCII
        $zipSizeMB = [math]::Round(((Get-Item -LiteralPath $zipPath).Length / 1MB), 2)
    }

    Write-Host ""
    Write-Host "=== Release Packaging Summary ===" -ForegroundColor Cyan
    Write-Host ("Bundled Output : {0} ({1} MB)" -f $distBundleDir, $bundleSizeMB) -ForegroundColor Green
    Write-Host ("Bundled Corpus : {0} playbooks (.md), {1} scripts (.ps1)" -f $bundledPlaybooks, $bundledScripts) -ForegroundColor Green
    if (-not $NoZip) {
        Write-Host ("Release Zip    : {0} ({1} MB)" -f $zipPath, $zipSizeMB) -ForegroundColor Green
        Write-Host ("SHA-256 File   : {0}" -f $shaPath) -ForegroundColor Green
    }
    $warnFile = Join-Path (Join-Path $buildDir "guideit_master") "warn-guideit_master.txt"
    if (Test-Path -LiteralPath $warnFile) {
        $warnCount = @(Get-Content -LiteralPath $warnFile).Count
        Write-Host ("PyInstaller Warn Log: {0} ({1} lines)" -f $warnFile, $warnCount) -ForegroundColor DarkGray
    }
}

Write-Host ("GuideIT Master Build Pipeline (PowerShell {0})" -f $PSVersionTable.PSVersion) -ForegroundColor White
Write-Host ("Using Python: {0}" -f $PythonExe) -ForegroundColor DarkGray
Invoke-VerificationSuite

if ($Package) {
    Invoke-PackageBuildAndSmokeTest
}

Write-Host ""
Write-Host "Build pipeline completed successfully." -ForegroundColor Green
exit 0
