#!/usr/bin/env bash
set -euo pipefail

APP_NAME="sysmon"
VERSION="${1:-0.1.0}"
DIST_DIR="dist"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"

echo "Building macOS .app bundle..."

# Build with PyInstaller onefile mode
pyinstaller --onefile --name sysmon --strip --clean --noconfirm run.py

# Clean previous .app bundle
rm -rf "${APP_BUNDLE}"

# Create .app directory structure
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"

# Copy the single-file binary
cp "${DIST_DIR}/sysmon" "${APP_BUNDLE}/Contents/MacOS/"

# Create Info.plist
cat > "${APP_BUNDLE}/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>sysmon</string>
    <key>CFBundleDisplayName</key>
    <string>sysmon</string>
    <key>CFBundleIdentifier</key>
    <string>com.sysmon.cli</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleExecutable</key>
    <string>sysmon</string>
</dict>
</plist>
EOF

echo "Created ${APP_BUNDLE}"
echo "Run with: open ${APP_BUNDLE}"
echo "Or directly: ${APP_BUNDLE}/Contents/MacOS/sysmon"
