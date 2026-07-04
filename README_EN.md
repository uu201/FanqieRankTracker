# 🏆 Fanqie Rank Tracker

[![中文](https://img.shields.io/badge/lang-中文-red)](README.md)

> 📚 Tracks **all of Fanqie Novel's male & female channel rankings** (Female New / Female Reading / Male New / Male Reading), with daily automated scraping and AI-powered trend analysis, deployed as a premium online dashboard.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🕷️ Auto Scraping | Daily automated scraping of Top 30 per category across 4 boards; categories auto-discovered from each board page |
| 🔀 Multi-board Switch | Two-level tabs (Female / Male × New / Reading) for one-click switching, each board's data independent |
| 📊 Trend Analysis | Automatic day-over-day comparison: new entries / dropped / rank changes / readership growth |
| 🤖 AI Summary | OpenAI-compatible API integration for per-category market trend analysis |
| 🧭 Type Trend Page | Standalone trend page aggregating multi-day data, summarizing genre tracks, hot categories and frequent themes per channel; rule-based fallback when no API |
| 🖥️ Dashboard | Dark editorial-style dashboard with typewriter animation and waterfall book cards |
| 📱 Responsive | Full mobile support with slide-out sidebar menu |
| 🔌 Data API | Per-board (slug-namespaced) static `lastest` JSON endpoints, readable by type |
| ⚡ Fully Automated | GitHub Actions + GitHub Pages, zero server maintenance |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+**
- **Git**
- A GitHub account
- (Optional) An OpenAI-compatible API key for AI analysis

### Step 1: Fork the Repository

Click the **Fork** button on the top-right corner of the GitHub page to fork this repository to your own account.

### Step 2: Enable GitHub Pages

1. Go to your forked repo → **Settings** → **Pages**
2. Under Source, select **Deploy from a branch**
3. Select `main` branch and `/ (root)` directory
4. Click **Save**

After a few minutes, your dashboard will be live at: `https://<your-username>.github.io/FanqieRankTracker/`

### Step 3: Configure Secrets (Optional, for AI Analysis)

Go to repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**, and add the following three secrets:

| Secret Name | Description | Example |
|---|---|---|
| `API_BASE_URL` | OpenAI-compatible API endpoint | `https://api.openai.com/v1` |
| `API_KEY` | API key | `sk-xxxxxxxxxxxxx` |
| `API_MODEL` | Model name | `gpt-4o-mini` |

> **💡 Tip:** Any OpenAI-compatible API works (e.g., Moonshot / DeepSeek / self-hosted endpoints). If these secrets are not configured, the system will automatically fall back to rule-based summaries — **core functionality is unaffected**.

### Step 4: Trigger the First Run Manually

1. Go to repo → **Actions** → Select **Daily Fanqie Rank Scraper** on the left
2. Click **Run workflow** → **Run workflow** on the top-right
3. Wait for the workflow to complete (~3–5 minutes)

After a successful run, data files will be generated under `data/<board>/`. Open the GitHub Pages link to view your dashboard.

### Step 5: Sit Back and Relax

GitHub Actions is configured to run automatically at **UTC 18:17 (02:17 Beijing Time on the next calendar day)** every day. The workflow also sets `TZ=Asia/Shanghai`, so snapshot dates are recorded in Beijing time. No further manual action is needed — data and dashboard will auto-update daily.

Use the sidebar **two-level tabs** to switch between Female / Male and New / Reading boards (tabs with no data are auto-disabled). The **Trend** button (top-right) opens `trend.html` for genre tracks, hot categories and frequent themes over the last 7 / 14 / 30 days or all time.

---

## 🔌 Data API

The build script generates slug-namespaced static JSON endpoints on GitHub Pages. Board slugs: `female-new`, `female-read`, `male-new`, `male-read`.

| Type | Path | Description |
|---|---|---|
| Board index | `api/boards.json` | All boards that have data, with slug / channel / latest date |
| Type index | `api/<slug>/lastest.json` | All available types for the board and their URLs |
| Full data | `api/<slug>/lastest/all.json` | `type=all`, all categories, trends and books for the board |
| Single type | `api/<slug>/lastest/<type>.json` | Data for a specific type, e.g. `api/female-new/lastest/古风世情.json` |

```bash
curl https://<your-username>.github.io/FanqieRankTracker/api/boards.json
curl https://<your-username>.github.io/FanqieRankTracker/api/female-new/lastest/all.json
```

---

## 🔧 Local Development

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/FanqieRankTracker.git
cd FanqieRankTracker

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Run the scraper (Top 30 per category)
python scrape_fanqie_ranks.py

# 5. Build dashboard data (optional, set env vars for AI analysis)
pip install openai
export API_BASE_URL="https://your-api-endpoint/v1"
export API_KEY="your-api-key"
export API_MODEL="your-model-name"
python scripts/build_latest.py

# 6. Preview frontend locally
python -m http.server 8000
# Then open http://localhost:8000
```

---

## 📁 Project Structure

```
FanqieRankTracker/
├── .github/workflows/
│   └── scrape.yml              # GitHub Actions automation workflow
├── css/
│   └── style.css               # Dark editorial theme styles
├── js/
│   ├── boards.js               # Shared multi-board utils (board load / ?board sync / path factory)
│   ├── app.js                  # Dashboard rendering (waterfall + typewriter animation)
│   ├── trend.js                # Type trend page logic
│   └── book.js                 # Book detail page logic
├── scripts/
│   └── build_latest.py         # Trend comparison + AI analysis build script (all enabled boards)
├── data/
│   └── <slug>/                 # One directory per board, e.g. female-new / male-new
│       ├── snapshots/
│       │   └── ranks_YYYYMMDD.json   # Daily raw snapshots
│       ├── trends/
│       │   └── YYYY-MM-DD.json       # Trend archives
│       ├── latest_ranks.json   # Latest aggregated data (dashboard source)
│       ├── dates.json          # Available date index
│       └── market_summary.json # Market hot AI/rule summary
├── api/
│   ├── boards.json             # Board index
│   └── <slug>/lastest/         # Per-board latest static endpoints (all + per type)
├── boards_config.py            # Board registry (single source of truth: 4 boards + genres + keywords)
├── index.html                  # Dashboard entry page
├── trend.html                  # Type trend analysis page
├── book.html                   # Book detail page
├── scrape_fanqie_ranks.py      # Multi-board Fanqie Novel scraper (Playwright)
├── discover_boards.py          # Board discovery helper (to obtain real /rank/ URLs)
├── requirements.txt            # Python dependencies
└── README.md                   # Chinese documentation
```

---

## ⚙️ How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                GitHub Actions (Daily at 02:17 CST)          │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Playwright   │───▶│  build_latest │───▶│  git commit  │  │
│  │  Scrape rank  │    │  Trend diff   │    │  Auto push   │  │
│  │  data         │    │  + AI summary │    │  to main     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                             │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
                    GitHub Pages auto-deploy
                    User visits dashboard 🌐
```

---

## 📝 FAQ

<details>
<summary><b>Q: What if the workflow fails?</b></summary>

Check the error message in the Actions log. Common causes:
- Fanqie Novel page structure changed → Update the scraper selectors
- Playwright installation timeout → Try re-running the workflow

</details>

<details>
<summary><b>Q: Can I use it without configuring AI secrets?</b></summary>

Yes! The system will automatically fall back to rule-based summaries (e.g., "3 new entries; Book X rose +5 ranks"). You just won't have the AI natural language analysis.

</details>

<details>
<summary><b>Q: How do I add/remove boards or track other channels?</b></summary>

All 4 male & female boards are built in and enabled. To adjust, edit `BOARDS` in `boards_config.py`: each board has `slug` / `name` / `channel` / `init_url` / `rank_prefix` / `enabled`. Use `discover_boards.py` on a machine that can reach Fanqie to obtain a new board's real `/rank/` URL.

</details>

---

## 📜 License

MIT

---

<p align="center">
  <sub>Made with ☕ and 🤖 — Data updates daily via automation, zero manual maintenance required</sub>
</p>
