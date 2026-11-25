# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for GuideIT Master (onedir Windows desktop bundle)."""

from __future__ import annotations

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

BUNDLED_DATA_DIRS = [
    ("playbooks", "playbooks"),
    ("powershell_scripts", "powershell_scripts"),
    ("taxonomy", "taxonomy"),
    ("templates", "templates"),
    ("docs", "docs"),
]

EXCLUDED_ROOT_DIRS = (
    "data",
    "_ref_GuideIT",
    "_ref_PowerShellStore",
    "tests",
)

SPEC_ROOT = Path(SPECPATH).resolve()

for _src_rel, _dst_rel in BUNDLED_DATA_DIRS:
    if _src_rel in EXCLUDED_ROOT_DIRS or _dst_rel in EXCLUDED_ROOT_DIRS:
        raise RuntimeError(f"Forbidden directory in BUNDLED_DATA_DIRS: {_src_rel}")
    if not (SPEC_ROOT / _src_rel).is_dir():
        raise FileNotFoundError(
            f"Required bundled asset directory missing: {SPEC_ROOT / _src_rel}"
        )

datas = [(str(SPEC_ROOT / src_rel), dst_rel) for src_rel, dst_rel in BUNDLED_DATA_DIRS]

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "shiboken6",
    "sqlite3",
    "_sqlite3",
    "winreg",
    "ctypes",
    "ctypes.wintypes",
    "guideit_master.main",
    *collect_submodules("guideit_master"),
]

excludes = [
    # Test tooling, packager internals & unused stdlib modules
    "pytest",
    "_pytest",
    "pluggy",
    "PyInstaller",
    "pyinstaller",
    "Pygments",
    "pygments",
    "tkinter",
    "unittest",
    "doctest",
    "pdb",
    # Unused heavy Qt6 / PySide6 submodules
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtHttpServer",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuick3D",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtCharts",
    "PySide6.QtGraphs",
    "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSerialBus",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
]

a = Analysis(
    [str(SPEC_ROOT / "main.py")],
    pathex=[str(SPEC_ROOT), str(SPEC_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GuideIT_Master",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GuideIT_Master",
)
