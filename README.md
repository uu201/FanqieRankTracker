# 🏆 番茄风向标 · Fanqie Rank Tracker

[![English](https://img.shields.io/badge/lang-English-blue)](README_EN.md)

> 📚 追踪**番茄小说男女频全部排行榜**（女频新书榜 / 女频阅读榜 / 男频新书榜 / 男频阅读榜），每日自动抓取榜单数据并结合 AI 生成趋势分析，部署为精美的在线看板。

---

## ✨ 功能概览

| 功能 | 说明 |
|------|------|
| 🕷️ 自动爬取 | 每日定时抓取男女频 4 个榜单各分类的 Top 30，分类自动从榜单页发现 |
| 🔀 多榜切换 | 前端两级 Tab（女频 / 男频 × 新书榜 / 阅读榜）一键切换，各榜数据独立 |
| 📊 趋势对比 | 自动对比相邻两天数据：新上榜 / 掉榜 / 排名变化 / 阅读量增长 |
| 🤖 AI 风向分析 | 接入 OpenAI 兼容 API，按分类生成市场趋势速评 |
| 🧭 类型风向标 | 独立趋势页聚合多日数据，按频道总结综合赛道、具体热门分类和高频题材；未配置 API 时自动规则兜底 |
| 🖥️ 精美看板 | 暗色编辑风格仪表盘，带打字机动画和瀑布流书籍卡片 |
| 📱 移动适配 | 完整的移动端适配，侧边栏抽屉式菜单 |
| 🔌 数据接口 | 按榜单 slug 生成静态 `lastest` JSON 接口，可按类型读取最新数据 |
| ⚡ 全自动化 | GitHub Actions + GitHub Pages，零服务器运维 |

---

## 🚀 食用指南

### 前置条件

- **Python 3.9+**
- **Git**
- 一个 GitHub 账号
- （可选）一个 OpenAI 兼容 API 的密钥，用于 AI 分析

### 第一步：Fork 仓库

点击 GitHub 页面右上角的 **Fork** 按钮，将项目 Fork 到你自己的账号下。

### 第二步：开启 GitHub Pages

1. 进入你 Fork 后的仓库 → **Settings** → **Pages**
2. Source 选择 **Deploy from a branch**
3. Branch 选择 `main`，目录选择 `/ (root)`
4. 点击 **Save**

稍等几分钟，你的看板就会上线：`https://<你的用户名>.github.io/FanqieRankTracker/`

### 第三步：配置 Secrets（可选，开启 AI 分析）

进入仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，添加以下三个 Secret：

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `API_BASE_URL` | OpenAI 兼容 API 的地址 | `https://api.openai.com/v1` |
| `API_KEY` | API 密钥 | `sk-xxxxxxxxxxxxx` |
| `API_MODEL` | 模型名称 | `gpt-4o-mini` |

> **💡 提示：** 任何 OpenAI 兼容接口均可使用（如 Moonshot / DeepSeek / 自建服务等）。如果不配置这三个 Secret，系统将自动使用基于规则的摘要替代 AI 分析，**不影响核心功能**。

### 第四步：手动触发首次运行

1. 进入仓库 → **Actions** → 左侧选择 **Daily Fanqie Rank Scraper**
2. 点击右上角 **Run workflow** → **Run workflow**
3. 等待 Workflow 运行完成（约 3–5 分钟）

运行成功后，`data/<榜单>/` 目录下会自动生成数据文件，打开 GitHub Pages 链接即可看到看板。

### 第五步：坐等自动更新

GitHub Actions 已配置为 **每天 UTC 18:17（北京时间次日 02:17）** 自动运行。Workflow 同时设置了 `TZ=Asia/Shanghai`，快照日期会按北京时间记录。之后无需任何手动操作，数据和看板会每天自动更新。

看板侧栏的**两级 Tab** 可在女频 / 男频、新书榜 / 阅读榜之间切换（无数据的榜单 Tab 会自动置灰）。右上角的 **风向标** 可进入 `trend.html`，先查看当下火热综合赛道、具体热门分类和高频题材，再按具体类型查看近 7 / 14 / 30 日或全部周期的趋势分析。全站热点会优先使用 AI 总结，未配置 API 或生成失败时使用规则统计文案兜底。

---

## 🔌 最新数据接口

构建脚本会按榜单 slug 同步生成 GitHub Pages 可直接访问的静态 JSON 接口。榜单 slug：`female-new`（女频新书榜）、`female-read`（女频阅读榜）、`male-new`（男频新书榜）、`male-read`（男频阅读榜）。

| 类型 | 路径 | 说明 |
|---|---|---|
| 榜单索引 | `api/boards.json` | 返回所有已有数据的榜单及其 slug、频道、最新日期 |
| 类型索引 | `api/<slug>/lastest.json` | 返回该榜所有可用类型及对应 URL |
| 全量数据 | `api/<slug>/lastest/all.json` | `type=all`，返回该榜全部分类、趋势和书籍 |
| 单类型数据 | `api/<slug>/lastest/<类型>.json` | 返回指定类型的数据，例如 `api/female-new/lastest/古风世情.json` |

示例：

```bash
curl https://<你的用户名>.github.io/FanqieRankTracker/api/boards.json
curl https://<你的用户名>.github.io/FanqieRankTracker/api/female-new/lastest/all.json
curl https://<你的用户名>.github.io/FanqieRankTracker/api/male-new/lastest/东方仙侠.json
```

---

## 🔧 本地开发

```bash
# 1. 克隆仓库
git clone https://github.com/<你的用户名>/FanqieRankTracker.git
cd FanqieRankTracker

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 4. 运行爬虫（每个分类抓取 Top 30）
python scrape_fanqie_ranks.py

# 5. 构建看板数据（可选，带 AI 分析需设置环境变量）
pip install openai
export API_BASE_URL="https://your-api-endpoint/v1"
export API_KEY="your-api-key"
export API_MODEL="your-model-name"
python scripts/build_latest.py

# 6. 本地预览前端
python -m http.server 8000
# 打开 http://localhost:8000
```

---

## 📁 项目结构

```
FanqieRankTracker/
├── .github/workflows/
│   └── scrape.yml              # GitHub Actions 自动化工作流
├── css/
│   └── style.css               # 暗色编辑风格主题样式
├── js/
│   ├── boards.js               # 多榜单共享工具（榜单加载 / ?board 同步 / 路径工厂）
│   ├── app.js                  # 看板渲染逻辑（瀑布流 + 打字机动画）
│   ├── trend.js                # 类型风向标趋势页逻辑
│   └── book.js                 # 作品详情页逻辑
├── scripts/
│   └── build_latest.py         # 趋势对比 + AI 分析构建脚本（遍历所有启用榜单）
├── data/
│   └── <slug>/                 # 每个榜单一个目录，如 female-new / male-new
│       ├── snapshots/
│       │   └── ranks_YYYYMMDD.json   # 每日原始快照
│       ├── trends/
│       │   └── YYYY-MM-DD.json       # 趋势归档
│       ├── latest_ranks.json   # 最新聚合数据（看板数据源）
│       ├── dates.json          # 可用日期索引
│       └── market_summary.json # 全站热点 AI/规则总结
├── api/
│   ├── boards.json             # 榜单总索引
│   └── <slug>/lastest/         # 各榜最新数据静态接口（all + 按类型拆分）
├── boards_config.py            # 榜单注册表（单一事实源：4 个榜 + 赛道分组 + 关键词）
├── index.html                  # 仪表盘入口页
├── trend.html                  # 类型风向标趋势分析页
├── book.html                   # 作品详情页
├── scrape_fanqie_ranks.py      # 番茄小说多榜单爬虫（Playwright）
├── discover_boards.py          # 榜单发现脚本（拿真实 /rank/ URL 用）
├── requirements.txt            # Python 依赖
└── README.md                   # 本文件
```

---

## ⚙️ 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                   GitHub Actions (每日 02:17)                │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Playwright   │───▶│  build_latest │───▶│  git commit  │  │
│  │  爬取榜单数据  │    │  趋势对比      │    │  自动提交     │  │
│  │              │    │  + AI 分析     │    │  到 main     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                             │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
                    GitHub Pages 自动部署
                    用户访问在线看板 🌐
```

---

## 📝 常见问题

<details>
<summary><b>Q: Workflow 运行失败怎么办？</b></summary>

检查 Actions 日志中的错误信息。常见原因：
- 番茄小说页面结构变更 → 需要更新爬虫选择器
- Playwright 安装超时 → 尝试重新运行

</details>

<details>
<summary><b>Q: 不配置 AI Secret 也能用吗？</b></summary>

可以！系统会自动 fallback 到基于规则的摘要（如"新增3本上榜；《XX》排名上升+5位"）。只是没有 AI 自然语言分析而已。

</details>

<details>
<summary><b>Q: 想增减榜单或换其他频道怎么办？</b></summary>

男女频 4 个榜单已内置启用。如需调整，编辑 `boards_config.py` 的 `BOARDS`：每个榜单配置 `slug` / `name` / `channel` / `init_url` / `rank_prefix` / `enabled` 即可。新榜单的真实 `/rank/` URL 可用 `discover_boards.py` 在可访问番茄的机器上抓取。

</details>

---

## 📜 License

MIT

---

<p align="center">
  <sub>Made with ☕ and 🤖 — 数据每日自动更新，无需手动维护</sub>
</p>
