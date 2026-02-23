"""
Bad block checking for USB drives.
Linux:   badblocks utility
Windows: chkdsk /R (via core.platform.windows)
Runs as a QThread to avoid blocking the UI.
"""
import re
import subprocess
import sys
from PyQt6.QtCore import QThread, pyqtSignal


class BadBlockChecker(QThread):
    """
    Runs badblocks on a device and reports progress.

    Signals:
        progress(int):         0-100 percent complete
        log(str):              Log message
        bad_block_found(int):  Block number of a found bad block
        finished_ok(int):      Total bad blocks found
        error(str):            Error message
    """
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    bad_block_found = pyqtSignal(int)
    finished_ok = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(
        self,
        device_path: str,
        destructive: bool = False,
        block_size: int = 4096,
        parent=None,
    ):
        super().__init__(parent)
        self.device_path = device_path
        self.destructive = destructive
        self.block_size = block_size
        self._process = None
        self._abort = False

    def run(self):
        self._abort = False
        mode = "Schreibtest (destruktiv)" if self.destructive else "Lesetest (nicht-destruktiv)"
        self.log.emit(f"Starte Bad-Block-Prüfung [{mode}] auf {self.device_path}...")

        if sys.platform == "win32":
            self._run_windows()
            return

        cmd = ["badblocks", "-b", str(self.block_size), "-s", "-v"]
        if self.destructive:
            cmd.append("-w")
        cmd.append(self.device_path)

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            self.error.emit("'badblocks' nicht gefunden. Bitte installieren: sudo apt install e2fsprogs")
            return
        except PermissionError:
            self.error.emit("Keine Berechtigung für badblocks. Bitte als root/sudo ausführen.")
            return

        bad_blocks = []
        percent_pattern = re.compile(r"(\d+\.\d+)%")
        block_pattern = re.compile(r"^(\d+)$")

        try:
            for line in self._process.stdout:
                if self._abort:
                    self._process.terminate()
                    self.log.emit("Abgebrochen.")
                    return

                line = line.strip()
                if not line:
                    continue

                # Progress: "Checking for bad blocks (non-destructive read-write test): 12.34% done"
                match = percent_pattern.search(line)
                if match:
                    pct = float(match.group(1))
                    self.progress.emit(int(pct))
                    continue

                # Bad block number
                if block_pattern.match(line):
                    block_num = int(line)
                    bad_blocks.append(block_num)
                    self.bad_block_found.emit(block_num)
                    self.log.emit(f"Schlechter Block gefunden: {block_num}")
                    continue

                # General output
                self.log.emit(line)

            self._process.wait()

        except Exception as e:
            self.error.emit(f"Fehler während der Prüfung: {e}")
            return

        if self._process.returncode not in (0, None) and not self._abort:
            self.error.emit(f"badblocks beendet mit Fehlercode {self._process.returncode}")
            return

        count = len(bad_blocks)
        self.progress.emit(100)
        if count == 0:
            self.log.emit("Keine schlechten Blöcke gefunden.")
        else:
            self.log.emit(f"Prüfung abgeschlossen: {count} schlechte Blöcke gefunden.")
        self.finished_ok.emit(count)

    def abort(self):
        self._abort = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def _run_windows(self):
        """Windows: use chkdsk /R via check_bad_blocks_win."""
        from core.platform.windows import get_disk_number, get_disk_drive_letters, check_bad_blocks_win

        disk_num = get_disk_number(self.device_path)
        if disk_num is None:
            self.error.emit(f"Ungültiger Gerätepfad: {self.device_path}")
            return

        letters = get_disk_drive_letters(disk_num)
        if not letters:
            self.error.emit(
                "Kein Laufwerksbuchstabe für dieses Gerät gefunden. "
                "Bitte zuerst formatieren, damit chkdsk ausgeführt werden kann."
            )
            return

        drive_letter = letters[0]
        bad_count = check_bad_blocks_win(
            drive_letter=drive_letter,
            log_callback=self.log.emit,
            progress_callback=self.progress.emit,
        )
        self.progress.emit(100)
        if bad_count == 0:
            self.log.emit("Keine schlechten Sektoren gefunden (chkdsk).")
        else:
            self.log.emit(f"chkdsk: {bad_count} fehlerhafte Sektoren gefunden.")
        self.finished_ok.emit(bad_count)
