#!/bin/bash
# Erstellt ein .deb-Paket für LinBurn
# Verwendung: bash packaging/build_deb.sh
# Ergebnis: linburn_1.0.0_amd64.deb im aktuellen Verzeichnis

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="1.0.0"
ARCH="amd64"
PKG_NAME="linburn"
PKG_DIR="/tmp/linburn_pkg"
INSTALL_DIR="/usr/lib/linburn"

echo "=== LinBurn .deb Build ==="
echo "Version: $VERSION"
echo "Quellverzeichnis: $SCRIPT_DIR"
echo ""

# Clean previous build
rm -rf "$PKG_DIR"

# Create directory structure
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR${INSTALL_DIR}"
mkdir -p "$PKG_DIR/usr/local/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/256x256/apps"

# Copy application files
echo "Kopiere Anwendungsdateien..."
cp -r "$SCRIPT_DIR/main.py" "$PKG_DIR${INSTALL_DIR}/"
cp -r "$SCRIPT_DIR/core"    "$PKG_DIR${INSTALL_DIR}/"
cp -r "$SCRIPT_DIR/gui"     "$PKG_DIR${INSTALL_DIR}/"
cp    "$SCRIPT_DIR/requirements.txt" "$PKG_DIR${INSTALL_DIR}/"

# Copy icon
if [ -f "$SCRIPT_DIR/packaging/flatpak/io.github.linburn.LinBurn.png" ]; then
    cp "$SCRIPT_DIR/packaging/flatpak/io.github.linburn.LinBurn.png" \
       "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/linburn.png"
fi

# Create launcher script
cat > "$PKG_DIR/usr/local/bin/linburn" << 'EOF'
#!/bin/bash
exec sudo python3 /usr/lib/linburn/main.py "$@"
EOF
chmod 755 "$PKG_DIR/usr/local/bin/linburn"

# Create desktop entry
cat > "$PKG_DIR/usr/share/applications/linburn.desktop" << EOF
[Desktop Entry]
Name=LinBurn
Comment=Bootbaren USB-Stick erstellen
Exec=linburn
Icon=linburn
Terminal=false
Type=Application
Categories=Utility;System;
Keywords=USB;Boot;ISO;Flash;
EOF

# Create DEBIAN/control
cat > "$PKG_DIR/DEBIAN/control" << EOF
Package: linburn
Version: ${VERSION}
Architecture: ${ARCH}
Maintainer: LinBurn <linburn@github.com>
Depends: python3 (>= 3.10), python3-pyqt6 | python3-pip, parted, dosfstools, ntfs-3g, e2fsprogs, rsync
Recommends: syslinux, grub2-common, grub-efi-amd64, wimtools
Section: utils
Priority: optional
Description: Bootbaren USB-Stick erstellen (Linux)
 LinBurn erstellt bootbare USB-Sticks aus ISO-Abbildern.
 Unterstützt Windows 11 mit TPM/SecureBoot-Bypass, ISO-Modus,
 DD-Modus, FAT32/NTFS-Formatierung und Bad-Block-Prüfung.
EOF

# Create DEBIAN/postinst (install Python dependencies)
cat > "$PKG_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e
pip3 install pyudev PyQt6 --quiet --break-system-packages 2>/dev/null \
    || pip3 install pyudev PyQt6 --quiet || true
echo "LinBurn installiert. Starten mit: linburn"
EOF
chmod 755 "$PKG_DIR/DEBIAN/postinst"

# Set permissions
find "$PKG_DIR" -type d -exec chmod 755 {} \;
find "$PKG_DIR" -type f -exec chmod 644 {} \;
chmod 755 "$PKG_DIR/usr/local/bin/linburn"
chmod 755 "$PKG_DIR/DEBIAN/postinst"

# Build the .deb
OUTPUT="${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo ""
echo "Erstelle ${OUTPUT}..."
dpkg-deb --build --root-owner-group "$PKG_DIR" "$SCRIPT_DIR/${OUTPUT}"

echo ""
echo "=== Fertig ==="
echo "Paket: ${SCRIPT_DIR}/${OUTPUT}"
echo ""
echo "Installieren mit:"
echo "  sudo dpkg -i ${OUTPUT}"
echo "  sudo apt install -f   # Falls Abhängigkeiten fehlen"
