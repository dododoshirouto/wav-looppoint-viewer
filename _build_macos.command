#!/usr/bin/env bash
# build_macos.command
set -euo pipefail

APP_NAME="WavLoopInspector"
MAIN="_main.py"

venv/bin/python3 -m pip install --upgrade pip >/dev/null
venv/bin/python3 -m pip show pyinstaller >/dev/null || venv/bin/python3 -m pip install pyinstaller

rm -rf build "dist/${APP_NAME}.app" 2>/dev/null || true

# D&Dをargvに通す --argv-emulation はPyInstallerの正式機能
# appにWAVをドロップ→パスがsys.argvに入る
venv/bin/pyinstaller WavLoopInspector.spec --clean

echo "成功: dist/${APP_NAME}.app"
