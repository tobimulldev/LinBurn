# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for LinBurn Windows .exe
# Run from repo root: pyinstaller packaging/windows/linburn.spec

import os

block_cipher = None

# Repo root is two levels up from this spec file
REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))


a = Analysis(
    [os.path.join(REPO_ROOT, "main.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[
        (os.path.join(REPO_ROOT, "Assets"), "Assets"),
    ],
    hiddenimports=[
        # PyQt6 — some sub-modules are not auto-detected
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        # LinBurn core modules
        "core.platform.windows",
        "core.device_manager",
        "core.formatter",
        "core.usb_writer",
        "core.bootloader",
        "core.bad_block_checker",
        "core.iso_analyzer",
        "core.windows_patches",
        "gui.main_window",
        "gui.translations",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude Linux-only packages
    excludes=["pyudev"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="LinBurn",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,                 # embed requireAdministrator manifest
    icon=os.path.join(REPO_ROOT, "Assets", "icon.ico"),
)
