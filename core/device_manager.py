"""
USB device detection and management.
Linux:   lsblk + pyudev
Windows: PowerShell Get-Disk + polling monitor
"""
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

if sys.platform != "win32":
    try:
        import pyudev
        PYUDEV_AVAILABLE = True
    except ImportError:
        PYUDEV_AVAILABLE = False
else:
    PYUDEV_AVAILABLE = False


@dataclass
class Device:
    name: str        # e.g. "sdb" (Linux) or "PhysicalDrive1" (Windows)
    path: str        # e.g. "/dev/sdb" or r"\\.\PhysicalDrive1"
    size: str        # e.g. "32.0 GB"
    size_bytes: int
    model: str       # e.g. "SanDisk Ultra"
    tran: str        # transport: "usb"
    removable: bool

    def __str__(self):
        model = self.model or "Unknown Device"
        return f"{model} ({self.size}) [{self.path}]"


class DeviceManager:
    """Lists and manages USB block devices (cross-platform)."""

    @staticmethod
    def list_devices() -> list[Device]:
        if sys.platform == "win32":
            return DeviceManager._list_devices_windows()
        return DeviceManager._list_devices_linux()

    # ------------------------------------------------------------------
    # Linux implementation
    # ------------------------------------------------------------------

    @staticmethod
    def _list_devices_linux() -> list[Device]:
        try:
            result = subprocess.run(
                ["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MODEL,TRAN,RM"],
                capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            return []

        devices = []
        for block in data.get("blockdevices", []):
            if DeviceManager._is_usb_device_linux(block):
                dev = DeviceManager._parse_device_linux(block)
                if dev:
                    devices.append(dev)
        return devices

    @staticmethod
    def _is_usb_device_linux(block: dict) -> bool:
        tran = (block.get("tran") or "").lower()
        rm = block.get("rm")
        dtype = (block.get("type") or "").lower()
        return dtype == "disk" and (tran == "usb" or rm in (True, "1", 1))

    @staticmethod
    def _parse_device_linux(block: dict) -> Optional[Device]:
        name = block.get("name", "")
        if not name:
            return None
        size_raw = block.get("size", 0)
        try:
            size_bytes = int(size_raw) if size_raw else 0
        except (ValueError, TypeError):
            size_bytes = 0
        return Device(
            name=name,
            path=f"/dev/{name}",
            size=DeviceManager._format_size(size_bytes),
            size_bytes=size_bytes,
            model=(block.get("model") or "").strip(),
            tran=(block.get("tran") or "").lower(),
            removable=bool(block.get("rm")),
        )

    # ------------------------------------------------------------------
    # Windows implementation
    # ------------------------------------------------------------------

    @staticmethod
    def _list_devices_windows() -> list[Device]:
        from core.platform.windows import list_usb_devices_win
        raw = list_usb_devices_win()
        devices = []
        for d in raw:
            num = d.get("Number")
            name = d.get("FriendlyName", "").strip()
            size_bytes = int(d.get("Size") or 0)
            dev = Device(
                name=f"PhysicalDrive{num}",
                path=f"\\\\.\\PhysicalDrive{num}",
                size=DeviceManager._format_size(size_bytes),
                size_bytes=size_bytes,
                model=name,
                tran="usb",
                removable=True,
            )
            devices.append(dev)
        return devices

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes == 0:
            return "?"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    @staticmethod
    def get_partitions(device_path: str) -> list[str]:
        """Return list of partition paths for a device (Linux only)."""
        if sys.platform == "win32":
            return []  # Windows: partitions accessed via drive letters
        try:
            result = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,TYPE", device_path],
                capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)
            partitions = []
            for block in data.get("blockdevices", []):
                for child in block.get("children", []):
                    if child.get("type") == "part":
                        partitions.append(f"/dev/{child['name']}")
            return partitions
        except Exception:
            return []

    @staticmethod
    def unmount_device(device_path: str) -> bool:
        """Unmount all partitions of a device."""
        if sys.platform == "win32":
            return DeviceManager._unmount_device_windows(device_path)
        return DeviceManager._unmount_device_linux(device_path)

    @staticmethod
    def _unmount_device_linux(device_path: str) -> bool:
        import time

        def _run(cmd):
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
            except subprocess.TimeoutExpired:
                pass

        _run(["fuser", "-k", "-9", "-m", device_path])
        time.sleep(0.3)

        partitions = DeviceManager.get_partitions(device_path)
        for target in partitions + [device_path]:
            _run(["fuser", "-k", "-9", "-m", target])
            _run(["umount", "-l", target])

        time.sleep(0.5)

        try:
            with open("/proc/mounts") as f:
                return device_path not in f.read()
        except OSError:
            return True

    @staticmethod
    def _unmount_device_windows(device_path: str) -> bool:
        from core.platform.windows import get_disk_number, unmount_device_win
        disk_num = get_disk_number(device_path)
        if disk_num is None:
            return True
        unmount_device_win(disk_num)
        return True


# ---------------------------------------------------------------------------
# Hotplug monitor
# ---------------------------------------------------------------------------

class UdevMonitor(QThread):
    """
    Monitors USB hotplug events.
    Linux:   pyudev netlink (event-driven)
    Windows: polling every 2 seconds
    """
    device_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def run(self):
        if sys.platform == "win32":
            self._run_windows()
        else:
            self._run_linux()

    def _run_linux(self):
        if not PYUDEV_AVAILABLE:
            return
        try:
            context = pyudev.Context()
            monitor = pyudev.Monitor.from_netlink(context)
            monitor.filter_by(subsystem="block")
            self._running = True
            for device in iter(monitor.poll, None):
                if not self._running:
                    break
                if device.action in ("add", "remove", "change"):
                    self.device_changed.emit()
        except Exception:
            pass

    def _run_windows(self):
        """Poll for USB device changes every 2 seconds."""
        import time
        from core.platform.windows import list_usb_devices_win
        self._running = True
        prev_nums: set = set()
        while self._running:
            try:
                current = {d.get("Number") for d in list_usb_devices_win()}
                if current != prev_nums:
                    prev_nums = current
                    self.device_changed.emit()
            except Exception:
                pass
            # Sleep in short slices so stop() is responsive
            for _ in range(20):
                if not self._running:
                    return
                time.sleep(0.1)

    def stop(self):
        self._running = False
        self.quit()
