import sys
import os
import time
import threading
import re
import subprocess
import json
import logging
import tempfile
import contextlib
import zipfile
import shutil
from collections import deque

logging.basicConfig(
    filename=os.path.expanduser("~/.silverspoon.log"),
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QFileDialog, QAbstractItemView,
    QCheckBox, QDialog, QFormLayout, QSpinBox, QDialogButtonBox,
    QMessageBox, QInputDialog, QSplashScreen, QMenu, QStyledItemDelegate
)
from PyQt6.QtGui import QAction, QDesktopServices, QIcon, QPixmap, QColor, QBrush, QKeySequence
from PyQt6.QtCore import Qt, QTimer, QUrl, QEvent

class ProgressBarDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if index.column() == 0:
            item = self.parent().itemFromIndex(index)
            if item:
                progress = item.data(0, Qt.ItemDataRole.UserRole)
                status = item.data(1, Qt.ItemDataRole.UserRole)
                
                if progress is not None and isinstance(progress, (int, float)):
                    if status == "Error" or status == "Contains Errors":
                        bg_color = QColor(231, 76, 60, 50)
                    elif status in ("Completed", "Extracted"):
                        bg_color = QColor(46, 204, 113, 50)
                    else:
                        bg_color = QColor(52, 152, 219, 50)

                    rect = option.rect
                    progress_width = int(rect.width() * (progress / 100.0))
                    progress_rect = rect.adjusted(0, 0, progress_width - rect.width(), 0)
                    
                    painter.save()
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(bg_color))
                    painter.drawRect(progress_rect)
                    painter.restore()
        
        super().paint(painter, option, index)

from curl_cffi import requests as curl_requests
from cf_turnstile import TurnstileSolver
from PyQt6.QtCore import QMetaObject, Q_ARG
from update_logic import UpdateCheckerThread, UpdateDownloaderDialog

CURRENT_VERSION = "v1.4.0"
GITHUB_REPO = "billysams21/SilverSpoon"

def get_settings_path():
    return os.path.expanduser("~/.silverspoon_settings.json")

def load_settings():
    if sys.platform == "win32":
        default_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(default_downloads):
            try:
                os.makedirs(default_downloads, exist_ok=True)
            except Exception:
                default_downloads = os.path.abspath(".")
    else:
        default_downloads = os.path.abspath(".")
        
    default_settings = {
        "default_save_dir": default_downloads,
        "max_workers": 3,
        "extract_after_download": False,
        "auto_retry_errors": False,
        "captcha_timeout": 10,
        "column_widths": {},
        "skip_delete_confirmation": False,
        "show_warning_dialog": True,
        "last_update_check": 0.0
    }
    settings_path = get_settings_path()
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                default_settings.update(loaded)
        except Exception:
            pass

    save_settings(default_settings)
    
    return default_settings

def save_settings(settings):
    settings_path = get_settings_path()
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Failed to save settings: {e}")

def format_error_message(error, max_length=160):
    text = str(error).strip()
    lower_text = text.lower()
    error_type = type(error).__name__

    if "connectionabortederror" in lower_text or "10053" in text:
        return "Connection was aborted by your computer or network security software. Try again, or check firewall/antivirus settings."
    if "connection reset" in lower_text or "connectionreseterror" in lower_text:
        return "Connection was reset by the server or your network. Try again later."
    if "timed out" in lower_text or "timeout" in lower_text:
        return "The connection timed out. Check your network and try again."

    if not text:
        return error_type

    text = re.sub(r"\s+", " ", text)
    if len(text) > max_length:
        text = text[:max_length].rstrip() + "..."
    return f"{error_type}: {text}"

class WarningDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to SilverSpoon!")
        self.setMinimumWidth(500)
        self.settings = settings
        
        layout = QVBoxLayout(self)
        
        # Shortcuts Section
        shortcuts_label = QLabel("<b>Keyboard Shortcuts:</b>")
        layout.addWidget(shortcuts_label)
        
        shortcuts_text = (
            "<ul>"
            "<li><b>[S] or [Space]</b>: Start / Resume selected downloads</li>"
            "<li><b>[P] or [Space]</b>: Pause selected downloads</li>"
            "<li><b>[C]</b>: Cancel selected downloads</li>"
            "<li><b>[R]</b>: Retry failed downloads</li>"
            "<li><b>[F]</b>: Force Redownload selected tasks</li>"
            "<li><b>[Delete] or [Backspace]</b>: Delete selected tasks</li>"
            "</ul>"
        )
        shortcuts_display = QLabel(shortcuts_text)
        shortcuts_display.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(shortcuts_display)
        
        # Warning Section
        warning_label = QLabel("<b>⚠️ VPN USERS WARNING ⚠️</b>")
        warning_label.setStyleSheet("color: red; font-size: 14px;")
        warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning_label)
        
        warning_text = QLabel(
            "Cloudflare will aggressively block known VPN IPs. If your downloads are "
            "failing or getting stuck, and you have tried to <i>Force Redownload</i> but "
            "it keeps failing, <b>TURN OFF YOUR VPN</b>."
        )
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("color: black; font-weight: bold; padding: 10px; background-color: #ffffff; border-radius: 5px;")
        layout.addWidget(warning_text)
        
        # Don't show again checkbox
        self.dont_show_checkbox = QCheckBox("Don't show this again")
        layout.addWidget(self.dont_show_checkbox)
        
        # OK Button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)

    def accept(self):
        if self.dont_show_checkbox.isChecked():
            self.settings["show_warning_dialog"] = False
        super().accept()

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        
        self.current_settings = current_settings
        
        layout = QFormLayout(self)
        
        # Save Directory
        dir_layout = QHBoxLayout()
        default_dir = self.current_settings.get("default_save_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
        self.dir_input = QLineEdit(default_dir)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(browse_btn)
        layout.addRow("Default Save Directory:", dir_layout)
        
        # Max Workers
        self.workers_spinbox = QSpinBox()
        self.workers_spinbox.setRange(1, 10)
        self.workers_spinbox.setValue(self.current_settings.get("max_workers", 3))
        layout.addRow("Max Concurrent Downloads:", self.workers_spinbox)
        
        # Bandwidth Limit
        self.bandwidth_spinbox = QSpinBox()
        self.bandwidth_spinbox.setRange(0, 1000) # 0 means unlimited
        self.bandwidth_spinbox.setSuffix(" MB/s")
        self.bandwidth_spinbox.setSpecialValueText("Unlimited")
        self.bandwidth_spinbox.setValue(self.current_settings.get("bandwidth_limit", 0))
        layout.addRow("Global Bandwidth Limit:", self.bandwidth_spinbox)
        
        # CAPTCHA Timeout
        self.captcha_spinbox = QSpinBox()
        self.captcha_spinbox.setRange(5, 120)
        self.captcha_spinbox.setSuffix(" seconds")
        self.captcha_spinbox.setValue(self.current_settings.get("captcha_timeout", 10))
        layout.addRow("CAPTCHA Solve Timeout:", self.captcha_spinbox)
        
        # Extract Option
        self.extract_checkbox = QCheckBox()
        self.extract_checkbox.setChecked(self.current_settings.get("extract_after_download", False))
        layout.addRow("Extract after download by default:", self.extract_checkbox)
        
        # Auto-retry Errors Option
        self.auto_retry_checkbox = QCheckBox()
        self.auto_retry_checkbox.setChecked(self.current_settings.get("auto_retry_errors", False))
        layout.addRow("Automatically retry failed downloads (up to 3 times):", self.auto_retry_checkbox)
        
        # Skip Delete Confirmation Option
        self.skip_delete_checkbox = QCheckBox()
        self.skip_delete_checkbox.setChecked(self.current_settings.get("skip_delete_confirmation", False))
        layout.addRow("Skip delete confirmation:", self.skip_delete_checkbox)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.reset_btn = button_box.addButton("Reset Defaults", QDialogButtonBox.ButtonRole.ResetRole)
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.dir_input.text())
        if folder:
            self.dir_input.setText(os.path.abspath(folder))

    def reset_to_defaults(self):
        reply = QMessageBox.question(
            self, 'Confirm Reset', 
            "Are you sure you want to reset all settings to their default values? (Includes showing warnings and UI sizes)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if sys.platform == "win32":
                default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            else:
                default_dir = os.path.abspath(".")
            
            self.dir_input.setText(default_dir)
            self.workers_spinbox.setValue(3)
            self.bandwidth_spinbox.setValue(0)
            self.captcha_spinbox.setValue(10)
            self.extract_checkbox.setChecked(False)
            self.auto_retry_checkbox.setChecked(False)
            self.skip_delete_checkbox.setChecked(False)
            
            # Reset background invisible settings as well
            self.current_settings["column_widths"] = {}
            self.current_settings["show_warning_dialog"] = True

    def get_updated_settings(self):
        return {
            "default_save_dir": self.dir_input.text(),
            "max_workers": self.workers_spinbox.value(),
            "bandwidth_limit": self.bandwidth_spinbox.value(),
            "captcha_timeout": self.captcha_spinbox.value(),
            "extract_after_download": self.extract_checkbox.isChecked(),
            "auto_retry_errors": self.auto_retry_checkbox.isChecked(),
            "skip_delete_confirmation": self.skip_delete_checkbox.isChecked(),
            "column_widths": self.current_settings.get("column_widths", {}),
            "show_warning_dialog": self.current_settings.get("show_warning_dialog", True),
            "last_update_check": self.current_settings.get("last_update_check", 0.0)
        }

class DownloadTask:
    def __init__(self, link, base_save_dir, folder_name=None):
        self.link = link.strip()
        self.base_save_dir = base_save_dir
        
        self.file_id = self.link.split('/')[-1].split('#')[0]
        self.filename = self.link.split('#')[-1] if '#' in self.link else self.file_id
        
        if folder_name:
            self.folder_name = folder_name
        else:
            # Fallback calculate smart directory grouping based on prefix
            match = re.search(r'(.*?)(\.part\d+\.rar|\.rar)$', self.filename, re.IGNORECASE)
            if match:
                self.folder_name = match.group(1).strip('._-')
            else:
                self.folder_name = self.filename.rsplit('.', 1)[0]
            
        self.save_dir = os.path.normpath(os.path.join(self.base_save_dir, self.folder_name))
        self.filepath = os.path.normpath(os.path.join(self.save_dir, self.filename))
        
        self.status = "Queued"
        self.progress = 0.0
        self.speed = 0.0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.error_message = ""
        self.retry_count = 0
        
        self.pause_flag = False
        self.cancel_flag = False
        self.tree_item = None
        self.is_selected = False

    def to_dict(self):
        return {
            "link": self.link,
            "base_save_dir": self.base_save_dir,
            "folder_name": self.folder_name,
            "status": self.status,
            "error_message": self.error_message,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "progress": self.progress
        }
        
    @classmethod
    def from_dict(cls, data):
        task = cls(data["link"], data["base_save_dir"], data["folder_name"])
        # Ensure it doesn't auto-start if it was active when closed
        if data["status"] in ("Downloading", "Pending", "Starting...", "Resolving Container...", "Pausing...", "Solving CAPTCHA..."):
            task.status = "Paused"
            task.pause_flag = True
        else:
            task.status = data["status"]
            
        task.downloaded_bytes = data.get("downloaded_bytes", 0)
        task.total_bytes = data.get("total_bytes", 0)
        task.progress = data.get("progress", 0.0)
        task.error_message = data.get("error_message", "")
        return task

def get_history_path():
    return os.path.expanduser("~/.silverspoon_history.json")

def load_history():
    history_path = get_history_path()
    tasks = []
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item_data in data:
                    tasks.append(DownloadTask.from_dict(item_data))
        except Exception:
            pass
    return tasks

def save_history(tasks):
    history_path = get_history_path()
    try:
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump([t.to_dict() for t in tasks], f, indent=4)
    except Exception as e:
        print(f"Failed to save history: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SilverSpoon - UI (PyQt6)")
        self.resize(1000, 650)
        
        if hasattr(sys, '_MEIPASS'):
            self.base_dir = sys._MEIPASS
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            
        icon_path = os.path.join(self.base_dir, 'SilverSpoon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.settings = load_settings()
        
        self.tasks = []
        self.max_workers = self.settings.get("max_workers", 3)
        captcha_timeout = self.settings.get("captcha_timeout", 10)
        self.turnstile_solver = TurnstileSolver(timeout=captcha_timeout)
        self.dl_session = curl_requests.Session(impersonate="chrome")
        self.is_all_selected = False
        self.extracted_folders = set()
        
        self.setup_ui()
        self.load_tasks_from_history()
        
        if self.settings.get("show_warning_dialog", True):
            QTimer.singleShot(100, self.show_warning_dialog)

        if sys.platform == "win32" and hasattr(sys, 'frozen'):
            self.update_checker = UpdateCheckerThread(CURRENT_VERSION, GITHUB_REPO, get_settings_path())
            self.update_checker.update_available.connect(self.prompt_update)
            self.update_checker.check_finished.connect(self.update_last_check_time)
            self.update_checker.start()

        self.manager_thread = threading.Thread(target=self.download_manager, daemon=True)
        self.manager_thread.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(500)

    def closeEvent(self, event):
        save_history(self.tasks)
        col_widths = {}
        for i in range(self.tree.columnCount()):
            col_widths[str(i)] = self.tree.columnWidth(i)
        self.settings["column_widths"] = col_widths
        save_settings(self.settings)
        self.turnstile_solver.stop()
        event.accept()

    def setup_ui(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        
        import_action = QAction("&Import Links from File...", self)
        import_action.triggered.connect(self.import_links_from_file)
        file_menu.addAction(import_action)
        
        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()

        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu_bar.addMenu("&Help")
        
        github_action = QAction("&GitHub Repository", self)
        github_action.triggered.connect(self.open_github_link)
        help_menu.addAction(github_action)
        
        contact_action = QAction("&Contact Us", self)
        contact_action.triggered.connect(self.open_contact_link)
        help_menu.addAction(contact_action)
        
        contributing_action = QAction("C&ontributing Guide", self)
        contributing_action.triggered.connect(self.show_contributing_dialog)
        help_menu.addAction(contributing_action)
        
        help_menu.addSeparator()
        
        welcome_action = QAction("&Welcome", self)
        welcome_action.triggered.connect(self.show_warning_dialog_manual)
        help_menu.addAction(welcome_action)
        
        check_update_action = QAction("Check for &Updates...", self)
        check_update_action.triggered.connect(self.manual_update_check)
        help_menu.addAction(check_update_action)

        about_menu = menu_bar.addMenu("&About")
        
        about_action = QAction("&About SilverSpoon", self)
        about_action.triggered.connect(self.show_about_dialog)
        about_menu.addAction(about_action)
        
        donate_action = QAction("&Donate", self)
        donate_action.triggered.connect(self.open_donate_link)
        about_menu.addAction(donate_action)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Base Save Directory:"))
        default_dir = self.settings.get("default_save_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
        self.dir_input = QLineEdit(default_dir)
        dir_layout.addWidget(self.dir_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(browse_btn)
        main_layout.addLayout(dir_layout)

        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("Paste Links Here (one per line):"))
        
        paste_btn = QPushButton("Paste from Clipboard")
        paste_btn.clicked.connect(self.paste_from_clipboard)
        stats_layout.addWidget(paste_btn)
        
        stats_layout.addStretch()
        self.global_speed_label = QLabel("Global Speed: 0.00 MB/s")
        self.global_speed_label.setStyleSheet("font-weight: bold; color: #2ecc71;")
        stats_layout.addWidget(self.global_speed_label)
        main_layout.addLayout(stats_layout)
        
        self.text_links = QTextEdit()
        self.text_links.setAcceptRichText(False)
        self.text_links.setMaximumHeight(80)
        # Override the paste event of QTextEdit or handle it through shortcuts if needed.
        # However, QTextEdit natively handles pastes. To intercept rich text paste, 
        # we can either subclass QTextEdit or just install an event filter.
        # Let's install an event filter on text_links to intercept pastes.
        self.text_links.installEventFilter(self)
        main_layout.addWidget(self.text_links)
        
        add_btn = QPushButton("Add Links to Queue")
        add_btn.setStyleSheet("background-color: #2e55cc; color: white; font-weight: bold; padding: 6px;")
        add_btn.clicked.connect(self.add_links)
        main_layout.addWidget(add_btn)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(7)
        self.tree.setHeaderLabels(["Filename / Folder", "Sel", "Status", "Progress", "Speed", "ETA", "Size"])

        self.tree.setItemDelegate(ProgressBarDelegate(self.tree))
        
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tree.setColumnWidth(1, 40)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        
        saved_widths = self.settings.get("column_widths", {})
        if saved_widths:
            for i in range(self.tree.columnCount()):
                width = saved_widths.get(str(i))
                if width:
                    self.tree.setColumnWidth(i, width)
        else:
            self.tree.setColumnWidth(0, 300)
            self.tree.setColumnWidth(2, 100)
            self.tree.setColumnWidth(3, 80)
            self.tree.setColumnWidth(4, 80)
            self.tree.setColumnWidth(5, 80)
            self.tree.setColumnWidth(6, 120)

        self.tree.header().moveSection(1, 0)
        
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        
        self.tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.tree.installEventFilter(self)
        
        self.tree.itemClicked.connect(self.handle_item_clicked)
        self.tree.itemSelectionChanged.connect(self.handle_item_selection_changed)
        self.tree.setStyleSheet("""
            QTreeView::indicator { width: 16px; height: 16px; }
            QTreeView::item:selected { outline: none; }
        """)
        main_layout.addWidget(self.tree)

        action_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        action_layout.addWidget(self.select_all_btn)
        
        self.start_btn = QPushButton("Start / Resume")
        self.start_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 6px;")
        self.start_btn.clicked.connect(self.start_downloads)
        action_layout.addWidget(self.start_btn)
        
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 6px;")
        self.pause_btn.clicked.connect(self.pause_selected)
        action_layout.addWidget(self.pause_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 6px;")
        self.cancel_btn.clicked.connect(self.cancel_selected)
        action_layout.addWidget(self.cancel_btn)
        
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setStyleSheet("background-color: #9b59b6; color: white; font-weight: bold; padding: 6px;")
        self.retry_btn.clicked.connect(self.retry_selected)
        action_layout.addWidget(self.retry_btn)

        self.force_redownload_btn = QPushButton("Force Redownload")
        self.force_redownload_btn.setStyleSheet("background-color: #300101; color: white; font-weight: bold; padding: 6px;")
        self.force_redownload_btn.clicked.connect(self.force_redownload_selected)
        action_layout.addWidget(self.force_redownload_btn)

        self.copy_log_btn = QPushButton("Copy Error Details")
        self.copy_log_btn.setStyleSheet("background-color: #555; color: white; font-weight: bold; padding: 6px;")
        self.copy_log_btn.clicked.connect(self.copy_selected_error_log)
        action_layout.addWidget(self.copy_log_btn)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; padding: 6px;")
        self.delete_btn.clicked.connect(self.delete_selected)
        action_layout.addWidget(self.delete_btn)
        
        action_layout.addStretch()
        
        self.extract_checkbox = QCheckBox("Extract after download")
        self.extract_checkbox.setChecked(self.settings.get("extract_after_download", False))
        action_layout.addWidget(self.extract_checkbox)
        
        clear_btn = QPushButton("Clear Completed")
        clear_btn.clicked.connect(self.clear_finished)
        action_layout.addWidget(clear_btn)
        
        main_layout.addLayout(action_layout)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        elif event.key() == Qt.Key.Key_F:
            self.force_redownload_selected()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, source, event):
        if source == self.text_links and event.type() == QEvent.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Paste):
                self.paste_from_clipboard()
                return True
        if hasattr(self, 'tree') and source == self.tree and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self.delete_selected()
                return True
            if event.key() == Qt.Key.Key_F:
                self.force_redownload_selected()
                return True
            if event.key() == Qt.Key.Key_S:
                self.start_downloads()
                return True
            if event.key() == Qt.Key.Key_P:
                self.pause_selected()
                return True
            if event.key() == Qt.Key.Key_Space:
                selected = self.get_selected_tasks()
                if selected:
                    if selected[0].status in ("Downloading", "Starting..."):
                        self.pause_selected()
                    else:
                        self.start_downloads()
                return True
            if event.key() == Qt.Key.Key_C:
                self.cancel_selected()
                return True
            if event.key() == Qt.Key.Key_R:
                self.retry_selected()
                return True
        return super().eventFilter(source, event)

    def show_tree_context_menu(self, position):
        item = self.tree.itemAt(position)
        if item and not any(t.tree_item and t.tree_item.checkState(1) == Qt.CheckState.Checked for t in self.tasks):
            if not item.isSelected():
                self.tree.clearSelection()
            self.tree.setCurrentItem(item)
            item.setSelected(True)

        menu = QMenu(self)
        menu.addAction("[S] Start / Resume", self.start_downloads)
        menu.addAction("[P] Pause", self.pause_selected)
        menu.addAction("[C] Cancel", self.cancel_selected)
        menu.addSeparator()
        menu.addAction("Extract Now", self.manual_extract_selected)
        menu.addAction("Open Folder", self.open_selected_folder)
        menu.addSeparator()
        menu.addAction("[R] Retry", self.retry_selected)
        menu.addAction("[F] Force Redownload", self.force_redownload_selected)
        menu.addAction("Copy Error Details", self.copy_selected_error_log)
        menu.addSeparator()
        menu.addAction("Delete", self.delete_selected)
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def get_or_create_batch_item(self, folder_name):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.text(0) == folder_name:
                return item

        batch_item = QTreeWidgetItem(self.tree)
        batch_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        batch_item.setText(0, folder_name)
        batch_item.setCheckState(1, Qt.CheckState.Unchecked)
        batch_item.setExpanded(True)
        return batch_item

    def open_selected_folder(self):
        tasks = self.get_selected_tasks()
        if not tasks:
            return
            
        # Open the folder of the first selected task
        folder_path = tasks[0].save_dir
        if not os.path.exists(folder_path):
            QMessageBox.information(self, "Folder Not Found", f"The folder does not exist yet:\n{folder_path}")
            return
            
        try:
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder_path])
            else:
                subprocess.Popen(['xdg-open', folder_path])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open folder:\n{e}")

    def trigger_history_save(self):
        if not hasattr(self, '_history_save_timer'):
            self._history_save_timer = QTimer()
            self._history_save_timer.setSingleShot(True)
            self._history_save_timer.timeout.connect(lambda: save_history(self.tasks))
        QMetaObject.invokeMethod(self._history_save_timer, "start", Qt.ConnectionType.QueuedConnection, Q_ARG(int, 500))

    def add_task_to_ui(self, task):
        batch_item = self.get_or_create_batch_item(task.folder_name)
        
        child_item = QTreeWidgetItem(batch_item)
        child_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        
        child_item.setText(0, task.filename)

        check_state = Qt.CheckState.Checked if task.is_selected else Qt.CheckState.Unchecked
        child_item.setCheckState(1, check_state)
        
        child_item.setText(2, task.status)
        child_item.setText(3, "0%")
        child_item.setText(4, "-")
        child_item.setText(5, "-")
        child_item.setText(6, "-")
        
        task.tree_item = child_item
        
        if task not in self.tasks:
            self.tasks.append(task)
            self.trigger_history_save()

    def copy_selected_error_log(self):
        for task in self.get_selected_tasks():
            if "Error" in task.status:
                self.copy_error_log(task)
                return
        QMessageBox.information(self, "No Error Selected", "Select a failed task first, then copy its error details.")

    def copy_error_log(self, task):
        log_path = os.path.expanduser("~/.silverspoon.log")
        if not os.path.exists(log_path):
            QMessageBox.information(self, "No Log", "No error log found.")
            return
            
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                logs = f.readlines()
                
            keywords = [task.link, task.file_id, task.filename]
            matching_logs = [line for line in logs if any(keyword and keyword in line for keyword in keywords)]
            relevant_logs = "".join(matching_logs[-20:] if matching_logs else logs[-20:])
            
            if not relevant_logs.strip():
                QMessageBox.information(self, "Log Empty", "The error log is empty.")
                return
                
            clipboard = QApplication.clipboard()
            log_label = "Matching log lines" if matching_logs else "Recent log lines"
            clipboard.setText(f"Task File: {task.filename}\nTask Link: {task.link}\nStatus: {task.status}\n\n{log_label}:\n{relevant_logs}")
            QMessageBox.information(self, "Log Copied", "Relevant error logs have been copied to your clipboard.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read log file: {e}")

    def load_tasks_from_history(self):
        loaded_tasks = load_history()
        for task in loaded_tasks:
            self.add_task_to_ui(task)
            if task.status == "Extracted":
                self.extracted_folders.add(task.folder_name)
            elif task.status == "Extracting...":
                task.status = "Completed"

    def import_links_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Links", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    current_text = self.text_links.toPlainText()
                    if current_text.strip():
                        self.text_links.setText(current_text + "\n" + content)
                    else:
                        self.text_links.setText(content)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to read file:\n{e}")

    def open_github_link(self):
        QDesktopServices.openUrl(QUrl("https://github.com/billysams21/SilverSpoon"))
        
    def open_contact_link(self):
        QDesktopServices.openUrl(QUrl("https://github.com/billysams21/SilverSpoon/issues"))
        
    def open_donate_link(self):
        QDesktopServices.openUrl(QUrl("https://ko-fi.com/billysm23"))

    def show_contributing_dialog(self):
        QMessageBox.information(self, "Contributing Guide",
            "<h3>Contributing to SilverSpoon</h3>"
            "<p>We welcome contributions! Please see the <b>CONTRIBUTING.md</b> file in the repository for full details.</p>"
            "<p><b>Quick Rules:</b></p>"
            "<ul>"
            "<li>Always work on the <code>dev</code> branch.</li>"
            "<li>Carefully test your changes before submitting a PR.</li>"
            "<li>Report bugs via the GitHub Issues tab.</li>"
            "</ul>"
        )

    def show_about_dialog(self):
        QMessageBox.about(self, "About SilverSpoon",
            "<h3>SilverSpoon v1.4.0</h3>"
            "<p>A simple, fast bulk downloader for FuckingFast links developed by billysams21.</p>"
            "<p>Select your links, paste them in, and hit Add!</p>"
            "<p>Licensed under the GNU GPLv3.</p>"
            "<hr>"
            "<h4>Changelog (v1.4.0 - Short):</h4>"
            "<ul>"
            "<li><b>New:</b> Bandwidth limiter in Settings to cap global download speed.</li>"
            "<li><b>New:</b> Built-in Cloudflare Turnstile CAPTCHA solver using a hidden Chromium browser.</li>"
            "<li><b>New:</b> Visual progress bars drawn directly behind file/folder names.</li>"
            "<li><b>New:</b> Manual \"Extract Now\" context menu action for downloaded batches.</li>"
            "<li><b>Fix:</b> Stabilized download speed calculation with a 3-second rolling average.</li>"
            "<li><b>Fix:</b> More accurate ETA calculation and smarter folder name adjustment.</li>"
            "</ul>"
            "<hr>"
            "<h4>Changelog (v1.3.0 - Short):</h4>"
            "<ul>"
            "<li><b>New:</b> Built-in auto-updater for Windows executables.</li>"
            "<li><b>New:</b> VPN warning dialog to help with Cloudflare blocking.</li>"
            "<li><b>New:</b> Default save directory smartly falls back to user Downloads folder.</li>"
            "<li><b>New:</b> Reset Settings to Defaults button.</li>"
            "<li><b>New:</b> Toggle pause/resume with the Spacebar.</li>"
            "<li><b>Fix:</b> Better directory creation error handling during downloads.</li>"
            "</ul>"
            "<hr>"
            "<h4>Changelog (v1.2.1 - Short):</h4>"
            "<ul>"
            "<li><b>New:</b> Right-click context menu and keyboard shortcuts.</li>"
            "<li><b>New:</b> Force Redownload action.</li>"
            "<li><b>New:</b> Hover error tooltips and 'Copy Error Details' log extraction.</li>"
            "<li><b>New:</b> Extraction support for Linux and macOS.</li>"
            "</ul>"
            "<p><i>See CHANGELOG.md for full details.</i></p>"
        )

    def show_warning_dialog(self):
        dialog = WarningDialog(self.settings, self)
        dialog.exec()
        save_settings(self.settings)

    def show_warning_dialog_manual(self):
        dialog = WarningDialog(self.settings, self)
        dialog.dont_show_checkbox.setChecked(not self.settings.get("show_warning_dialog", True))
        dialog.exec()
        save_settings(self.settings)

    def manual_update_check(self):
        self.manual_checker = UpdateCheckerThread(CURRENT_VERSION, GITHUB_REPO, get_settings_path(), force=True)
        self.manual_checker.update_available.connect(self.prompt_update)
        self.manual_checker.check_finished.connect(self.update_last_check_time)
        self.manual_checker.no_update_found.connect(lambda: QMessageBox.information(self, "Up to date", "You are already using the latest version of SilverSpoon!"))
        self.manual_checker.error_checking.connect(lambda err: QMessageBox.warning(self, "Update Check Failed", f"Could not check for updates:\n{err}"))
        self.manual_checker.start()
        
    def update_last_check_time(self, timestamp):
        self.settings["last_update_check"] = timestamp
        save_settings(self.settings)
        self.settings = load_settings()
        
    def prompt_update(self, version, changelog, download_url):
        current_exe_dir = os.path.dirname(sys.executable)
        test_file = os.path.join(current_exe_dir, ".update_test_permission")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except PermissionError:
            QMessageBox.warning(
                self, "Update Available (Admin Required)",
                f"Version {version} is available!\n\n"
                f"However, SilverSpoon is located in a protected folder:\n{current_exe_dir}\n\n"
                "Please run SilverSpoon as Administrator to update automatically, or move it to a normal folder like Downloads or Desktop."
            )
            return
        except Exception:
            pass
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Update Available: {version}")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"<b>A new version ({version}) is available!</b>"))
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown(changelog)
        layout.addWidget(text_edit)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        btn_box.button(QDialogButtonBox.StandardButton.Yes).setText("Download and Restart")
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.execute_update(download_url)
            
    def execute_update(self, download_url):
        dl_dialog = UpdateDownloaderDialog(download_url, self)
        if dl_dialog.exec() == QDialog.DialogCode.Accepted:
            zip_path = dl_dialog.temp_zip
            extract_dir = os.path.join(tempfile.gettempdir(), f"silverspoon_extract_{int(time.time())}")
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                    
                new_app_dir = None
                for root, _, files in os.walk(extract_dir):
                    if any(file.lower() == "silverspoon.exe" for file in files):
                        new_app_dir = root
                        break

                if not new_app_dir:
                    raise Exception("Could not find SilverSpoon.exe inside the downloaded zip.")

                internal_dir = os.path.join(new_app_dir, "_internal")
                has_curl_metadata = os.path.isdir(internal_dir) and any(
                    entry.startswith("curl_cffi-")
                    and entry.endswith(".dist-info")
                    and os.path.isfile(os.path.join(internal_dir, entry, "METADATA"))
                    for entry in os.listdir(internal_dir)
                )
                if not has_curl_metadata:
                    raise Exception(
                        "The downloaded release is incomplete: curl_cffi metadata is missing. "
                        "Please download the complete SilverSpoon folder ZIP."
                    )
                    
                current_exe = sys.executable
                current_exe_name = os.path.basename(current_exe)
                current_app_dir = os.path.dirname(current_exe)
                
                if not current_exe_name.lower().startswith("silverspoon"):
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("Update Downloaded (Manual Action Required)")
                    msg_box.setText(
                        f"The update has been downloaded and extracted to:\n{extract_dir}\n\n"
                        "Because you are running SilverSpoon from a differently named executable or script, "
                        "the automatic replacement was aborted to keep you safe."
                    )
                    
                    copy_btn = msg_box.addButton("Copy Directory Path", QMessageBox.ButtonRole.ActionRole)
                    ok_btn = msg_box.addButton(QMessageBox.StandardButton.Ok)
                    msg_box.setDefaultButton(ok_btn)
                    
                    msg_box.exec()
                    
                    if msg_box.clickedButton() == copy_btn:
                        QApplication.clipboard().setText(extract_dir)
                        QMessageBox.information(self, "Copied", "Directory path copied to clipboard.")
                        
                    return
                
                save_history(self.tasks)
                save_settings(self.settings)

                bat_path = os.path.join(tempfile.gettempdir(), f"silverspoon_update_{int(time.time())}.bat")
                backup_app_dir = current_app_dir + ".previous"
                success_marker = os.path.join(tempfile.gettempdir(), f"silverspoon_update_success_{int(time.time())}.marker")
                with open(bat_path, 'w') as bat:
                    bat.write('@echo off\n')
                    bat.write('echo Updating SilverSpoon...\n')
                    bat.write('set PYINSTALLER_RESET_ENVIRONMENT=1\n')
                    bat.write('set _MEIPASS=\n')
                    bat.write('set _MEIPASS2=\n')
                    bat.write(f'del /f /q "{success_marker}" > nul 2>&1\n')
                    bat.write(f'if exist "{backup_app_dir}" rmdir /s /q "{backup_app_dir}"\n')
                    bat.write(':wait_for_exit\n')
                    bat.write(f'move "{current_app_dir}" "{backup_app_dir}" > nul 2>&1\n')
                    bat.write('if not errorlevel 1 goto install\n')
                    bat.write('timeout /t 1 /nobreak > nul\n')
                    bat.write('goto wait_for_exit\n')
                    bat.write(':install\n')
                    bat.write(f'robocopy "{new_app_dir}" "{current_app_dir}" /E /COPY:DAT /R:3 /W:1 > nul\n')
                    bat.write('if errorlevel 8 goto rollback\n')
                    bat.write(f'set "SILVERSPOON_UPDATE_SUCCESS_MARKER={success_marker}"\n')
                    bat.write(f'start "" "{current_exe}"\n')
                    bat.write('for /l %%i in (1,1,30) do (\n')
                    bat.write(f'    if exist "{success_marker}" goto success\n')
                    bat.write('    timeout /t 1 /nobreak > nul\n')
                    bat.write(')\n')
                    bat.write(':rollback\n')
                    bat.write(f'if exist "{current_app_dir}" rmdir /s /q "{current_app_dir}"\n')
                    bat.write(f'move "{backup_app_dir}" "{current_app_dir}" > nul 2>&1\n')
                    bat.write(f'if exist "{current_exe}" start "" "{current_exe}"\n')
                    bat.write('goto cleanup\n')
                    bat.write(':success\n')
                    bat.write(f'rmdir /s /q "{backup_app_dir}" > nul 2>&1\n')
                    bat.write(':cleanup\n')
                    bat.write(f'del /f /q "{success_marker}" > nul 2>&1\n')
                    bat.write(f'rmdir /s /q "{extract_dir}" > nul 2>&1\n')
                    bat.write(f'del /q "{zip_path}" > nul 2>&1\n')
                    bat.write('del "%~f0"\n')
                
                CREATE_NO_WINDOW = 0x08000000
                subprocess.Popen(
                    ["cmd.exe", "/c", bat_path],
                    creationflags=CREATE_NO_WINDOW,
                    close_fds=True,
                    # The updater must not retain the app directory as its working directory,
                    # or Windows will prevent the batch file from renaming that directory.
                    cwd=tempfile.gettempdir(),
                )
                
                QApplication.quit()
                sys.exit(0)
                
            except Exception as e:
                QMessageBox.critical(self, "Update Failed", f"Failed to apply the update:\n{str(e)}")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.get_updated_settings()
            save_settings(self.settings)
            self.max_workers = self.settings.get("max_workers", 3)
            new_timeout = self.settings.get("captcha_timeout", 10)
            self.turnstile_solver.TOKEN_TIMEOUT = new_timeout
            default_dir = self.settings.get("default_save_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
            self.dir_input.setText(default_dir)
            self.extract_checkbox.setChecked(self.settings.get("extract_after_download", False))

    def browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.dir_input.text())
        if folder:
            self.dir_input.setText(os.path.abspath(folder))

    def paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        text = ""
        if mime_data.hasHtml():
            # If the clipboard contains HTML, extract href links
            html = mime_data.html()
            # Simple regex to find hrefs
            import re
            links = re.findall(r'href=[\'"]?([^\'" >]+)', html)
            if links:
                # Filter out anything that clearly isn't an http link
                text = "\n".join(link for link in links if link.startswith('http'))
        
        # Fallback to plain text if no links were found in HTML or if it's just plain text
        if not text and mime_data.hasText():
            text = mime_data.text()

        if text:
            current_text = self.text_links.toPlainText()
            if current_text.strip():
                self.text_links.setText(current_text + "\n" + text)
            else:
                self.text_links.setText(text)

    def add_links(self):
        text = self.text_links.toPlainText().strip()
        if not text:
            return
            
        links = [line.strip().lstrip("- ") for line in text.split('\n') if line.strip() and line.lstrip("- ").startswith('http')]
        if not links:
            return
            
        save_dir = os.path.abspath(self.dir_input.text())
        
        # Try to guess a folder name from the first link
        suggested_folder = ""
        first_link = links[0]
        first_filename = first_link.split('#')[-1] if '#' in first_link else first_link.split('/')[-1].split('#')[0]
        match = re.search(r'(.*?)(\.part\d+\.rar|\.rar)$', first_filename, re.IGNORECASE)
        if match:
            suggested_folder = match.group(1).strip('._-')
        else:
            suggested_folder = first_filename.rsplit('.', 1)[0]
            
        suggested_folder = suggested_folder.replace('_--_fitgirl-repacks.site', '')

        folder_name, ok = QInputDialog.getText(
            self, 
            "Batch Folder Name", 
            "Enter a folder name for these files:\n(This groups main game and optional files together)",
            QLineEdit.EchoMode.Normal,
            suggested_folder
        )
        
        if not ok or not folder_name.strip():
            return
            
        folder_name = folder_name.strip()
        
        for link in links:
            task = DownloadTask(link, save_dir, folder_name)
            self.add_task_to_ui(task)
            
        self.text_links.clear()

    def toggle_select_all(self):
        all_checked = True
        total_items = 0

        for i in range(self.tree.topLevelItemCount()):
            batch_item = self.tree.topLevelItem(i)
            if batch_item.checkState(1) != Qt.CheckState.Checked:
                all_checked = False
            for j in range(batch_item.childCount()):
                total_items += 1
                if batch_item.child(j).checkState(1) != Qt.CheckState.Checked:
                    all_checked = False
                    
        if total_items == 0:
            return
            
        self.is_all_selected = not all_checked
        state = Qt.CheckState.Checked if self.is_all_selected else Qt.CheckState.Unchecked

        for i in range(self.tree.topLevelItemCount()):
            batch_item = self.tree.topLevelItem(i)
            batch_item.setCheckState(1, state)
            for j in range(batch_item.childCount()):
                child_item = batch_item.child(j)
                child_item.setCheckState(1, state)
                
        for task in self.tasks:
            task.is_selected = self.is_all_selected

    def handle_item_clicked(self, item, col):
        if col == 1:
            state = item.checkState(1)

            if item.parent() is None:
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(1, state)
                    task = next((t for t in self.tasks if t.tree_item == child), None)
                    if task:
                        task.is_selected = (state == Qt.CheckState.Checked)
            else:
                task = next((t for t in self.tasks if t.tree_item == item), None)
                if task:
                    task.is_selected = (state == Qt.CheckState.Checked)
                    
    def handle_item_selection_changed(self):
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            if top_item.isSelected():
                top_item.setCheckState(1, Qt.CheckState.Checked)
            else:
                top_item.setCheckState(1, Qt.CheckState.Unchecked)

            for j in range(top_item.childCount()):
                child = top_item.child(j)
                if top_item.isSelected() or child.isSelected():
                    child.setCheckState(1, Qt.CheckState.Checked)
                    task = next((t for t in self.tasks if t.tree_item == child), None)
                    if task:
                        task.is_selected = True
                else:
                    child.setCheckState(1, Qt.CheckState.Unchecked)
                    task = next((t for t in self.tasks if t.tree_item == child), None)
                    if task:
                        task.is_selected = False

    def get_selected_tasks(self):
        checked = [t for t in self.tasks if t.tree_item and t.tree_item.checkState(1) == Qt.CheckState.Checked]
        if checked:
            return checked

        selected_items = self.tree.selectedItems()
        selected_tasks = []
        for item in selected_items:
            if item.parent() is None:
                for i in range(item.childCount()):
                    child = item.child(i)
                    task = next((t for t in self.tasks if t.tree_item == child), None)
                    if task and task not in selected_tasks:
                        selected_tasks.append(task)
            else:
                task = next((t for t in self.tasks if t.tree_item == item), None)
                if task and task not in selected_tasks:
                    selected_tasks.append(task)
        return selected_tasks

    def start_downloads(self):
        for task in self.get_selected_tasks():
            if task.status in ("Queued", "Cancelled", "Error", "Paused", "Pausing...", "CAPTCHA Timeout", "Solving CAPTCHA..."):
                task.status = "Pending"
                task.error_message = ""
                task.cancel_flag = False
                task.pause_flag = False

    def pause_selected(self):
        for task in self.get_selected_tasks():
            if task.status in ("Downloading", "Pending", "Starting..."):
                task.pause_flag = True
                task.status = "Pausing..." if task.status == "Downloading" else "Paused"

    def cancel_selected(self):
        for task in self.get_selected_tasks():
            if task.status in ("Downloading", "Pending", "Paused", "Starting...", "Queued"):
                task.cancel_flag = True
                task.pause_flag = False
                task.status = "Cancelled"

    def retry_selected(self):
        for task in self.get_selected_tasks():
            if "Error" in task.status or task.status == "CAPTCHA Timeout":
                task.status = "Pending"
                task.error_message = ""
                task.cancel_flag = False
                task.pause_flag = False
                task.retry_count = 0

    def force_redownload_selected(self):
        tasks_to_redownload = self.get_selected_tasks()
        if not tasks_to_redownload:
            QMessageBox.information(self, "No Selection", "Select one or more tasks to force redownload.")
            return

        active_statuses = {"Downloading", "Pending", "Starting...", "Pausing...", "Extracting..."}

        files_with_progress = []
        for task in tasks_to_redownload:
            if task.status not in active_statuses and task.progress > 0 and task.status != "Error":
                files_with_progress.append(task)
                
        if files_with_progress:
            reply = QMessageBox.warning(
                self, 'Confirm Force Redownload',
                f"You have selected {len(files_with_progress)} file(s) that already have download progress.\n\n"
                f"Forcing a redownload will PERMANENTLY DELETE the partially downloaded file(s) and start from 0%.\n\n"
                f"Are you sure you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        redownloaded = 0
        skipped = 0
        failed = 0

        for task in tasks_to_redownload:
            if task.status in active_statuses:
                skipped += 1
                continue

            try:
                if os.path.exists(task.filepath):
                    os.remove(task.filepath)
            except Exception as e:
                failed += 1
                task.status = "Error"
                task.error_message = f"Could not delete existing file before redownload. {format_error_message(e)}"
                continue

            task.cancel_flag = False
            task.pause_flag = False
            task.progress = 0.0
            task.speed = 0.0
            task.downloaded_bytes = 0
            task.total_bytes = 0
            task.error_message = ""
            task.status = "Pending"
            self.extracted_folders.discard(task.folder_name)
            redownloaded += 1

        if skipped or failed or redownloaded == 0:
            QMessageBox.information(
                self,
                "Force Redownload",
                f"Queued: {redownloaded}\nSkipped active tasks: {skipped}\nFailed: {failed}"
            )

    def delete_selected(self):
        tasks_to_delete = self.get_selected_tasks()
        if not tasks_to_delete:
            return
            
        delete_files = False
        
        if not self.settings.get("skip_delete_confirmation", False):
            dialog = QDialog(self)
            dialog.setWindowTitle("Confirm Delete")
            layout = QVBoxLayout(dialog)
            
            label = QLabel(f"Are you sure you want to delete {len(tasks_to_delete)} selected task(s)?")
            layout.addWidget(label)
            
            file_checkbox = QCheckBox("Also delete downloaded files from disk")
            layout.addWidget(file_checkbox)
            
            dont_ask_checkbox = QCheckBox("Don't ask again")
            layout.addWidget(dont_ask_checkbox)
            
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                delete_files = file_checkbox.isChecked()
                if dont_ask_checkbox.isChecked():
                    self.settings["skip_delete_confirmation"] = True
                    self.skip_delete_checkbox.setChecked(True) if hasattr(self, 'skip_delete_checkbox') else None
                    save_settings(self.settings)
            else:
                return # Cancelled
                
        # Proceed with deletion
        for task in tasks_to_delete:
            # 1. Cancel the task if it's active
            task.cancel_flag = True
            task.status = "Cancelled"

            # 2. Delete the physical file if requested
            if delete_files and os.path.exists(task.filepath):
                try:
                    os.remove(task.filepath)
                except Exception as e:
                    print(f"Failed to delete {task.filepath}: {e}")

            # 3. Remove from UI tree
            if task.tree_item:
                parent = task.tree_item.parent()
                if parent:
                    parent.removeChild(task.tree_item)
                    if parent.childCount() == 0:
                        idx = self.tree.indexOfTopLevelItem(parent)
                        if idx >= 0:
                            self.tree.takeTopLevelItem(idx)
                            
            # 4. Remove from tasks list
            if task in self.tasks:
                self.tasks.remove(task)
                
        self.trigger_history_save()
                
    def clear_finished(self):
        to_remove = [t for t in self.tasks if t.status in ("Completed", "Extracted", "Cancelled")]
        
        if not to_remove:
            return
            
        for t in to_remove:
            if t.tree_item:
                parent = t.tree_item.parent()
                if parent:
                    parent.removeChild(t.tree_item)
                    # If parent batch is now empty, remove it too
                    if parent.childCount() == 0:
                        idx = self.tree.indexOfTopLevelItem(parent)
                        if idx >= 0:
                            self.tree.takeTopLevelItem(idx)
            self.tasks.remove(t)
            
        self.trigger_history_save()

    def format_eta(self, seconds):
        if seconds <= 0 or seconds == float('inf'):
            return "-"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m}m"
        elif m > 0:
            return f"{m}m {s}s"
        else:
            return f"{s}s"

    def update_ui(self):
        global_speed = 0.0
        
        # Update individual tasks
        for task in self.tasks:
            if not task.tree_item:
                continue
            prog_str = f"{task.progress:.1f}%" if task.status not in ("Extracted", "Extracting...", "Extract Error") else "-"
            speed_str = f"{task.speed:.2f} MB/s" if task.status == "Downloading" else "-"
            size_mb = task.total_bytes / (1024*1024)
            dl_mb = task.downloaded_bytes / (1024*1024)
            size_str = f"{dl_mb:.1f} / {size_mb:.1f} MB" if task.total_bytes > 0 else "-"
            
            eta_str = "-"
            if task.status == "Downloading" and task.speed > 0 and task.total_bytes > 0:
                remaining_bytes = task.total_bytes - task.downloaded_bytes
                eta_seconds = remaining_bytes / (task.speed * 1024 * 1024)
                eta_str = self.format_eta(eta_seconds)
            elif task.status in ("Completed", "Extracted", "Extracting..."):
                eta_str = "-"
            
            task.tree_item.setText(2, task.status)
            # Apply word wrap to the tooltip text to avoid very long horizontal lines
            if "Error" in task.status and task.error_message:
                import textwrap
                wrapped_text = "\n".join(textwrap.wrap(task.error_message, width=60))
                task.tree_item.setToolTip(2, wrapped_text)
            else:
                task.tree_item.setToolTip(2, "")
            task.tree_item.setText(3, prog_str)
            task.tree_item.setText(4, speed_str)
            task.tree_item.setText(5, eta_str)
            task.tree_item.setText(6, size_str)
            
            if task.status == "Downloading":
                global_speed += task.speed
                
            # Store the progress and status in the item's data for the custom delegate to paint
            task.tree_item.setData(0, Qt.ItemDataRole.UserRole, task.progress)
            task.tree_item.setData(1, Qt.ItemDataRole.UserRole, task.status)
                
        self.global_speed_label.setText(f"Global Speed: {global_speed:.2f} MB/s")
            
        # Update top-level batch folders
        for i in range(self.tree.topLevelItemCount()):
            batch_item = self.tree.topLevelItem(i)
            total_dl = 0
            total_size = 0
            total_speed = 0.0
            
            all_completed = True
            any_error = False
            any_downloading = False
            
            child_count = batch_item.childCount()
            if child_count == 0:
                continue
                
            for j in range(child_count):
                child = batch_item.child(j)
                task = next((t for t in self.tasks if t.tree_item == child), None)
                if task:
                    # Add task.total_bytes if it's available
                    if hasattr(task, 'total_bytes') and task.total_bytes > 0:
                        total_dl += getattr(task, 'downloaded_bytes', 0)
                        total_size += task.total_bytes
                    elif task.status == "Downloading" and hasattr(task, 'total_bytes'):
                        total_dl += getattr(task, 'downloaded_bytes', 0)
                        total_size += getattr(task, 'total_bytes', 0)
                    else:
                        # Estimate total size for UI based on largest known file
                        ext = os.path.splitext(task.filename)[1].lower()
                        if ext in ('.rar', '.zip'):
                            largest_known = max([getattr(x, 'total_bytes', 0) for x in self.tasks if x.folder_name == batch_item.text(0)] + [0])
                            total_size += largest_known
                            
                    total_speed += getattr(task, 'speed', 0.0)
                    
                    if task.status not in ("Completed", "Extracted"):
                        all_completed = False
                    if "Error" in task.status:
                        any_error = True
                    if task.status in ("Downloading", "Starting...", "Pending"):
                        any_downloading = True
                        
            # Determine batch status
            batch_status = "Queued"
            if all_completed:
                if any(t.status == "Extracting..." for t in [next((t for t in self.tasks if t.tree_item == batch_item.child(k)), None) for k in range(batch_item.childCount()) if next((t for t in self.tasks if t.tree_item == batch_item.child(k)), None)]):
                    batch_status = "Extracting..."
                else:
                    batch_status = "Completed"
            elif any_error:
                batch_status = "Contains Errors"
            elif any_downloading:
                batch_status = "Active"
                
            prog = (total_dl / total_size * 100) if total_size > 0 else 0
            prog_str = f"{prog:.1f}%"
            speed_str = f"{total_speed:.2f} MB/s" if total_speed > 0 else "-"
            size_mb = total_size / (1024*1024)
            dl_mb = total_dl / (1024*1024)
            size_str = f"{dl_mb:.1f} / {size_mb:.1f} MB" if total_size > 0 else "-"
            
            eta_str = "-"
            if any_downloading and total_speed > 0 and total_size > 0:
                largest_known_size = 0
                for k in range(batch_item.childCount()):
                    t = next((x for x in self.tasks if x.tree_item == batch_item.child(k)), None)
                    if t and hasattr(t, 'total_bytes') and t.total_bytes > largest_known_size:
                        largest_known_size = t.total_bytes
                
                # Calculate ETA for the entire batch using all tasks
                remaining_bytes_batch = 0
                for k in range(batch_item.childCount()):
                    t = next((x for x in self.tasks if x.tree_item == batch_item.child(k)), None)
                    if t:
                        if hasattr(t, 'total_bytes') and t.total_bytes > 0:
                            remaining_bytes_batch += (t.total_bytes - getattr(t, 'downloaded_bytes', 0))
                        else:
                            ext = os.path.splitext(t.filename)[1].lower()
                            if ext in ('.rar', '.zip'):
                                remaining_bytes_batch += largest_known_size
                        
                if remaining_bytes_batch > 0:
                    eta_seconds = remaining_bytes_batch / (total_speed * 1024 * 1024)
                    eta_str = self.format_eta(eta_seconds)
            
            batch_item.setText(2, batch_status)
            batch_item.setToolTip(2, "")
            batch_item.setText(3, prog_str)
            batch_item.setText(4, speed_str)
            batch_item.setText(5, eta_str)
            batch_item.setText(6, size_str)
            
            # Store the progress and status in the item's data for the custom delegate to paint
            batch_item.setData(0, Qt.ItemDataRole.UserRole, prog)
            batch_item.setData(1, Qt.ItemDataRole.UserRole, batch_status)
            
    def download_manager(self):
        while True:
            # CAPTCHA resolution belongs to the same worker slot as the actual
            # transfer. Otherwise each resolving task stops counting as active
            # and the manager can exceed the configured concurrency limit.
            active = sum(
                1 for t in self.tasks
                if t.status in ("Downloading", "Starting...", "Solving CAPTCHA...")
            )
            if active < self.max_workers:
                for task in self.tasks:
                    if task.status == "Pending":
                        task.status = "Starting..."
                        threading.Thread(target=self.download_worker, args=(task,), daemon=True).start()
                        active += 1
                        if active >= self.max_workers:
                            break
            
            # Check for extraction
            if self.extract_checkbox.isChecked():
                self.check_extraction()
                
            time.sleep(1)
            
    def manual_extract_selected(self):
        selected_tasks = self.get_selected_tasks()
        if not selected_tasks:
            QMessageBox.information(self, "No Selection", "Select one or more tasks to extract.")
            return
            
        # Group tasks by folder name to extract batch-by-batch
        folders = {}
        for task in selected_tasks:
            if task.folder_name not in folders:
                folders[task.folder_name] = []
            folders[task.folder_name].append(task)
            
        for folder_name, tasks_in_folder in folders.items():
            if any(t.status == "Extracting..." for t in tasks_in_folder):
                continue
                
            all_folder_tasks = [t for t in self.tasks if t.folder_name == folder_name]
            
            # Remove from extracted set so it can be extracted again if needed
            self.extracted_folders.discard(folder_name)
            self.extracted_folders.add(folder_name)
            
            threading.Thread(target=self.extract_folder, args=(all_folder_tasks,), daemon=True).start()

    def check_extraction(self):
        # Group tasks by folder
        folders = {}
        for task in self.tasks:
            if task.folder_name not in folders:
                folders[task.folder_name] = []
            folders[task.folder_name].append(task)
            
        for folder_name, tasks_in_folder in folders.items():
            if folder_name in self.extracted_folders:
                continue
                
            valid_extraction_statuses = {"Completed", "Extracted", "Extracting..."}
            if tasks_in_folder and all(t.status in valid_extraction_statuses for t in tasks_in_folder):
                if all(t.status == "Extracted" for t in tasks_in_folder):
                    self.extracted_folders.add(folder_name)
                    continue
                    
                # If ANY task in this folder is currently Extracting..., don't spawn another thread
                if any(t.status == "Extracting..." for t in tasks_in_folder):
                    continue
                    
                self.extracted_folders.add(folder_name)
                threading.Thread(target=self.extract_folder, args=(tasks_in_folder,), daemon=True).start()

    def extract_folder(self, tasks_in_folder):
        save_dir = tasks_in_folder[0].save_dir
        folder_name = tasks_in_folder[0].folder_name
        
        for t in tasks_in_folder:
            t.status = "Extracting..."
            
        try:
            files = os.listdir(save_dir)
            files.sort()
            
            vols_to_extract = []
            for f in files:
                # 1. Main multipart start (.part01.rar, .part1.rar)
                if re.search(r'\.part0*1\.rar$', f, re.IGNORECASE):
                    vols_to_extract.append(os.path.join(save_dir, f))
                # 2. Sequential start (.001)
                elif re.search(r'\.001$', f):
                    vols_to_extract.append(os.path.join(save_dir, f))
                # 3. Standalone .rar or .zip (not part of a sequence)
                elif f.lower().endswith(('.rar', '.zip')) and not re.search(r'\.part\d+\.rar$', f, re.IGNORECASE):
                    vols_to_extract.append(os.path.join(save_dir, f))
                    
            if not vols_to_extract and files:
                # Fallback to just the first file alphabetically
                vols_to_extract.append(os.path.join(save_dir, files[0]))
                
            if not vols_to_extract:
                for t in tasks_in_folder:
                    t.status = "Extract Error (No File)"
                    t.error_message = f"No archive file was found in {save_dir}."
                if folder_name in self.extracted_folders:
                    self.extracted_folders.remove(folder_name)
                return
                
            # Locate an available extractor (platform-aware)
            extractor_type = None
            base_cmd = None
            if sys.platform == 'win32':
                # Windows: prefer installed 7-Zip > WinRAR > bundled 7z.exe
                if hasattr(sys, '_MEIPASS'):
                    bundled_7z = os.path.join(sys._MEIPASS, '7z.exe')
                else:
                    bundled_7z = os.path.join(os.path.dirname(os.path.abspath(__file__)), '7z.exe')
                installed_7z = r"C:\Program Files\7-Zip\7z.exe"
                installed_winrar = r"C:\Program Files\WinRAR\WinRAR.exe"
                if os.path.exists(installed_7z):
                    extractor_type = '7z'
                    base_cmd = installed_7z
                elif os.path.exists(installed_winrar):
                    extractor_type = 'winrar'
                    base_cmd = installed_winrar
                elif os.path.exists(bundled_7z):
                    extractor_type = '7z'
                    base_cmd = bundled_7z
            else:
                if shutil.which('7z'):
                    extractor_type = '7z'
                    base_cmd = '7z'
                elif shutil.which('unrar'):
                    extractor_type = 'unrar'
                    base_cmd = 'unrar'
                
            if not extractor_type:
                for t in tasks_in_folder:
                    t.status = "Extract Error (No extractor found)"
                    t.error_message = "No supported extractor was found. Install 7-Zip or WinRAR, then retry extraction."
                if folder_name in self.extracted_folders:
                    self.extracted_folders.remove(folder_name)
                return
                
            # Extract each base volume found
            creationflags = 0x08000000 if sys.platform == 'win32' else 0
            for vol in vols_to_extract:
                if extractor_type == '7z':
                    cmd = [base_cmd, 'x', vol, f'-o{save_dir}', '-y']
                elif extractor_type == 'winrar':
                    cmd = [base_cmd, 'x', '-y', vol, f'{save_dir}\\']
                elif extractor_type == 'unrar':
                    cmd = [base_cmd, 'x', vol, f'{save_dir}/', '-y']
                    
                subprocess.run(
                    cmd,
                    check=True,
                    creationflags=creationflags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
            
            for t in tasks_in_folder:
                t.status = "Extracted"
                t.error_message = ""
            self.trigger_history_save()
                
        except subprocess.CalledProcessError as e:
            logging.error(f"Extraction error (subprocess): {e}", exc_info=True)
            for t in tasks_in_folder:
                t.status = "Extract Error (Corrupt?)"
                t.error_message = f"Extractor failed with exit code {e.returncode}. The archive may be corrupt, incomplete, or password-protected."
            if folder_name in self.extracted_folders:
                self.extracted_folders.remove(folder_name)
            self.trigger_history_save()
        except Exception as e:
            logging.error(f"Extraction error: {e}", exc_info=True)
            for t in tasks_in_folder:
                t.status = f"Extract Error"
                t.error_message = f"Extraction failed: {format_error_message(e)}"
            if folder_name in self.extracted_folders:
                self.extracted_folders.remove(folder_name)
            self.trigger_history_save()

    def get_direct_link(self, task):
        try:
            task.status = "Solving CAPTCHA..."
            result = self.turnstile_solver.get_direct_link(task.link)
            direct_link = result.get("direct_url")
            if direct_link:
                # Stash cookies/UA on the task for the download transport
                task._dl_cookies = result.get("cookies", {})
                task._dl_user_agent = result.get("user_agent", "")
                return direct_link
            task.status = "CAPTCHA Timeout"
            task.error_message = "The file host did not return a direct download link. The link may be expired or unavailable."
        except Exception as e:
            logging.error(f"Error getting direct link for {task.link}: {e}", exc_info=True)
            if "after " in str(e) and " seconds" in str(e):
                task.status = "CAPTCHA Timeout"
            else:
                task.status = "Error"
            task.error_message = f"Could not get the direct download link. {format_error_message(e)}"
            return None
        if not task.error_message:
            task.status = "Error"
            task.error_message = "Could not get the direct download link. The link may be expired or blocked."
        return None

    def download_worker(self, task):
        dl_url = self.get_direct_link(task)
        if not dl_url:
            if not task.cancel_flag and not task.pause_flag:
                if self.settings.get("auto_retry_errors", False) and task.retry_count < 3:
                    task.retry_count += 1
                    task.status = "Pending"
                    task.error_message = ""
                    logging.info(f"Auto-retrying {task.filename} (attempt {task.retry_count}/3) after missing direct link")
                else:
                    if task.status != "CAPTCHA Timeout":
                        task.status = "Error"
                    if not task.error_message:
                        task.error_message = "Could not get the direct download link."
            return
            
        if task.cancel_flag:
            task.status = "Cancelled"
            return
            
        if task.pause_flag:
            task.status = "Paused"
            return

        task.status = "Downloading"
        task.error_message = ""
        
        try:
            if not os.path.exists(task.save_dir):
                try:
                    os.makedirs(task.save_dir, exist_ok=True)
                except Exception as e:
                    if self.settings.get("auto_retry_errors", False) and task.retry_count < 3:
                        task.retry_count += 1
                        task.status = "Pending"
                        task.error_message = ""
                        logging.info(f"Auto-retrying {task.filename} (attempt {task.retry_count}/3) after directory error")
                    else:
                        task.status = "Error"
                        task.error_message = f"Failed to create save directory '{task.save_dir}'. {format_error_message(e)}"
                    self.trigger_history_save()
                    return
                
            initial_size = 0
            if os.path.exists(task.filepath):
                initial_size = os.path.getsize(task.filepath)
                
            headers = {}
            if getattr(task, '_dl_user_agent', None):
                headers['User-Agent'] = task._dl_user_agent
                
            head_req = self.dl_session.head(dl_url, cookies=getattr(task, '_dl_cookies', {}), headers=headers, allow_redirects=True)
            # Some hosts reject HEAD while accepting the actual ranged GET. Only
            # trust Content-Length when the HEAD request itself succeeded.
            total_size = 0
            if 200 <= head_req.status_code < 300:
                try:
                    total_size = int(head_req.headers.get('content-length', 0))
                except (TypeError, ValueError):
                    total_size = 0
            task.total_bytes = total_size
            
            if initial_size > 0 and initial_size == total_size:
                task.downloaded_bytes = total_size
                task.progress = 100
                task.status = "Completed"
                task.error_message = ""
                return
                
            resume_header = headers.copy()
            mode = 'wb'
            if initial_size > 0:
                resume_header['Range'] = f'bytes={initial_size}-'
                mode = 'ab'
                
            with contextlib.closing(self.dl_session.get(dl_url, stream=True, headers=resume_header, cookies=getattr(task, '_dl_cookies', {}))) as r:
                if r.status_code == 416 and initial_size > 0:
                    content_range = r.headers.get('content-range', '')
                    match = re.search(r'/([0-9]+)$', content_range)
                    if match and initial_size == int(match.group(1)):
                        task.total_bytes = initial_size
                        task.downloaded_bytes = initial_size
                        task.progress = 100
                        task.speed = 0
                        task.status = "Completed"
                        task.error_message = ""
                        self.trigger_history_save()
                        return
                if r.status_code not in (200, 206):
                    if r.status_code in (403, 503):
                        preview = r.text[:500] if hasattr(r, 'text') else "No text body"
                        logging.error(f"Download 403/503 for {dl_url}. Body preview: {preview}")
                    
                    if self.settings.get("auto_retry_errors", False) and task.retry_count < 3:
                        task.retry_count += 1
                        task.status = "Pending"
                        task.error_message = ""
                        logging.info(f"Auto-retrying {task.filename} (attempt {task.retry_count}/3) after HTTP {r.status_code}")
                    else:
                        task.status = "Error"
                        task.error_message = f"Download request failed. Server returned HTTP {r.status_code}."
                    return
                    
                if r.status_code == 200 and initial_size > 0:
                    # server ignores range header, restart from beginning
                    mode = 'wb'
                    initial_size = 0
                    
                task.downloaded_bytes = initial_size
                if total_size == 0:
                    content_range = r.headers.get('content-range', '')
                    match = re.search(r'/([0-9]+)$', content_range)
                    if match:
                        task.total_bytes = int(match.group(1))
                    else:
                        try:
                            task.total_bytes = int(r.headers.get('content-length', 0)) + initial_size
                        except (TypeError, ValueError):
                            task.total_bytes = 0
                    
                start_time = time.time()
                last_time = start_time
                bytes_since_last = 0
                # Keep a short history instead of reporting only the latest
                # half-second burst of socket data.
                speed_samples = deque([(start_time, task.downloaded_bytes)])
                
                with open(task.filepath, mode) as f:
                    limit_mb_s = self.settings.get("bandwidth_limit", 0)
                    max_workers = self.settings.get("max_workers", 3)
                    
                    limit_bytes_s = 0
                    if limit_mb_s > 0 and max_workers > 0:
                        limit_bytes_s = (limit_mb_s * 1024 * 1024) / max_workers
                    
                    for chunk in r.iter_content(chunk_size=8192*8):
                        if task.pause_flag:
                            task.status = "Paused"
                            task.speed = 0
                            return
                        if task.cancel_flag:
                            task.status = "Cancelled"
                            task.speed = 0
                            return
                            
                        if chunk:
                            f.write(chunk)
                            size = len(chunk)
                            task.downloaded_bytes += size
                            bytes_since_last += size
                            
                            now = time.time()
                            
                            # Simple Token Bucket / Sleep for Bandwidth Limiting
                            if limit_bytes_s > 0:
                                expected_time = bytes_since_last / limit_bytes_s
                                actual_time = now - last_time
                                if expected_time > actual_time:
                                    time.sleep(expected_time - actual_time)
                                    now = time.time()
                            
                            speed_samples.append((now, task.downloaded_bytes))
                            while len(speed_samples) > 1 and now - speed_samples[0][0] > 3:
                                speed_samples.popleft()
                            window_start, window_bytes = speed_samples[0]
                            window_duration = now - window_start
                            if window_duration > 0:
                                task.speed = (
                                    (task.downloaded_bytes - window_bytes) / window_duration
                                ) / (1024 * 1024)
                            if task.total_bytes > 0:
                                task.progress = (task.downloaded_bytes / task.total_bytes) * 100

                            if now - last_time > 0.5:
                                last_time = now
                                bytes_since_last = 0
                
                task.progress = 100
                task.speed = 0
                task.status = "Completed"
                task.error_message = ""
                self.trigger_history_save()
                
        except Exception as e:
            logging.error(f"Download worker error for task {task.link}: {e}", exc_info=True)
            if not task.cancel_flag and not task.pause_flag:
                if self.settings.get("auto_retry_errors", False) and task.retry_count < 3:
                    task.retry_count += 1
                    task.status = "Pending"
                    task.error_message = ""
                    logging.info(f"Auto-retrying {task.filename} (attempt {task.retry_count}/3)")
                else:
                    task.status = "Error"
                    task.error_message = f"Download failed. {format_error_message(e)}"
                self.trigger_history_save()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Determine base directory for assets
    if hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    # Show splash screen
    splash_pixmap = QPixmap(os.path.join(base_dir, "SilverSpoon.png"))
    
    # If the image is extremely large, scale it down for the splash screen
    if not splash_pixmap.isNull():
        if splash_pixmap.width() > 600 or splash_pixmap.height() > 400:
            splash_pixmap = splash_pixmap.scaled(600, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
    splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    
    # Allow Qt events to process so the splash screen renders immediately
    app.processEvents()
    
    # Setup window and load things while splash is visible
    window = MainWindow()
    update_success_marker = os.environ.get("SILVERSPOON_UPDATE_SUCCESS_MARKER")
    if update_success_marker:
        try:
            with open(update_success_marker, "w", encoding="utf-8") as marker:
                marker.write("SilverSpoon started successfully.\n")
        except OSError:
            pass
    
    # After 1 second (1000 ms), close splash and show main window
    QTimer.singleShot(1000, splash.close)
    QTimer.singleShot(1000, window.show)
    
    sys.exit(app.exec())
