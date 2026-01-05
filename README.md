# Ari - 自主认知型AI实体

![Ari Terminal UI](https://via.placeholder.com/800x400/1e1e1e/ffffff?text=Ari+Terminal+UI)

Ari是一个旨在打破传统AI助手界限的自主认知型AI实体。其核心设计理念是通过深度任务分解、持久化认知、多功能工具集、项目具象化和能力自我扩展，实现与用户的高效、可靠、透明的协作。

## 🎯 核心特性

- **多Agent架构**: 主Agent + 动态子Agent，支持复杂任务分解
- **长期记忆**: 集成Mem0LongTermMemory，支持文件缓存
- **现代化TUI**: 基于Textual的分区化终端界面
- **完美中文支持**: 输入、删除、光标控制完全适配中文
- **流式输出**: 实时渲染Agent思考过程和结果
- **任务状态追踪**: 可视化任务执行进度

## 🖥️ 终端界面设计

Ari的终端界面采用深色主题美学设计，分为五个主要区域：

### 1. 思考过程区 (左上)
- 显示Ari的内部推理链
- 实时更新当前思考状态
- 黄色💡图标标识

### 2. 任务规划与状态区 (中上)  
- 结构化表格展示任务步骤
- 状态图标：⏳(待处理)、🔄(进行中)、✅(完成)、❌(错误)
- 动态颜色指示执行状态

### 3. 结果输出区 (右部)
- 主内容显示区域
- 支持Markdown渲染
- 代码语法高亮
- 流式自动滚动

### 4. 系统消息区 (底部上方)
- 非阻塞系统通知
- 时间戳和级别标识
- 最多保留10条消息

### 5. 用户输入区 (底部)
- 三行高度输入框
- 完美中文字符支持
- Enter发送，Ctrl+C中断

## 🎨 配色方案

- **背景**: 深灰色 (`$surface`)
- **主色调**: 蓝色系 (`$primary`)  
- **成功**: 绿色 (`$success`)
- **警告**: 黄色 (`$warning`)
- **错误**: 红色 (`$error`)
- **文本**: 白色/浅灰色 (`$text`)

## ⚡ 快捷键

- `Enter`: 发送消息
- `Ctrl+C`: 中断当前操作
- `Ctrl+Q`: 退出应用
- 方向键: 光标移动
- `Home/End`: 行首/行尾

## 📦 项目结构

```
Ari/
├── core/              # Agent核心模块
├── ui/                # 终端UI实现
├── skill/             # 技能集
├── utils.py           # 助手函数
├── tools/             # 扩展工具目录
├── config/            # 配置加载
├── memory/            # 记忆数据目录
├── tests/             # 测试文件目录
├── .env               # 配置文件
├── main.py            # 入口文件
├── pyproject.toml     # 项目依赖
└── README.md          # 项目文档
```

## 🚀 快速开始

1. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入您的API密钥
   ```

2. **安装依赖**
   ```bash
   uv sync
   ```

3. **启动Ari**
   ```bash
   python main.py
   ```

## 🔧 配置说明

所有配置项都在 `.env` 文件中，包含中文注释：

```env
# ======================
# Ari 项目配置文件
# ======================

# 项目基本信息
PROJECT_NAME=Ari

# LLM 配置
LLM_API_KEY=your_llm_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o

# 嵌入模型配置
EMBEDDING_API_KEY=your_embedding_api_key_here
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# 记忆相关配置
MEMORY_PATH=./memory/vector_store
EMBEDDING_CACHE_DIR=./memory/embedding_cache
```

## 🤝 协作模式

Ari支持两种协作模式：

### 1. 聊天模式
- 简单对话、问答
- 直接由主Agent处理

### 2. 复杂任务模式  
- 任务分解为多个子任务
- 动态创建专家子Agent
- 并行/串行执行协调
- 结果整合和验证

## 📜 技术栈

- **Python**: 3.13+
- **AgentScope**: 1.0
- **Textual**: 7.0+ (TUI框架)
- **Mem0**: 长期记忆
- **uv**: 虚拟环境管理

## 🎯 设计理念

Ari的设计遵循以下原则：

1. **用户友好**: 直观的界面，完美的中文支持
2. **透明可信**: 展示完整的思考过程和任务状态  
3. **高效可靠**: 智能任务分解，错误处理机制
4. **可扩展**: 模块化设计，易于添加新功能
5. **美观优雅**: 现代化的深色主题UI设计

---

> **Ari - 让AI协作变得简单、智能、美丽** ✨