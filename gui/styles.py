"""
QSS Dark Theme for LinBurn.
Dark UI theme for the LinBurn application.
"""

DARK_THEME = """
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: "Segoe UI", "Ubuntu", "DejaVu Sans", sans-serif;
    font-size: 10pt;
}

QMainWindow {
    background-color: #1e1e1e;
}

/* Title bar area */
QLabel#title_label {
    color: #ffffff;
    font-size: 16pt;
    font-weight: bold;
    padding: 4px 0px;
}

QLabel#subtitle_label {
    color: #aaaaaa;
    font-size: 8pt;
}

/* Group boxes */
QGroupBox {
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 12px;
    color: #b0b0b0;
    font-size: 9pt;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    color: #888888;
}

/* Labels */
QLabel {
    color: #cccccc;
    background-color: transparent;
}

QLabel#section_label {
    color: #888888;
    font-size: 8pt;
    text-transform: uppercase;
}

/* ComboBox */
QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 4px 8px;
    color: #e0e0e0;
    min-height: 24px;
}

QComboBox:hover {
    border-color: #555555;
}

QComboBox:focus {
    border-color: #0078d4;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #3a3a3a;
    border-radius: 0 3px 3px 0;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #888888;
    width: 0;
    height: 0;
    margin-right: 4px;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
    color: #e0e0e0;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 2px 8px;
}

/* LineEdit */
QLineEdit {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 4px 8px;
    color: #e0e0e0;
    min-height: 24px;
}

QLineEdit:focus {
    border-color: #0078d4;
}

QLineEdit:read-only {
    color: #888888;
    background-color: #252525;
}

/* Buttons */
QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 5px 16px;
    color: #e0e0e0;
    min-height: 26px;
    min-width: 60px;
}

QPushButton:hover {
    background-color: #3a3a3a;
    border-color: #555555;
}

QPushButton:pressed {
    background-color: #444444;
}

QPushButton:disabled {
    color: #555555;
    border-color: #2a2a2a;
    background-color: #252525;
}

QPushButton#btn_start {
    background-color: #0078d4;
    border-color: #0078d4;
    color: #ffffff;
    font-weight: bold;
    min-width: 80px;
}

QPushButton#btn_start:hover {
    background-color: #1084d8;
    border-color: #1084d8;
}

QPushButton#btn_start:pressed {
    background-color: #006cc0;
}

QPushButton#btn_start:disabled {
    background-color: #1a3a5e;
    border-color: #1a3a5e;
    color: #446688;
}

QPushButton#btn_cancel {
    background-color: #c42b2b;
    border-color: #c42b2b;
    color: #ffffff;
    min-width: 80px;
}

QPushButton#btn_cancel:hover {
    background-color: #d03535;
}

QPushButton#btn_browse {
    min-width: 32px;
    max-width: 32px;
    padding: 4px 6px;
}

QPushButton#btn_refresh {
    min-width: 32px;
    max-width: 32px;
    padding: 4px 6px;
}

/* CheckBox */
QCheckBox {
    color: #cccccc;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #555555;
    border-radius: 2px;
    background-color: #2d2d2d;
}

QCheckBox::indicator:checked {
    background-color: #0078d4;
    border-color: #0078d4;
    image: none;
}

QCheckBox::indicator:hover {
    border-color: #888888;
}

QCheckBox:disabled {
    color: #555555;
}

/* RadioButton */
QRadioButton {
    color: #cccccc;
    spacing: 6px;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #555555;
    border-radius: 7px;
    background-color: #2d2d2d;
}

QRadioButton::indicator:checked {
    background-color: #0078d4;
    border-color: #0078d4;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    background-color: #252525;
    text-align: center;
    color: #cccccc;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #0078d4;
    border-radius: 2px;
}

/* Text Areas / Log */
QTextEdit {
    background-color: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 3px;
    color: #aaaaaa;
    font-family: "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 9pt;
    padding: 4px;
}

/* Splitter */
QSplitter::handle {
    background-color: #3a3a3a;
}

/* Separator line */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #3a3a3a;
    background-color: #3a3a3a;
}

/* ScrollBar */
QScrollBar:vertical {
    background: #1e1e1e;
    width: 12px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #3a3a3a;
    border-radius: 5px;
    min-height: 20px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background: #4a4a4a;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #1e1e1e;
    height: 12px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #3a3a3a;
    border-radius: 5px;
    min-width: 20px;
    margin: 2px;
}

/* ToolTip */
QToolTip {
    background-color: #3a3a3a;
    color: #e0e0e0;
    border: 1px solid #555555;
    padding: 3px 6px;
    border-radius: 3px;
}

/* Status bar */
QStatusBar {
    background-color: #252525;
    border-top: 1px solid #3a3a3a;
    color: #888888;
    font-size: 9pt;
}

/* Warning group box for Windows patches */
QGroupBox#win_patches_group {
    border: 1px solid #4a3500;
    background-color: #1a1200;
}

QGroupBox#win_patches_group::title {
    color: #c8960c;
}
"""


LIGHT_THEME = """
QWidget {
    background-color: #f0f0f0;
    color: #1e1e1e;
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 10pt;
}
"""
