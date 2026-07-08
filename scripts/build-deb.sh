#!/usr/bin/env bash
set -euo pipefail

APP_NAME="sysmon"
VERSION="${1:-0.1.0}"
ARCH="${2:-amd64}"
DIST_DIR="dist"
DEB_FILE="${DIST_DIR}/${APP_NAME}_${VERSION}_${ARCH}.deb"

echo "Building Linux .deb package..."

# Build with PyInstaller onefile mode
pyinstaller --onefile --name sysmon --strip --clean --noconfirm run.py

# Clean previous build
rm -rf "${DEB_FILE}"
mkdir -p "${DIST_DIR}"

# Create .deb directory structure
DEB_DIR="${DIST_DIR}/${APP_NAME}_${VERSION}_${ARCH}"
rm -rf "${DEB_DIR}"
mkdir -p "${DEB_DIR}/DEBIAN"
mkdir -p "${DEB_DIR}/usr/bin"
mkdir -p "${DEB_DIR}/usr/share/applications"

# Copy binary
cp "${DIST_DIR}/sysmon" "${DEB_DIR}/usr/bin/"

# Create control file
cat > "${DEB_DIR}/DEBIAN/control" << EOF
Package: ${APP_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: libc6 (>= 2.17), libgcc-s1 (>= 4.2)
Maintainer: sysmon developers <sysmon@example.com>
Description: Lightweight cross-platform system monitor
 Shows CPU, memory, disk, temperature, GPU, battery, and
 power usage in a terminal with a live-updating display.
 Zero external dependencies — pure Python stdlib.
EOF

# Create .desktop file
cat > "${DEB_DIR}/usr/share/applications/sysmon.desktop" << EOF
[Desktop Entry]
Type=Application
Name=sysmon
Comment=Lightweight system monitor
Exec=sysmon
Terminal=true
Categories=System;Monitor;
Keywords=system;monitor;cpu;memory;disk;
EOF

# Calculate installed size (in KB)
INSTALLED_SIZE=$(du -sk "${DEB_DIR}/usr" | cut -f1)
echo "Installed-Size: ${INSTALLED_SIZE}" >> "${DEB_DIR}/DEBIAN/control"

# Build the .deb
dpkg-deb --root-owner-group --build "${DEB_DIR}" "${DEB_FILE}"

echo "Created ${DEB_FILE}"
echo "Install with: sudo dpkg -i ${DEB_FILE}"
