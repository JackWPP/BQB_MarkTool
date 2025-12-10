import os
import json
import shutil
import sqlite3
from datetime import datetime

class IngestionManager:
    def __init__(self, source_path, library_root, organize_by_season=True, is_folder_source=False, log_callback=None, progress_callback=None):
        self.source_path = source_path
        self.library_root = library_root
        self.organize_by_season = organize_by_season
        self.is_folder_source = is_folder_source
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self._is_running = True

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)

    def run(self):
        try:
            self.log(">>> 开始入库流程 (Starting Ingestion)...")
            
            # 1. Gather all JSON data
            all_items = []
            
            if self.is_folder_source:
                self.log(f"扫描目录: {self.source_path}")
                for root, dirs, files in os.walk(self.source_path):
                    for file in files:
                        if file.lower().endswith('.json'):
                            full_path = os.path.join(root, file)
                            try:
                                with open(full_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    if isinstance(data, list):
                                        for item in data:
                                            item['_source_json'] = full_path
                                        all_items.extend(data)
                                        self.log(f"已读取: {file} ({len(data)} items)")
                            except Exception as e:
                                self.log(f"读取失败 {file}: {e}")
            else:
                self.log(f"读取文件: {self.source_path}")
                try:
                    with open(self.source_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for item in data:
                                item['_source_json'] = self.source_path
                            all_items = data
                except Exception as e:
                    self.log(f"读取失败: {e}")
                    return

            total_items = len(all_items)
            self.log(f"总计发现 {total_items} 个待处理项。")
            
            if total_items == 0:
                self.log("没有数据需要处理。")
                return

            # 2. Init DB
            self.init_db()
            
            conn = sqlite3.connect("buct_gallery.db")
            cursor = conn.cursor()
            
            # 3. Process each item
            processed_count = 0
            
            for item in all_items:
                if not self._is_running: break
                
                try:
                    # Find Source Image
                    source_image_path = self.resolve_source_image(item)
                    if not source_image_path:
                        self.log(f"跳过 (找不到图片): {item.get('filename')}")
                        continue
                        
                    # Determine Destination
                    season = item.get("tags", {}).get("attributes", {}).get("season", "Unknown")
                    if not self.organize_by_season:
                        season = "Unsorted"
                    
                    # Target folder: Library/Season/
                    target_dir = os.path.join(self.library_root, season)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # Target filename
                    ext = os.path.splitext(item['filename'])[1]
                    new_filename = f"{item['uuid']}{ext}"
                    target_path = os.path.join(target_dir, new_filename)
                    
                    # Copy File
                    if not os.path.exists(target_path):
                        shutil.copy2(source_image_path, target_path)
                    
                    # Handle Thumbnail
                    thumb_target_path = ""
                    source_thumb = self.resolve_source_thumb(item)
                    if source_thumb:
                        thumb_dir = os.path.join(self.library_root, "thumbs", season)
                        os.makedirs(thumb_dir, exist_ok=True)
                        thumb_target_name = f"{item['uuid']}_thumb{ext}"
                        thumb_target_path = os.path.join(thumb_dir, thumb_target_name)
                        if not os.path.exists(thumb_target_path):
                            shutil.copy2(source_thumb, thumb_target_path)

                    # Update DB
                    self.upsert_db(cursor, item, target_path, thumb_target_path)
                    
                    processed_count += 1
                    if self.progress_callback:
                        self.progress_callback(processed_count, total_items)
                    
                    if processed_count % 10 == 0:
                        conn.commit()
                        
                except Exception as e:
                    self.log(f"处理错误 {item.get('filename')}: {e}")
            
            conn.commit()
            conn.close()
            self.log(">>> 入库完成 (Ingestion Complete) <<<")
            
        except Exception as e:
            self.log(f"致命错误: {e}")

    def resolve_source_image(self, item):
        path = item.get("original_path")
        json_dir = os.path.dirname(item['_source_json'])
        
        if path and os.path.exists(path):
            return path
            
        filename = item.get("filename")
        if not filename and path:
            filename = os.path.basename(path)
            
        candidates = [
            os.path.join(json_dir, filename),
            os.path.join(json_dir, "images", filename),
            os.path.join(json_dir, "..", filename)
        ]
        
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def resolve_source_thumb(self, item):
        path = item.get("thumb_path")
        if not path: return None
        
        json_dir = os.path.dirname(item['_source_json'])
        
        if os.path.exists(path): return path
        
        candidates = [
            os.path.join(json_dir, path),
            os.path.join(json_dir, "thumb", os.path.basename(path))
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def init_db(self):
        conn = sqlite3.connect("buct_gallery.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                uuid TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                original_path TEXT,
                processed_path TEXT,
                thumb_path TEXT,
                width INTEGER,
                height INTEGER,
                campus TEXT,
                season TEXT,
                category TEXT,
                keywords TEXT,
                meta TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                annotated_at DATETIME
            );
        """)
        conn.commit()
        conn.close()

    def upsert_db(self, cursor, item, processed_path, thumb_path):
        tags = item.get("tags", {})
        attrs = tags.get("attributes", {})
        
        cursor.execute("""
            INSERT OR REPLACE INTO photos (
                uuid, filename, original_path, processed_path, thumb_path, 
                width, height, campus, season, category, keywords, meta, annotated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item['uuid'],
            item['filename'],
            item.get('original_path'),
            processed_path,
            thumb_path,
            item.get('width'),
            item.get('height'),
            attrs.get('campus'),
            attrs.get('season'),
            attrs.get('category'),
            json.dumps(tags.get('keywords', []), ensure_ascii=False),
            json.dumps(tags.get('meta', {}), ensure_ascii=False),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

    def stop(self):
        self._is_running = False
