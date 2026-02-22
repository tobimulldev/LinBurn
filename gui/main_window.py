"""
Main application window for LinBurn.
Provides an interface for creating bootable USB drives on Linux.
"""
import os
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QCheckBox,
    QProgressBar, QTextEdit, QGroupBox, QFileDialog, QMessageBox,
    QFrame,
)

from core.device_manager import DeviceManager, UdevMonitor, Device
from core.iso_analyzer import IsoAnalyzer, IsoInfo
from core.usb_writer import UsbWriter, WriteConfig
from core.bad_block_checker import BadBlockChecker
from gui.styles import DARK_THEME
from gui.translations import tr, set_language, get_language


class IsoAnalyzerThread(QThread):
    """Runs ISO analysis in background."""
    done = pyqtSignal(object)  # IsoInfo

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        info = IsoAnalyzer.analyze(self.path)
        self.done.emit(info)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._writer: Optional[UsbWriter] = None
        self._bad_block_checker: Optional[BadBlockChecker] = None
        self._iso_info: Optional[IsoInfo] = None
        self._iso_analyzer_thread: Optional[IsoAnalyzerThread] = None
        self._devices: list[Device] = []
        self._udev_monitor: Optional[UdevMonitor] = None

        self.setMinimumWidth(520)
        self.setMinimumHeight(580)
        self.resize(540, 680)

        self._build_ui()
        self._apply_theme()
        self._connect_signals()
        self._retranslate_ui()
        self._refresh_devices()
        self._start_udev_monitor()

    # ------------------------------------------------------------------
    # UI Building
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        main_layout.addLayout(self._build_header())
        main_layout.addWidget(self._separator())
        main_layout.addLayout(self._build_device_row())
        main_layout.addLayout(self._build_iso_row())
        main_layout.addWidget(self._separator())
        main_layout.addLayout(self._build_options_grid())
        main_layout.addWidget(self._separator())
        main_layout.addLayout(self._build_advanced_options())
        main_layout.addWidget(self._separator())

        # Windows 11 patches (hidden by default)
        self._win_group = self._build_win_patches_group()
        main_layout.addWidget(self._win_group)
        self._win_group.setVisible(False)

        main_layout.addLayout(self._build_progress_section())
        main_layout.addWidget(self._separator())
        main_layout.addLayout(self._build_buttons())

        # Log (collapsible)
        self._log_group = QGroupBox()
        log_layout = QVBoxLayout(self._log_group)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(150)
        log_layout.addWidget(self._log_text)
        main_layout.addWidget(self._log_group)

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        title = QLabel("LinBurn")
        title.setObjectName("title_label")
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)

        self._lbl_subtitle = QLabel()
        self._lbl_subtitle.setObjectName("subtitle_label")
        self._lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignBottom)

        layout.addWidget(title)
        layout.addWidget(self._lbl_subtitle)
        layout.addStretch()

        self._header_status = QLabel("")
        layout.addWidget(self._header_status)

        self._btn_lang = QPushButton()
        self._btn_lang.setObjectName("btn_lang")
        self._btn_lang.setFixedWidth(40)
        self._btn_lang.setToolTip("Switch language / Sprache wechseln")
        layout.addWidget(self._btn_lang)

        return layout

    def _build_device_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self._lbl_device = QLabel()
        self._lbl_device.setMinimumWidth(130)
        self._combo_device = QComboBox()
        self._combo_device.setMinimumWidth(280)

        self._btn_refresh = QPushButton("⟳")
        self._btn_refresh.setObjectName("btn_refresh")

        layout.addWidget(self._lbl_device)
        layout.addWidget(self._combo_device, stretch=1)
        layout.addWidget(self._btn_refresh)
        return layout

    def _build_iso_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self._lbl_boot_type = QLabel()
        self._lbl_boot_type.setMinimumWidth(130)

        self._combo_boot_type = QComboBox()
        self._combo_boot_type.setMinimumWidth(160)

        self._edit_iso_path = QLineEdit()
        self._edit_iso_path.setReadOnly(True)

        self._btn_browse = QPushButton("...")
        self._btn_browse.setObjectName("btn_browse")

        layout.addWidget(self._lbl_boot_type)
        layout.addWidget(self._combo_boot_type)
        layout.addWidget(self._edit_iso_path, stretch=1)
        layout.addWidget(self._btn_browse)
        return layout

    def _build_options_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        col_label_width = 130

        self._lbl_image_option = QLabel()
        self._lbl_image_option.setMinimumWidth(col_label_width)
        self._combo_image_option = QComboBox()
        grid.addWidget(self._lbl_image_option, 0, 0)
        grid.addWidget(self._combo_image_option, 0, 1)

        self._lbl_scheme = QLabel()
        self._lbl_scheme.setMinimumWidth(col_label_width)
        self._combo_scheme = QComboBox()
        self._combo_scheme.addItems(["MBR", "GPT"])
        grid.addWidget(self._lbl_scheme, 1, 0)
        grid.addWidget(self._combo_scheme, 1, 1)

        self._lbl_target = QLabel()
        self._lbl_target.setMinimumWidth(col_label_width)
        self._combo_target = QComboBox()
        grid.addWidget(self._lbl_target, 2, 0)
        grid.addWidget(self._combo_target, 2, 1)

        self._lbl_fs = QLabel()
        self._lbl_fs.setMinimumWidth(col_label_width)
        self._combo_fs = QComboBox()
        grid.addWidget(self._lbl_fs, 3, 0)
        grid.addWidget(self._combo_fs, 3, 1)

        self._lbl_cluster = QLabel()
        self._lbl_cluster.setMinimumWidth(col_label_width)
        self._combo_cluster = QComboBox()
        grid.addWidget(self._lbl_cluster, 4, 0)
        grid.addWidget(self._combo_cluster, 4, 1)

        self._lbl_vol = QLabel()
        self._lbl_vol.setMinimumWidth(col_label_width)
        self._edit_label = QLineEdit("LINBURN")
        self._edit_label.setMaxLength(32)
        grid.addWidget(self._lbl_vol, 5, 0)
        grid.addWidget(self._edit_label, 5, 1)

        return grid

    def _build_advanced_options(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(4)

        self._chk_quick_format = QCheckBox()
        self._chk_quick_format.setChecked(True)

        self._chk_bad_blocks = QCheckBox()

        layout.addWidget(self._chk_quick_format)
        layout.addWidget(self._chk_bad_blocks)
        return layout

    def _build_win_patches_group(self) -> QGroupBox:
        group = QGroupBox()
        group.setObjectName("win_patches_group")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        self._win_warning = QLabel()
        self._win_warning.setStyleSheet("color: #c8960c; font-size: 9pt;")
        layout.addWidget(self._win_warning)

        self._chk_bypass_tpm = QCheckBox()
        self._chk_bypass_tpm.setChecked(True)
        self._chk_bypass_secureboot = QCheckBox()
        self._chk_bypass_secureboot.setChecked(True)
        self._chk_bypass_ram = QCheckBox()
        self._chk_bypass_ram.setChecked(True)
        self._chk_remove_online = QCheckBox()
        self._chk_remove_online.setChecked(True)

        layout.addWidget(self._chk_bypass_tpm)
        layout.addWidget(self._chk_bypass_secureboot)
        layout.addWidget(self._chk_bypass_ram)
        layout.addWidget(self._chk_remove_online)
        return group

    def _build_progress_section(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(4)

        step_row = QHBoxLayout()
        self._lbl_step = QLabel()
        self._lbl_step.setStyleSheet("color: #666666; font-size: 8pt;")
        self._lbl_step_name = QLabel("")
        self._lbl_step_name.setStyleSheet("color: #888888; font-size: 8pt;")
        self._lbl_step_name.setAlignment(Qt.AlignmentFlag.AlignRight)
        step_row.addWidget(self._lbl_step)
        step_row.addWidget(self._lbl_step_name, stretch=1)
        layout.addLayout(step_row)

        self._step_bar = QProgressBar()
        self._step_bar.setRange(0, 100)
        self._step_bar.setValue(0)
        self._step_bar.setTextVisible(True)
        self._step_bar.setMinimumHeight(16)
        self._step_bar.setStyleSheet(
            "QProgressBar { font-size: 8pt; } "
            "QProgressBar::chunk { background-color: #005a9e; }"
        )
        layout.addWidget(self._step_bar)

        self._lbl_status = QLabel()
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_status.setStyleSheet(
            "color: #aaaaaa; font-size: 9pt; font-family: monospace;"
        )
        self._lbl_status.setMinimumHeight(18)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setMinimumHeight(22)

        layout.addWidget(self._lbl_status)
        layout.addWidget(self._progress_bar)
        return layout

    def _build_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._btn_about = QPushButton()
        layout.addWidget(self._btn_about)
        layout.addStretch()

        self._btn_start = QPushButton("START")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.setMinimumWidth(90)

        self._btn_cancel = QPushButton()
        self._btn_cancel.setObjectName("btn_cancel")
        self._btn_cancel.setEnabled(False)

        self._btn_close = QPushButton()

        layout.addWidget(self._btn_start)
        layout.addWidget(self._btn_cancel)
        layout.addWidget(self._btn_close)
        return layout

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def _toggle_language(self):
        set_language("en" if get_language() == "de" else "de")
        self._retranslate_ui()
        self._refresh_devices()

    def _retranslate_ui(self):
        self.setWindowTitle(tr("window_title"))
        self._lbl_subtitle.setText(tr("subtitle"))
        self._btn_lang.setText("EN" if get_language() == "de" else "DE")

        # Device row
        self._lbl_device.setText(tr("device_label"))
        self._combo_device.setToolTip(tr("device_tooltip"))
        self._btn_refresh.setToolTip(tr("refresh_tooltip"))

        # ISO row
        self._lbl_boot_type.setText(tr("boot_type_label"))
        idx = self._combo_boot_type.currentIndex()
        self._combo_boot_type.blockSignals(True)
        self._combo_boot_type.clear()
        self._combo_boot_type.addItems([tr("boot_iso"), tr("boot_format_only")])
        self._combo_boot_type.setCurrentIndex(max(0, idx))
        self._combo_boot_type.blockSignals(False)
        self._edit_iso_path.setPlaceholderText(tr("iso_placeholder"))
        self._btn_browse.setToolTip(tr("browse_tooltip"))

        # Options grid
        self._lbl_image_option.setText(tr("image_option_label"))
        idx = self._combo_image_option.currentIndex()
        self._combo_image_option.blockSignals(True)
        self._combo_image_option.clear()
        self._combo_image_option.addItems([tr("image_standard"), tr("image_dd")])
        self._combo_image_option.setToolTip(tr("image_option_tooltip"))
        self._combo_image_option.setCurrentIndex(max(0, idx))
        self._combo_image_option.blockSignals(False)

        self._lbl_scheme.setText(tr("scheme_label"))
        self._combo_scheme.setToolTip(tr("scheme_tooltip"))

        self._lbl_target.setText(tr("target_label"))
        idx = self._combo_target.currentIndex()
        self._combo_target.blockSignals(True)
        self._combo_target.clear()
        self._combo_target.addItems([tr("target_bios"), tr("target_uefi"), tr("target_both")])
        self._combo_target.setCurrentIndex(2 if idx < 0 else idx)
        self._combo_target.blockSignals(False)

        self._lbl_fs.setText(tr("fs_label"))
        idx = self._combo_fs.currentIndex()
        self._combo_fs.blockSignals(True)
        self._combo_fs.clear()
        self._combo_fs.addItems([tr("fs_fat32"), "NTFS", "exFAT", "ext4"])
        self._combo_fs.setCurrentIndex(max(0, idx))
        self._combo_fs.blockSignals(False)

        self._lbl_cluster.setText(tr("cluster_label"))
        self._update_cluster_sizes()

        self._lbl_vol.setText(tr("vol_label"))

        # Advanced options
        self._chk_quick_format.setText(tr("quick_format"))
        self._chk_quick_format.setToolTip(tr("quick_format_tooltip"))
        self._chk_bad_blocks.setText(tr("bad_blocks"))
        self._chk_bad_blocks.setToolTip(tr("bad_blocks_tooltip"))

        # Windows patches group
        self._win_group.setTitle(tr("win_group"))
        self._win_warning.setText(tr("win_warning"))
        self._chk_bypass_tpm.setText(tr("win_bypass_tpm"))
        self._chk_bypass_secureboot.setText(tr("win_bypass_secureboot"))
        self._chk_bypass_ram.setText(tr("win_bypass_ram"))
        self._chk_remove_online.setText(tr("win_remove_online"))

        # Progress
        self._lbl_step.setText(tr("step_label"))
        self._step_bar.setFormat(tr("step_format"))
        self._lbl_status.setText(tr("status_ready"))
        self._progress_bar.setFormat(tr("total_format"))

        # Buttons
        self._btn_about.setText(tr("btn_about"))
        self._btn_cancel.setText(tr("btn_cancel"))
        self._btn_close.setText(tr("btn_close"))

        # Log group
        self._log_group.setTitle(tr("log_group"))

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self):
        self.setStyleSheet(DARK_THEME)

    # ------------------------------------------------------------------
    # Signals & Connections
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._btn_refresh.clicked.connect(self._refresh_devices)
        self._btn_browse.clicked.connect(self._browse_iso)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_close.clicked.connect(self.close)
        self._btn_about.clicked.connect(self._show_about)
        self._btn_lang.clicked.connect(self._toggle_language)
        self._combo_boot_type.currentIndexChanged.connect(self._on_boot_type_changed)
        self._combo_image_option.currentIndexChanged.connect(self._on_image_option_changed)
        self._combo_fs.currentIndexChanged.connect(self._update_cluster_sizes)
        self._combo_scheme.currentIndexChanged.connect(self._on_scheme_changed)

    # ------------------------------------------------------------------
    # Device Management
    # ------------------------------------------------------------------

    def _refresh_devices(self):
        self._devices = DeviceManager.list_devices()
        self._combo_device.clear()

        if not self._devices:
            self._combo_device.addItem(tr("no_device"))
            self._btn_start.setEnabled(False)
        else:
            for dev in self._devices:
                self._combo_device.addItem(str(dev))
            self._btn_start.setEnabled(True)

    def _start_udev_monitor(self):
        try:
            self._udev_monitor = UdevMonitor(self)
            self._udev_monitor.device_changed.connect(self._refresh_devices)
            self._udev_monitor.start()
        except Exception:
            pass  # udev not available, manual refresh only

    def _current_device(self) -> Optional[Device]:
        idx = self._combo_device.currentIndex()
        if 0 <= idx < len(self._devices):
            return self._devices[idx]
        return None

    # ------------------------------------------------------------------
    # ISO Selection & Analysis
    # ------------------------------------------------------------------

    def _browse_iso(self):
        # Determine real user's home directory when running as root
        import pwd
        start_dir = "/"
        sudo_user = os.environ.get("SUDO_USER")
        pkexec_uid = os.environ.get("PKEXEC_UID")
        if sudo_user:
            try:
                start_dir = pwd.getpwnam(sudo_user).pw_dir
            except KeyError:
                pass
        elif pkexec_uid:
            try:
                start_dir = pwd.getpwuid(int(pkexec_uid)).pw_dir
            except (KeyError, ValueError):
                pass
        elif os.geteuid() != 0:
            start_dir = os.path.expanduser("~")

        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("iso_open_title"),
            start_dir,
            tr("iso_filter"),
        )
        if not path:
            return

        self._edit_iso_path.setText(path)
        self._iso_info = None
        self._win_group.setVisible(False)
        self._lbl_status.setText(tr("analyzing_iso"))
        self._log(tr("analyzing_iso_log"))

        self._iso_analyzer_thread = IsoAnalyzerThread(path, self)
        self._iso_analyzer_thread.done.connect(self._on_iso_analyzed)
        self._iso_analyzer_thread.start()

    def _on_iso_analyzed(self, info: IsoInfo):
        self._iso_info = info

        if info.error:
            self._log(tr("iso_analysis_error").format(info.error))
            self._lbl_status.setText(tr("iso_analysis_failed"))
            return

        yes = tr("yes")
        no = tr("no")
        self._log(
            f"ISO: {info.label} | {info.size_str} | "
            f"{tr('lbl_bootable')}: {yes if info.is_bootable else no} | "
            f"UEFI: {yes if info.has_uefi else no} | "
            f"Windows: {yes if info.is_windows else no}"
        )

        # Apply recommendations
        scheme_idx = 1 if info.recommended_scheme == "GPT" else 0
        self._combo_scheme.setCurrentIndex(scheme_idx)

        fs_map = {"FAT32": 0, "NTFS": 1, "exFAT": 2, "ext4": 3}
        self._combo_fs.setCurrentIndex(fs_map.get(info.recommended_fs, 0))

        if info.label:
            self._edit_label.setText(info.label[:32])

        if info.is_windows11:
            self._win_group.setVisible(True)
            self._log(tr("win11_detected_log"))
        else:
            self._win_group.setVisible(False)

        self._lbl_status.setText(tr("iso_ready"))
        self._update_cluster_sizes()

    # ------------------------------------------------------------------
    # UI Updates
    # ------------------------------------------------------------------

    def _on_boot_type_changed(self, idx: int):
        is_iso = idx == 0
        self._edit_iso_path.setVisible(is_iso)
        self._btn_browse.setVisible(is_iso)
        self._combo_image_option.setVisible(is_iso)

    def _on_image_option_changed(self, idx: int):
        is_dd = idx == 1  # DD mode
        self._combo_scheme.setEnabled(not is_dd)
        self._combo_target.setEnabled(not is_dd)
        self._combo_fs.setEnabled(not is_dd)
        self._combo_cluster.setEnabled(not is_dd)
        self._edit_label.setEnabled(not is_dd)
        self._chk_quick_format.setEnabled(not is_dd)

    def _on_scheme_changed(self, _idx: int):
        # MBR doesn't support UEFI-only target (index 1)
        if self._combo_scheme.currentText() == "MBR":
            if self._combo_target.currentIndex() == 1:
                self._combo_target.setCurrentIndex(0)

    def _update_cluster_sizes(self):
        fs_map = {0: "FAT32", 1: "NTFS", 2: "exFAT", 3: "ext4"}
        fs = fs_map.get(self._combo_fs.currentIndex(), "FAT32")
        default = tr("cluster_default")
        sizes = {
            "FAT32":  [default, "512 B", "1 KB", "2 KB", "4 KB", "8 KB", "16 KB", "32 KB"],
            "NTFS":   [default, "512 B", "1 KB", "2 KB", "4 KB", "8 KB", "16 KB", "32 KB", "64 KB"],
            "exFAT":  [default, "4 KB", "8 KB", "16 KB", "32 KB", "64 KB", "128 KB"],
            "ext4":   [default, "1 KB", "2 KB", "4 KB", "8 KB", "16 KB", "32 KB", "64 KB"],
        }
        self._combo_cluster.clear()
        self._combo_cluster.addItems(sizes.get(fs, [default]))

    def _get_cluster_size_bytes(self) -> int:
        # Index 0 is always "Default/Standard" regardless of language
        if self._combo_cluster.currentIndex() == 0:
            return 0
        text = self._combo_cluster.currentText()
        try:
            val, unit = text.split()
            val = int(val)
            if unit == "B":
                return val
            elif unit == "KB":
                return val * 1024
            elif unit == "MB":
                return val * 1024 * 1024
        except (ValueError, AttributeError):
            return 0
        return 0

    def _get_filesystem(self) -> str:
        fs_map = {0: "FAT32", 1: "NTFS", 2: "exFAT", 3: "ext4"}
        return fs_map.get(self._combo_fs.currentIndex(), "FAT32")

    def _get_target_system(self) -> str:
        target_map = {0: "BIOS", 1: "UEFI", 2: "BIOS+UEFI"}
        return target_map.get(self._combo_target.currentIndex(), "BIOS+UEFI")

    # ------------------------------------------------------------------
    # Start / Cancel
    # ------------------------------------------------------------------

    def _on_start(self):
        device = self._current_device()
        if not device:
            QMessageBox.warning(self, tr("dlg_no_device_title"), tr("dlg_no_device_msg"))
            return

        boot_type = self._combo_boot_type.currentIndex()
        is_format_only = boot_type == 1
        iso_path = self._edit_iso_path.text().strip()

        if not is_format_only and not iso_path:
            QMessageBox.warning(self, tr("dlg_no_iso_title"), tr("dlg_no_iso_msg"))
            return

        if not is_format_only and not os.path.isfile(iso_path):
            QMessageBox.warning(
                self,
                tr("dlg_file_not_found_title"),
                tr("dlg_file_not_found_msg").format(iso_path),
            )
            return

        # Confirmation
        msg = tr("dlg_confirm_warning").format(device)
        if not is_format_only:
            msg += tr("dlg_confirm_iso").format(os.path.basename(iso_path))
        msg += tr("dlg_confirm_cont")

        reply = QMessageBox.question(
            self, tr("dlg_confirm_title"), msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if is_format_only:
            mode = "FORMAT"
        elif self._combo_image_option.currentIndex() == 1:
            mode = "DD"
        else:
            mode = "ISO"

        config = WriteConfig(
            iso_path=iso_path,
            device_path=device.path,
            mode=mode,
            scheme=self._combo_scheme.currentText(),
            target_system=self._get_target_system(),
            filesystem=self._get_filesystem(),
            cluster_size=self._get_cluster_size_bytes(),
            label=self._edit_label.text().strip() or "LINBURN",
            quick_format=self._chk_quick_format.isChecked(),
            check_bad_blocks=self._chk_bad_blocks.isChecked(),
            win_bypass_tpm=self._chk_bypass_tpm.isChecked() if self._win_group.isVisible() else False,
            win_bypass_secureboot=self._chk_bypass_secureboot.isChecked() if self._win_group.isVisible() else False,
            win_bypass_ram=self._chk_bypass_ram.isChecked() if self._win_group.isVisible() else False,
            win_remove_online=self._chk_remove_online.isChecked() if self._win_group.isVisible() else False,
        )

        if config.check_bad_blocks:
            self._start_bad_block_check(device.path, config)
        else:
            self._start_write(config)

    def _start_bad_block_check(self, device_path: str, config: WriteConfig):
        self._set_writing_state(True)
        self._log(tr("log_bad_block_start"))

        self._bad_block_checker = BadBlockChecker(device_path, parent=self)
        self._bad_block_checker.progress.connect(self._progress_bar.setValue)
        self._bad_block_checker.log.connect(self._log)
        self._bad_block_checker.bad_block_found.connect(
            lambda b: self._log(tr("log_bad_block").format(b))
        )
        self._bad_block_checker.finished_ok.connect(
            lambda count: self._on_bad_block_done(count, config)
        )
        self._bad_block_checker.error.connect(self._on_error)
        self._bad_block_checker.start()

    def _on_bad_block_done(self, count: int, config: WriteConfig):
        if count > 0:
            reply = QMessageBox.question(
                self,
                tr("dlg_bad_blocks_title"),
                tr("dlg_bad_blocks_msg").format(count),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._set_writing_state(False)
                return

        self._start_write(config)

    def _start_write(self, config: WriteConfig):
        self._set_writing_state(True)
        self._log(tr("log_write_start").format(config.mode))
        self._log(tr("log_device").format(config.device_path))
        if config.iso_path:
            self._log(tr("log_iso").format(config.iso_path))

        self._step_bar.setValue(0)
        self._lbl_step.setText(tr("step_label"))
        self._lbl_step_name.setText("")

        self._writer = UsbWriter(config, parent=self)
        self._writer.progress.connect(self._progress_bar.setValue)
        self._writer.step_progress.connect(self._on_step_progress)
        self._writer.status.connect(self._lbl_status.setText)
        self._writer.log.connect(self._log)
        self._writer.finished_ok.connect(self._on_write_done)
        self._writer.error.connect(self._on_error)
        self._writer.start()

    def _on_cancel(self):
        reply = QMessageBox.question(
            self,
            tr("dlg_cancel_title"),
            tr("dlg_cancel_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self._writer and self._writer.isRunning():
            self._writer.abort()
            self._log(tr("log_abort_req"))
        if self._bad_block_checker and self._bad_block_checker.isRunning():
            self._bad_block_checker.abort()
            self._log(tr("log_bad_block_aborted"))
        self._set_writing_state(False)
        self._lbl_status.setText(tr("status_cancelled"))

    def _on_step_progress(self, current: int, total: int, name: str):
        self._lbl_step.setText(tr("step_format_dyn").format(current, total))
        self._lbl_step_name.setText(name)
        pct = int(current / total * 100) if total else 0
        self._step_bar.setValue(pct)

    def _on_write_done(self):
        self._progress_bar.setValue(100)
        self._step_bar.setValue(100)
        self._lbl_status.setText(tr("status_done"))
        self._log(tr("log_done"))
        QMessageBox.information(self, tr("dlg_done_title"), tr("dlg_done_msg"))
        self._set_writing_state(False)

    def _on_error(self, msg: str):
        self._lbl_status.setText(tr("status_error"))
        self._log(tr("log_error").format(msg))
        QMessageBox.critical(self, tr("dlg_error_title"), tr("dlg_error_msg").format(msg))
        self._set_writing_state(False)

    def _set_writing_state(self, writing: bool):
        self._btn_start.setEnabled(not writing)
        self._btn_cancel.setEnabled(writing)
        self._btn_refresh.setEnabled(not writing)
        self._btn_browse.setEnabled(not writing)
        self._combo_device.setEnabled(not writing)
        if not writing:
            self._writer = None
            self._bad_block_checker = None

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, msg: str):
        self._log_text.append(msg)
        scrollbar = self._log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------

    def _show_about(self):
        QMessageBox.about(self, tr("dlg_about_title"), tr("dlg_about_msg"))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._writer and self._writer.isRunning():
            reply = QMessageBox.question(
                self,
                tr("dlg_quit_title"),
                tr("dlg_quit_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._writer.abort()
            self._writer.wait(3000)

        if self._iso_analyzer_thread and self._iso_analyzer_thread.isRunning():
            self._iso_analyzer_thread.quit()
            if not self._iso_analyzer_thread.wait(1000):
                self._iso_analyzer_thread.terminate()
                self._iso_analyzer_thread.wait()

        if self._bad_block_checker and self._bad_block_checker.isRunning():
            self._bad_block_checker.abort()
            if not self._bad_block_checker.wait(2000):
                self._bad_block_checker.terminate()
                self._bad_block_checker.wait()

        if self._udev_monitor:
            self._udev_monitor.stop()
            if not self._udev_monitor.wait(500):
                self._udev_monitor.terminate()
                self._udev_monitor.wait()

        event.accept()
