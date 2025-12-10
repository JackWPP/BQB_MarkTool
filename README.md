# BUCT 图片智能打标系统 (Image Tagging System)

这是一个基于 Human-in-the-Loop (人机回环) 理念设计的图片打标系统。它结合了本地多模态大模型 (Local VLM) 的自动化能力和人工校验的精准性，提供从**预处理**、**任务分发**、**人工标注**到**归档入库**的全流程解决方案。

## 核心特性

*   **本地化智能预处理 (Local Auto-Labeling)**: 支持连接 OpenAI 兼容接口（如 LM Studio, vLLM），调用 Qwen-VL 等多模态模型自动识别图片季节、场景类别及关键物体，数据不出本地，安全高效。
*   **可视化预处理与分发**: 提供 GUI 界面，支持实时预览 AI 打标结果，并一键将大任务切分为**包含图片和数据的独立任务包 (.zip)**，便于团队协作。
*   **高效人工校验客户端**: 专为标注人员设计，支持标签芯片管理、智能路径解析、快捷键操作 (Ctrl+S 保存)，适配深色模式。
*   **自动化入库管理 (Smart Ingestion)**: 
    *   **智能合并**: 自动扫描文件夹中分散的任务包 (JSON + 图片)。
    *   **自动归档**: 根据标注的“季节”属性 (Spring/Summer/Autumn/Winter) 自动分类整理文件。
    *   **数据库同步**: 自动更新 SQLite 数据库，确保文件路径与元数据一致。

## 环境安装

1.  **克隆项目**
    ```bash
    git clone <repository_url>
    cd bqb_pic_project
    ```

2.  **安装依赖**
    建议使用 Python 3.10+ 环境。
    ```bash
    pip install -r requirements.txt
    ```

3.  **模型服务配置 (Local LLM)**
    本系统默认设计为连接本地模型服务。推荐使用 [LM Studio](https://lmstudio.ai/) 或其他支持 OpenAI 格式的推理后端。
    *   **启动服务**: 加载 `qwen-vl` 等视觉模型，开启本地 Server (默认端口 1234)。
    *   **修改配置**: 编辑 `config.py`：
        ```python
        # config.py
        API_BASE_URL = "http://localhost:1234/v1"  # 本地服务地址
        MODEL_NAME = "qwen3-vl-4b-instruct"       # 模型名称
        # DASHSCOPE_API_KEY = "..."               # (已弃用，如需云端可自行恢复)
        ```

## 使用流程

### 1. 数据预处理 (Pre-process)

运行预处理工具箱：
```bash
python preprocess_gui.py
```

*   **操作**:
    *   切换到 **"1. 预处理 (Pre-process)"** 标签页。
    *   选择包含原始图片的文件夹。
    *   点击“开始处理”，系统会调用本地 API 进行打标。
    *   处理结果会自动保存到 `pre_annotated.json`。

### 2. 任务分发 (Task Distribution)

当图片数量较多时，使用分发功能生成独立的任务包：

*   **操作**:
    *   在 `preprocess_gui.py` 中切换到 **"2. 任务分发 (Task Split)"** 标签页。
    *   选择上一步生成的 `pre_annotated.json`。
    *   设置每份任务的图片数量（例如 200 张）。
    *   勾选 **"同时生成 ZIP 压缩包"**。
    *   点击“开始切分”。
*   **结果**:
    *   系统会在 `_dist` 目录下生成多个任务文件夹（如 `xxx_task_001`）。
    *   每个文件夹内包含：**切分后的 JSON 文件** + **对应的图片文件**。
    *   生成的 `.zip` 包可直接分发给标注人员。

### 3. 人工校验 (Human Verification)

标注人员收到任务包后，解压并运行打标客户端：
```bash
python gui.py
```

*   **操作**:
    *   通过菜单 **"文件 -> 打开"** 加载任务文件夹中的 `task_data.json`。
    *   **图片预览**: 自动加载文件夹内的图片。
    *   **修改标签**: 点击预设按钮或输入文本修改 AI 预标注的结果。
    *   **保存**: 按 `Ctrl+S` 保存修改。

### 4. 归档入库 (Smart Ingestion)

当所有分散的标注任务回收后（得到多个包含已修改 JSON 的文件夹），使用入库工具统一整理：

```bash
python import_gui.py
```

*   **操作**:
    *   **数据源**: 选择包含所有回收任务包的**父文件夹**（系统会自动递归扫描所有 `.json`）。
    *   **媒体库位置**: 指定最终存放照片的根目录（如 `D:/BUCT_Library`）。
    *   勾选 **"按季节自动归档"**。
    *   点击 **"开始入库"**。
*   **执行动作**:
    *   程序会解析所有 JSON 数据。
    *   将图片移动/复制到媒体库下的 `Spring`, `Summer`, `Autumn`, `Winter` 文件夹中。
    *   图片重命名为 UUID 格式以避免冲突。
    *   将最终的元数据写入 `buct_gallery.db` SQLite 数据库。

## 文件结构

*   `preprocess_gui.py`: **预处理与分发工具** (GUI) - 集成 AI 打标与任务切分打包。
*   `gui.py`: **人工打标客户端** (GUI) - 用于校验和修正标签。
*   `import_gui.py`: **入库管理工具** (GUI) - 用于合并任务与归档文件。
*   `pre_process.py`: 核心预处理逻辑 (API 调用、图像处理)。
*   `ingestion_logic.py`: 核心入库逻辑 (文件整理、数据库操作)。
*   `config.py`: 系统配置文件 (API 地址、模型参数)。
*   `buct_gallery.db`: 最终存储元数据的 SQLite 数据库。

## 常见问题

*   **Q: 为什么预处理时报错连接失败？**
    *   A: 请确保本地 LM Studio 服务器已启动，并且 `config.py` 中的 `API_BASE_URL` 与服务器地址一致。

*   **Q: 入库时如何处理重复图片？**
    *   A: 入库工具使用 UUID 作为唯一标识。如果同一 UUID 的图片已存在，数据库记录会被更新，文件会根据策略覆盖或跳过。建议在分发前确保 UUID 不重复（预处理阶段会自动生成）。
