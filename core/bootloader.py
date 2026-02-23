"""
Bootloader installation for USB drives (Linux).
Syslinux (BIOS/MBR) + GRUB-EFI (UEFI).
"""
import os
import shutil
import subprocess
import glob as _glob
from typing import Optional


class BootloaderError(Exception):
    pass


class BootloaderInstaller:
    """Installs bootloaders on formatted USB partitions."""

    SYSLINUX_MBR_PATHS = [
        "/usr/lib/syslinux/mbr/mbr.bin",
        "/usr/lib/syslinux/mbr.bin",
        "/usr/share/syslinux/mbr.bin",
        "/usr/lib/SYSLINUX/mbr.bin",
    ]

    @classmethod
    def install(
        cls,
        device_path: str,
        partition_path: str,
        mount_point: str,
        target_system: str,
        scheme: str,
        log_callback=None,
    ):
        """
        Install appropriate bootloader.
        target_system: "BIOS" | "UEFI" | "BIOS+UEFI"
        """
        def log(msg):
            if log_callback:
                log_callback(msg)

        if target_system in ("BIOS", "BIOS+UEFI"):
            log("Installiere BIOS-Bootloader (Syslinux)...")
            try:
                cls._install_syslinux(device_path, partition_path, mount_point, log)
            except BootloaderError as e:
                log(f"Syslinux fehlgeschlagen, versuche GRUB-Legacy: {e}")
                cls._install_grub_bios(device_path, mount_point, log)

        if target_system in ("UEFI", "BIOS+UEFI"):
            log("Installiere UEFI-Bootloader...")
            cls._install_uefi(device_path, partition_path, mount_point, log)

    @classmethod
    def install_from_iso(
        cls,
        device_path: str,
        partition_path: str,
        mount_point: str,
        iso_mount: str,
        target_system: str,
        log_callback=None,
    ):
        """
        Try to use the bootloader bundled in the ISO first.
        Falls back to system-installed bootloaders.
        """
        def log(msg):
            if log_callback:
                log_callback(msg)

        efi_copied = False

        # Windows has its own bootloader — skip syslinux
        is_windows = (
            os.path.exists(os.path.join(iso_mount, "sources", "install.wim")) or
            os.path.exists(os.path.join(iso_mount, "sources", "install.esd"))
        )
        if is_windows:
            log("Windows-ISO erkannt: Verwende eingebetteten Bootloader (bootmgr/EFI).")
            return

        # Copy EFI directory from ISO if present
        iso_efi = os.path.join(iso_mount, "EFI")
        if os.path.isdir(iso_efi) and target_system in ("UEFI", "BIOS+UEFI"):
            dest_efi = os.path.join(mount_point, "EFI")
            if not os.path.exists(dest_efi):
                log("Kopiere EFI-Bootloader aus ISO...")
                shutil.copytree(iso_efi, dest_efi)
                efi_copied = True

        if target_system in ("BIOS", "BIOS+UEFI"):
            iso_isolinux = os.path.join(iso_mount, "isolinux")
            if os.path.isdir(iso_isolinux):
                log("Konvertiere isolinux zu syslinux...")
                cls._convert_isolinux_to_syslinux(iso_mount, mount_point, log)
                cls._install_syslinux(device_path, partition_path, mount_point, log)
            else:
                cls._install_syslinux(device_path, partition_path, mount_point, log)

        if not efi_copied and target_system in ("UEFI", "BIOS+UEFI"):
            cls._install_uefi(device_path, partition_path, mount_point, log)

    @classmethod
    def _install_syslinux(
        cls, device_path: str, partition_path: str, mount_point: str, log
    ):
        result = subprocess.run(
            ["syslinux", "--install", partition_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise BootloaderError(f"syslinux: {result.stderr.strip()}")

        mbr_bin = cls._find_syslinux_mbr()
        if mbr_bin:
            log(f"Schreibe Syslinux MBR von {mbr_bin}...")
            result2 = subprocess.run(
                ["dd", f"if={mbr_bin}", f"of={device_path}",
                 "bs=440", "count=1", "conv=notrunc"],
                capture_output=True, text=True
            )
            if result2.returncode != 0:
                log(f"Warnung: MBR schreiben fehlgeschlagen: {result2.stderr.strip()}")
        else:
            log("Warnung: Syslinux MBR nicht gefunden, überspringe...")

        cls._copy_syslinux_modules(mount_point, log)

    @classmethod
    def _install_grub_bios(cls, device_path: str, mount_point: str, log):
        result = subprocess.run(
            ["grub-install",
             "--target=i386-pc",
             f"--boot-directory={mount_point}/boot",
             device_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise BootloaderError(f"grub-install (BIOS): {result.stderr.strip()}")

    @classmethod
    def _install_uefi(
        cls, device_path: str, partition_path: str, mount_point: str, log
    ):
        efi_dir = os.path.join(mount_point, "EFI", "BOOT")
        os.makedirs(efi_dir, exist_ok=True)

        result = subprocess.run(
            ["grub-install",
             "--target=x86_64-efi",
             "--no-nvram",
             f"--efi-directory={mount_point}",
             f"--boot-directory={mount_point}/boot",
             "--removable",
             device_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            log(f"Warnung: grub-install (UEFI): {result.stderr.strip()}")
            cls._install_uefi_fallback(mount_point, log)

    @classmethod
    def _install_uefi_fallback(cls, mount_point: str, log):
        log("Versuche alternativen UEFI-Bootloader...")
        efi_paths = [
            "/usr/lib/grub/x86_64-efi/grub.efi",
            "/usr/lib/grub/grub.efi",
        ]
        efi_boot_dir = os.path.join(mount_point, "EFI", "BOOT")
        os.makedirs(efi_boot_dir, exist_ok=True)
        for src in efi_paths:
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(efi_boot_dir, "BOOTX64.EFI"))
                log("EFI-Binary kopiert.")
                return
        log("Warnung: Kein UEFI-EFI-Binary gefunden.")

    @classmethod
    def _convert_isolinux_to_syslinux(cls, iso_mount: str, usb_mount: str, log):
        iso_isolinux = os.path.join(iso_mount, "isolinux")
        usb_syslinux = os.path.join(usb_mount, "syslinux")
        os.makedirs(usb_syslinux, exist_ok=True)

        for item in os.listdir(iso_isolinux):
            src = os.path.join(iso_isolinux, item)
            dst_name = "syslinux.cfg" if item.lower() == "isolinux.cfg" else item
            dst = os.path.join(usb_syslinux, dst_name)
            if os.path.isfile(src):
                shutil.copy2(src, dst)

    @classmethod
    def _find_syslinux_mbr(cls) -> Optional[str]:
        for path in cls.SYSLINUX_MBR_PATHS:
            if os.path.exists(path):
                return path
        matches = _glob.glob("/usr/**/mbr.bin", recursive=True)
        if matches:
            return matches[0]
        return None

    @classmethod
    def _copy_syslinux_modules(cls, mount_point: str, log):
        required_modules = ["ldlinux.c32", "libcom32.c32", "libutil.c32", "menu.c32"]
        module_dirs = [
            "/usr/lib/syslinux/modules/bios",
            "/usr/share/syslinux",
            "/usr/lib/syslinux",
        ]
        dest_dir = os.path.join(mount_point, "syslinux")
        os.makedirs(dest_dir, exist_ok=True)

        for module in required_modules:
            for mod_dir in module_dirs:
                src = os.path.join(mod_dir, module)
                if os.path.exists(src):
                    shutil.copy2(src, dest_dir)
                    break
