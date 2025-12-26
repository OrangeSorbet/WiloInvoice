import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView, QProgressBar,
    QFrame, QGraphicsDropShadowEffect, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPropertyAnimation, QRect, QPoint, QEasingCurve
from PySide6.QtGui import QColor

from .core import InvoicePipeline
from .storage import StorageEngine
from .security import SecurityManager
from .utils import setup_logger

logger = setup_logger()

class AssetManager:
    @staticmethod
    def load_stylesheet():
        path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'styles.qss')
        path = os.path.abspath(path)
        if os.path.exists(path):
            with open(path, "r") as f: return f.read()
        return ""

class StatusBadge(QLabel):
    def __init__(self, text, status_type):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        colors = {
            "Processed": ("#dcfce7", "#166534"),
            "Duplicate": ("#ffedd5", "#9a3412"),
            "Error":     ("#fee2e2", "#991b1b")
        }
        bg, text_col = colors.get(status_type, ("#e2e8f0", "#475569"))
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {text_col};
                border-radius: 10px;
                padding: 4px 12px;
                font-weight: 700;
                font-size: 11px;
            }}
        """)

class Toast(QLabel):
    def __init__(self, parent, message, level="info", duration=3000):
        super().__init__(parent)
        self.setText(message)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        color_map = {"info": "#3b82f6", "success": "#22c55e", "warning": "#f59e0b", "error": "#ef4444"}
        bg_color = color_map.get(level, "#333")
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                padding: 12px 16px;
                border-radius: 6px;
                font-weight: 500;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setYOffset(4)
        self.setGraphicsEffect(shadow)
        
        self.adjustSize()
        self.setFixedWidth(min(400, parent.width() - 40))
        self._animate(duration)

    def _animate(self, duration):
        parent = self.parent()
        margin = 24
        x_pos = parent.width() - self.width() - margin
        start_y = parent.height()
        end_y = parent.height() - self.height() - margin

        self.move(x_pos, start_y)
        self.show()

        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(300)
        self.anim.setStartValue(QPoint(x_pos, start_y))
        self.anim.setEndValue(QPoint(x_pos, end_y))
        
        self.anim.setEasingCurve(QEasingCurve.OutCubic) 
        self.anim.start()
        
        QTimer.singleShot(duration, lambda: (self.close(), self.deleteLater()))

class Worker(QThread):
    progress = Signal(str, str, str)
    finished = Signal()

    def __init__(self, files):
        super().__init__()
        self.files = files
        self.pipeline = InvoicePipeline()
        self.storage = StorageEngine()

    def run(self):
        for path in self.files:
            try:
                fname = os.path.basename(path)
                fhash = SecurityManager.get_file_hash(path)
                data = self.pipeline.process_invoice(path)
                saved = self.storage.save_invoice(fname, fhash, data)
                
                status = "Processed" if saved else "Duplicate"
                vendor = data.get("vendor_name", "Unknown")
                
                self.progress.emit(fname, vendor, status)
            except Exception as e:
                logger.error(f"Failed {path}: {e}")
                self.progress.emit(os.path.basename(path), "N/A", "Error")
        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wilow Invoice Extractor")
        self.resize(1100, 750)
        
        style_content = AssetManager.load_stylesheet()
        if style_content:
            self.setStyleSheet(style_content)
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(24)

        # Header
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        
        title_block = QWidget()
        tb = QVBoxLayout(title_block)
        tb.setContentsMargins(0,0,0,0)
        tb.setSpacing(4)
        
        lbl_title = QLabel("Invoice Extraction")
        lbl_title.setObjectName("HeaderTitle")
        lbl_sub = QLabel("Secure offline processing pipeline • v1.0")
        lbl_sub.setObjectName("HeaderSubtitle")
        tb.addWidget(lbl_title)
        tb.addWidget(lbl_sub)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setProperty("class", "outline")
        self.btn_export.setEnabled(False)
        self.btn_export.setFixedWidth(120)

        self.btn_upload = QPushButton("Upload Invoices")
        self.btn_upload.setProperty("class", "primary")
        self.btn_upload.setFixedWidth(160)

        h_layout.addWidget(title_block)
        h_layout.addStretch()
        h_layout.addWidget(self.btn_export)
        h_layout.addWidget(self.btn_upload)
        main_layout.addWidget(header)

        # Card
        self.card = QFrame()
        self.card.setObjectName("ContentCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 15))
        self.card.setGraphicsEffect(shadow)
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        lbl_card = QLabel("Processed Queue")
        lbl_card.setObjectName("CardTitle")
        card_layout.addWidget(lbl_card)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Filename", "Vendor Identified", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        card_layout.addWidget(self.table)
        main_layout.addWidget(self.card)

        # Footer
        footer = QWidget()
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        self.lbl_status = QLabel("System Ready")
        self.lbl_status.setFixedHeight(28)
        self.lbl_status.setObjectName("StatusPill")
        self.update_status_pill("System Ready", "idle")
        
        main_layout.addWidget(self.progress_bar)
        f_layout.addWidget(self.lbl_status)
        f_layout.addStretch()
        main_layout.addWidget(footer)

    def _connect_signals(self):
        self.btn_upload.clicked.connect(self.upload_files)
        self.btn_export.clicked.connect(self.export_data)

    def show_toast(self, message, level="info"):
        Toast(self, message, level)

    def update_status_pill(self, message, state="idle"):
        self.lbl_status.setText(message)
        styles = {
            "idle":    "background-color: transparent; color: #64748b;",
            "working": "background-color: #e0f2fe; color: #0284c7; border: 1px solid #bae6fd;", 
            "success": "background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0;", 
            "error":   "background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca;"  
        }
        base_style = "padding: 0 16px; border-radius: 14px; font-weight: 600; font-size: 12px;"
        self.lbl_status.setStyleSheet(f"QLabel {{ {base_style} {styles.get(state, styles['idle'])} }}")

    def upload_files(self):
        try:
            files, _ = QFileDialog.getOpenFileNames(self, "Select Invoice PDFs", "", "PDF Files (*.pdf)")
            if not files: return

            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0) 
            self.update_status_pill("Encrypting and processing files...", "working")
            self.btn_upload.setEnabled(False)
            self.btn_export.setEnabled(False)
            
            self.worker = Worker(files)
            self.worker.progress.connect(self.handle_progress)
            self.worker.finished.connect(self.handle_finished)
            self.worker.start()
        except Exception as e:
            logger.error(f"UI Upload Error: {e}")
            self.show_toast("Critical error initializing upload.", "error")
            self.update_status_pill("Error", "error")

    def handle_progress(self, fname, vendor, status):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(fname))
        self.table.setItem(row, 1, QTableWidgetItem(vendor))
        
        container = QWidget()
        l = QHBoxLayout(container)
        l.setContentsMargins(0, 2, 0, 2)
        l.setAlignment(Qt.AlignLeft)
        l.addWidget(StatusBadge(status, status))
        self.table.setCellWidget(row, 2, container)
        self.table.scrollToBottom()

    def handle_finished(self):
        self.progress_bar.setVisible(False)
        self.update_status_pill("Processing complete", "success")
        self.btn_upload.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.show_toast("Batch processing finished.", "success")

    def export_data(self):
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Export Data", "invoices_export.csv", "CSV Files (*.csv)")
            if path:
                count = StorageEngine().export_to_csv(path)
                self.update_status_pill(f"Exported {count} records", "success")
                self.show_toast(f"Successfully exported {count} records.", "success")
        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.show_toast("Failed to export data.", "error")