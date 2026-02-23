"""
ISO image analysis: detects boot capability, UEFI support, Windows version, etc.
Linux:   mount -o loop,ro + isoinfo fallback
Windows: PowerShell Mount-DiskImage (via core.platform.windows)
"""
import os
import subprocess
import sys
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
        if sys.platform == "win32":
            cls._check_contents_windows(path, info)
            return

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
    def _check_contents_windows(cls, path: str, info: IsoInfo):
        """Windows: mount ISO via Mount-DiskImage and inspect contents."""
        from core.platform.windows import inspect_iso_contents_win, unmount_iso_win
        mounted = False
        try:
            result = inspect_iso_contents_win(path)
            mount_letter = result.get("mount_letter")
            mounted = mount_letter is not None

            if result.get("has_efi"):
                info.has_uefi = True
                info.is_bootable = True
            if result.get("has_isolinux"):
                info.has_bios_boot = True
                info.is_bootable = True
            if result.get("is_windows"):
                info.is_windows = True
                info.is_bootable = True
                if mount_letter:
                    info.is_windows11 = cls._is_windows11(mount_letter)
        except Exception:
            pass  # mounting failed; fall back to direct ISO reading below
        finally:
            if mounted:
                try:
                    unmount_iso_win(path)
                except Exception:
                    pass

        # ── Fallback: read ISO 9660 directory without mounting ──────────────
        # Covers the case where Mount-DiskImage failed (e.g. path with spaces,
        # insufficient rights, or ISO already mounted).
        if not info.is_windows:
            for wim_rel in ("sources/install.wim", "sources/install.esd"):
                if cls._iso_find_file(path, wim_rel) is not None:
                    info.is_windows = True
                    info.is_bootable = True
                    break
            if info.is_windows:
                if (cls._iso_find_file(path, "efi") is not None or
                        cls._iso_find_file(path, "EFI") is not None):
                    info.has_uefi = True

        # ── Win11 detection fallback: parse WIM XML directly from ISO ───────
        if info.is_windows and not info.is_windows11:
            info.is_windows11 = cls._detect_win11_from_iso_direct(path)

    @classmethod
    def _is_windows11(cls, mount_point: str) -> bool:
        """Detect Windows 11 by checking WIM metadata."""
        if sys.platform == "win32":
            return cls._is_windows11_win(mount_point)

        # Linux: wiminfo from wimtools package
        try:
            result = subprocess.run(
                ["wiminfo", os.path.join(mount_point, "sources", "install.wim")],
                capture_output=True, text=True, timeout=10
            )
            if "windows 11" in result.stdout.lower():
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Linux fallback: MediaMeta.xml
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
    def _is_windows11_win(cls, mount_letter: str) -> bool:
        """Detect Windows 11 on Windows using DISM + PE version fallback."""
        from core.platform.windows import _NO_WINDOW

        # Method 1: DISM /get-wiminfo (always available on Windows 10/11)
        for wim_name in ("install.wim", "install.esd"):
            wim = os.path.join(mount_letter, "sources", wim_name)
            if os.path.exists(wim):
                try:
                    r = subprocess.run(
                        ["dism", "/get-wiminfo", f"/wimfile:{wim}"],
                        capture_output=True, text=True, timeout=30,
                        creationflags=_NO_WINDOW,
                    )
                    if "windows 11" in r.stdout.lower():
                        return True
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
                break  # found the wim file, no need to check esd too

        # Method 2: Read setup.exe PE version via ctypes
        # Windows 11 build number >= 22000
        setup = os.path.join(mount_letter, "setup.exe")
        if os.path.exists(setup):
            try:
                build = cls._get_pe_build_win(setup)
                if build is not None and build >= 22000:
                    return True
            except Exception:
                pass

        # Method 3: MediaMeta.xml text heuristic
        media_meta = os.path.join(mount_letter, "MediaMeta.xml")
        if os.path.exists(media_meta):
            try:
                with open(media_meta, "r", errors="replace") as f:
                    content = f.read().lower()
                if "windows 11" in content or "22000" in content:
                    return True
            except OSError:
                pass

        return False

    @staticmethod
    def _get_pe_build_win(exe_path: str):
        """Return the build number from a PE file's VS_FIXEDFILEINFO (Windows only)."""
        import ctypes
        import ctypes.wintypes

        ver = ctypes.windll.version
        size = ver.GetFileVersionInfoSizeW(exe_path, None)
        if not size:
            return None

        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(exe_path, 0, size, buf):
            return None

        lp = ctypes.c_void_p()
        n = ctypes.c_uint()
        if not ver.VerQueryValueW(buf, "\\", ctypes.byref(lp), ctypes.byref(n)):
            return None

        # VS_FIXEDFILEINFO: dwFileVersionLS at offset 12
        # build number = high word of LS (e.g. 22000 for Win11)
        ls = ctypes.c_uint32.from_address(lp.value + 12).value
        return ls >> 16

    # ── Pure-Python ISO 9660 helpers ─────────────────────────────────────────

    @classmethod
    def _iso_find_file(cls, iso_path: str, rel_path: str):
        """
        Locate a file inside an ISO 9660 image without mounting.
        rel_path: forward-slash separated, case-insensitive (e.g. "sources/install.wim")
        Returns (byte_offset, size) tuple or None if not found.
        """
        SECTOR = 2048
        parts = [p.upper().encode("ascii") for p in rel_path.split("/")]
        try:
            with open(iso_path, "rb") as f:
                # Primary Volume Descriptor at sector 16
                f.seek(16 * SECTOR)
                pvd = f.read(SECTOR)
                if len(pvd) < 190 or pvd[1:6] != b"CD001":
                    return None

                # Root directory: sector at PVD[158:162], size at PVD[166:170]
                dir_sector = int.from_bytes(pvd[158:162], "little")
                dir_size   = int.from_bytes(pvd[166:170], "little")

                for i, target in enumerate(parts):
                    f.seek(dir_sector * SECTOR)
                    dir_data = f.read(dir_size)
                    found = False
                    pos = 0
                    while pos < len(dir_data):
                        dr_len = dir_data[pos]
                        if dr_len == 0:
                            # Padding to next sector boundary
                            pos = ((pos // SECTOR) + 1) * SECTOR
                            continue
                        if pos + dr_len > len(dir_data):
                            break
                        name_len   = dir_data[pos + 32]
                        raw_name   = dir_data[pos + 33: pos + 33 + name_len]
                        name       = raw_name.split(b";")[0].upper()
                        is_dir     = bool(dir_data[pos + 25] & 0x02)
                        e_sector   = int.from_bytes(dir_data[pos + 2:pos + 6],   "little")
                        e_size     = int.from_bytes(dir_data[pos + 10:pos + 14], "little")
                        if name == target:
                            if i == len(parts) - 1:          # last component → file
                                return (e_sector * SECTOR, e_size)
                            elif is_dir:                     # intermediate dir → descend
                                dir_sector, dir_size = e_sector, e_size
                                found = True
                                break
                        pos += dr_len
                    if not found and i < len(parts) - 1:
                        return None  # intermediate directory not found
        except OSError:
            return None
        return None

    @classmethod
    def _detect_win11_from_iso_direct(cls, iso_path: str) -> bool:
        """
        Detect Windows 11 by reading install.wim/esd directly from the ISO
        without mounting. Parses ISO 9660 directory and WIM header to reach
        the uncompressed XML metadata section, then searches for "Windows 11".
        """
        for wim_rel in ("sources/install.wim", "sources/install.esd"):
            loc = cls._iso_find_file(iso_path, wim_rel)
            if loc is None:
                continue
            wim_iso_offset, wim_size = loc
            try:
                with open(iso_path, "rb") as f:
                    # Read first 96 bytes of the WIM file (header through XML descriptor)
                    f.seek(wim_iso_offset)
                    header = f.read(96)
                    if len(header) < 96 or header[:8] != b"MSWIM\x00\x00\x00":
                        continue

                    # WIM XML data resource descriptor starts at header offset 72
                    # Layout (24 bytes): [size+flags: 8][offset: 8][original_size: 8]
                    size_flags   = int.from_bytes(header[72:80], "little")
                    compressed   = size_flags & ((1 << 56) - 1)   # bits 0-55
                    flags        = (size_flags >> 56) & 0xFF       # bits 56-63
                    xml_rel_off  = int.from_bytes(header[80:88], "little")
                    xml_orig_sz  = int.from_bytes(header[88:96], "little")

                    # Only handle uncompressed XML (flags == 0); ESD uses LZMS
                    if flags != 0 or xml_rel_off == 0 or xml_orig_sz == 0:
                        continue

                    read_sz = min(xml_orig_sz, compressed, 2 * 1024 * 1024)
                    f.seek(wim_iso_offset + xml_rel_off)
                    xml_data = f.read(read_sz)

                    # WIM XML is UTF-16LE; search for "Windows 11"
                    if "Windows 11".encode("utf-16-le") in xml_data:
                        return True
            except OSError:
                continue
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
