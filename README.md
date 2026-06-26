# 🕷️ AI 全自动网页抓取与可视化分析看板

输入任意网页 URL，用大白话告诉 AI 你想提取什么数据，剩下的全自动完成。

## ✨ 功能特性

- **🌐 智能网页抓取** — 自动清洗 HTML，提取纯文本，支持任意网站
- **🤖 AI 结构化提取** — 用大模型将网页内容转成标准 JSON 表格数据
- **🔍 智能页面扫描** — 不确定该提取什么？AI 先帮你分析页面内容，给出建议
- **📊 自动可视化** — 自动识别数值列，生成柱状图/折线图
- **🧠 AI 数据分析报告** — 自动撰写 200 字数据洞察分析报告
- **🤖 robots.txt 合规检查** — 遵守爬虫协议，合法爬取
- **💾 一键导出** — 提取的数据可下载为 JSON 文件
- **🔄 智能容错** — 第一轮提取失败时自动用泛化策略重试

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

方式一：设置环境变量（推荐）

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY="sk-your-api-key"

# macOS / Linux
export DEEPSEEK_API_KEY="sk-your-api-key"
```

方式二：在应用侧边栏手动输入

### 3. 启动应用

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`

### 4. 使用

1. 在左侧边栏配置 API（默认使用 DeepSeek）
2. 输入要抓取的网页 URL
3. 用大白话描述你想提取什么数据
4. 点击「🚀 开始抓取并 AI 提取」
5. 查看数据表格、图表和 AI 分析报告

## 📦 项目结构

```
ai-web-scraper/
├── app.py                      # Streamlit 主入口
├── services/
│   ├── __init__.py
│   ├── scraper.py              # 网页抓取 + robots.txt 检查
│   ├── ai_extractor.py         # AI 结构化数据提取 + 智能扫描
│   └── analyzer.py             # 数值列识别 + AI 分析报告
├── utils/
│   └── __init__.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 🔧 兼容的大模型 API

| 平台 | API Base URL | 模型名称示例 |
|------|-------------|------------|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| SiliconFlow | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` |

> 只要支持 OpenAI 兼容格式的 API 都可以使用。

## 📝 使用示例

**场景一：抓取招聘信息**

- URL: `https://www.zhipin.com/web/geek/job?query=Python`
- 需求：`提取所有职位名称、公司名、薪资待遇和工作地点`

**场景二：抓取新闻列表**

- URL: `https://news.ycombinator.com`
- 需求：`提取所有新闻的标题、链接和得分`

**场景三：不确定该提取什么**

- 填好 URL，点「🔍 智能扫描」按钮
- AI 会分析页面内容，告诉你有哪些数据可以提取

## ⚠️ 注意事项

- 请遵守目标网站的 robots.txt 协议
- 不要对同一网站发起高频请求
- 提取结果的质量取决于网页结构和 AI 模型能力
- 动态渲染的网页（React/Vue）可能抓取不到内容

## 📄 License

MIT
