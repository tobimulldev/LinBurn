#!/bin/bash
# LinBurn - Installations-Skript
# Installiert alle Abhängigkeiten für Ubuntu/Debian-basierte Systeme

set -e

echo "=== LinBurn Installation ==="
echo ""

# Check if running as root for apt
if [ "$EUID" -ne 0 ]; then
    echo "Für die Installation von Systempaketen werden Root-Rechte benötigt."
    echo "Starte mit sudo..."
    exec sudo bash "$0" "$@"
fi

# Detect package manager
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt-get"
    PKG_INSTALL="apt-get install -y"
    echo "Paketmanager: apt (Debian/Ubuntu)"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    PKG_INSTALL="dnf install -y"
    echo "Paketmanager: dnf (Fedora/RHEL)"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    PKG_INSTALL="pacman -S --noconfirm"
    echo "Paketmanager: pacman (Arch Linux)"
else
    echo "Warnung: Unbekannter Paketmanager. Bitte Abhängigkeiten manuell installieren."
    PKG_INSTALL=""
fi

# System dependencies
echo ""
echo "Installiere Systemabhängigkeiten..."

if [ "$PKG_MANAGER" = "apt-get" ]; then
    apt-get update -qq
    apt-get install -y \
        python3 \
        python3-pip \
        parted \
        dosfstools \
        ntfs-3g \
        exfatprogs \
        e2fsprogs \
        syslinux \
        syslinux-common \
        grub2-common \
        grub-efi-amd64 \
        rsync \
        genisoimage \
        udev \
        util-linux

    # wimtools is optional (for Windows 11 detection)
    apt-get install -y wimtools 2>/dev/null || true

elif [ "$PKG_MANAGER" = "dnf" ]; then
    dnf install -y \
        python3 \
        python3-pip \
        python3-qt6 \
        parted \
        dosfstools \
        ntfs-3g \
        exfatprogs \
        e2fsprogs \
        syslinux \
        grub2 \
        grub2-efi-x64 \
        rsync \
        genisoimage

elif [ "$PKG_MANAGER" = "pacman" ]; then
    pacman -S --noconfirm \
        python \
        python-pip \
        python-pyqt6 \
        parted \
        dosfstools \
        ntfs-3g \
        exfatprogs \
        e2fsprogs \
        syslinux \
        grub \
        rsync \
        cdrkit
fi

echo ""
echo "Installiere Python-Abhängigkeiten..."
# Use --break-system-packages for Ubuntu 23.04+ where pip is externally managed
pip3 install -r "$(dirname "$0")/requirements.txt" --quiet --break-system-packages 2>/dev/null \
    || pip3 install -r "$(dirname "$0")/requirements.txt" --quiet

echo ""
echo "Erstelle Desktop-Eintrag..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > /usr/share/applications/linburn.desktop << EOF
[Desktop Entry]
Name=LinBurn
Comment=Bootbaren USB-Stick erstellen
Exec=sudo python3 ${SCRIPT_DIR}/main.py
Icon=drive-removable-media
Terminal=false
Type=Application
Categories=Utility;System;
Keywords=USB;Boot;ISO;Flash;
EOF

echo ""
echo "Erstelle Starter-Skript in /usr/local/bin/linburn..."
cat > /usr/local/bin/linburn << EOF
#!/bin/bash
exec sudo python3 "${SCRIPT_DIR}/main.py" "\$@"
EOF
chmod +x /usr/local/bin/linburn

echo ""
echo "=== Installation abgeschlossen ==="
echo ""
echo "Starten mit:"
echo "  sudo python3 ${SCRIPT_DIR}/main.py"
echo "  oder: linburn"
echo ""
