# BUCT 图片智能打标系统 (Image Tagging System)

这是一个基于 Human-in-the-Loop (人机回环) 理念设计的图片打标系统。它结合了多模态大模型 (VLM) 的自动化能力和人工校验的精准性，旨在高效构建高质量的图片数据集。

## 核心特性

*   **智能预处理 (Auto-Labeling)**: 集成通义千问 VL (Qwen-VL) 模型，自动识别图片季节、场景类别及关键物体。
*   **可视化预处理工具**: 提供 GUI 界面，支持实时预览、处理进度展示、暂停/断点续传。
*   **任务分发 (Task Splitting)**: 内置任务切分工具，可将大规模 JSON 标注文件自动切分为多个小文件，便于团队分工协作。
*   **高效人工校验客户端 (Tagging Client)**:
    *   **标签芯片 (Tag Chips)**: 现代化标签管理，支持一键删除。
    *   **智能路径解析**: 自动解决跨设备协作时的图片路径丢失问题。
    *   **沉浸式体验**: 全中文界面，支持快捷键 (Ctrl+S 保存, 左右键切换)，深色模式适配。
*   **轻量级数据存储**: 使用 SQLite 数据库，单文件存储，易于备份和迁移。

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

3.  **配置 API Key**
    修改 `config.py` 文件，填入你的阿里云 DashScope API Key：
    ```python
    DASHSCOPE_API_KEY = "sk-xxxxxxxxxxxxxxxx"
    ```

## 使用流程

### 1. 数据预处理 (Pre-process)

运行预处理工具箱：
```bash
python preprocess_gui.py
```

*   **功能**:
    *   选择图片文件夹。
    *   点击“开始处理”，系统会自动调用 AI 进行打标。
    *   **实时预览**: 右侧窗口会实时显示当前正在处理的图片。
    *   **结果展示**: 实时显示 AI 返回的标签信息。
    *   支持**暂停**和**停止**，处理结果会自动保存到 `pre_annotated.json`。

### 2. 任务分发 (可选)

如果图片数量较多（如几千张），可以在 `preprocess_gui.py` 的 **"2. 任务分发"** 标签页中进行操作：
1.  选择生成的 `pre_annotated.json`。
2.  设置每份任务包含的图片数量（例如 200 张）。
3.  点击切分，生成 `_part1.json`, `_part2.json` 等文件，分发给不同人员。

### 3. 人工校验 (Human Verification)

标注人员运行打标客户端：
```bash
python gui.py
```

*   **操作**:
    *   通过菜单 **"文件 -> 打开"** 加载分配到的 JSON 文件。
    *   **图片预览**: 自动缩放适应窗口。
    *   **修改标签**:
        *   点击预设按钮快速添加/删除。
        *   在输入框输入新标签并回车。
        *   点击标签上的 `×` 号删除。
    *   **保存**: 点击“保存”或按 `Ctrl+S`。系统会自动生成缩略图并更新 JSON。

### 4. 数据入库 (Database Import)

所有校验完成后，将 JSON 文件导入 SQLite 数据库：

1.  初始化数据库（首次运行）：
    ```bash
    sqlite3 images.db < schema.sql
    ```
    *(注: `import_to_sqlite.py` 也会自动处理建表逻辑)*

2.  运行导入脚本：
    ```bash
    python import_to_sqlite.py
    ```
    *脚本会读取 `pre_annotated.json` (或修改代码指定其他文件) 并写入 `images.db`。*

## 文件结构

*   `preprocess_gui.py`: 预处理与任务分发工具 (GUI)。
*   `gui.py`: 人工打标校验客户端 (GUI)。
*   `pre_process.py`: 核心预处理逻辑 (包含 VLM 调用、EXIF 提取)。
*   `config.py`: 配置文件。
*   `schema.sql`: 数据库表结构定义。
*   `import_to_sqlite.py`: 数据入库脚本。
*   `requirements.txt`: 项目依赖列表。

## 常见问题

*   **Q: 图片加载失败？**
    *   A: `gui.py` 内置了智能路径解析。只要 JSON 文件和图片文件夹在相对路径上保持一致（例如在同一目录下，或图片在 `images/` 子目录），系统都能自动找到。如果找不到，系统会弹窗提示你手动指定一次图片根目录。

*   **Q: 预处理中断了怎么办？**
    *   A: 系统会实时保存进度。直接重新运行程序，它会跳过已处理的图片（基于文件名去重）。
