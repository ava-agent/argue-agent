# Argue Agent - 实时辩论助手

> **在线体验**: https://argue-agent.vercel.app

实时监听对话并自动验证对方论点，帮助你在实时沟通中掌握主动权。

## 功能

- **实时语音转录** - 支持中文语音实时转文字（需要 Deepgram API Key）
- **论点提取** - 自动识别对方发言中的可验证论点
- **事实核查** - 通过 DuckDuckGo 搜索验证论点真实性
- **反驳建议** - 生成针对性的反驳或确认建议
- **手机端访问** - 暗色主题，响应式界面，适配手机屏幕

## 架构概览

![Architecture](docs/images/architecture.png)

系统采用流水线架构，从语音/文本输入到最终判定结果，数据经过以下阶段：

1. **语音转文字** - Deepgram Nova-3 实时转录（可选）
2. **断句累积** - 将流式转录片段累积为完整语句
3. **论点提取** - GLM-4 LLM 提取可验证的事实性论点
4. **证据搜索** - DuckDuckGo 并发搜索验证
5. **判定综合** - GLM-4 LLM 综合证据给出 6 级判定

## 技术栈与数据模型

![Tech Stack & Data Models](docs/images/tech-stack.png)

| 层 | 技术 | 说明 |
|---|------|------|
| 后端框架 | FastAPI + Uvicorn | 异步 Web 服务，支持 WebSocket |
| AI/LLM | OpenAI SDK → GLM-4-Flash | 智谱大模型，兼容 OpenAI 接口 |
| 语音识别 | Deepgram Nova-3 | WebSocket 实时流式转录（可选） |
| 搜索引擎 | DuckDuckGo Search | 免费事实验证搜索 |
| 数据验证 | Pydantic v2 | 类型安全的数据模型 |
| 前端 | 原生 JS + CSS | 暗色主题，移动端适配 |

## 快速开始

### 1. 安装依赖

```bash
cd argue-agent
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 GLM API Key
# ARGUE_GLM_API_KEY=your-glm-api-key-here
```

### 3. 启动服务

```bash
python -m argue_agent
```

### 4. 访问应用

- **电脑浏览器**: http://localhost:8000
- **手机浏览器**: http://<你的局域网IP>:8000

### 5. 使用方式

- **文本模式**: 在输入框中输入对方说的话，点击"发送"
- **语音模式**: 点击麦克风按钮开始录音（需要 Deepgram API Key）

## API Key 获取

| API | 用途 | 获取方式 | 免费额度 |
|-----|------|----------|----------|
| 智谱 GLM | 论点提取、判定 | [智谱开放平台](https://open.bigmodel.cn/) | 新用户赠送 tokens |
| Deepgram | 语音转文字 | [Deepgram 官网](https://console.deepgram.com/) | $200 额度 |

## 项目结构

```
argue-agent/
├── pyproject.toml           # 项目配置
├── vercel.json              # Vercel 部署配置
├── requirements.txt         # Vercel Python 依赖
├── Dockerfile               # Docker 部署
├── .env.example             # 配置模板
├── api/
│   └── index.py             # Vercel Serverless API
├── public/
│   └── index.html           # 体验站前端（The Arbiter）
├── docs/images/             # 文档图片
├── src/argue_agent/
│   ├── __main__.py          # 启动入口
│   ├── config.py            # 配置管理（Pydantic Settings）
│   ├── server.py            # FastAPI 服务 + WebSocket
│   ├── analysis/
│   │   ├── models.py        # 数据模型（Claim, Verdict 等）
│   │   ├── extractor.py     # GLM 论点提取
│   │   └── accumulator.py   # 流式断句累积
│   ├── search/
│   │   └── ddg_search.py    # DuckDuckGo 并发搜索
│   ├── verdict/
│   │   └── synthesizer.py   # GLM 判定综合
│   ├── stt/
│   │   ├── base.py          # STT 抽象接口
│   │   └── deepgram_stt.py  # Deepgram WebSocket STT
│   ├── audio/
│   │   └── processor.py     # Float32→Int16 PCM 转换
│   └── web/static/
│       └── index.html       # 响应式暗色主题 UI
└── scripts/
    └── demo_text.py         # 文本模式 CLI 演示
```

## 文本模式测试

不需要语音功能，直接测试核心管道：

```bash
python scripts/demo_text.py
```

输入对方的发言，系统会自动提取论点并搜索验证。

## 部署

### Vercel + Supabase（在线体验站）

![Deployment Architecture](docs/images/deployment.png)

体验站采用 Vercel 静态前端 + Serverless Python API + Supabase PostgreSQL 的架构：

```bash
# 安装 Vercel CLI
npm i -g vercel

# 链接项目并部署
vercel link
vercel env add ARGUE_GLM_API_KEY production
vercel env add SUPABASE_URL production
vercel env add SUPABASE_ANON_KEY production
vercel deploy --prod
```

### Docker（本地/服务器）

```bash
docker build -t argue-agent .
docker run -d -p 8000:8000 \
  -e ARGUE_GLM_API_KEY=your-key \
  -e ARGUE_DEEPGRAM_API_KEY=your-key \
  argue-agent
```

## 延迟

从对方说完一句话到看到验证结果，约 3-6 秒：

| 阶段 | 耗时 | 说明 |
|------|------|------|
| 语音转录 | ~300ms | Deepgram 流式识别 |
| 论点提取 | ~1-2s | GLM-4 JSON 结构化输出 |
| 证据搜索 | ~1-2s | DuckDuckGo 并发查询 |
| 判定综合 | ~1-2s | GLM-4 综合分析 |

## 配置项

所有配置通过环境变量设置，前缀为 `ARGUE_`：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ARGUE_GLM_API_KEY` | （必填） | 智谱 GLM API Key |
| `ARGUE_DEEPGRAM_API_KEY` | （可选） | Deepgram 语音识别 Key |
| `ARGUE_GLM_MODEL` | `glm-4-flash` | GLM 模型名称 |
| `ARGUE_HOST` | `0.0.0.0` | 监听地址 |
| `ARGUE_PORT` | `8000` | 监听端口 |
| `ARGUE_EXTRACTION_CONFIDENCE_THRESHOLD` | `0.5` | 论点提取置信度阈值 |
| `ARGUE_SEARCH_MAX_QUERIES_PER_CLAIM` | `3` | 每个论点最大搜索查询数 |
| `ARGUE_SEARCH_MAX_RESULTS_PER_QUERY` | `5` | 每次搜索最大结果数 |
