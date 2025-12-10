# 技术与开发文档 (Development Documentation)

本文档详细记录了 **BUCT 图片智能打标系统** 的架构设计、核心技术实现细节以及维护指南，旨在帮助开发者快速理解系统并进行二次开发。

## 1. 系统架构

系统整体采用 **Human-in-the-Loop (人机回环)** 架构，分为三个主要阶段：

1. **自动化预处理 (Auto-Labeling Pipeline)**:
   * **输入**: 原始图片文件夹。
   * **处理**: 提取 EXIF 信息 -> 调用 VLM (Qwen-VL) 进行语义理解 -> 生成初步标签。
   * **输出**: 包含元数据和预测标签的 JSON 文件 (`pre_annotated.json`)。
2. **人工校验与修正 (Human Verification)**:
   * **输入**: 预标注 JSON 文件。
   * **交互**: 标注人员通过 GUI 客户端 (`gui.py`) 审核并修正 AI 的错误，添加遗漏标签。
   * **输出**: 经过校验的 JSON 文件 (Clean Data)。
3. **持久化存储 (Storage)**:
   * **输入**: 校验后的 JSON。
   * **处理**: 数据清洗与格式转换。
   * **输出**: SQLite 数据库 (`images.db`)，便于后续检索和训练使用。

## 2. 核心模块详解

### 2.1 预处理模块 (`pre_process.py`)

* **职责**: 负责底层的图片遍历、API 调用和数据组装。
* **关键技术**:
  * **VLM 集成**: 使用 `dashscope` SDK 调用通义千问 VL 模型。
  * **断点续传**: 在启动时会读取已存在的 JSON 文件，建立 `processed_files` 集合。每次处理前检查该集合，跳过已完成的文件。
  * **鲁棒性设计**:
    * **重试机制**: 对 API 调用失败的情况，内置了 `max_retries=3` 的重试逻辑。
    * **信号处理**: 捕获 `SIGINT` (Ctrl+C)，确保程序被强行终止时也能保存当前进度（仅在主线程模式下生效）。
  * **回调机制**: 为了支持 GUI 显示进度，`process_folder` 函数接受 `progress_callback`, `log_callback`, `preview_callback` 等多个回调函数，实现了逻辑与界面的解耦。

### 2.2 预处理 GUI (`preprocess_gui.py`)

* **职责**: 提供可视化的预处理操作界面和任务分发工具。
* **关键技术**:
  * **多线程 (QThread)**: 使用 `WorkerThread` 将耗时的图片处理逻辑放入后台线程，防止主界面卡死。
  * **暂停/继续**: 利用 `QWaitCondition` 和 `QMutex` 实现了线程级的暂停功能。
  * **信号槽 (Signal/Slot)**: 线程通过 Signal 将日志、进度和预览图片路径发送回主线程更新 UI。
  * **深色模式**: 自定义 QSS (Qt Style Sheet) 实现了全全局深色主题适配。

### 2.3 打标客户端 (`gui.py`)

* **职责**: 供标注人员使用，强调交互效率。
* **关键技术**:
  * **智能路径解析 (`resolve_image_path`)**: 解决了多人协作时绝对路径失效的问题。系统会按顺序尝试：绝对路径 -> JSON同级目录 -> `images/` 子目录 -> 上级目录。如果都失败，会弹窗请求用户手动指定一次根目录。
  * **自适应图片控件 (`ScalableImageLabel`)**: 重写了 `resizeEvent`，实现图片随窗口大小变化而保持长宽比缩放。
  * **标签芯片 (`TagWidget`)**: 基于 `QWidget` 和 `QHBoxLayout` 组合封装的自定义控件，实现了标签的胶囊样式和内嵌删除按钮。

### 2.4 数据入库 (`import_to_sqlite.py`)

* **职责**: 将 JSON 数据导入关系型数据库。
* **关键技术**:
  * **JSON 序列化**: 由于 SQLite 不直接支持数组类型，我们将 `keywords` (list) 和 `meta` (dict) 序列化为 JSON 字符串存储在 `TEXT` 字段中。
  * **UUID 主键**: 使用图片的 UUID 作为唯一标识，防止重复导入。

## 3. 数据库设计 (`schema.sql`)

目前采用单表设计 `images`：

| 字段名            | 类型             | 说明                      |
| :---------------- | :--------------- | :------------------------ |
| `uuid`          | TEXT PRIMARY KEY | 图片唯一标识              |
| `filename`      | TEXT             | 文件名                    |
| `original_path` | TEXT             | 原始路径 (参考用)         |
| `season`        | TEXT             | 季节 (Spring/Summer...)   |
| `category`      | TEXT             | 场景类别                  |
| `keywords_json` | TEXT             | 关键词列表 (JSON Array)   |
| `meta_json`     | TEXT             | 元数据 (拍摄时间、EXIF等) |
| `created_at`    | DATETIME         | 入库时间                  |

## 4. 维护与扩展指南

### 如何添加新的预设标签？

1. 打开 `gui.py`。
2. 搜索 `presets = [...]` 列表。
3. 在列表中添加新的字符串即可，界面会自动渲染。

### 如何更换 VLM 模型？

1. 打开 `config.py`，修改 `MODEL_NAME`。
2. 打开 `pre_process.py`，找到 `call_vlm` 函数。
3. 如果新模型的 API 格式不同（例如从 DashScope 换成 OpenAI），需要重写 `call_vlm` 中的 `messages` 构造逻辑和 `response` 解析逻辑。

### 如何修改 UI 样式？

* **预处理工具**: 修改 `preprocess_gui.py` 中的 `apply_stylesheet` 方法。
* **打标客户端**: 修改 `gui.py` 中各个 Widget 的 `setStyleSheet` 调用。

## 5. 已知问题与待办

* [ ] **缩略图生成**: 目前虽然代码中有生成缩略图的逻辑，但在 SQLite 导入时并未充分利用，后续可考虑在数据库中直接存储 Base64 缩略图以便 Web 端展示。
* [ ] **多选标签**: 目前预设标签是单选/多选混合逻辑，未来可优化为更灵活的标签组管理。
