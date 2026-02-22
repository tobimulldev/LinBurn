"""
USB device detection and management.
Uses lsblk for device enumeration and pyudev for hotplug events.
"""
import json
import subprocess
from dataclasses import dataclass
from typing import Optional

try:
    import pyudev
    PYUDEV_AVAILABLE = True
except ImportError:
    PYUDEV_AVAILABLE = False

from PyQt6.QtCore import QObject, pyqtSignal, QThread


@dataclass
class Device:
    name: str        # e.g. "sdb"
    path: str        # e.g. "/dev/sdb"
    size: str        # e.g. "32G"
    size_bytes: int
    model: str       # e.g. "SanDisk Ultra"
    tran: str        # transport: "usb"
    removable: bool

    def __str__(self):
        model = self.model or "Unbekanntes Gerät"
        return f"{model} ({self.size}) [{self.path}]"


class DeviceManager:
    """Lists and monitors USB block devices."""

    @staticmethod
    def list_devices() -> list[Device]:
        """Return list of removable USB block devices."""
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
            if DeviceManager._is_usb_device(block):
                dev = DeviceManager._parse_device(block)
                if dev:
                    devices.append(dev)
        return devices

    @staticmethod
    def _is_usb_device(block: dict) -> bool:
        tran = (block.get("tran") or "").lower()
        rm = block.get("rm")
        dtype = (block.get("type") or "").lower()
        # Accept USB or removable disks (some USB hubs report tran differently)
        return dtype == "disk" and (tran == "usb" or rm in (True, "1", 1))

    @staticmethod
    def _parse_device(block: dict) -> Optional[Device]:
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
        """Return list of partition paths for a device (e.g. ['/dev/sdb1', '/dev/sdb2'])."""
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
        """Aggressively unmount all partitions of a device."""
        import time

        def _run(cmd):
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
            except subprocess.TimeoutExpired:
                pass

        # Kill any processes using the device
        _run(["fuser", "-k", "-9", "-m", device_path])
        time.sleep(0.3)

        partitions = DeviceManager.get_partitions(device_path)

        # Unmount each partition and the device itself
        targets = partitions + [device_path]
        for target in targets:
            _run(["fuser", "-k", "-9", "-m", target])
            _run(["umount", "-l", target])   # lazy unmount — never blocks

        time.sleep(0.5)

        # Verify nothing is still mounted
        try:
            with open("/proc/mounts") as f:
                return device_path not in f.read()
        except OSError:
            return True


class UdevMonitor(QThread):
    """Monitors USB hotplug events using pyudev."""
    device_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def run(self):
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

    def stop(self):
        self._running = False
        self.quit()
