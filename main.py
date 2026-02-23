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
    """Ensure the program runs with administrator / root privileges."""
    if sys.platform == "win32":
        _check_admin_windows()
    else:
        _check_root_linux()


def _check_root_linux():
    if os.geteuid() != 0:
        print("Fehler: LinBurn muss als root (sudo) ausgeführt werden.")
        print("Starte neu mit sudo...")
        args = [sys.executable] + sys.argv
        os.execvp("sudo", ["sudo"] + args)
        sys.exit(1)


def _check_admin_windows():
    import ctypes
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin = False

    if not is_admin:
        # Re-launch with UAC elevation prompt
        try:
            params = " ".join(f'"{a}"' for a in sys.argv)
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, params, None, 1
            )
        except Exception as e:
            print(f"Fehler beim Starten mit Admin-Rechten: {e}")
        sys.exit(0)


def check_dependencies():
    """Check for required system tools (Linux only)."""
    if sys.platform == "win32":
        return  # All Windows tools are built-in (diskpart, format, DISM, etc.)

    import shutil
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
        missing_pkgs = " ".join(sorted({pkg for cmd, pkg in required.items()
                                        if not shutil.which(cmd)}))
        print(f"Installieren mit: sudo apt install {missing_pkgs}")
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
