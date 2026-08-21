# Design system themes and stylesheets for SilverSpoon (PyQt6)
# Industrial / Swiss clean aesthetic with crisp, subtle borders and minimal rounding
import os as _os
import sys as _sys

# Support both dev (..\\theme_assets) and PyInstaller frozen (_MEIPASS/theme_assets)
if getattr(_sys, "_MEIPASS", None):
    _ASSET_DIR = _os.path.join(_sys._MEIPASS, "theme_assets").replace("\\", "/")
else:
    _ASSET_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "theme_assets").replace("\\", "/")

def _asset(name: str) -> str:
    return f"{_ASSET_DIR}/{name}"

# Pre-resolve png paths for QSS image urls (Qt requires file paths, data: URIs are unreliable)
_CHECK_WHITE = _asset("check_white.png")
_CHECK_GREY = _asset("check_grey.png")
_CHECK_GREY_DARK = _asset("check_grey_dark.png")
_DOT_WHITE = _asset("dot_white.png")
_DOT_GREY = _asset("dot_grey.png")
_DOT_GREY_DARK = _asset("dot_grey_dark.png")

DARK_THEME_QSS = """
QMainWindow {
    background-color: #0d0f12;
    color: #e6edf3;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", "Roboto", "Helvetica Neue", sans-serif;
    font-size: 13px;
    color: #c9d1d9;
}

/* Bento Cards / Containers */
QFrame#bentoCard {
    background-color: #14171d;
    border: 1px solid #222731;
    border-radius: 3px;
}

QFrame#bentoCard:hover {
    border: 1px solid #2d3442;
}

QFrame#statusCard {
    background-color: #14171d;
    border: 1px solid #222731;
    border-radius: 3px;
}

/* Headers & Labels */
QLabel#sectionTitle {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #6e7681;
}

QLabel#statValue {
    font-size: 18px;
    font-weight: 700;
    color: #58a6ff;
}

QLabel#statLabel {
    font-size: 11px;
    font-weight: 600;
    color: #8b949e;
}

QLabel#speedDisplay {
    font-size: 20px;
    font-weight: 800;
    color: #3fb950;
    letter-spacing: -0.5px;
}

/* Input Fields */
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background-color: #0a0c0f;
    border: 1px solid #222731;
    border-radius: 2px;
    padding: 6px 8px;
    color: #f0f6fc;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #58a6ff;
    background-color: #0d1015;
}

QLineEdit:hover, QTextEdit:hover, QSpinBox:hover, QComboBox:hover {
    border: 1px solid #323a48;
}

/* ComboBox Dropdown */
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left-width: 0px;
    border-radius: 0px;
}

QComboBox QAbstractItemView {
    background-color: #14171d;
    border: 1px solid #2d3442;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
    padding: 2px;
    outline: none;
    border-radius: 2px;
}

/* Push Buttons */
QPushButton {
    background-color: #1c2128;
    border: 1px solid #2d333b;
    border-radius: 2px;
    color: #c9d1d9;
    font-weight: 600;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #282f38;
    border-color: #444c56;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #14181f;
    border-color: #58a6ff;
}

QPushButton:disabled {
    background-color: #12151a;
    border-color: #1c2128;
    color: #484f58;
}

/* Semantic Button Styles */
QPushButton#primaryBtn {
    background-color: #1f6feb;
    border: 1px solid #388bfd;
    color: #ffffff;
}

QPushButton#primaryBtn:hover {
    background-color: #388bfd;
    border-color: #58a6ff;
}

QPushButton#primaryBtn:pressed {
    background-color: #1158c7;
}

QPushButton#successBtn {
    background-color: #238636;
    border: 1px solid #2ea043;
    color: #ffffff;
}

QPushButton#successBtn:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}

QPushButton#successBtn:pressed {
    background-color: #196c2e;
}

QPushButton#warningBtn {
    background-color: #9e6a03;
    border: 1px solid #bb8009;
    color: #ffffff;
}

QPushButton#warningBtn:hover {
    background-color: #bb8009;
    border-color: #d29922;
}

QPushButton#dangerBtn {
    background-color: #da3633;
    border: 1px solid #f85149;
    color: #ffffff;
}

QPushButton#dangerBtn:hover {
    background-color: #f85149;
    border-color: #ff7b72;
}

QPushButton#purpleBtn {
    background-color: #8957e5;
    border: 1px solid #a371f7;
    color: #ffffff;
}

QPushButton#purpleBtn:hover {
    background-color: #a371f7;
}

QPushButton#darkRedBtn {
    background-color: #4d1212;
    border: 1px solid #731b1b;
    color: #f0f6fc;
}

QPushButton#darkRedBtn:hover {
    background-color: #6b1818;
    border-color: #942222;
}

/* Tree Widget / Task List */
QTreeWidget {
    background-color: #101318;
    border: 1px solid #222731;
    border-radius: 2px;
    padding: 2px;
    color: #e6edf3;
    outline: none;
}

QTreeWidget::item {
    height: 28px;
    border-radius: 1px;
    padding: 1px 3px;
    margin: 1px 0px;
}

QTreeWidget::item:hover {
    background-color: #171b22;
}

QTreeWidget::item:selected {
    background-color: #1c222d;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #14171d;
    color: #7d8590;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 5px 8px;
    border: none;
    border-bottom: 1px solid #222731;
}

/* CheckBox */
QCheckBox {
    color: #c9d1d9;
    font-weight: 500;
    spacing: 6px;
}

QCheckBox:disabled {
    color: #57606a;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 2px;
    border: 1px solid #303746;
    background-color: #0a0c0f;
}

QCheckBox::indicator:hover {
    border: 1px solid #58a6ff;
}

QCheckBox::indicator:checked {
    background-color: #1f6feb;
    border: 1px solid #58a6ff;
    image: url("__CHECK_WHITE__");
}

QCheckBox::indicator:disabled {
    border: 1px solid #21262d;
    background-color: #161b22;
}

QCheckBox::indicator:checked:disabled {
    background-color: #21262d;
    border: 1px solid #30363d;
    image: url("__CHECK_GREY_DARK__");
}

/* RadioButton */
QRadioButton {
    color: #c9d1d9;
    font-weight: 500;
    spacing: 6px;
}

QRadioButton:disabled {
    color: #57606a;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1px solid #303746;
    background-color: #0a0c0f;
}

QRadioButton::indicator:hover {
    border: 1px solid #58a6ff;
}

QRadioButton::indicator:checked {
    background-color: #1f6feb;
    border: 1px solid #58a6ff;
    image: url("__DOT_WHITE__");
}

QRadioButton::indicator:disabled {
    border: 1px solid #21262d;
    background-color: #161b22;
}

QRadioButton::indicator:checked:disabled {
    background-color: #21262d;
    border: 1px solid #30363d;
    image: url("__DOT_GREY_DARK__");
}

/* GroupBox & DateEdit */
QGroupBox {
    font-weight: 700;
    font-size: 11px;
    color: #8b949e;
    border: 1px solid #222731;
    border-radius: 3px;
    margin-top: 14px;
    padding-top: 14px;
    background-color: #101318;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    background-color: #0d0f12;
}

QDateEdit {
    background-color: #0a0c0f;
    border: 1px solid #222731;
    border-radius: 2px;
    padding: 4px 6px;
    color: #f0f6fc;
}

QDateEdit:focus {
    border: 1px solid #58a6ff;
}

QDateEdit:disabled {
    background-color: #161b22;
    border-color: #21262d;
    color: #484f58;
}

/* Menu & MenuBar */
QMenuBar {
    background-color: #0d0f12;
    color: #c9d1d9;
    border-bottom: 1px solid #1c2128;
    padding: 0px 4px;
}

QMenuBar::item {
    padding: 2px 6px;
    border-radius: 2px;
}

QMenuBar::item:selected {
    background-color: #1c2128;
    color: #ffffff;
}

QMenu {
    background-color: #14171d;
    border: 1px solid #2d3442;
    border-radius: 3px;
    padding: 4px;
    color: #c9d1d9;
}

QMenu::item {
    padding: 5px 20px 5px 10px;
    border-radius: 2px;
}

QMenu::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #222731;
    margin: 3px 4px;
}

/* ScrollBar */
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #262c38;
    min-height: 20px;
    border-radius: 1px;
    margin: 1px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3b4455;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #262c38;
    min-width: 20px;
    border-radius: 1px;
    margin: 1px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #3b4455;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ToolTip */
QToolTip {
    background-color: #161b22;
    color: #f0f6fc;
    border: 1px solid #30363d;
    border-radius: 2px;
    padding: 5px 8px;
}
"""

LIGHT_THEME_QSS = """
QMainWindow {
    background-color: #f6f8fa;
    color: #1f2328;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", "Roboto", "Helvetica Neue", sans-serif;
    font-size: 13px;
    color: #24292f;
}

/* Bento Cards / Containers */
QFrame#bentoCard {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 3px;
}

QFrame#bentoCard:hover {
    border: 1px solid #afb8c1;
}

QFrame#statusCard {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 3px;
}

/* Headers & Labels */
QLabel#sectionTitle {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #656d76;
}

QLabel#statValue {
    font-size: 18px;
    font-weight: 700;
    color: #0969da;
}

QLabel#statLabel {
    font-size: 11px;
    font-weight: 600;
    color: #57606a;
}

QLabel#speedDisplay {
    font-size: 20px;
    font-weight: 800;
    color: #1a7f37;
    letter-spacing: -0.5px;
}

/* Input Fields */
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 2px;
    padding: 6px 8px;
    color: #1f2328;
    selection-background-color: #0969da;
    selection-color: #ffffff;
}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #0969da;
    background-color: #ffffff;
}

QLineEdit:hover, QTextEdit:hover, QSpinBox:hover, QComboBox:hover {
    border: 1px solid #8c959f;
}

/* ComboBox Dropdown */
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left-width: 0px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    selection-background-color: #0969da;
    selection-color: #ffffff;
    padding: 2px;
    outline: none;
    border-radius: 2px;
}

/* Push Buttons */
QPushButton {
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 2px;
    color: #24292f;
    font-weight: 600;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #eaeef2;
    border-color: #8c959f;
    color: #1f2328;
}

QPushButton:pressed {
    background-color: #e1e4e8;
}

QPushButton:disabled {
    background-color: #f6f8fa;
    border-color: #e1e4e8;
    color: #8c959f;
}

/* Semantic Button Styles */
QPushButton#primaryBtn {
    background-color: #0969da;
    border: 1px solid #085fc5;
    color: #ffffff;
}

QPushButton#primaryBtn:hover {
    background-color: #085fc5;
}

QPushButton#primaryBtn:pressed {
    background-color: #074794;
}

QPushButton#successBtn {
    background-color: #1f883d;
    border: 1px solid #1a7f37;
    color: #ffffff;
}

QPushButton#successBtn:hover {
    background-color: #1a7f37;
}

QPushButton#warningBtn {
    background-color: #9a6700;
    border: 1px solid #825600;
    color: #ffffff;
}

QPushButton#warningBtn:hover {
    background-color: #825600;
}

QPushButton#dangerBtn {
    background-color: #d1242f;
    border: 1px solid #b62324;
    color: #ffffff;
}

QPushButton#dangerBtn:hover {
    background-color: #b62324;
}

QPushButton#purpleBtn {
    background-color: #8250df;
    border: 1px solid #6e40c9;
    color: #ffffff;
}

QPushButton#purpleBtn:hover {
    background-color: #6e40c9;
}

QPushButton#darkRedBtn {
    background-color: #6e0c1f;
    border: 1px solid #570918;
    color: #ffffff;
}

QPushButton#darkRedBtn:hover {
    background-color: #570918;
}

/* Tree Widget */
QTreeWidget {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 2px;
    padding: 2px;
    color: #1f2328;
    outline: none;
}

QTreeWidget::item {
    height: 28px;
    border-radius: 1px;
    padding: 1px 3px;
    margin: 1px 0px;
}

QTreeWidget::item:hover {
    background-color: #f3f4f6;
}

QTreeWidget::item:selected {
    background-color: #e8f0fe;
    color: #0969da;
}

QHeaderView::section {
    background-color: #f6f8fa;
    color: #57606a;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 5px 8px;
    border: none;
    border-bottom: 1px solid #d0d7de;
}

/* CheckBox */
QCheckBox {
    color: #24292f;
    font-weight: 500;
    spacing: 6px;
}

QCheckBox:disabled {
    color: #8c959f;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 2px;
    border: 1px solid #d0d7de;
    background-color: #ffffff;
}

QCheckBox::indicator:hover {
    border: 1px solid #0969da;
}

QCheckBox::indicator:checked {
    background-color: #0969da;
    border: 1px solid #0969da;
    image: url("__CHECK_WHITE__");
}

QCheckBox::indicator:disabled {
    border: 1px solid #e1e4e8;
    background-color: #f6f8fa;
}

QCheckBox::indicator:checked:disabled {
    background-color: #d0d7de;
    border: 1px solid #d0d7de;
    image: url("__CHECK_GREY__");
}

/* RadioButton */
QRadioButton {
    color: #24292f;
    font-weight: 500;
    spacing: 6px;
}

QRadioButton:disabled {
    color: #8c959f;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1px solid #d0d7de;
    background-color: #ffffff;
}

QRadioButton::indicator:hover {
    border: 1px solid #0969da;
}

QRadioButton::indicator:checked {
    background-color: #0969da;
    border: 1px solid #0969da;
    image: url("__DOT_WHITE__");
}

QRadioButton::indicator:disabled {
    border: 1px solid #e1e4e8;
    background-color: #f6f8fa;
}

QRadioButton::indicator:checked:disabled {
    background-color: #d0d7de;
    border: 1px solid #d0d7de;
    image: url("__DOT_GREY__");
}

/* GroupBox & DateEdit */
QGroupBox {
    font-weight: 700;
    font-size: 11px;
    color: #57606a;
    border: 1px solid #d0d7de;
    border-radius: 3px;
    margin-top: 14px;
    padding-top: 14px;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    background-color: #f6f8fa;
}

QDateEdit {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 2px;
    padding: 4px 6px;
    color: #1f2328;
}

QDateEdit:focus {
    border: 1px solid #0969da;
}

QDateEdit:disabled {
    background-color: #f6f8fa;
    border-color: #e1e4e8;
    color: #8c959f;
}

/* Menu & MenuBar */
QMenuBar {
    background-color: #f6f8fa;
    color: #24292f;
    border-bottom: 1px solid #d0d7de;
    padding: 0px 4px;
}

QMenuBar::item {
    padding: 2px 6px;
    border-radius: 2px;
}

QMenuBar::item:selected {
    background-color: #eaeef2;
    color: #1f2328;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 3px;
    padding: 4px;
    color: #24292f;
}

QMenu::item {
    padding: 5px 20px 5px 10px;
    border-radius: 2px;
}

QMenu::item:selected {
    background-color: #0969da;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #d0d7de;
    margin: 3px 4px;
}

/* ScrollBar */
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #d0d7de;
    min-height: 20px;
    border-radius: 1px;
    margin: 1px;
}

QScrollBar::handle:vertical:hover {
    background-color: #afb8c1;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #d0d7de;
    min-width: 20px;
    border-radius: 1px;
    margin: 1px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #afb8c1;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ToolTip */
QToolTip {
    background-color: #24292f;
    color: #ffffff;
    border: 1px solid #1f2328;
    border-radius: 2px;
    padding: 5px 8px;
}
"""

# Resolve placeholder image urls to real file paths (must happen after both QSS blocks are defined)
DARK_THEME_QSS = (
    DARK_THEME_QSS.replace("__CHECK_WHITE__", _CHECK_WHITE)
    .replace("__CHECK_GREY_DARK__", _CHECK_GREY_DARK)
    .replace("__DOT_WHITE__", _DOT_WHITE)
    .replace("__DOT_GREY_DARK__", _DOT_GREY_DARK)
)
LIGHT_THEME_QSS = (
    LIGHT_THEME_QSS.replace("__CHECK_WHITE__", _CHECK_WHITE)
    .replace("__CHECK_GREY__", _CHECK_GREY)
    .replace("__DOT_WHITE__", _DOT_WHITE)
    .replace("__DOT_GREY__", _DOT_GREY)
)

