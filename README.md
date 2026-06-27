# AI 旅行规划师 (AI Travel Planner)

基于大模型的智能旅行规划助手，支持多用户、自带 API Key（BYOK），自动查询天气、搜索攻略、计算预算。

## 功能

- 🌤️ **实时天气** — 调用 wttr.in 获取全球任意城市天气
- 🔍 **攻略搜索** — 集成 Tavily 搜索引擎，获取最新酒店/门票/交通信息
- 🧮 **预算计算** — LLM 自动提取价格数据并计算总费用
- 💬 **流式输出** — 像 ChatGPT 一样逐字输出
- 🔐 **多用户 + 加密** — 每人独立账户，API Key 用 AES-256-GCM 加密存储
- 🔑 **BYOK 模式** — 用户自带 DeepSeek + Tavily Key，各自付费

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/yimingliu111/AI-travel-planner.git
cd AI-travel-planner

# 2. 创建虚拟环境
python -m venv .venv
source .venv/Scripts/activate   # Windows
# source .venv/bin/activate      # macOS / Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动 Web 界面
python AI-travel-agent.py
```

浏览器打开 `http://127.0.0.1:7860`，注册账户，填入你的 API Key 即可使用。

## 所需 API Key

| 服务 | 获取地址 | 用途 |
|------|---------|------|
| DeepSeek | https://platform.deepseek.com | 大语言模型 |
| Tavily | https://tavily.com | 搜索引擎 |

## 项目结构

```
├── AI-travel-agent.py    # Gradio Web 界面
├── FirstAgentTest.py     # Agent 核心逻辑（Function Calling + 多轮工具调用）
├── user_manager.py       # 用户管理 + AES-256 加密
├── test_tools.py         # 单元测试（12 个用例）
├── requirements.txt      # 依赖列表
└── .gitignore
```

## 运行测试

```bash
pytest test_tools.py -v
```

## 技术栈

- **LLM**: DeepSeek API (OpenAI 兼容 Function Calling)
- **搜索**: Tavily Search API
- **Web**: Gradio
- **加密**: AES-256-GCM (PyCryptodome)
- **测试**: pytest

## 架构

```
用户 → Gradio Web → Agent 核心
                      ├── Function Calling (tools 定义)
                      ├── 多轮工具调用循环 (最多 5 轮)
                      ├── 流式输出 (stream=True)
                      └── 用户隔离 (每人独立 history + API Key)
```

## License

MIT
