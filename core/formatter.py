"""
USB drive partitioning and formatting.
Supports MBR/GPT partition schemes and FAT32/NTFS/exFAT/ext4 filesystems.
"""
import os
import signal
import subprocess
import threading
import time
from typing import Optional


def _run(cmd, timeout=15, capture=False):
    """
    Run a command with a hard wall-clock timeout.

    Uses a daemon thread so that even D-state (uninterruptible I/O) processes
    cannot block the caller: we join the thread for at most `timeout` seconds,
    then kill the process group and return immediately without waiting for the
    (potentially unkillable) process to exit.

    Returns (returncode, stdout, stderr).
    """
    kwargs: dict = {"start_new_session": True}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
        kwargs["text"] = True
    else:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL

    result: dict = {"rc": None, "out": "", "err": ""}

    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except FileNotFoundError:
        return -1, "", f"Befehl nicht gefunden: {cmd[0]}"

    def _worker():
        try:
            out, err = proc.communicate()
            result["rc"] = proc.returncode
            result["out"] = out or ""
            result["err"] = err or ""
        except Exception:
            result["rc"] = -1

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        # Timed out — kill entire process group (best-effort; D-state may survive)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            try:
                proc.kill()
            except Exception:
                pass
        # Do NOT join the thread — it may be stuck in kernel D-state forever.
        # It is a daemon thread so it won't block program exit.
        return -1, "", ""

    return result["rc"] if result["rc"] is not None else -1, result["out"], result["err"]


class FormatterError(Exception):
    pass


class Formatter:
    """Handles partitioning and filesystem creation on a USB device."""

    CLUSTER_SIZES = {
        "FAT32":  [512, 1024, 2048, 4096, 8192, 16384, 32768],
        "NTFS":   [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536],
        "exFAT":  [4096, 8192, 16384, 32768, 65536, 131072],
        "ext4":   [1024, 2048, 4096, 8192, 16384, 32768, 65536],
    }

    @classmethod
    def format_device(
        cls,
        device_path: str,
        scheme: str = "MBR",
        filesystem: str = "FAT32",
        label: str = "LINBURN",
        cluster_size: int = 0,
        quick_format: bool = True,
        log_callback=None,
    ) -> str:
        """
        Partition and format the USB device.
        Returns the partition path (e.g. '/dev/sdb1').
        """
        def log(msg):
            if log_callback:
                log_callback(msg)

        log(f"Lösche bestehende Signaturen auf {device_path}...")
        cls._wipe_device(device_path)
        time.sleep(1.0)

        log(f"Partitioniere {device_path} mit Schema {scheme}...")
        cls._create_partition_table(device_path, scheme)
        time.sleep(1.0)

        log(f"Erstelle Partition...")
        cls._create_partition(device_path, scheme, filesystem)
        time.sleep(1.5)

        # Force kernel to re-read partition table
        _run(["partprobe", device_path], timeout=10)
        _run(["blockdev", "--rereadpt", device_path], timeout=10)
        _run(["udevadm", "settle", "--timeout=5"], timeout=8)

        # Retry up to 10 seconds for the partition node to appear
        partition = None
        for _ in range(20):
            partition = cls._get_first_partition(device_path)
            if partition:
                break
            time.sleep(0.5)
            _run(["partprobe", device_path], timeout=5)
            _run(["udevadm", "settle", "--timeout=3"], timeout=5)

        if not partition:
            raise FormatterError(
                f"Keine Partition auf {device_path} gefunden nach Formatierung.\n"
                f"Tipp: Überprüfe ob der USB-Stick korrekt eingesteckt ist."
            )

        log(f"Formatiere {partition} als {filesystem}...")
        cls._format_partition(partition, filesystem, label, cluster_size, quick_format)

        log(f"Formatierung abgeschlossen: {partition}")
        return partition

    @classmethod
    def format_device_dual(
        cls,
        device_path: str,
        label: str = "WINDOWS",
        quick_format: bool = True,
        log_callback=None,
    ) -> tuple:
        """
        Create Windows UEFI-optimised dual-partition layout on GPT:
          Partition 1: 300 MiB  FAT32  (EFI System Partition – UEFI can always read this)
          Partition 2: rest      NTFS   (Windows installation files, supports >4 GB install.wim)

        Returns (efi_partition_path, data_partition_path).
        """
        def log(msg):
            if log_callback:
                log_callback(msg)

        log(f"Lösche bestehende Signaturen auf {device_path}...")
        cls._wipe_device(device_path)
        time.sleep(1.0)

        log("Erstelle GPT-Partitionstabelle...")
        rc, _, stderr = _run(
            ["parted", "-s", "--", device_path, "mklabel", "gpt"],
            timeout=20, capture=True
        )
        if rc not in (0,) and rc != -1:
            raise FormatterError(f"GPT mklabel fehlgeschlagen: {stderr.strip()}")
        time.sleep(1.0)

        log("Erstelle EFI-Partition (300 MiB, FAT32)...")
        _run(["parted", "-s", device_path, "mkpart", "EFI", "fat32", "1MiB", "301MiB"], timeout=20)
        _run(["parted", "-s", device_path, "set", "1", "esp", "on"], timeout=10)
        time.sleep(0.5)

        log("Erstelle Windows-Datenpartition (NTFS)...")
        _run(["parted", "-s", device_path, "mkpart", "Windows", "ntfs", "301MiB", "100%"], timeout=20)
        time.sleep(1.5)

        # Let kernel re-read partition table
        _run(["partprobe", device_path], timeout=10)
        _run(["blockdev", "--rereadpt", device_path], timeout=10)
        _run(["udevadm", "settle", "--timeout=5"], timeout=8)

        # Wait for both partition nodes
        efi_part = None
        data_part = None
        for _ in range(20):
            efi_part = cls._get_nth_partition(device_path, 1)
            data_part = cls._get_nth_partition(device_path, 2)
            if efi_part and data_part:
                break
            time.sleep(0.5)
            _run(["partprobe", device_path], timeout=5)
            _run(["udevadm", "settle", "--timeout=3"], timeout=5)

        if not efi_part or not data_part:
            raise FormatterError(
                f"Partitionen nicht gefunden nach Formatierung auf {device_path}."
            )

        log(f"Formatiere {efi_part} als FAT32 (EFI)...")
        rc, _, stderr = _run(["mkfs.fat", "-F", "32", "-n", "EFI", efi_part], timeout=60, capture=True)
        if rc not in (0,):
            raise FormatterError(f"FAT32-Formatierung fehlgeschlagen: {stderr.strip()}")

        log(f"Formatiere {data_part} als NTFS...")
        ntfs_cmd = ["mkfs.ntfs", "-L", label[:32]]
        if quick_format:
            ntfs_cmd.append("-f")
        ntfs_cmd.append(data_part)
        rc, _, stderr = _run(ntfs_cmd, timeout=120, capture=True)
        if rc not in (0,):
            raise FormatterError(f"NTFS-Formatierung fehlgeschlagen: {stderr.strip()}")

        log(f"Dual-Partition fertig: EFI={efi_part}, Daten={data_part}")
        return efi_part, data_part

    @classmethod
    def _get_nth_partition(cls, device_path: str, n: int) -> Optional[str]:
        """Return path of the nth partition (1-based) using lsblk."""
        try:
            result = subprocess.run(
                ["lsblk", "-rno", "NAME,TYPE", device_path],
                capture_output=True, text=True, timeout=5
            )
            parts = [
                f"/dev/{line.split()[0]}"
                for line in result.stdout.splitlines()
                if len(line.split()) == 2 and line.split()[1] == "part"
            ]
            if len(parts) >= n:
                return parts[n - 1]
        except Exception:
            pass
        # Fallback: guess common naming
        base = device_path.rstrip("0123456789")
        sep = "p" if device_path[-1].isdigit() else ""
        candidate = f"{base}{sep}{n}"
        return candidate if os.path.exists(candidate) else None

    @classmethod
    def _wipe_device(cls, device_path: str):
        """Wipe existing partition table signatures so parted can take over."""
        _run(["wipefs", "-a", "-f", device_path], timeout=10)
        # Zero out first 1 MiB — no conv=fsync to avoid blocking on busy devices
        _run(["dd", "if=/dev/zero", f"of={device_path}", "bs=512", "count=2048"], timeout=10)

    @classmethod
    def _create_partition_table(cls, device_path: str, scheme: str):
        label_type = "msdos" if scheme == "MBR" else "gpt"
        rc, _, stderr = _run(
            ["parted", "-s", "--", device_path, "mklabel", label_type],
            timeout=20, capture=True
        )
        if rc == -1:
            raise FormatterError("parted mklabel: Timeout — Gerät antwortet nicht.")
        if rc != 0:
            raise FormatterError(
                f"Partitionstabelle erstellen fehlgeschlagen: {stderr.strip()}"
            )

    @classmethod
    def _create_partition(cls, device_path: str, scheme: str, filesystem: str):
        # Map filesystem to parted fs-type
        parted_fs = {
            "FAT32": "fat32",
            "NTFS": "ntfs",
            "exFAT": "fat32",  # parted doesn't know exfat, use fat32 type
            "ext4": "ext4",
        }.get(filesystem, "fat32")

        rc, _, stderr = _run(
            ["parted", "-s", device_path, "mkpart", "primary", parted_fs, "1MiB", "100%"],
            timeout=20, capture=True
        )
        if rc == -1:
            raise FormatterError("parted mkpart: Timeout — Gerät antwortet nicht.")
        if rc != 0:
            raise FormatterError(f"Partition erstellen fehlgeschlagen: {stderr}")

        # Set boot flag for MBR
        if scheme == "MBR":
            _run(["parted", "-s", device_path, "set", "1", "boot", "on"], timeout=10)

    @classmethod
    def _get_first_partition(cls, device_path: str) -> Optional[str]:
        """Return path of first partition on device."""
        base = os.path.basename(device_path)

        # 1. Common naming patterns: sdX1, mmcblk0p1, nvme0n1p1
        candidates = [
            f"{device_path}1",
            f"{device_path}p1",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate

        # 2. Ask lsblk directly (most reliable)
        try:
            result = subprocess.run(
                ["lsblk", "-rno", "NAME,TYPE", device_path],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1] == "part":
                    path = f"/dev/{parts[0]}"
                    if os.path.exists(path):
                        return path
        except Exception:
            pass

        # 3. Fallback: scan /proc/partitions
        try:
            with open("/proc/partitions") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4 and parts[3].startswith(base) and parts[3] != base:
                        path = f"/dev/{parts[3]}"
                        if os.path.exists(path):
                            return path
        except OSError:
            pass

        return None

    @classmethod
    def _format_partition(
        cls,
        partition: str,
        filesystem: str,
        label: str,
        cluster_size: int,
        quick_format: bool,
    ):
        label = label[:11] if filesystem == "FAT32" else label[:32]

        if filesystem == "FAT32":
            cmd = ["mkfs.fat", "-F", "32", "-n", label]
            if cluster_size > 0:
                cmd += ["-s", str(cluster_size // 512)]
            cmd.append(partition)

        elif filesystem == "NTFS":
            cmd = ["mkfs.ntfs", "-L", label]
            if quick_format:
                cmd.append("-f")
            if cluster_size > 0:
                cmd += ["-c", str(cluster_size)]
            cmd.append(partition)

        elif filesystem == "exFAT":
            cmd = ["mkfs.exfat", "-n", label]
            if cluster_size > 0:
                cmd += ["-c", str(cluster_size)]
            cmd.append(partition)

        elif filesystem == "ext4":
            cmd = ["mkfs.ext4", "-L", label]
            if cluster_size > 0:
                cmd += ["-b", str(cluster_size)]
            cmd.append(partition)

        else:
            raise FormatterError(f"Unbekanntes Dateisystem: {filesystem}")

        rc, _, stderr = _run(cmd, timeout=120, capture=True)
        if rc == -1:
            raise FormatterError(f"Formatierung ({filesystem}): Timeout nach 120s.")
        if rc != 0:
            raise FormatterError(
                f"Formatierung fehlgeschlagen ({filesystem}): {stderr.strip()}"
            )
