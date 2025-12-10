import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Config
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:1234/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-vl-4b-instruct")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# Preprocessing Config
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
RESIZE_TARGET_SIZE = int(os.getenv("RESIZE_TARGET_SIZE", 1024))

# GUI Config
WINDOW_TITLE = "BUCT Tagger - 北化图库智能打标系统"
WINDOW_WIDTH = int(os.getenv("WINDOW_WIDTH", 1200))
WINDOW_HEIGHT = int(os.getenv("WINDOW_HEIGHT", 800))
