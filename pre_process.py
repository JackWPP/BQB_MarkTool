import os
import json
import uuid
import glob
import time
import signal
import sys
import threading
from datetime import datetime
from PIL import Image, ExifTags
import requests
import base64
import config

# Set API Key
# dashscope.api_key = config.DASHSCOPE_API_KEY

class ImagePreprocessor:
    def __init__(self, input_dir, output_file="pre_annotated.json"):
        self.input_dir = input_dir
        self.output_file = output_file
        self.data = []
        self.processed_files = set()
        self.load_existing_data()
        
        # Handle Ctrl+C gracefully (only if in main thread)
        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGINT, self.signal_handler)
            except ValueError:
                # Fallback if for some reason we are not in main thread context properly
                pass

    def signal_handler(self, sig, frame):
        print("\nProcess interrupted! Saving current progress...")
        self.save_data()
        sys.exit(0)

    def load_existing_data(self):
        """Load existing JSON to support resuming."""
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                    # Build a set of already processed filenames for quick lookup
                    # Using absolute path is safer if filenames are duplicates in different folders (though structure here assumes flat or we use path)
                    # Let's use the relative filename or original_path check
                    for item in self.data:
                        if "original_path" in item:
                            self.processed_files.add(os.path.abspath(item["original_path"]))
                print(f"Loaded {len(self.data)} existing records. Resuming...")
            except Exception as e:
                print(f"Warning: Failed to load existing data ({e}). Starting fresh.")
                # Backup corrupt file just in case
                if os.path.exists(self.output_file):
                    os.rename(self.output_file, self.output_file + f".bak.{int(time.time())}")

    def save_data(self):
        """Save current data to JSON."""
        try:
            # Write to temp file first then rename to avoid corruption on crash during write
            temp_file = self.output_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            if os.path.exists(self.output_file):
                os.remove(self.output_file)
            os.rename(temp_file, self.output_file)
            print(f"Progress saved to {self.output_file}")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to save data: {e}")

    def get_exif_date(self, img):
        """Extract date from EXIF data."""
        try:
            exif = img._getexif()
            if not exif:
                return None
            
            # 36867 is DateTimeOriginal, 306 is DateTime
            date_str = exif.get(36867) or exif.get(306)
            
            if date_str:
                # Format usually: 'YYYY:MM:DD HH:MM:SS'
                dt = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            # Silent fail for exif is fine, just return None
            pass
        return None

    def compress_image_for_api(self, image_path):
        """Resize image for VLM API to save tokens."""
        try:
            img = Image.open(image_path)
            # Calculate new size preserving aspect ratio
            max_size = config.RESIZE_TARGET_SIZE
            ratio = min(max_size / img.width, max_size / img.height)
            
            if ratio < 1:
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            temp_path = f"temp_{uuid.uuid4().hex}.jpg"
            img.save(temp_path, quality=85)
            return temp_path
        except Exception as e:
            print(f"Error compressing image: {e}")
            return image_path

    def call_vlm(self, image_path):
        """Call Local VLM to analyze the image."""
        # Compress first
        temp_path = self.compress_image_for_api(image_path)
        
        try:
            with open(temp_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            prompt = """请分析这张图片。
1. 判断季节 (Spring/Summer/Autumn/Winter)。
2. 判断场景类型 (Landscape/Portrait/Activity/Documentary)。
3. 提取画面中的关键物体 (不超过5个) 使用中文标签。
请以纯JSON格式返回，不要包含Markdown格式标记，格式如下:
{
    "season": "...",
    "category": "...",
    "objects": ["...", "..."]
}"""

            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": config.MODEL_NAME,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.7,
                "max_tokens": -1,
                "stream": False
            }

            response = requests.post(
                f"{config.API_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )

            # Clean up temp file
            if temp_path != image_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return content
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"VLM Call Exception: {e}")
            if temp_path != image_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return None

    def parse_vlm_response(self, response_text):
        """Parse the JSON response from VLM."""
        if not response_text:
            return {}
        
        try:
            # Strip markdown code blocks if present
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON. Raw: {response_text[:50]}...")
            return {"raw_description": response_text}

    def process_folder(self, progress_callback=None, log_callback=None, preview_callback=None, result_callback=None, check_pause=None):
        files = []
        # Recursive search is better usually, but let's stick to flat or one level
        # Using os.walk to be more robust
        for root, dirs, filenames in os.walk(self.input_dir):
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() in config.IMAGE_EXTENSIONS:
                    files.append(os.path.join(root, filename))
        
        total_files = len(files)
        msg = f"Found {total_files} images in '{self.input_dir}'."
        print(msg)
        if log_callback: log_callback(msg)
        
        # Filter out already processed
        files_to_process = [f for f in files if os.path.abspath(f) not in self.processed_files]
        skipped_count = total_files - len(files_to_process)
        if skipped_count > 0:
            msg = f"Skipping {skipped_count} already processed images."
            print(msg)
            if log_callback: log_callback(msg)

        for i, file_path in enumerate(files_to_process):
            # Check pause before starting new item
            if check_pause:
                check_pause()

            current_idx = skipped_count + i + 1
            msg = f"Processing [{current_idx}/{total_files}]: {os.path.basename(file_path)}"
            print(msg)
            if log_callback: log_callback(msg)
            if progress_callback: progress_callback(current_idx, total_files)
            if preview_callback: preview_callback(file_path)
            
            try:
                item = {
                    "uuid": str(uuid.uuid4()),
                    "filename": os.path.basename(file_path),
                    "original_path": os.path.abspath(file_path),
                    "processed_path": "", 
                    "thumb_path": "",
                    "width": 0,
                    "height": 0,
                    "tags": {
                        "attributes": {},
                        "keywords": [],
                        "meta": {}
                    }
                }

                # 1. Basic Image Info (Local)
                with Image.open(file_path) as img:
                    item["width"], item["height"] = img.size
                    date_taken = self.get_exif_date(img)
                    if date_taken:
                        item["tags"]["meta"]["date_taken"] = date_taken

                # 2. VLM Call (Remote)
                # Add retry logic for network stability
                retry_count = 0
                max_retries = 3
                vlm_raw = None
                
                while retry_count < max_retries:
                    if check_pause: check_pause() # Check pause during retries too
                    vlm_raw = self.call_vlm(file_path)
                    if vlm_raw:
                        break
                    print(f"  Retrying VLM call ({retry_count + 1}/{max_retries})...")
                    retry_count += 1
                    time.sleep(2) # Wait before retry
                
                if not vlm_raw:
                    msg = f"  Failed to get VLM response for {os.path.basename(file_path)}. Marking as manual needed."
                    print(msg)
                    if log_callback: log_callback(msg)
                    item["tags"]["meta"]["error"] = "VLM API Failed"
                else:
                    vlm_data = self.parse_vlm_response(vlm_raw)
                    # Map VLM data
                    if "season" in vlm_data:
                        item["tags"]["attributes"]["season"] = vlm_data["season"]
                    if "category" in vlm_data:
                        item["tags"]["attributes"]["category"] = vlm_data["category"]
                    if "objects" in vlm_data:
                        item["tags"]["keywords"] = vlm_data["objects"]
                    
                    if "raw_description" in vlm_data:
                        item["tags"]["meta"]["vlm_description"] = vlm_data["raw_description"]
                
                if result_callback: result_callback(item)

                self.data.append(item)
                self.processed_files.add(os.path.abspath(file_path))
                
                # Save frequently (every 1 image to be super safe, or every 5)
                # Since VLM is slow, saving every 1 image is negligible cost
                self.save_data()
                
                # Rate limit
                time.sleep(1)

            except Exception as e:
                msg = f"ERROR processing {file_path}: {e}"
                print(msg)
                if log_callback: log_callback(msg)
                # Continue to next file instead of crashing
                continue

        msg = "All processing complete."
        print(msg)
        if log_callback: log_callback(msg)

if __name__ == "__main__":
    input_folder = sys.argv[1] if len(sys.argv) > 1 else "."
    if not os.path.isdir(input_folder):
        print(f"Error: Directory '{input_folder}' not found.")
        sys.exit(1)
        
    processor = ImagePreprocessor(input_folder)
    processor.process_folder()
