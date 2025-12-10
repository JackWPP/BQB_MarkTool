import sys
import os
import json
import math
import time
import shutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QProgressBar, QTextEdit, QFileDialog, 
                             QMessageBox, QGroupBox, QSpinBox, QTabWidget, QLineEdit, 
                             QGridLayout, QSizePolicy, QScrollArea, QCheckBox, QProgressDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QWaitCondition, QMutex
from PyQt6.QtGui import QPixmap

# Import existing logic
from pre_process import ImagePreprocessor

# Import shared widget if possible, or redefine
class ScalableImageLabel(QLabel):
    """QLabel that scales its pixmap to fill available space while keeping aspect ratio."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 200)
        self._pixmap = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setStyleSheet("background-color: #1e1e1e; border-radius: 5px; border: 1px solid #333;")

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self.update_image()

    def resizeEvent(self, event):
        self.update_image()
        super().resizeEvent(event)

    def update_image(self):
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            super().setPixmap(scaled)

class WorkerThread(QThread):
    progress_signal = pyqtSignal(int, int) # current, total
    log_signal = pyqtSignal(str)
    preview_signal = pyqtSignal(str) # image path
    result_signal = pyqtSignal(dict) # item dict
    finished_signal = pyqtSignal()

    def __init__(self, input_dir, output_file):
        super().__init__()
        self.input_dir = input_dir
        self.output_file = output_file
        self.processor = None
        self._is_running = True
        self._is_paused = False
        self._pause_mutex = QMutex()
        self._pause_condition = QWaitCondition()

    def run(self):
        self.processor = ImagePreprocessor(self.input_dir, self.output_file)
        try:
            self.processor.process_folder(
                progress_callback=self.emit_progress,
                log_callback=self.emit_log,
                preview_callback=self.emit_preview,
                result_callback=self.emit_result,
                check_pause=self.check_pause
            )
        except Exception as e:
            self.emit_log(f"严重错误: {e}")
        self.finished_signal.emit()

    def check_pause(self):
        self._pause_mutex.lock()
        if self._is_paused:
            self.emit_log(">>> 任务已暂停 (Task Paused) <<<")
            self._pause_condition.wait(self._pause_mutex)
            self.emit_log(">>> 任务继续 (Task Resumed) <<<")
        self._pause_mutex.unlock()
        
        if not self._is_running:
            sys.exit(0) # Force thread exit

    def pause(self):
        self._pause_mutex.lock()
        self._is_paused = True
        self._pause_mutex.unlock()

    def resume(self):
        self._pause_mutex.lock()
        self._is_paused = False
        self._pause_condition.wakeAll()
        self._pause_mutex.unlock()

    def stop(self):
        self._is_running = False
        # Wake up if paused so it can exit
        self.resume()

    def emit_progress(self, current, total):
        self.progress_signal.emit(current, total)

    def emit_log(self, msg):
        self.log_signal.emit(msg)
        
    def emit_preview(self, path):
        self.preview_signal.emit(path)
        
    def emit_result(self, item):
        self.result_signal.emit(item)

class PreprocessWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BUCT 打标工具箱 - 预处理与分发")
        self.resize(1000, 700)
        
        self.worker = None
        self.is_paused = False

        # Apply Dark Theme
        self.apply_stylesheet()
        self.init_ui()

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                font-size: 10pt;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 20px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
                color: #ddd;
            }
            QLineEdit, QSpinBox, QTextEdit {
                background-color: #3b3b3b;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                color: #fff;
                selection-background-color: #0078d7;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #0078d7;
            }
            QPushButton {
                background-color: #444;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px 15px;
                color: #fff;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton:pressed {
                background-color: #333;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #777;
                border-color: #444;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 5px;
                text-align: center;
                background-color: #333;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background: #333;
                color: #aaa;
                padding: 8px 20px;
                border: 1px solid #444;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #2b2b2b;
                color: #fff;
                border-bottom: 1px solid #2b2b2b; /* blend with pane */
            }
            QTabBar::tab:hover {
                background: #444;
            }
            QScrollArea {
                border: none;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Tab 1: Pre-processing
        self.tab_process = QWidget()
        self.init_process_tab(self.tab_process)
        tabs.addTab(self.tab_process, "1. 预处理 (AI Auto-Label)")

        # Tab 2: Task Splitting
        self.tab_split = QWidget()
        self.init_split_tab(self.tab_split)
        tabs.addTab(self.tab_split, "2. 任务分发 (Task Split)")

    def init_process_tab(self, tab):
        main_layout = QHBoxLayout(tab)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        
        # Left Column: Config & Logs (40%)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        # 1. Config Group
        grp_input = QGroupBox("配置 (Configuration)")
        input_layout = QGridLayout()
        input_layout.setSpacing(10)
        
        self.input_dir_edit = QLineEdit()
        self.input_dir_btn = QPushButton("选择图片文件夹")
        self.input_dir_btn.clicked.connect(self.select_input_dir)
        
        self.output_file_edit = QLineEdit("pre_annotated.json")
        
        input_layout.addWidget(QLabel("图片目录:"), 0, 0)
        input_layout.addWidget(self.input_dir_edit, 0, 1)
        input_layout.addWidget(self.input_dir_btn, 0, 2)
        
        input_layout.addWidget(QLabel("输出 JSON:"), 1, 0)
        input_layout.addWidget(self.output_file_edit, 1, 1)
        
        grp_input.setLayout(input_layout)
        left_layout.addWidget(grp_input)

        # 2. Progress Group
        grp_progress = QGroupBox("进度 (Progress)")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(25)
        progress_layout.addWidget(self.pbar)
        self.progress_label = QLabel("Waiting to start...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        grp_progress.setLayout(progress_layout)
        left_layout.addWidget(grp_progress)

        # 3. Controls
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始处理 (Start)")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        self.pause_btn = QPushButton("暂停 (Pause)")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet("background-color: #FFC107; color: black; font-weight: bold;")

        self.stop_btn = QPushButton("停止 (Stop)")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.stop_btn)
        left_layout.addLayout(btn_layout)

        # 4. Logs
        left_layout.addWidget(QLabel("运行日志 (Logs):"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # No inline style needed, handled by global stylesheet
        left_layout.addWidget(self.log_text)
        
        main_layout.addWidget(left_widget, 4)

        # Right Column: Preview & Result (60%)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Image Preview
        preview_group = QGroupBox("实时预览 (Live Preview)")
        preview_layout = QVBoxLayout()
        self.image_preview = ScalableImageLabel()
        self.image_preview.setText("暂无预览\n(No Preview)")
        preview_layout.addWidget(self.image_preview)
        preview_group.setLayout(preview_layout)
        right_layout.addWidget(preview_group, 6)

        # Tags Result
        result_group = QGroupBox("识别结果 (Recognition Result)")
        result_layout = QVBoxLayout()
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        # Remove the white background style, let it use global dark theme
        result_layout.addWidget(self.result_text)
        result_group.setLayout(result_layout)
        right_layout.addWidget(result_group, 4)

        main_layout.addWidget(right_widget, 6)

    def init_split_tab(self, tab):
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        grp_split = QGroupBox("切分大任务文件 (Split Task)")
        split_layout = QGridLayout()
        split_layout.setSpacing(15)

        self.split_input_edit = QLineEdit()
        self.split_input_btn = QPushButton("选择 JSON 文件")
        self.split_input_btn.clicked.connect(self.select_split_json)

        self.split_count_spin = QSpinBox()
        self.split_count_spin.setRange(1, 10000)
        self.split_count_spin.setValue(100)
        self.split_count_spin.setSuffix(" 张/每份")
        self.split_count_spin.setMinimumWidth(150)
        
        self.zip_checkbox = QCheckBox("同时生成 ZIP 压缩包 (Generate .zip)")
        self.zip_checkbox.setChecked(True)

        self.split_btn = QPushButton("开始切分并生成任务包 (Split & Generate)")
        self.split_btn.clicked.connect(self.run_split)
        self.split_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")

        split_layout.addWidget(QLabel("源 JSON:"), 0, 0)
        split_layout.addWidget(self.split_input_edit, 0, 1)
        split_layout.addWidget(self.split_input_btn, 0, 2)
        
        split_layout.addWidget(QLabel("切分大小:"), 1, 0)
        split_layout.addWidget(self.split_count_spin, 1, 1)
        split_layout.addWidget(self.zip_checkbox, 1, 2)
        
        split_layout.addWidget(self.split_btn, 2, 0, 1, 3)
        
        grp_split.setLayout(split_layout)
        layout.addWidget(grp_split)
        
        # Instructions
        info_label = QLabel("""
        <b>使用说明:</b><br>
        1. 选择预处理生成的完整 JSON 文件 (如 <i>pre_annotated.json</i>)。<br>
        2. 设置每个子任务包含的图片数量。<br>
        3. 点击切分，系统会创建独立的任务文件夹。<br>
        4. 每个文件夹包含：<b>需标注的图片文件</b> + <b>task_data.json</b>。<br>
        5. 可直接分发压缩包给标注人员。
        """)
        # Update to dark theme compatible styling
        info_label.setStyleSheet("background: #333; padding: 15px; border-radius: 5px; color: #ddd; border: 1px solid #555;")
        layout.addWidget(info_label)
        
        layout.addStretch()

    # --- Actions ---

    def select_input_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if d:
            self.input_dir_edit.setText(d)

    def select_split_json(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 JSON", "", "JSON Files (*.json)")
        if f:
            self.split_input_edit.setText(f)

    def start_processing(self):
        input_dir = self.input_dir_edit.text()
        output_file = self.output_file_edit.text()
        
        if not input_dir or not os.path.exists(input_dir):
            QMessageBox.warning(self, "错误", "无效的输入目录。")
            return

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.log_text.clear()
        self.result_text.clear()
        self.pbar.setValue(0)
        self.is_paused = False
        self.pause_btn.setText("暂停 (Pause)")
        self.pause_btn.setStyleSheet("background-color: #FFC107; color: black; font-weight: bold;")

        self.worker = WorkerThread(input_dir, output_file)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.append_log)
        self.worker.preview_signal.connect(self.update_preview)
        self.worker.result_signal.connect(self.update_result)
        self.worker.finished_signal.connect(self.processing_finished)
        self.worker.start()

    def toggle_pause(self):
        if not self.worker: return
        
        if self.is_paused:
            self.worker.resume()
            self.is_paused = False
            self.pause_btn.setText("暂停 (Pause)")
            self.pause_btn.setStyleSheet("background-color: #FFC107; color: black; font-weight: bold;")
        else:
            self.worker.pause()
            self.is_paused = True
            self.pause_btn.setText("继续 (Resume)")
            self.pause_btn.setStyleSheet("background-color: #8BC34A; color: white; font-weight: bold;")

    def stop_processing(self):
        if self.worker:
            self.worker.stop()
            self.append_log("正在停止...")
            self.stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)

    def update_progress(self, current, total):
        self.pbar.setMaximum(total)
        self.pbar.setValue(current)
        self.progress_label.setText(f"Processing: {current} / {total}")

    def append_log(self, msg):
        self.log_text.append(msg)
        # Auto scroll
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())
        
    def update_preview(self, path):
        if os.path.exists(path):
            self.image_preview.setPixmap(QPixmap(path))
        else:
            self.image_preview.setText("Preview Error")
            
    def update_result(self, item):
        # Pretty print tags
        tags = item.get("tags", {})
        keywords = tags.get("keywords", [])
        attrs = tags.get("attributes", {})
        season = attrs.get("season", "-")
        category = attrs.get("category", "-")
        
        # Use style for dark mode text
        html = f"""
        <div style='color: #e0e0e0;'>
        <h3 style='margin-top:0'>File: {item.get("filename")}</h3>
        <p><b>Season:</b> {season}</p>
        <p><b>Category:</b> {category}</p>
        <p><b>Keywords:</b></p>
        <ul>
        """
        for k in keywords:
            html += f"<li>{k}</li>"
        html += "</ul>"
        
        if "error" in tags.get("meta", {}):
            html += f"<p style='color:#ff5555'><b>Error:</b> {tags['meta']['error']}</p>"
        
        html += "</div>"
            
        self.result_text.setHtml(html)

    def processing_finished(self):
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.append_log("任务已结束。")
        if not self.worker or self.worker._is_running: # Only show if finished naturally
             QMessageBox.information(self, "完成", "处理完成！")

    def run_split(self):
        json_path = self.split_input_edit.text()
        per_file = self.split_count_spin.value()
        do_zip = self.zip_checkbox.isChecked()
        
        if not os.path.exists(json_path):
            QMessageBox.warning(self, "错误", "找不到 JSON 文件。")
            return
            
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            total = len(data)
            if total == 0:
                 QMessageBox.warning(self, "警告", "JSON 文件为空。")
                 return

            chunks = math.ceil(total / per_file)
            
            base_dir = os.path.dirname(json_path)
            json_filename = os.path.basename(json_path)
            base_name_no_ext = os.path.splitext(json_filename)[0]
            
            output_root = os.path.join(base_dir, f"{base_name_no_ext}_dist")
            os.makedirs(output_root, exist_ok=True)
            
            # Progress Dialog
            progress = QProgressDialog("正在处理任务包...", "取消", 0, total, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            
            processed_count = 0
            
            for i in range(chunks):
                if progress.wasCanceled():
                    break
                    
                chunk_data = data[i*per_file : (i+1)*per_file]
                
                # Create task folder
                task_folder_name = f"{base_name_no_ext}_task_{i+1:03d}"
                task_folder_path = os.path.join(output_root, task_folder_name)
                
                # Clean recreate if exists
                if os.path.exists(task_folder_path):
                    shutil.rmtree(task_folder_path)
                os.makedirs(task_folder_path, exist_ok=True)
                
                new_chunk_data = []
                
                for item in chunk_data:
                    if progress.wasCanceled():
                        break
                        
                    src_path = item.get("original_path")
                    # Try to resolve relative path if absolute doesn't exist
                    if not src_path or not os.path.exists(src_path):
                        # Try relative to json dir
                        possible_path = os.path.join(base_dir, item.get("filename", ""))
                        if os.path.exists(possible_path):
                            src_path = possible_path
                    
                    if src_path and os.path.exists(src_path):
                        filename = os.path.basename(src_path)
                        dst_path = os.path.join(task_folder_path, filename)
                        
                        try:
                            shutil.copy2(src_path, dst_path)
                            
                            # Update item path for the task
                            new_item = item.copy()
                            new_item["original_path"] = filename # Relative path
                            new_chunk_data.append(new_item)
                        except Exception as copy_err:
                            print(f"Copy error: {copy_err}")
                    else:
                        print(f"Warning: Image not found {src_path}")
                    
                    processed_count += 1
                    progress.setValue(processed_count)
                
                # Save JSON in the folder
                task_json_path = os.path.join(task_folder_path, "task_data.json")
                with open(task_json_path, 'w', encoding='utf-8') as f:
                    json.dump(new_chunk_data, f, ensure_ascii=False, indent=2)
                
                # Zip if requested
                if do_zip:
                    shutil.make_archive(task_folder_path, 'zip', task_folder_path)

            progress.setValue(total)
            QMessageBox.information(self, "成功", f"已生成 {chunks} 个任务包。\n输出目录: {output_root}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"切分失败: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PreprocessWindow()
    window.show()
    sys.exit(app.exec())
