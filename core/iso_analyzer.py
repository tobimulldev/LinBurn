"""
ISO image analysis: detects boot capability, UEFI support, Windows version, etc.
"""
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional


@dataclass
class IsoInfo:
    path: str
    size_bytes: int = 0
    size_str: str = ""
    label: str = ""
    is_bootable: bool = False
    has_uefi: bool = False
    has_bios_boot: bool = False
    is_windows: bool = False
    is_windows11: bool = False
    recommended_fs: str = "FAT32"
    recommended_scheme: str = "MBR"
    error: Optional[str] = None


class IsoAnalyzer:
    """Analyzes ISO 9660 images to extract boot and system information."""

    # ISO 9660 Primary Volume Descriptor starts at sector 16 (offset 0x8000)
    PVD_OFFSET = 0x8000
    # El Torito boot catalog signature
    ELTORITO_SIG = b"CD001"

    @classmethod
    def analyze(cls, iso_path: str) -> IsoInfo:
        info = IsoInfo(path=iso_path)

        if not os.path.isfile(iso_path):
            info.error = f"Datei nicht gefunden: {iso_path}"
            return info

        info.size_bytes = os.path.getsize(iso_path)
        info.size_str = cls._format_size(info.size_bytes)

        try:
            cls._read_pvd(iso_path, info)
            cls._check_boot_records(iso_path, info)
            cls._check_contents(iso_path, info)
            cls._set_recommendations(info)
        except Exception as e:
            info.error = str(e)

        return info

    @classmethod
    def _read_pvd(cls, path: str, info: IsoInfo):
        """Read ISO 9660 Primary Volume Descriptor for label."""
        with open(path, "rb") as f:
            f.seek(cls.PVD_OFFSET)
            pvd = f.read(2048)

        if len(pvd) < 2048:
            return

        # Verify ISO signature
        if pvd[1:6] != cls.ELTORITO_SIG:
            return

        # Volume identifier is at offset 40, 32 bytes
        volume_id = pvd[40:72].decode("ascii", errors="replace").strip()
        info.label = volume_id if volume_id else "ISO"

    @classmethod
    def _check_boot_records(cls, path: str, info: IsoInfo):
        """Check for El Torito boot record (BIOS bootable) at sector 17."""
        with open(path, "rb") as f:
            f.seek(0x8800)  # Sector 17
            bvd = f.read(2048)

        if len(bvd) < 8:
            return

        # Boot Record Volume Descriptor type = 0
        if bvd[0] == 0 and bvd[1:6] == cls.ELTORITO_SIG:
            info.is_bootable = True
            info.has_bios_boot = True

    @classmethod
    def _check_contents(cls, path: str, info: IsoInfo):
        """Mount ISO and inspect directory structure."""
        mount_point = tempfile.mkdtemp(prefix="linburn_iso_")
        mounted = False
        try:
            result = subprocess.run(
                ["mount", "-o", "loop,ro", path, mount_point],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                # Try without root: use isoinfo
                cls._check_contents_isoinfo(path, info)
                return
            mounted = True

            # Check for EFI
            efi_paths = [
                os.path.join(mount_point, "EFI"),
                os.path.join(mount_point, "efi"),
                os.path.join(mount_point, "boot", "efi"),
            ]
            if any(os.path.isdir(p) for p in efi_paths):
                info.has_uefi = True
                info.is_bootable = True

            # Check for Windows
            sources = os.path.join(mount_point, "sources")
            if os.path.isdir(sources):
                install_wim = os.path.join(sources, "install.wim")
                install_esd = os.path.join(sources, "install.esd")
                if os.path.exists(install_wim) or os.path.exists(install_esd):
                    info.is_windows = True
                    info.is_bootable = True
                    # Try to detect Windows 11
                    info.is_windows11 = cls._is_windows11(mount_point)

            # Syslinux / isolinux → BIOS bootable Linux
            isolinux = os.path.join(mount_point, "isolinux")
            if os.path.isdir(isolinux):
                info.has_bios_boot = True
                info.is_bootable = True

        finally:
            if mounted:
                subprocess.run(["umount", mount_point], capture_output=True)
            try:
                os.rmdir(mount_point)
            except OSError:
                pass

    @classmethod
    def _check_contents_isoinfo(cls, path: str, info: IsoInfo):
        """Fallback: use isoinfo to list ISO contents without mounting."""
        try:
            result = subprocess.run(
                ["isoinfo", "-l", "-i", path],
                capture_output=True, text=True, timeout=15
            )
            listing = result.stdout.lower()
            if "efi" in listing:
                info.has_uefi = True
                info.is_bootable = True
            if "install.wim" in listing or "install.esd" in listing:
                info.is_windows = True
                info.is_bootable = True
            if "isolinux" in listing or "syslinux" in listing:
                info.has_bios_boot = True
                info.is_bootable = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    @classmethod
    def _is_windows11(cls, mount_point: str) -> bool:
        """Detect Windows 11 by checking WIM metadata."""
        # Check for win11 marker
        try:
            result = subprocess.run(
                ["wiminfo", os.path.join(mount_point, "sources", "install.wim")],
                capture_output=True, text=True, timeout=10
            )
            if "windows 11" in result.stdout.lower():
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check setup.exe version as fallback (Windows 11 setup is version 10.0.22xxx)
        setup = os.path.join(mount_point, "setup.exe")
        if os.path.exists(setup):
            try:
                result = subprocess.run(
                    ["exiftool", "-FileVersion", setup],
                    capture_output=True, text=True, timeout=5
                )
                version_line = result.stdout.strip()
                # Windows 11 build >= 22000
                if "22" in version_line:
                    return True
            except FileNotFoundError:
                pass

        # Heuristic: check MediaCreationTool or ProductVersion in media
        media_info = os.path.join(mount_point, "MediaMeta.xml")
        if os.path.exists(media_info):
            try:
                with open(media_info, "r", errors="replace") as f:
                    content = f.read().lower()
                if "windows 11" in content or "22000" in content:
                    return True
            except OSError:
                pass

        return False

    @classmethod
    def _set_recommendations(cls, info: IsoInfo):
        """Set recommended filesystem and partition scheme based on analysis."""
        if info.is_windows:
            if info.has_uefi:
                info.recommended_fs = "NTFS"
                info.recommended_scheme = "GPT"
            else:
                info.recommended_fs = "NTFS"
                info.recommended_scheme = "MBR"
        elif info.has_uefi and info.has_bios_boot:
            info.recommended_fs = "FAT32"
            info.recommended_scheme = "GPT"
        elif info.has_uefi:
            info.recommended_fs = "FAT32"
            info.recommended_scheme = "GPT"
        else:
            info.recommended_fs = "FAT32"
            info.recommended_scheme = "MBR"

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
