"""
Windows platform helpers for LinBurn.
Provides Windows equivalents of Linux tools:
  lsblk       → PowerShell Get-Disk
  parted       → diskpart
  mkfs.*       → diskpart format
  dd           → Python raw I/O
  mount -o loop → PowerShell Mount-DiskImage
  badblocks    → chkdsk /R
  wimlib-imagex → dism /split-image  (WIM splitting)
                → dism /image (boot.wim patching)
"""
import json
import os
import re
import subprocess
import tempfile
import time
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# PowerShell helper
# ---------------------------------------------------------------------------

def run_powershell(script: str, timeout: int = 30) -> Tuple[int, str, str]:
    """Run a PowerShell one-liner / script block and return (rc, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "PowerShell not found"
    except subprocess.TimeoutExpired:
        return -1, "", "PowerShell timeout"


# ---------------------------------------------------------------------------
# DiskPart helper
# ---------------------------------------------------------------------------

def run_diskpart(commands: list, timeout: int = 60) -> Tuple[int, str]:
    """Write diskpart commands to a temp script file and run diskpart /s."""
    script_text = "\n".join(commands) + "\nexit\n"
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    try:
        tmp.write(script_text)
        tmp.close()
        result = subprocess.run(
            ["diskpart", "/s", tmp.name],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode, result.stdout
    except FileNotFoundError:
        return -1, "diskpart not found"
    except subprocess.TimeoutExpired:
        return -1, "diskpart timeout"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Disk number helpers
# ---------------------------------------------------------------------------

def get_disk_number(device_path: str) -> Optional[int]:
    r"""Extract disk number from \\.\PhysicalDriveN → N."""
    m = re.search(r"(\d+)$", device_path)
    return int(m.group(1)) if m else None


def physical_drive(disk_num: int) -> str:
    return f"\\\\.\\PhysicalDrive{disk_num}"


# ---------------------------------------------------------------------------
# Device enumeration
# ---------------------------------------------------------------------------

def list_usb_devices_win() -> list:
    """
    Return list of USB disks via PowerShell Get-Disk.
    Each element: {"Number": N, "FriendlyName": "...", "Size": bytes}
    """
    script = (
        "Get-Disk | Where-Object {$_.BusType -eq 'USB'} | "
        "Select-Object Number, FriendlyName, Size | "
        "ConvertTo-Json -Compress"
    )
    rc, out, _ = run_powershell(script, timeout=15)
    if rc != 0 or not out.strip():
        return []
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        return data or []
    except json.JSONDecodeError:
        return []


# ---------------------------------------------------------------------------
# Device unmounting / locking
# ---------------------------------------------------------------------------

def unmount_device_win(disk_num: int):
    """Remove all drive-letter assignments from partitions on a disk."""
    script = f"""
$disk = Get-Disk -Number {disk_num} -ErrorAction SilentlyContinue
if ($disk) {{
    $disk | Get-Partition -ErrorAction SilentlyContinue |
    Where-Object {{ $_.DriveLetter }} |
    ForEach-Object {{
        Remove-PartitionAccessPath -DiskNumber {disk_num} `
            -PartitionNumber $_.PartitionNumber `
            -AccessPath "$($_.DriveLetter):" `
            -ErrorAction SilentlyContinue
    }}
}}
"""
    run_powershell(script, timeout=20)


def get_disk_drive_letters(disk_num: int) -> list:
    """Return all drive letters currently assigned to partitions on disk_num."""
    script = (
        f"Get-Partition -DiskNumber {disk_num} -ErrorAction SilentlyContinue | "
        "Where-Object {$_.DriveLetter} | "
        "Select-Object -ExpandProperty DriveLetter"
    )
    rc, out, _ = run_powershell(script, timeout=15)
    if rc != 0 or not out.strip():
        return []
    return [l.strip() + ":" for l in out.splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# Disk partitioning (diskpart)
# ---------------------------------------------------------------------------

def wipe_disk_win(disk_num: int) -> Tuple[int, str]:
    """Clean a disk (remove all partitions and filesystem data)."""
    return run_diskpart([
        f"select disk {disk_num}",
        "clean",
    ], timeout=30)


def create_single_partition_win(
    disk_num: int,
    scheme: str,
    filesystem: str,
    label: str,
    quick: bool,
) -> Optional[str]:
    """
    Create a single primary partition on disk_num.
    Returns the assigned drive letter (e.g. 'E:') or None on failure.
    """
    fs_map = {"FAT32": "fat32", "NTFS": "ntfs", "exFAT": "exfat", "ext4": "fat32"}
    win_fs = fs_map.get(filesystem, "fat32")
    label_safe = (label[:11] if filesystem == "FAT32" else label[:32]).replace('"', '')
    q = "quick " if quick else ""

    cmds = [f"select disk {disk_num}", "clean"]
    if scheme == "GPT":
        cmds.append("convert gpt")
    cmds += [
        "create partition primary",
        "select partition 1",
    ]
    if scheme == "MBR":
        cmds.append("active")
    cmds += [
        f'format fs={win_fs} label="{label_safe}" {q}override',
        "assign",
    ]

    rc, out = run_diskpart(cmds, timeout=180)

    # Parse "DiskPart successfully assigned the drive letter or mount point."
    m = re.search(r"assigned the drive letter\s+([A-Za-z])", out, re.IGNORECASE)
    if m:
        return m.group(1).upper() + ":"
    # Fallback: query PowerShell
    time.sleep(1)
    return _query_last_partition_letter(disk_num)


def create_dual_partition_win(
    disk_num: int,
    label: str,
    quick: bool,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create GPT dual-partition layout for Windows ISOs:
      Part 1: 300 MiB FAT32 (EFI System)
      Part 2: rest    NTFS  (data / install files)
    Returns (efi_letter, data_letter).
    """
    label_safe = label[:32].replace('"', '')
    q = "quick " if quick else ""

    cmds = [
        f"select disk {disk_num}", "clean", "convert gpt",
        "create partition efi size=300",
        'format fs=fat32 label="EFI" quick override',
        "assign",
        "create partition primary",
        f'format fs=ntfs label="{label_safe}" {q}override',
        "assign",
    ]
    rc, out = run_diskpart(cmds, timeout=300)

    letters = re.findall(r"assigned the drive letter\s+([A-Za-z])", out, re.IGNORECASE)
    efi = (letters[0].upper() + ":") if len(letters) >= 1 else None
    data = (letters[1].upper() + ":") if len(letters) >= 2 else None

    if not efi or not data:
        time.sleep(1)
        all_letters = _query_all_partition_letters(disk_num)
        if len(all_letters) >= 2:
            efi = all_letters[0]
            data = all_letters[1]
        elif len(all_letters) == 1:
            data = all_letters[0]

    return efi, data


def _query_last_partition_letter(disk_num: int) -> Optional[str]:
    script = (
        f"Get-Partition -DiskNumber {disk_num} -ErrorAction SilentlyContinue | "
        "Where-Object {$_.DriveLetter} | Select-Object -Last 1 -ExpandProperty DriveLetter"
    )
    rc, out, _ = run_powershell(script, timeout=15)
    return (out.strip().upper() + ":") if rc == 0 and out.strip() else None


def _query_all_partition_letters(disk_num: int) -> list:
    script = (
        f"Get-Partition -DiskNumber {disk_num} -ErrorAction SilentlyContinue | "
        "Where-Object {$_.DriveLetter} | Select-Object -ExpandProperty DriveLetter"
    )
    rc, out, _ = run_powershell(script, timeout=15)
    if rc != 0 or not out.strip():
        return []
    return [l.strip().upper() + ":" for l in out.splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# ISO mounting
# ---------------------------------------------------------------------------

def mount_iso_win(iso_path: str) -> Optional[str]:
    """
    Mount an ISO using PowerShell Mount-DiskImage (Windows 8+).
    Returns the drive letter with trailing backslash (e.g. 'E:\\') or None.
    """
    script = (
        f'(Mount-DiskImage -ImagePath "{iso_path}" -PassThru | '
        f'Get-Volume).DriveLetter'
    )
    rc, out, _ = run_powershell(script, timeout=30)
    if rc == 0 and out.strip():
        letter = out.strip().split()[-1].upper()  # last non-empty line
        return letter + ":\\"
    return None


def unmount_iso_win(iso_path: str):
    """Unmount a previously mounted ISO image."""
    script = f'Dismount-DiskImage -ImagePath "{iso_path}" -ErrorAction SilentlyContinue'
    run_powershell(script, timeout=15)


# ---------------------------------------------------------------------------
# DD-mode raw write
# ---------------------------------------------------------------------------

def dd_write_win(
    iso_path: str,
    device_path: str,
    chunk_size: int = 4 * 1024 * 1024,
    progress_callback=None,   # (written_bytes, total_bytes)
    abort_check=None,         # () -> bool
):
    """
    Write ISO directly to a physical disk (DD mode) via Python raw I/O.
    Requires the process to be running as Administrator.
    """
    iso_size = os.path.getsize(iso_path)
    with open(iso_path, "rb") as src, open(device_path, "rb+") as dst:
        written = 0
        while True:
            if abort_check and abort_check():
                return
            chunk = src.read(chunk_size)
            if not chunk:
                break
            dst.write(chunk)
            written += len(chunk)
            if progress_callback and iso_size > 0:
                progress_callback(written, iso_size)
        dst.flush()
        try:
            os.fsync(dst.fileno())
        except OSError:
            pass


# ---------------------------------------------------------------------------
# WIM splitting (for large install.wim on FAT32)
# ---------------------------------------------------------------------------

def split_wim_win(src_wim: str, dst_swm: str, max_size_mb: int = 3800) -> bool:
    """
    Split install.wim using DISM.
    Returns True on success.
    """
    try:
        result = subprocess.run(
            [
                "dism",
                f"/split-image",
                f"/ImageFile:{src_wim}",
                f"/SWMFile:{dst_swm}",
                f"/FileSize:{max_size_mb}",
            ],
            capture_output=True, text=True, timeout=1200,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# WIM patching (boot.wim for Windows 11 bypass)
# ---------------------------------------------------------------------------

def patch_boot_wim_win(boot_wim: str, log) -> bool:
    """
    Replace appraiserres.dll inside boot.wim using DISM (Windows).
    Mounts image index 2 to a temp dir, replaces the DLL, commits changes.
    Returns True on success.
    """
    tmp_mount = tempfile.mkdtemp(prefix="linburn_wim_")
    try:
        # Mount boot.wim index 2 (Windows Setup WinPE)
        r1 = subprocess.run(
            ["dism", f"/Mount-Image", f"/ImageFile:{boot_wim}",
             "/Index:2", f"/MountDir:{tmp_mount}"],
            capture_output=True, text=True, timeout=120,
        )
        if r1.returncode != 0:
            log(f"Warnung: DISM Mount fehlgeschlagen: {r1.stderr.strip()[:200]}")
            return False

        # Replace appraiserres.dll with empty stub
        dll_path = os.path.join(
            tmp_mount, "Windows", "System32", "appraiserres.dll"
        )
        if os.path.exists(dll_path):
            try:
                os.chmod(dll_path, 0o644)
            except OSError:
                pass
            with open(dll_path, "wb") as f:
                f.write(b"")

        # Commit and unmount
        r2 = subprocess.run(
            ["dism", f"/Unmount-Image", f"/MountDir:{tmp_mount}", "/Commit"],
            capture_output=True, text=True, timeout=120,
        )
        if r2.returncode == 0:
            log("boot.wim gepatcht: appraiserres.dll in WinPE deaktiviert.")
            return True
        else:
            log(f"Warnung: DISM Unmount/Commit fehlgeschlagen: {r2.stderr.strip()[:200]}")
            # Try to unmount without committing to clean up
            subprocess.run(
                ["dism", f"/Unmount-Image", f"/MountDir:{tmp_mount}", "/Discard"],
                capture_output=True, timeout=60,
            )
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log(f"Warnung: DISM nicht verfügbar ({e}) — boot.wim nicht gepatcht.")
        return False
    finally:
        try:
            os.rmdir(tmp_mount)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Bootloader (BIOS via bootsect)
# ---------------------------------------------------------------------------

def install_bios_bootloader_win(drive_letter: str, log) -> bool:
    """
    Install BIOS MBR bootloader using bootsect.exe (if available).
    drive_letter: e.g. 'E:' (without backslash)
    """
    # bootsect.exe is not in System32 by default — it's on Windows installation media.
    # Try common locations and PATH.
    candidates = [
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                     "System32", "bootsect.exe"),
        "bootsect.exe",  # in PATH
    ]
    for bootsect in candidates:
        if bootsect == "bootsect.exe" or os.path.exists(bootsect):
            try:
                r = subprocess.run(
                    [bootsect, "/nt60", drive_letter, "/mbr"],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode == 0:
                    log(f"BIOS-Bootloader (bootsect) installiert auf {drive_letter}.")
                    return True
            except FileNotFoundError:
                pass
    log("Hinweis: bootsect.exe nicht gefunden — BIOS-Boot nicht verfügbar. "
        "UEFI funktioniert weiterhin (EFI-Dateien wurden kopiert).")
    return False


# ---------------------------------------------------------------------------
# Bad block check (chkdsk)
# ---------------------------------------------------------------------------

def check_bad_blocks_win(
    drive_letter: str,
    log_callback,
    progress_callback,
) -> int:
    """
    Run chkdsk /R on drive_letter to detect bad sectors.
    Returns count of bad sectors found (0 = no issues).
    drive_letter: e.g. 'E:'
    """
    log_callback(f"Starte CHKDSK auf {drive_letter} (kann Minuten dauern)...")
    try:
        proc = subprocess.Popen(
            ["chkdsk", drive_letter, "/R"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        log_callback("chkdsk nicht gefunden.")
        return 0

    bad_sectors = 0
    percent_re = re.compile(r"(\d+)\s*percent", re.IGNORECASE)
    bad_re = re.compile(r"(\d[\d,]*)\s+(?:KB|bytes).*(?:bad|fehlerhafte)", re.IGNORECASE)

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        log_callback(line)

        m = percent_re.search(line)
        if m:
            progress_callback(int(m.group(1)))

        m = bad_re.search(line)
        if m:
            try:
                bad_sectors = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

    proc.wait()
    return bad_sectors


# ---------------------------------------------------------------------------
# ISO content inspection (without mounting)
# ---------------------------------------------------------------------------

def inspect_iso_contents_win(iso_path: str) -> dict:
    """
    Mount an ISO temporarily and inspect its contents.
    Returns dict with keys: has_efi, is_windows, has_isolinux, mount_letter.
    Caller is responsible for calling unmount_iso_win(iso_path) afterwards.
    """
    info = {"has_efi": False, "is_windows": False, "has_isolinux": False}
    letter = mount_iso_win(iso_path)
    if not letter:
        return info

    info["mount_letter"] = letter
    info["has_efi"] = (
        os.path.isdir(os.path.join(letter, "EFI")) or
        os.path.isdir(os.path.join(letter, "efi"))
    )
    info["is_windows"] = (
        os.path.exists(os.path.join(letter, "sources", "install.wim")) or
        os.path.exists(os.path.join(letter, "sources", "install.esd"))
    )
    info["has_isolinux"] = os.path.isdir(os.path.join(letter, "isolinux"))
    return info
