"""
USB writing engine.
Handles DD mode (direct image write) and ISO mode (partition + format + copy + bootloader).
Runs as a QThread to keep the UI responsive.
"""
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.formatter import Formatter, FormatterError
from core.bootloader import BootloaderInstaller, BootloaderError
from core.windows_patches import WindowsPatcher
from core.device_manager import DeviceManager


@dataclass
class WriteConfig:
    """All parameters for a USB write operation."""
    iso_path: str
    device_path: str
    mode: str                    # "DD" | "ISO" | "FORMAT"
    scheme: str = "MBR"          # "MBR" | "GPT"
    target_system: str = "BIOS+UEFI"  # "BIOS" | "UEFI" | "BIOS+UEFI"
    filesystem: str = "FAT32"    # "FAT32" | "NTFS" | "exFAT" | "ext4"
    cluster_size: int = 0        # 0 = auto
    label: str = "LINBURN"
    quick_format: bool = True
    check_bad_blocks: bool = False
    # Windows 11 patches
    win_bypass_tpm: bool = False
    win_bypass_secureboot: bool = False
    win_bypass_ram: bool = False
    win_remove_online: bool = False


class UsbWriter(QThread):
    """
    Main USB writing thread.

    Signals:
        progress(int):    Overall progress 0-100
        status(str):      Short status message (shown in progress bar label)
        log(str):         Detailed log message
        finished_ok():    Completed successfully
        error(str):       Fatal error message
    """
    progress = pyqtSignal(int)       # Overall 0-100
    step_progress = pyqtSignal(int, int, str)  # (current_step, total_steps, step_name)
    status = pyqtSignal(str)
    log = pyqtSignal(str)
    finished_ok = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, config: WriteConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._abort = False

    def abort(self):
        self._abort = True
        if hasattr(self, "_current_proc") and self._current_proc:
            self._current_proc.terminate()

    def run(self):
        cfg = self.config
        try:
            if cfg.mode == "DD":
                self._run_dd()
            elif cfg.mode == "ISO":
                self._run_iso()
            elif cfg.mode == "FORMAT":
                self._run_format_only()
            else:
                self.error.emit(f"Unbekannter Modus: {cfg.mode}")
                return
        except Exception as e:
            self.error.emit(str(e))
            return

        if not self._abort:
            self.progress.emit(100)
            self.status.emit("Fertig")
            self.finished_ok.emit()

    # ------------------------------------------------------------------
    # DD Mode
    # ------------------------------------------------------------------

    def _run_dd(self):
        cfg = self.config
        self._log(f"DD-Modus: Schreibe {cfg.iso_path} → {cfg.device_path}")
        self._status("Unmounte Gerät...")

        DeviceManager.unmount_device(cfg.device_path)
        if self._abort:
            return

        iso_size = os.path.getsize(cfg.iso_path)
        self._log(f"ISO-Größe: {self._fmt_size(iso_size)}")
        self._status("Schreibe Image...")

        cmd = [
            "dd",
            f"if={cfg.iso_path}",
            f"of={cfg.device_path}",
            "bs=4M",
            "conv=fsync",
            "oflag=direct",
            "status=progress",
        ]

        self._current_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        bytes_written = 0
        for line in self._current_proc.stdout:
            if self._abort:
                self._current_proc.terminate()
                return

            line = line.strip()
            if not line:
                continue

            # dd progress: "12345678 bytes (12 MB, 12 MiB) copied, 1.5 s, 8.1 MB/s"
            match = re.search(r"^(\d+)\s+bytes", line)
            if match:
                bytes_written = int(match.group(1))
                if iso_size > 0:
                    pct = min(99, int(bytes_written / iso_size * 100))
                    self.progress.emit(pct)
                    speed_match = re.search(r"([\d.]+\s+[KMGT]B/s)", line)
                    speed = speed_match.group(1) if speed_match else ""
                    self._status(f"Schreibe... {self._fmt_size(bytes_written)}/{self._fmt_size(iso_size)} {speed}")
            else:
                self._log(line)

        self._current_proc.wait()
        if self._current_proc.returncode not in (0, None) and not self._abort:
            raise RuntimeError(f"dd beendet mit Fehlercode {self._current_proc.returncode}")

        self._log("DD-Schreibvorgang abgeschlossen.")

        # Sync
        self._status("Synchronisiere...")
        subprocess.run(["sync"], check=False)

    # ------------------------------------------------------------------
    # ISO Mode
    # ------------------------------------------------------------------

    # ISO mode step definitions: (name, overall_pct_start)
    _ISO_STEPS = [
        ("Gerät unmounten",       2),
        ("Partitionieren",        5),
        ("ISO einhängen",        18),
        ("USB einhängen",        22),
        ("Dateien kopieren",     25),
        ("Windows-Patches",      85),
        ("Bootloader",           90),
        ("Synchronisieren",      96),
    ]

    def _step(self, idx: int):
        """Emit step progress signal."""
        name = self._ISO_STEPS[idx][0]
        pct = self._ISO_STEPS[idx][1]
        self.step_progress.emit(idx + 1, len(self._ISO_STEPS), name)
        self._progress(pct)
        self._status(name + "...")

    def _run_iso(self):
        cfg = self.config
        iso_mount = None
        usb_mount = None

        try:
            # Step 1: Unmount
            self._step(0)
            self._log(f"Unmounte alle Partitionen von {cfg.device_path}...")
            DeviceManager.unmount_device(cfg.device_path)
            time.sleep(0.5)
            if self._abort:
                return

            # Step 3: Mount ISO early so we can detect Windows before partitioning
            self._step(2)
            iso_mount = tempfile.mkdtemp(prefix="linburn_iso_")
            result = subprocess.run(
                ["mount", "-o", "loop,ro", cfg.iso_path, iso_mount],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"ISO mounten fehlgeschlagen: {result.stderr.strip()}")
            self._log(f"ISO gemountet: {iso_mount}")

            # Detect Windows ISO
            install_wim = os.path.join(iso_mount, "sources", "install.wim")
            install_esd = os.path.join(iso_mount, "sources", "install.esd")
            is_windows = os.path.exists(install_wim) or os.path.exists(install_esd)

            # For Windows: always use FAT32 on a single partition so that
            # bootx64.efi, BCD and boot.wim are all on the same FAT32 volume
            # that UEFI firmware can read natively.
            # install.wim (>4 GB) will be split after copying.
            effective_fs = "FAT32" if is_windows else cfg.filesystem
            if is_windows and cfg.filesystem != "FAT32":
                self._log("Windows-ISO erkannt: Verwende FAT32 (UEFI-kompatibel, install.wim wird ggf. gesplittet).")

            # Step 2: Partition + Format
            self._step(1)
            try:
                partition = Formatter.format_device(
                    device_path=cfg.device_path,
                    scheme=cfg.scheme,
                    filesystem=effective_fs,
                    label=cfg.label,
                    cluster_size=cfg.cluster_size,
                    quick_format=cfg.quick_format,
                    log_callback=self._log,
                )
            except FormatterError as e:
                raise RuntimeError(f"Formatierung fehlgeschlagen: {e}")

            if self._abort:
                return

            # Step 4: Mount USB partition
            self._step(3)
            usb_mount = tempfile.mkdtemp(prefix="linburn_usb_")
            result = subprocess.run(
                ["mount", partition, usb_mount],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                raise RuntimeError(f"USB-Partition mounten fehlgeschlagen: {result.stderr.strip()}")
            self._log(f"USB gemountet: {usb_mount}")

            if self._abort:
                return

            # Step 5: Copy ISO contents
            # For Windows on FAT32: skip install.wim/install.esd during normal copy
            # (they may exceed FAT32's 4 GiB limit) — handled separately below.
            self._step(4)
            skip_for_split = set()
            if is_windows:
                for name in ("install.wim", "install.esd"):
                    src_wim = os.path.join(iso_mount, "sources", name)
                    if os.path.exists(src_wim) and os.path.getsize(src_wim) > self._FAT32_MAX:
                        skip_for_split.add(name)
                        self._log(f"{name} ({self._fmt_size(os.path.getsize(src_wim))}) > 4 GiB — wird separat gesplittet.")

            self._copy_iso_contents(iso_mount, usb_mount, skip_in_sources=skip_for_split)

            # Split and copy oversized install.wim/install.esd directly from ISO mount
            for name in skip_for_split:
                if self._abort:
                    return
                src_wim = os.path.join(iso_mount, "sources", name)
                dst_swm = os.path.join(usb_mount, "sources", name.replace(".wim", ".swm").replace(".esd", ".swm"))
                self._split_wim(src_wim, dst_swm)

            if self._abort:
                return

            # Step 6: Apply Windows patches if needed
            if cfg.win_bypass_tpm or cfg.win_bypass_secureboot or cfg.win_bypass_ram or cfg.win_remove_online:
                self._step(5)
                WindowsPatcher.apply(
                    usb_mount=usb_mount,
                    bypass_tpm=cfg.win_bypass_tpm,
                    bypass_secureboot=cfg.win_bypass_secureboot,
                    bypass_ram=cfg.win_bypass_ram,
                    remove_online_requirement=cfg.win_remove_online,
                    log_callback=self._log,
                )

            if self._abort:
                return

            # Step 7: Install bootloader
            self._step(6)
            self._status("Bootloader installieren...")
            try:
                BootloaderInstaller.install_from_iso(
                    device_path=cfg.device_path,
                    partition_path=partition,
                    mount_point=usb_mount,
                    iso_mount=iso_mount,
                    target_system=cfg.target_system,
                    log_callback=self._log,
                )
            except BootloaderError as e:
                self._log(f"Warnung: Bootloader-Fehler (möglicherweise nicht bootbar): {e}")

            # Step 8: Sync — can take many minutes for large ISOs on slow USB drives
            self._step(7)
            self._status("Synchronisiere (kann mehrere Minuten dauern)...")
            try:
                subprocess.run(["sync"], check=False, timeout=1200)  # up to 20 min
            except subprocess.TimeoutExpired:
                self._log("Warnung: sync Timeout — USB-Stick sicher auswerfen empfohlen.")

        finally:
            # Always unmount in correct order
            if usb_mount:
                subprocess.run(["umount", "-l", usb_mount], capture_output=True)
                try:
                    os.rmdir(usb_mount)
                except OSError:
                    pass
            if iso_mount:
                subprocess.run(["umount", "-l", iso_mount], capture_output=True)
                try:
                    os.rmdir(iso_mount)
                except OSError:
                    pass

        self._log("ISO-Modus abgeschlossen.")

    # FAT32 max file size is just under 4 GiB
    _FAT32_MAX = 4 * 1024 ** 3 - 1

    def _split_wim(self, src_wim: str, dst_swm: str):
        """Split a WIM/ESD file from src directly into dst_swm chunks (≤3800 MiB each)."""
        self._log(f"Splitte {os.path.basename(src_wim)} → {os.path.basename(dst_swm)} ...")
        self._status("Splitte install.wim (kann Minuten dauern)...")
        result = subprocess.run(
            ["wimlib-imagex", "split", src_wim, dst_swm, "3800"],
            capture_output=True, text=True, timeout=1200,
        )
        if result.returncode == 0:
            self._log("install.wim erfolgreich gesplittet (install.swm, install2.swm, ...).")
        else:
            self._log(f"Warnung: Split fehlgeschlagen: {result.stderr.strip()}")
            self._log("Tipp: 'sudo apt install wimtools' installieren.")

    # Chunk size for copying large files: 4 MB → progress updates during big files
    _CHUNK_SIZE = 4 * 1024 * 1024

    def _copy_iso_contents(self, src: str, dst: str, skip_in_sources: set = None):
        """Copy all files from ISO mount to USB with chunked I/O for live progress."""
        self._log(f"Kopiere Dateien: {src} → {dst}")

        total_size = self._dir_size(src)
        copied_size = 0
        self._log(f"Zu kopierende Datenmenge: {self._fmt_size(total_size)}")

        speed_window_start = time.monotonic()
        speed_window_bytes = 0
        current_speed = 0.0  # bytes/sec

        for root, dirs, files in os.walk(src):
            if self._abort:
                return

            rel_root = os.path.relpath(root, src)
            dst_root = os.path.join(dst, rel_root) if rel_root != "." else dst
            os.makedirs(dst_root, exist_ok=True)

            for filename in files:
                if self._abort:
                    return

                # Skip files that will be handled separately (e.g. install.wim split)
                if skip_in_sources and rel_root.lower() == "sources" and filename.lower() in {n.lower() for n in skip_in_sources}:
                    self._log(f"Überspringe {filename} (wird separat gesplittet).")
                    continue

                src_file = os.path.join(root, filename)
                dst_file = os.path.join(dst_root, filename)

                try:
                    # Always use chunked copy so progress updates during large files
                    with open(src_file, "rb") as fsrc, open(dst_file, "wb") as fdst:
                        while True:
                            if self._abort:
                                return
                            chunk = fsrc.read(self._CHUNK_SIZE)
                            if not chunk:
                                break
                            fdst.write(chunk)
                            chunk_len = len(chunk)
                            copied_size += chunk_len
                            speed_window_bytes += chunk_len

                            # Update speed & status every 0.5 s
                            now = time.monotonic()
                            elapsed = now - speed_window_start
                            if elapsed >= 0.5:
                                current_speed = speed_window_bytes / elapsed
                                speed_window_bytes = 0
                                speed_window_start = now

                            self._emit_copy_status(
                                copied_size, total_size, current_speed, filename
                            )

                    # Preserve metadata (timestamps etc.)
                    shutil.copystat(src_file, dst_file)

                except OSError as e:
                    self._log(f"Warnung: Konnte {filename} nicht kopieren: {e}")
                    continue

        self._log(f"Dateien kopiert: {self._fmt_size(copied_size)}")

    def _emit_copy_status(
        self, copied: int, total: int, speed: float, filename: str
    ):
        if total <= 0:
            return
        pct = 25 + int(copied / total * 60)  # maps 0→100% to 25→85%
        self.progress.emit(min(84, pct))

        copied_str = self._fmt_size(copied)
        total_str = self._fmt_size(total)

        if speed > 0:
            speed_str = self._fmt_size(int(speed)) + "/s"
            eta_str = self._fmt_eta((total - copied) / speed)
            self._status(
                f"Kopiere: {copied_str} / {total_str}  |  {speed_str}  |  ETA {eta_str}"
            )
        else:
            self._status(f"Kopiere: {copied_str} / {total_str}  ({filename})")

    # ------------------------------------------------------------------
    # Format-only Mode
    # ------------------------------------------------------------------

    def _run_format_only(self):
        cfg = self.config
        self._status("Unmounte Gerät...")
        DeviceManager.unmount_device(cfg.device_path)
        self._progress(10)

        if self._abort:
            return

        self._status("Formatiere...")
        try:
            Formatter.format_device(
                device_path=cfg.device_path,
                scheme=cfg.scheme,
                filesystem=cfg.filesystem,
                label=cfg.label,
                cluster_size=cfg.cluster_size,
                quick_format=cfg.quick_format,
                log_callback=self._log,
            )
        except FormatterError as e:
            raise RuntimeError(str(e))

        subprocess.run(["sync"], check=False)
        self._log("Formatierung abgeschlossen.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, msg: str):
        self.log.emit(msg)

    def _status(self, msg: str):
        self.status.emit(msg)

    def _progress(self, pct: int):
        self.progress.emit(pct)

    @staticmethod
    def _dir_size(path: str) -> int:
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total

    @staticmethod
    def _fmt_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    @staticmethod
    def _fmt_eta(seconds: float) -> str:
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            m, s = divmod(seconds, 60)
            return f"{m}m {s:02d}s"
        else:
            h, rem = divmod(seconds, 3600)
            m, s = divmod(rem, 60)
            return f"{h}h {m:02d}m"
