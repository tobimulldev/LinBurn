#!/usr/bin/env python3
"""
LinBurn für Linux
Erstellt bootbare USB-Sticks aus ISO-Abbildern.

Verwendung:
    sudo python3 main.py

Root-Rechte sind erforderlich für:
- Geräte-Zugriff (/dev/sdX)
- Partitionierung (parted)
- Formatierung (mkfs)
- Bootloader-Installation (syslinux, grub)
- ISO-Mounting (mount)
"""
import os
import sys


def check_root():
    """Ensure the program runs with root privileges."""
    if os.geteuid() != 0:
        print("Fehler: LinBurn muss als root (sudo) ausgeführt werden.")
        print("Starte neu mit sudo...")
        args = [sys.executable] + sys.argv
        os.execvp("sudo", ["sudo"] + args)
        sys.exit(1)


def check_dependencies():
    """Check for required system tools."""
    import shutil
    missing = []
    required = {
        "parted": "parted",
        "mkfs.fat": "dosfstools",
        "mkfs.ntfs": "ntfs-3g",
        "syslinux": "syslinux",
        "badblocks": "e2fsprogs",
    }
    warnings = []
    for cmd, pkg in required.items():
        if not shutil.which(cmd):
            warnings.append(f"  {cmd} (Paket: {pkg})")

    if warnings:
        print("Warnung: Folgende optionale Tools fehlen:")
        for w in warnings:
            print(w)
        print("Installieren mit: sudo apt install " +
              " ".join(set(required[k.split()[0]] for k in warnings
                           if k.split()[0] in required)))
        print()


def main():
    check_root()

    # Import Qt only after root check to avoid display issues
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from PyQt6.QtCore import Qt

    check_dependencies()

    app = QApplication(sys.argv)
    app.setApplicationName("LinBurn")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("LinBurn")

    # Set application style
    app.setStyle("Fusion")

    from gui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
