# WavLoopInspector.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

APP_NAME = "WavLoopInspector"
MAIN     = "_main.py"              # エントリ
ICON_WIN = "icon.ico"
ICON_MAC = "icon.icns"

# ---- 解析 ----
a = Analysis(
    [MAIN],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---- EXE（両OS共通）。macはあとでBUNDLEで包む ----
is_mac = (sys.platform == "darwin")
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name = (APP_NAME if is_mac else "wavloop_inspect"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console = (not is_mac),                # macはコンソール非表示
    icon    = (ICON_MAC if is_mac else ICON_WIN),
    argv_emulation = is_mac,               # macのD&D／OpenDocumentをargv化
)

# ---- macOS: .appバンドル化（D&D安定のためのInfo.plist込み）----
if is_mac:
    app = BUNDLE(
        exe,
        name=f"{APP_NAME}.app",
        icon=ICON_MAC,
        bundle_identifier="site.dodoneko.wavloop",
        info_plist={
            "CFBundleName": APP_NAME,
            "NSHighResolutionCapable": True,
            # ここがFinderに「.wav扱えるよ」を知らせる鍵
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "WAVE audio",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Default",
                # UTI: WAV（+保険でpublic.audio）
                "LSItemContentTypes": ["com.microsoft.waveform-audio", "public.audio"],
                "CFBundleTypeExtensions": ["wav", "wave"],
            }],
        },
    )
 }],
    },
)
