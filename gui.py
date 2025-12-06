import sys
import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QRadioButton, QButtonGroup, 
                             QLineEdit, QGridLayout, QMessageBox, QFrame, QSizePolicy, QFileDialog, QMenuBar, QMenu)
from PyQt6.QtCore import Qt, QSize, QEvent
from PyQt6.QtGui import QPixmap, QImage, QShortcut, QKeySequence, QIcon, QAction
from PIL import Image, ImageOps

import config

class FlowLayout(QGridLayout):
    """Simple helper to emulate flow layout using grid."""
    pass

class TagWidget(QWidget):
    """A chip-like widget for a tag with a delete button."""
    def __init__(self, text, delete_callback):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #e0e0e0;
                border-radius: 10px;
            }
        """)
        
        lbl = QLabel(text)
        lbl.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(lbl)
        
        btn = QPushButton("×")
        btn.setFixedSize(16, 16)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #666;
                font-weight: bold;
                background: transparent;
            }
            QPushButton:hover {
                color: red;
            }
        """)
        btn.clicked.connect(lambda: delete_callback(text))
        layout.addWidget(btn)

class ScalableImageLabel(QLabel):
    """QLabel that scales its pixmap to fill available space while keeping aspect ratio."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 200)
        self._pixmap = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

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

class TaggerWindow(QMainWindow):
    def __init__(self, json_path=None):
        super().__init__()
        self.json_path = json_path
        self.data = []
        self.current_index = 0
        self.dirty = False
        
        self.setWindowTitle(config.WINDOW_TITLE)
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        self.init_ui()
        
        if self.json_path:
            self.load_data()
            self.load_current_image()
        else:
            self.image_label.setText("请通过菜单 '文件 -> 打开' 选择 JSON 文件")

    def init_ui(self):
        # Menu Bar
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("文件 (File)")
        
        open_action = QAction("打开 (Open)...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        exit_action = QAction("退出 (Exit)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Left: Image Preview (Scalable)
        self.image_label = ScalableImageLabel()
        self.image_label.setStyleSheet("background-color: #2b2b2b; color: white; font-size: 16px;")
        main_layout.addWidget(self.image_label, 7)

        # Right: Control Panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel, 3)

        # Info
        self.info_label = QLabel("UUID: ...\n日期: ...")
        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        right_layout.addWidget(line)

        # Campus
        right_layout.addWidget(QLabel("<b>校区 (Campus):</b>"))
        self.campus_group = QButtonGroup(self)
        campus_layout = QHBoxLayout()
        for name in ["东区", "北区", "西区", "未知"]:
            rb = QRadioButton(name)
            self.campus_group.addButton(rb)
            campus_layout.addWidget(rb)
        right_layout.addLayout(campus_layout)

        # Season
        right_layout.addWidget(QLabel("<b>季节 (Season):</b>"))
        self.season_group = QButtonGroup(self)
        season_layout = QHBoxLayout()
        self.season_map = {"Spring": "春", "Summer": "夏", "Autumn": "秋", "Winter": "冬"}
        self.season_map_rev = {v: k for k, v in self.season_map.items()}
        
        for k, v in self.season_map.items():
            rb = QRadioButton(v)
            rb.setObjectName(k)
            self.season_group.addButton(rb)
            season_layout.addWidget(rb)
        right_layout.addLayout(season_layout)

        # Quick Tags
        right_layout.addWidget(QLabel("<b>快速标签 (Presets):</b>"))
        presets = ["母校之光", "图书馆", "第一教学楼", "行政楼", "樱花", "银杏", "军训", "毕业"]
        self.preset_buttons = {}
        preset_layout = QGridLayout()
        for i, tag in enumerate(presets):
            btn = QPushButton(tag)
            btn.setCheckable(True)
            btn.clicked.connect(self.toggle_preset_tag)
            self.preset_buttons[tag] = btn
            preset_layout.addWidget(btn, i // 3, i % 3)
        right_layout.addLayout(preset_layout)

        # Active Keywords (Chips)
        right_layout.addWidget(QLabel("<b>当前标签 (Active Tags):</b>"))
        
        # Container for tags
        self.tags_container = QWidget()
        self.tags_layout = QGridLayout(self.tags_container) 
        self.tags_layout.setSpacing(5)
        right_layout.addWidget(self.tags_container)

        # Add Tag Input
        add_tag_layout = QHBoxLayout()
        self.new_tag_input = QLineEdit()
        self.new_tag_input.setPlaceholderText("输入标签按回车...")
        self.new_tag_input.returnPressed.connect(self.add_manual_tag)
        add_btn = QPushButton("+")
        add_btn.clicked.connect(self.add_manual_tag)
        
        add_tag_layout.addWidget(self.new_tag_input)
        add_tag_layout.addWidget(add_btn)
        right_layout.addLayout(add_tag_layout)

        # Navigation & Save
        right_layout.addStretch()
        
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("上一张 (Prev)")
        self.prev_btn.clicked.connect(self.prev_image)
        self.next_btn = QPushButton("下一张 (Next)")
        self.next_btn.clicked.connect(self.next_image)
        self.save_btn = QPushButton("保存 (Save) [Ctrl+S]")
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.save_btn.clicked.connect(self.save_current)
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)
        right_layout.addLayout(nav_layout)
        right_layout.addWidget(self.save_btn)

        # Shortcuts
        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(self.save_current)
        
        self.shortcut_left = QShortcut(QKeySequence("Left"), self)
        self.shortcut_left.activated.connect(self.prev_image)
        
        self.shortcut_right = QShortcut(QKeySequence("Right"), self)
        self.shortcut_right.activated.connect(self.next_image)

        self.current_keywords = []
        self.image_root_override = None

    def open_file_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择预标注 JSON 文件", "", "JSON Files (*.json)")
        if f:
            self.json_path = f
            self.current_index = 0
            self.image_root_override = None # Reset override on new file
            self.load_data()
            self.load_current_image()

    def load_data(self):
        if not os.path.exists(self.json_path):
            QMessageBox.critical(self, "错误", f"找不到文件: {self.json_path}")
            return
        
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载 JSON: {e}")
            return

        if not self.data:
            QMessageBox.warning(self, "警告", "JSON 文件为空。")
            return

    def resolve_image_path(self, item):
        original_path = item.get("original_path", "")
        if not original_path:
            return None
        
        # 1. Try exact absolute path
        if os.path.exists(original_path):
            return original_path
            
        filename = item.get("filename") or os.path.basename(original_path)
        json_dir = os.path.dirname(os.path.abspath(self.json_path))
        
        # 2. Try override folder if set
        if self.image_root_override:
            candidate = os.path.join(self.image_root_override, filename)
            if os.path.exists(candidate):
                return candidate
                
        # 3. Common relative paths
        candidates = [
            os.path.join(json_dir, filename), # Same dir
            os.path.join(json_dir, "images", filename), # images/ subdir
            os.path.join(json_dir, "..", "images", filename), # ../images sibling
            os.path.join(json_dir, "..", filename), # Parent dir
        ]
        
        for c in candidates:
            if os.path.exists(c):
                return c
                
        # 4. Ask user (only once per session)
        if not self.image_root_override:
            reply = QMessageBox.question(
                self, 
                "找不到图片 (Image Not Found)", 
                f"无法找到图片: {filename}\n\n原路径: {original_path}\n\n是否手动指定图片所在的文件夹？\n(指定后将应用于所有图片)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹 (Select Image Folder)")
                if folder:
                    self.image_root_override = folder
                    # Recursively call to try with new override
                    return self.resolve_image_path(item)
                    
        return None

    def load_current_image(self):
        if not self.data:
            return

        if 0 <= self.current_index < len(self.data):
            item = self.data[self.current_index]
            
            # Load Image
            img_path = self.resolve_image_path(item)
            if img_path:
                pixmap = QPixmap(img_path)
                self.image_label.setPixmap(pixmap)
            else:
                self.image_label.setText(f"图片未找到 (Image Not Found):\n{item.get('original_path')}")

            # Update Info
            date_taken = item["tags"]["meta"].get("date_taken", "未知")
            self.info_label.setText(f"UUID: {item['uuid']}\n日期: {date_taken}\n文件: {item['filename']}")

            # Update Attributes
            attrs = item["tags"]["attributes"]
            
            # Campus
            campus = attrs.get("campus", "未知")
            for btn in self.campus_group.buttons():
                if btn.text() == campus:
                    btn.setChecked(True)
                    break
            else:
                for btn in self.campus_group.buttons():
                    if btn.text() == "未知":
                        btn.setChecked(True)

            # Season
            season_en = attrs.get("season")
            season_cn = self.season_map.get(season_en)
            found_season = False
            for btn in self.season_group.buttons():
                if btn.text() == season_cn:
                    btn.setChecked(True)
                    found_season = True
                    break
            if not found_season:
                 self.season_group.setExclusive(False)
                 for btn in self.season_group.buttons():
                     btn.setChecked(False)
                 self.season_group.setExclusive(True)

            # Keywords
            self.current_keywords = item["tags"].get("keywords", [])
            self.render_tags()
            
            # Update Preset Buttons State
            self.update_preset_buttons_state()

            self.setWindowTitle(f"{config.WINDOW_TITLE} - [{self.current_index + 1}/{len(self.data)}]")

    def render_tags(self):
        # Clear existing tags
        while self.tags_layout.count():
            child = self.tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add new tags
        col_count = 3
        for i, tag in enumerate(self.current_keywords):
            chip = TagWidget(tag, self.remove_tag)
            self.tags_layout.addWidget(chip, i // col_count, i % col_count)

    def remove_tag(self, tag):
        if tag in self.current_keywords:
            self.current_keywords.remove(tag)
            self.render_tags()
            self.update_preset_buttons_state()

    def add_manual_tag(self):
        text = self.new_tag_input.text().strip()
        if text and text not in self.current_keywords:
            self.current_keywords.append(text)
            self.render_tags()
            self.update_preset_buttons_state()
        self.new_tag_input.clear()

    def toggle_preset_tag(self):
        sender = self.sender()
        tag = sender.text()
        
        if sender.isChecked():
            if tag not in self.current_keywords:
                self.current_keywords.append(tag)
        else:
            if tag in self.current_keywords:
                self.current_keywords.remove(tag)
        
        self.render_tags()

    def update_preset_buttons_state(self):
        for tag, btn in self.preset_buttons.items():
            btn.setChecked(tag in self.current_keywords)

    def save_current(self):
        if not self.data: return

        item = self.data[self.current_index]
        
        # Campus
        campus_btn = self.campus_group.checkedButton()
        if campus_btn:
            item["tags"]["attributes"]["campus"] = campus_btn.text()
        
        # Season
        season_btn = self.season_group.checkedButton()
        if season_btn:
            item["tags"]["attributes"]["season"] = self.season_map_rev.get(season_btn.text(), "Unknown")

        # Keywords
        item["tags"]["keywords"] = self.current_keywords

        # Meta
        item["tags"]["meta"]["annotator"] = os.getenv("USERNAME", "User")
        item["tags"]["meta"]["last_modified"] = str(import_datetime_now())

        self.generate_thumbnail(item)
        self.save_json()
        self.next_image()

    def generate_thumbnail(self, item):
        try:
            original_path = item["original_path"]
            if not os.path.exists(original_path):
                return

            thumb_dir = os.path.join(os.path.dirname(self.json_path), "thumb")
            os.makedirs(thumb_dir, exist_ok=True)
            
            base_name = os.path.splitext(os.path.basename(original_path))[0]
            thumb_name = f"{base_name}_thumb.jpg"
            thumb_path = os.path.join(thumb_dir, thumb_name)
            
            with Image.open(original_path) as img:
                img = ImageOps.exif_transpose(img) 
                img.thumbnail((300, 300))
                img.save(thumb_path, quality=80)
            
            item["thumb_path"] = thumb_path
            
        except Exception as e:
            print(f"Thumbnail generation failed: {e}")

    def save_json(self):
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            self.statusBar().showMessage("已保存!", 1000)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def next_image(self):
        if self.current_index < len(self.data) - 1:
            self.current_index += 1
            self.load_current_image()
        else:
             QMessageBox.information(self, "提示", "这是最后一张图片了。")

    def prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()

def import_datetime_now():
    from datetime import datetime
    return datetime.now()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Optional CLI arg, but default behavior is open empty
    json_file = None
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        if not os.path.exists(json_file):
            json_file = None

    window = TaggerWindow(json_file)
    window.show()
    sys.exit(app.exec())
