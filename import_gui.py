import sys
import os
import json
import shutil
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QLineEdit, QFileDialog, QGroupBox, 
                             QMessageBox, QTextEdit, QProgressBar, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import config
from ingestion_logic import IngestionManager

class IngestionWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal()

    def __init__(self, source_path, library_root, organize_by_season=True, is_folder_source=False):
        super().__init__()
        self.manager = IngestionManager(
            source_path, 
            library_root, 
            organize_by_season, 
            is_folder_source,
            log_callback=self.emit_log,
            progress_callback=self.emit_progress
        )

    def run(self):
        self.manager.run()
        self.finished_signal.emit()

    def emit_log(self, msg):
        self.log_signal.emit(msg)

    def emit_progress(self, cur, total):
        self.progress_signal.emit(cur, total)

    def stop(self):
        self.manager.stop()



class ImportWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BUCT Gallery Ingestion - 入库工具")
        self.resize(900, 600)
        self.apply_stylesheet()
        self.init_ui()
        self.worker = None

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-family: "Segoe UI", sans-serif;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 20px;
                font-weight: bold;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                color: #aaa;
            }
            QLineEdit {
                background-color: #3b3b3b;
                border: 1px solid #555;
                padding: 5px;
                color: white;
            }
            QPushButton {
                background-color: #444;
                border: 1px solid #555;
                padding: 8px 15px;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton#ActionBtn {
                background-color: #2196F3;
                font-weight: bold;
                font-size: 14px;
            }
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #444;
                font-family: Consolas, monospace;
            }
            QProgressBar {
                text-align: center;
                border: 1px solid #555;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Source Section
        grp_src = QGroupBox("1. 数据源 (Source)")
        src_layout = QVBoxLayout()
        
        # Folder Mode
        hbox_src = QHBoxLayout()
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("选择包含 JSON/图片的文件夹 或 单个 JSON 文件...")
        self.src_btn = QPushButton("选择文件夹")
        self.src_btn.clicked.connect(self.select_src_folder)
        self.src_file_btn = QPushButton("选择文件")
        self.src_file_btn.clicked.connect(self.select_src_file)
        
        hbox_src.addWidget(self.src_edit)
        hbox_src.addWidget(self.src_btn)
        hbox_src.addWidget(self.src_file_btn)
        src_layout.addLayout(hbox_src)
        
        grp_src.setLayout(src_layout)
        layout.addWidget(grp_src)

        # 2. Destination Section
        grp_dst = QGroupBox("2. 媒体库位置 (Library Destination)")
        dst_layout = QVBoxLayout()
        
        hbox_dst = QHBoxLayout()
        self.dst_edit = QLineEdit()
        self.dst_edit.setPlaceholderText("选择用于存放整理后图片的根目录 (如 D:/BUCT_Library)...")
        self.dst_btn = QPushButton("选择目录")
        self.dst_btn.clicked.connect(self.select_dst_folder)
        
        hbox_dst.addWidget(self.dst_edit)
        hbox_dst.addWidget(self.dst_btn)
        dst_layout.addLayout(hbox_dst)
        
        self.chk_season = QCheckBox("按季节自动归档 (Auto-organize by Season)")
        self.chk_season.setChecked(True)
        dst_layout.addWidget(self.chk_season)
        
        grp_dst.setLayout(dst_layout)
        layout.addWidget(grp_dst)

        # 3. Action
        self.start_btn = QPushButton("开始入库 (Start Ingestion)")
        self.start_btn.setObjectName("ActionBtn")
        self.start_btn.clicked.connect(self.start_ingestion)
        layout.addWidget(self.start_btn)

        # 4. Progress & Logs
        self.pbar = QProgressBar()
        layout.addWidget(self.pbar)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

    def select_src_folder(self):
        d = QFileDialog.getExistingDirectory(self, "选择源文件夹")
        if d: self.src_edit.setText(d)

    def select_src_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择源 JSON", "", "JSON (*.json)")
        if f: self.src_edit.setText(f)

    def select_dst_folder(self):
        d = QFileDialog.getExistingDirectory(self, "选择媒体库根目录")
        if d: self.dst_edit.setText(d)

    def start_ingestion(self):
        src = self.src_edit.text().strip()
        dst = self.dst_edit.text().strip()
        
        if not src or not os.path.exists(src):
            QMessageBox.warning(self, "错误", "源路径无效。")
            return
        if not dst:
            QMessageBox.warning(self, "错误", "请选择目标媒体库目录。")
            return
            
        is_folder = os.path.isdir(src)
        
        self.start_btn.setEnabled(False)
        self.log_text.clear()
        self.pbar.setValue(0)
        
        self.worker = IngestionWorker(src, dst, self.chk_season.isChecked(), is_folder)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def append_log(self, msg):
        self.log_text.append(msg)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_progress(self, cur, total):
        self.pbar.setMaximum(total)
        self.pbar.setValue(cur)

    def on_finished(self):
        self.start_btn.setEnabled(True)
        QMessageBox.information(self, "完成", "入库操作已完成！\n数据已写入 buct_gallery.db")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ImportWindow()
    win.show()
    sys.exit(app.exec())
