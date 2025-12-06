# BUCT Tagger - 北化图库智能打标系统

## 简介
这是一个用于构建“人机回圈”图片数据生产管线的离线桌面工具。结合了 VLM (Qwen-VL) 的自动化预标注能力和人工校对的高精度特性。
本版本使用 **SQLite** 作为最终数据存储，便于迁移和备份。

## 目录结构
* `pre_process.py`: 预处理脚本 (Phase 1)
* `gui.py`: 标注客户端 (Phase 2)
* `import_to_sqlite.py`: 数据库入库脚本 (Phase 3)
* `config.py`: 配置文件
* `schema.sql`: SQLite 数据库建表语句
* `requirements.txt`: 依赖列表

## 快速开始

### 1. 环境安装
确保安装 Python 3.8+。

```bash
pip install -r requirements.txt
```

### 2. 配置
打开 `config.py`，确认 API Key 和其他配置。

### 3. 第一阶段：预处理 (Pre-process)
将待处理的图片放入文件夹 (例如 `raw_images`)。
```bash
python pre_process.py ./raw_images
```
生成 `pre_annotated.json`。

### 4. 第二阶段：人工打标 (Tagging)
启动 GUI 工具：
```bash
python gui.py pre_annotated.json
```
操作快捷键：
* `Ctrl+S`: 保存并下一张
* `Left`/`Right`: 切换图片

### 5. 第三阶段：入库 (Import to SQLite)
首先初始化数据库 (只需执行一次)：
```bash
python import_to_sqlite.py init
```
这会生成 `buct_gallery.db` 文件。

然后导入标注好的 JSON：
```bash
python import_to_sqlite.py import pre_annotated.json
```

### 数据库查询
你可以使用任意 SQLite 客户端（如 DB Browser for SQLite）查看 `buct_gallery.db`。
或在 Python 中查询：
```python
import sqlite3
conn = sqlite3.connect("buct_gallery.db")
cursor = conn.cursor()
cursor.execute("SELECT filename, keywords FROM photos WHERE season='秋'")
print(cursor.fetchall())
```
