#!/usr/bin/env bash
# build_macos.command
set -euo pipefail

APP_NAME="WavLoopInspector"
MAIN="_main.py"

python3 -m pip install --upgrade pip >/dev/null
python3 -m pip show pyinstaller >/dev/null || python3 -m pip install pyinstaller

rm -rf build "dist/${APP_NAME}.app" 2>/dev/null || true

# D&Dをargvに通す --argv-emulation はPyInstallerの正式機能
# appにWAVをドロップ→パスがsys.argvに入る
pyinstaller --onefile --windowed --clean \
  --argv-emulation \
  --osx-bundle-identifier site.dodoneko.wavloop \
  --name "${APP_NAME}" \
  --icon "icon.icns" \
  "${MAIN}"

echo "成功: dist/${APP_NAME}.app"
