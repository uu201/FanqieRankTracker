"""
构建 latest_ranks.json（多榜单版）：
对 boards_config 中每个启用的榜单分别：
1. 加载该榜单最近两天的快照（data/<slug>/snapshots/ranks_*.json）
2. 按分类对比趋势（新上榜/掉榜/排名变化/阅读量变化）
3. 可选调用 OpenAI 兼容 API 生成 AI 总结
4. 输出 data/<slug>/{latest_ranks,market_summary,dates}.json
   + data/<slug>/trends/YYYY-MM-DD.json
   + api/<slug>/lastest/{all,<type>,index}.json
最后在 api/boards.json 汇总全部榜单索引。
"""
import os
import re
import json
import glob
import sys
import argparse
from urllib.parse import quote

# 允许从仓库根目录导入 boards_config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from boards_config import enabled_boards, board_public_meta  # noqa: E402


def parse_reads(reads_str: str) -> float:
    """将 '15.2万' 这样的字符串转为数值，用于比较。"""
    if not reads_str or reads_str == "未知":
        return 0
    s = reads_str.strip().replace(",", "")
    try:
        if "万" in s:
            return float(s.replace("万", "")) * 10000
        return float(s)
    except ValueError:
        return 0


def format_reads_change(diff: float) -> str:
    """格式化阅读量变化。"""
    if abs(diff) >= 10000:
        return f"{'+' if diff > 0 else ''}{diff / 10000:.1f}万"
    return f"{'+' if diff > 0 else ''}{int(diff)}"


def load_snapshot(path: str) -> dict:
    """加载一个 JSON 快照文件。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_categories(today_cats: list, prev_cats: list) -> dict:
    """
    对比两天的分类数据，返回每个分类的趋势信息。
    key = 分类名, value = trend dict
    """
    # 构建 prev 的索引: cat_name -> {url: (rank, reads_str, title)}
    prev_index = {}
    for cat in prev_cats:
        url_map = {}
        for i, book in enumerate(cat.get("books", [])):
            url_map[book["url"]] = {
                "rank": i + 1,
                "reads": book.get("reads", "未知"),
                "title": book.get("title", "未知"),
                "intro": book.get("intro", "暂无简介"),
            }
        prev_index[cat["name"]] = url_map

    trends = {}
    for cat in today_cats:
        cat_name = cat["name"]
        prev_urls = prev_index.get(cat_name, {})
        today_books = cat.get("books", [])

        new_books = []
        dropped_books = []
        risers = []
        fallers = []
        reads_growth = []

        today_urls = set()
        for i, book in enumerate(today_books):
            url = book["url"]
            today_urls.add(url)
            today_rank = i + 1
            title = book.get("title", "未知")

            if url in prev_urls:
                prev_info = prev_urls[url]
                prev_rank = prev_info["rank"]
                rank_change = prev_rank - today_rank  # 正数=上升

                if rank_change > 0:
                    risers.append({"title": title, "change": f"+{rank_change}"})
                elif rank_change < 0:
                    fallers.append({"title": title, "change": str(rank_change)})

                # 阅读量变化
                today_reads = parse_reads(book.get("reads", ""))
                prev_reads = parse_reads(prev_info["reads"])
                if today_reads > 0 and prev_reads > 0:
                    diff = today_reads - prev_reads
                    if diff != 0:
                        reads_growth.append(
                            {"title": title, "growth": format_reads_change(diff)}
                        )
            else:
                new_books.append(title)

        # 掉出榜单的书（含简介以便 AI 分析题材）
        for url, info in prev_urls.items():
            if url not in today_urls:
                dropped_books.append({
                    "title": info["title"],
                    "intro": info.get("intro", "暂无简介")[:100],
                })

        # 排序：涨幅最大的在前
        risers.sort(key=lambda x: int(x["change"].replace("+", "")), reverse=True)
        fallers.sort(key=lambda x: int(x["change"]))
        reads_growth.sort(
            key=lambda x: parse_reads(x["growth"].replace("+", "")), reverse=True
        )

        trends[cat_name] = {
            "new_count": len(new_books),
            "dropped_count": len(dropped_books),
            "new_books": new_books[:5],
            "dropped_books": dropped_books[:5],
            "top_risers": risers[:3],
            "top_fallers": fallers[:3],
            "reads_growth": reads_growth[:3],
            "summary": "",  # AI 总结，由 generate_ai_summaries 填充
        }

    return trends


def generate_trend_summary_text(cat_name: str, trend: dict) -> str:
    """生成基于规则的简短趋势文本（作为 AI 总结不可用时的 fallback）。"""
    parts = []
    if trend["new_count"] > 0:
        parts.append(f"新增{trend['new_count']}本上榜")
    if trend["dropped_count"] > 0:
        dropped_titles = [d["title"] if isinstance(d, dict) else d
                          for d in trend.get("dropped_books", [])]
        if dropped_titles:
            parts.append(f"{trend['dropped_count']}本掉出（{'、'.join('《' + t + '》' for t in dropped_titles)}）")
        else:
            parts.append(f"{trend['dropped_count']}本掉出")
    if trend["top_risers"]:
        r = trend["top_risers"][0]
        parts.append(f"《{r['title']}》排名上升{r['change']}位")
    if trend["reads_growth"]:
        g = trend["reads_growth"][0]
        parts.append(f"《{g['title']}》阅读量{g['growth']}")
    if not parts:
        parts.append("榜单无明显变动")
    return "；".join(parts) + "。"


def build_ai_prompt(cat_name: str, cat: dict, trend: dict) -> str:
    """构建 AI 总结的 prompt（统一模板）。"""
    # 当前榜单书籍
    intros = []
    for i, book in enumerate(cat.get("books", [])[:20]):
        intros.append(
            f"{i+1}. 《{book['title']}》- {book.get('author', '未知')}\n"
            f"   在读：{book.get('reads', '未知')}\n"
            f"   简介：{book.get('intro', '无')[:200]}"
        )
    intros_text = "\n".join(intros)

    # 新上榜书籍
    new_books = trend.get("new_books", [])
    new_text = "、".join(f"《{t}》" for t in new_books) if new_books else "无"

    # 掉出榜单书籍（含简介）
    dropped = trend.get("dropped_books", [])
    if dropped:
        dropped_lines = []
        for d in dropped:
            if isinstance(d, dict):
                dropped_lines.append(f"《{d['title']}》（{d.get('intro', '暂无简介')[:50]}）")
            else:
                dropped_lines.append(f"《{d}》")
        dropped_text = "、".join(dropped_lines)
    else:
        dropped_text = "无"

    # 排名变动
    risers = trend.get("top_risers", [])
    risers_text = "、".join(f"《{r['title']}》{r['change']}" for r in risers) if risers else "无"
    fallers = trend.get("top_fallers", [])
    fallers_text = "、".join(f"《{f['title']}》{f['change']}" for f in fallers) if fallers else "无"

    return f"""你是一位网文行业分析师。请根据以下数据，为番茄小说「{cat_name}」分类新书榜生成结构化分析。

## 当前榜单 Top 20
{intros_text}

## 榜单变动
- 新上榜：{new_text}
- 掉出榜单：{dropped_text}
- 排名上升：{risers_text}
- 排名下降：{fallers_text}

## 输出要求（请严格按以下格式输出，使用 Markdown）

**🔥 题材趋势**
用1-2句话总结当前分类的主流题材和高频元素（如穿书/重生/系统/种田等），点明哪些设定扎堆出现。

**📖 读者偏好**
用1句话概括读者口味方向（甜宠/虐/爽/日常/暗黑等），以及金手指类型偏好。

**🆕 新上榜作品**
列出新上榜书名，每本用一句话点评其题材亮点或差异化卖点。

**📉 掉出榜单**
列出掉出书名及其题材方向，简要分析可能掉出的原因（如题材饱和、同质化等）。

**💡 值得关注**
挑1-2本有差异化潜力的作品，说明理由。

要求：每个板块2-3句话，总字数250字以内。语言简洁专业，像行业快报。"""


BATCH_SIZE = 6  # 每批合并的分类数，减少免费 API 的请求次数
API_REQUEST_INTERVAL_SECONDS = max(
    0.0, float(os.environ.get("API_REQUEST_INTERVAL_SECONDS", "15"))
)

MARKET_PERIODS = [("7", 7), ("14", 14), ("30", 30), ("all", None)]


_last_api_request_at = 0.0


def _wait_for_api_slot() -> None:
    """限制连续请求速度，避免免费端点触发 RPM 限制。"""
    global _last_api_request_at
    import time

    elapsed = time.monotonic() - _last_api_request_at
    if _last_api_request_at and elapsed < API_REQUEST_INTERVAL_SECONDS:
        time.sleep(API_REQUEST_INTERVAL_SECONDS - elapsed)
    _last_api_request_at = time.monotonic()


def _is_rate_limit_error(error: Exception) -> bool:
    """识别 OpenAI SDK 和 OpenCode 返回的 429 限流错误。"""
    status_code = getattr(error, "status_code", None)
    response = getattr(error, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    return status_code == 429 or "FreeUsageLimitError" in str(error)


def _retry_after_seconds(error: Exception, default: float = 60.0) -> float:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) if response is not None else {}
    value = headers.get("retry-after") or headers.get("Retry-After")
    try:
        return max(1.0, min(float(value), 900.0)) if value else default
    except (TypeError, ValueError):
        return default

# 注意：赛道分组(genre_groups)与题材关键词(keywords)已移至 boards_config.py，
# 按榜单传入下方相关函数，不再使用模块级常量。


def build_batch_ai_prompt(batch: list) -> str:
    """构建批量 AI 总结的 prompt。

    batch: list of (cat_name, cat_data, trend_data) tuples
    """
    sections = []
    for cat_name, cat, trend in batch:
        intros = []
        for i, book in enumerate(cat.get("books", [])[:20]):
            intros.append(
                f"{i+1}. 《{book['title']}》- {book.get('author', '未知')}\n"
                f"   在读：{book.get('reads', '未知')}\n"
                f"   简介：{book.get('intro', '无')[:200]}"
            )
        intros_text = "\n".join(intros)

        new_books = trend.get("new_books", [])
        new_text = "、".join(f"《{t}》" for t in new_books) if new_books else "无"

        dropped = trend.get("dropped_books", [])
        if dropped:
            dropped_lines = []
            for d in dropped:
                if isinstance(d, dict):
                    dropped_lines.append(
                        f"《{d['title']}》（{d.get('intro', '暂无简介')[:50]}）"
                    )
                else:
                    dropped_lines.append(f"《{d}》")
            dropped_text = "、".join(dropped_lines)
        else:
            dropped_text = "无"

        risers = trend.get("top_risers", [])
        risers_text = (
            "、".join(f"《{r['title']}》{r['change']}" for r in risers)
            if risers else "无"
        )
        fallers = trend.get("top_fallers", [])
        fallers_text = (
            "、".join(f"《{f['title']}》{f['change']}" for f in fallers)
            if fallers else "无"
        )

        sections.append(
            f"### 分类：{cat_name}\n\n"
            f"**当前榜单 Top 20：**\n{intros_text}\n\n"
            f"**榜单变动：**\n"
            f"- 新上榜：{new_text}\n"
            f"- 掉出榜单：{dropped_text}\n"
            f"- 排名上升：{risers_text}\n"
            f"- 排名下降：{fallers_text}"
        )

    all_sections = "\n\n---\n\n".join(sections)
    cat_names = [b[0] for b in batch]

    output_examples = "\n\n".join(
        f"===BEGIN: {name}===\n"
        f"**🔥 题材趋势** ...\n"
        f"**📖 读者偏好** ...\n"
        f"**🆕 新上榜作品** ...\n"
        f"**📉 掉出榜单** ...\n"
        f"**💡 值得关注** ...\n"
        f"===END: {name}==="
        for name in cat_names
    )

    return (
        f"你是一位网文行业分析师。请根据以下数据，"
        f"为番茄小说的多个分类新书榜分别生成结构化分析。\n\n"
        f"{all_sections}\n\n"
        f"## 输出要求\n\n"
        f"请严格按照以下格式，为每个分类分别输出分析。"
        f"每个分类的分析必须包裹在对应的标记中：\n\n"
        f"{output_examples}\n\n"
        f"每个板块2-3句话，每个分类总字数250字以内。"
        f"语言简洁专业，像行业快报。\n"
        f"注意：必须为每个分类都输出完整分析，不可省略任何分类。"
    )


def parse_batch_response(response_text: str, cat_names: list) -> dict:
    """解析批量 AI 响应，返回 {cat_name: summary} 字典。"""
    results = {}
    for name in cat_names:
        pattern = rf"===BEGIN:\s*{re.escape(name)}\s*===(.*?)===END:\s*{re.escape(name)}\s*==="
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            summary = match.group(1).strip()
            if summary:
                results[name] = summary
    return results


def _save_trends_incremental(trend_path: str, date: str,
                             prev_date: str, trends: dict):
    """增量保存趋势数据到文件（每批成功后立即写入）。"""
    if not trend_path:
        return
    trend_output = {
        "date": date,
        "prev_date": prev_date,
        "trends": trends,
    }
    with open(trend_path, "w", encoding="utf-8") as f:
        json.dump(trend_output, f, ensure_ascii=False, indent=2)


def api_type_filename(type_name: str) -> str:
    """将类型名转成适合作为静态 JSON 文件名的名称。"""
    name = (type_name or "").strip()
    name = re.sub(r"[\\/]+", "_", name)
    name = re.sub(r"[^\w\u4e00-\u9fff\s-]", "_", name)
    name = re.sub(r"\s+", "_", name).strip("._")
    return name or "unknown"


def write_json(path: str, payload: dict):
    """统一写 JSON，确保中文可读。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_lastest_api(output: dict, base_dir: str, slug: str):
    """生成静态 lastest 数据接口（按榜单 slug 命名空间）。

    - api/<slug>/lastest/all.json：该榜单全量数据
    - api/<slug>/lastest/<type>.json：单个类型数据
    - api/<slug>/lastest.json / index.json：类型索引
    """
    api_root = os.path.join(base_dir, "api", slug)
    lastest_dir = os.path.join(api_root, "lastest")
    os.makedirs(lastest_dir, exist_ok=True)
    for old_path in glob.glob(os.path.join(lastest_dir, "*.json")):
        os.remove(old_path)

    date = output.get("date", "")
    prev_date = output.get("prev_date", "")
    categories = output.get("categories", [])

    all_payload = {
        "type": "all",
        "date": date,
        "prev_date": prev_date,
        "categories": categories,
    }
    write_json(os.path.join(lastest_dir, "all.json"), all_payload)

    types = [{
        "type": "all",
        "url": f"api/{slug}/lastest/all.json",
        "category_count": len(categories),
        "book_count": sum(len(cat.get("books", [])) for cat in categories),
    }]

    used_filenames = {"all"}
    for cat in categories:
        type_name = cat.get("name", "")
        filename = api_type_filename(type_name)
        base_filename = filename
        suffix = 2
        while filename in used_filenames:
            filename = f"{base_filename}_{suffix}"
            suffix += 1
        used_filenames.add(filename)

        payload = {
            "type": type_name,
            "date": date,
            "prev_date": prev_date,
            "category": cat,
            "categories": [cat],
        }
        write_json(os.path.join(lastest_dir, f"{filename}.json"), payload)

        url = f"api/{slug}/lastest/{quote(filename)}.json"
        types.append({
            "type": type_name,
            "url": url,
            "book_count": len(cat.get("books", [])),
        })

    index_payload = {
        "slug": slug,
        "date": date,
        "prev_date": prev_date,
        "types": types,
    }
    write_json(os.path.join(lastest_dir, "index.json"), index_payload)
    write_json(os.path.join(api_root, "lastest.json"), index_payload)

    return lastest_dir


def parse_change(change: str) -> int:
    """解析 '+3' / '-2' 这类排名变化。"""
    try:
        return int(str(change or "0").replace("+", ""))
    except ValueError:
        return 0


def load_trend_rows(trends_dir: str) -> list:
    """加载全部趋势归档，按日期升序排列。"""
    rows = []
    for path in sorted(glob.glob(os.path.join(trends_dir, "*.json"))):
        try:
            data = load_snapshot(path)
            rows.append({
                "date": data.get("date", ""),
                "prev_date": data.get("prev_date", ""),
                "trends": data.get("trends", {}),
            })
        except Exception as e:
            print(f"  ⚠️  跳过趋势文件 {path}: {e}")
    return sorted([r for r in rows if r["date"]], key=lambda x: x["date"])


def summarize_market_rows(rows: list) -> dict:
    """汇总某个分类在一组趋势行中的动能指标。"""
    totals = {
        "new_count": 0,
        "dropped_count": 0,
        "riser_count": 0,
        "faller_count": 0,
        "read_count": 0,
        "read_growth_total": 0,
        "active_days": 0,
    }
    for row in rows:
        trend = row.get("trend") or {}
        riser_count = len(trend.get("top_risers", []))
        faller_count = len(trend.get("top_fallers", []))
        read_count = len(trend.get("reads_growth", []))
        read_growth_total = sum(
            parse_reads(item.get("growth", ""))
            for item in trend.get("reads_growth", [])
        )
        totals["new_count"] += int(trend.get("new_count", 0) or 0)
        totals["dropped_count"] += int(trend.get("dropped_count", 0) or 0)
        totals["riser_count"] += riser_count
        totals["faller_count"] += faller_count
        totals["read_count"] += read_count
        totals["read_growth_total"] += read_growth_total
        if (
            trend.get("new_count", 0) or trend.get("dropped_count", 0)
            or riser_count or faller_count or read_count
        ):
            totals["active_days"] += 1
    return totals


def market_score(totals: dict) -> int:
    """计算全站热点分：综合赛道和具体分类只看新增在读量。"""
    return round(totals["read_growth_total"])


def format_market_reads(value: float) -> str:
    """格式化市场层面的新增在读量。"""
    if abs(value) >= 10000:
        return f"{value / 10000:.1f}万"
    return str(round(value))


def collect_market_hot_types(categories: list, rows_window: list) -> list:
    """统计具体分类热度。"""
    result = []
    for name in categories:
        rows = [
            {"trend": row.get("trends", {}).get(name)}
            for row in rows_window
            if row.get("trends", {}).get(name)
        ]
        totals = summarize_market_rows(rows)
        score = market_score(totals)
        if score <= 0:
            continue
        result.append({
            "name": name,
            "score": score,
            "new_count": totals["new_count"],
            "dropped_count": totals["dropped_count"],
            "read_count": totals["read_count"],
            "read_growth_total": totals["read_growth_total"],
            "active_days": totals["active_days"],
        })
    return sorted(
        result,
        key=lambda x: (x["read_growth_total"], x["read_count"]),
        reverse=True
    )


def collect_market_hot_genres(categories: list, hot_types: list,
                              genre_groups: list) -> list:
    """按综合赛道聚合具体分类热度。genre_groups 为空时返回空列表（不做赛道聚合）。"""
    if not genre_groups:
        return []
    type_map = {item["name"]: item for item in hot_types}
    genres = []
    for group in genre_groups:
        matched = []
        for name in group["categories"]:
            if name not in categories:
                continue
            matched.append(type_map.get(name, {
                "name": name,
                "score": 0,
                "new_count": 0,
                "dropped_count": 0,
                "read_count": 0,
                "read_growth_total": 0,
                "active_days": 0,
            }))
        if not matched:
            continue
        read_growth_total = sum(item["read_growth_total"] for item in matched)
        if read_growth_total <= 0:
            continue
        lead = sorted(
            matched,
            key=lambda x: (x["read_growth_total"], x["read_count"]),
            reverse=True
        )[0]
        genres.append({
            "name": group["name"],
            "score": round(read_growth_total),
            "new_count": sum(item["new_count"] for item in matched),
            "dropped_count": sum(item["dropped_count"] for item in matched),
            "read_count": sum(item["read_count"] for item in matched),
            "read_growth_total": read_growth_total,
            "active_days": sum(item["active_days"] for item in matched),
            "lead_category": lead["name"],
            "categories": [item["name"] for item in matched],
        })
    return sorted(
        genres,
        key=lambda x: (x["read_growth_total"], x["read_count"]),
        reverse=True
    )


def add_theme_hits(score_map: dict, text: str, category_name: str,
                   weight: int, keywords: list):
    """给命中的题材关键词加权。"""
    source = str(text or "")
    if not source:
        return
    for keyword in keywords:
        if keyword not in source:
            continue
        item = score_map[keyword]
        item["count"] += weight
        item["categories"].add(category_name)


def collect_market_hot_themes(output: dict, rows_window: list,
                              categories: list, keywords: list) -> list:
    """只统计近期新上榜作品中的高频题材词。"""
    score_map = {
        name: {"name": name, "count": 0, "categories": set()}
        for name in keywords
    }
    latest_book_map = {}
    for cat in output.get("categories", []):
        for book in cat.get("books", []):
            title = book.get("title", "")
            if title:
                latest_book_map[title] = book

    for row in rows_window:
        for cat_name in categories:
            trend = row.get("trends", {}).get(cat_name)
            if not trend:
                continue
            for title in trend.get("new_books", []):
                book = latest_book_map.get(title, {})
                add_theme_hits(
                    score_map,
                    f"{title} {book.get('intro', '')}",
                    cat_name,
                    1,
                    keywords,
                )

    themes = []
    for item in score_map.values():
        if item["count"] <= 0:
            continue
        themes.append({
            "name": item["name"],
            "count": item["count"],
            "category_count": len(item["categories"]),
        })
    return sorted(
        themes,
        key=lambda x: (x["count"], x["category_count"]),
        reverse=True
    )


def build_rule_market_summary(period_label: str, hot_genres: list,
                              hot_types: list, hot_themes: list) -> str:
    """基于统计结果生成全站热点兜底文案。"""
    top_genres = "、".join(item["name"] for item in hot_genres[:2])
    top_types = "、".join(item["name"] for item in hot_types[:3])
    top_themes = "、".join(item["name"] for item in hot_themes[:6])
    if not top_genres and not top_types:
        return f"{period_label}暂无足够数据判断全站热点。"
    return (
        f"{period_label}里，{top_genres or top_types} 的阅读增长更强，"
        f"具体分类以 {top_types} 的新增在读更集中；新书题材上 {top_themes} "
        f"更高频，说明读者仍偏好强设定、强情绪钩子和明确爽点。"
    )


def build_market_summary_payload(output: dict, trends_dir: str,
                                 genre_groups: list, keywords: list) -> dict:
    """生成全站热点统计和规则兜底总结。"""
    categories = [cat.get("name", "") for cat in output.get("categories", [])]
    trend_rows = load_trend_rows(trends_dir)
    periods = {}

    for key, days in MARKET_PERIODS:
        rows_window = trend_rows if days is None else trend_rows[-days:]
        period_label = "全部样本" if days is None else f"近 {days} 日"
        hot_types = collect_market_hot_types(categories, rows_window)
        hot_genres = collect_market_hot_genres(categories, hot_types, genre_groups)
        hot_themes = collect_market_hot_themes(output, rows_window, categories, keywords)
        fallback_summary = build_rule_market_summary(
            period_label, hot_genres, hot_types, hot_themes
        )
        periods[key] = {
            "period": period_label,
            "source": "rule",
            "summary": fallback_summary,
            "fallback_summary": fallback_summary,
            "hot_genres": hot_genres[:5],
            "hot_types": hot_types[:6],
            "hot_themes": hot_themes[:14],
        }

    return {
        "date": output.get("date", ""),
        "prev_date": output.get("prev_date", ""),
        "periods": periods,
    }


def build_market_ai_prompt(payload: dict, board_name: str = "番茄新书榜") -> str:
    """构建全站热点 AI 总结 prompt。"""
    sections = []
    for key, data in payload.get("periods", {}).items():
        genres = "、".join(
            f"{item['name']}(新增在读{format_market_reads(item.get('read_growth_total', 0))}, "
            f"增长作品{item.get('read_count', 0)})"
            for item in data.get("hot_genres", [])[:5]
        )
        types = "、".join(
            f"{item['name']}(新增在读{format_market_reads(item.get('read_growth_total', 0))}, "
            f"增长作品{item.get('read_count', 0)})"
            for item in data.get("hot_types", [])[:6]
        )
        themes = "、".join(
            f"{item['name']}(新书{item['count']}本)"
            for item in data.get("hot_themes", [])[:10]
        )
        sections.append(
            f"周期 {key} / {data['period']}:\n"
            f"- 综合赛道（按阅读增长量排序）: {genres or '无'}\n"
            f"- 具体分类（按阅读增长量排序）: {types or '无'}\n"
            f"- 高频题材（只统计新上榜作品，按新书数量排序）: {themes or '无'}\n"
            f"- 规则兜底: {data['fallback_summary']}"
        )

    return f"""你是一位网文市场编辑，请根据番茄「{board_name}」的统计结果，为每个周期生成一段全站热点判断。

{chr(10).join(sections)}

要求：
1. 只基于给定统计，不要编造未出现的类型或题材。
2. 每个周期输出 1 段中文，80-140 字。
3. 综合赛道和具体分类必须按“新增在读/阅读增长”解读，不要写“榜单动能”或“排名动能”。
4. 高频题材必须按“新上榜作品数量”解读，不要混入存量榜单或摘要题材。
5. 点明综合赛道、具体分类、新书题材关键词，以及一句编辑判断。
6. 输出严格 JSON，不要 Markdown，不要解释，格式如下：
{{
  "7": "总结文本",
  "14": "总结文本",
  "30": "总结文本",
  "all": "总结文本"
}}"""


def parse_json_object(text: str) -> dict:
    """尽量从模型响应中提取 JSON 对象。"""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def enrich_market_summary_with_ai(payload: dict, api_key: str,
                                  base_url: str, model: str,
                                  board_name: str = "番茄新书榜",
                                  rate_limit_state: dict = None) -> dict:
    """使用 AI 改写全站热点总结；失败时保留规则兜底。"""
    try:
        from openai import OpenAI
    except ImportError:
        print("⚠️  openai 库未安装，跳过全站热点 AI 总结。")
        return payload

    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
        _wait_for_api_slot()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": build_market_ai_prompt(payload, board_name)}],
            max_tokens=900,
            temperature=0.5,
        )
        parsed = parse_json_object(response.choices[0].message.content)
        for key, summary in parsed.items():
            if key in payload["periods"] and isinstance(summary, str) and summary.strip():
                payload["periods"][key]["summary"] = summary.strip()
                payload["periods"][key]["source"] = "ai"
        print("✅ 全站热点 AI 总结已生成")
    except Exception as e:
        if _is_rate_limit_error(e) and rate_limit_state is not None:
            rate_limit_state["rate_limited"] = True
        print(f"⚠️  全站热点 AI 总结失败，使用规则兜底: {e}")

    return payload



def is_rule_summary(summary: str) -> bool:
    """判断一个总结是否为规则模板生成的（非 AI）。
    规则摘要特征：短小、分号分隔、以句号结尾、无换行。
    """
    if not summary:
        return True
    if summary == "首日数据，暂无趋势对比。":
        return True
    # 规则摘要一般 < 150 字，用分号分隔，无换行
    if len(summary) < 150 and "；" in summary and "\n" not in summary:
        return True
    return False


def generate_ai_summaries(categories: list, trends: dict,
                          api_key: str, base_url: str,
                          model: str, force: bool = False,
                          existing_trends: dict = None,
                          trend_path: str = None,
                          trend_date: str = "",
                          prev_date: str = "",
                          rate_limit_state: dict = None) -> dict:
    """通过 OpenAI 兼容 API 为每个分类生成 AI 总结。

    采用批量合并策略（每 BATCH_SIZE 个分类一次调用）减少 API 调用次数，
    并在每批成功后增量保存，避免中途失败丢失已完成的结果。
    普通批量失败的分类会自动降级为逐个重试；429 限流时停止后续请求并使用规则摘要。
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("⚠️  openai 库未安装，跳过 AI 总结。pip install openai")
        return trends

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
    existing_trends = existing_trends or {}

    # 1. 筛选需要生成总结的分类
    pending = []  # (cat_name, cat_data, trend_data)
    skipped = 0

    for cat in categories:
        cat_name = cat["name"]
        if cat_name not in trends:
            continue

        if not force:
            existing_summary = existing_trends.get(cat_name, {}).get("summary", "")
            if existing_summary and not is_rule_summary(existing_summary):
                trends[cat_name]["summary"] = existing_summary
                skipped += 1
                continue

        pending.append((cat_name, cat, trends[cat_name]))

    if skipped > 0:
        print(f"  ⏭️  跳过 {skipped} 个已有 AI 总结的分类")

    if not pending:
        print("  ✅ 所有分类已有 AI 总结，无需生成")
        return trends

    # 2. 分批处理
    batches = [
        pending[i:i + BATCH_SIZE]
        for i in range(0, len(pending), BATCH_SIZE)
    ]
    failed_cats = []  # 批量失败后需单独重试的分类
    rate_limit_hit = False

    print(f"  📦 共 {len(pending)} 个分类，分 {len(batches)} 批处理"
          f"（每批最多 {BATCH_SIZE} 个）")

    for batch_idx, batch in enumerate(batches):
        batch_names = [b[0] for b in batch]
        print(f"\n  📦 第 {batch_idx + 1}/{len(batches)} 批: "
              f"{', '.join(batch_names)}")

        prompt = build_batch_ai_prompt(batch)

        max_retries = 3
        batch_success = False
        for attempt in range(1, max_retries + 1):
            try:
                _wait_for_api_slot()
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500 * len(batch),
                    temperature=0.7,
                )
                content = response.choices[0].message.content
                if not content or not content.strip():
                    raise ValueError("API 返回空内容")

                # 解析批量响应
                parsed = parse_batch_response(content, batch_names)

                if parsed:
                    for name, summary in parsed.items():
                        trends[name]["summary"] = summary
                        print(f"    ✅ {name}")

                    # 未解析出的分类加入失败队列
                    for name in batch_names:
                        if name not in parsed:
                            print(f"    ⚠️  未解析到: {name}（将单独重试）")
                            failed_cats.append(
                                next(b for b in batch if b[0] == name)
                            )

                    # 增量保存
                    _save_trends_incremental(
                        trend_path, trend_date, prev_date, trends
                    )
                    batch_success = True
                    break
                else:
                    raise ValueError("批量响应解析失败，未匹配到任何分类")

            except Exception as e:
                print(f"    ⚠️  第 {attempt} 次失败: {e}")
                if _is_rate_limit_error(e):
                    if attempt < max_retries:
                        import time
                        delay = _retry_after_seconds(e)
                        print(f"    ⏳ 检测到 429，{delay:.0f} 秒后重试")
                        time.sleep(delay)
                    else:
                        rate_limit_hit = True
                        if rate_limit_state is not None:
                            rate_limit_state["rate_limited"] = True
                        print("    ⛔ 免费 API 仍在限流，停止本轮 AI 请求")
                    continue
                if attempt < max_retries:
                    import time
                    time.sleep(5 * attempt)

        if not batch_success:
            print(f"    ❌ 批量生成失败（已重试 {max_retries} 次），"
                  f"将逐个重试")
            failed_cats.extend(batch)
        if rate_limit_hit:
            # 不再将剩余批次拆成单分类请求，避免 429 时进一步放大流量。
            for remaining_batch in batches[batch_idx + 1:]:
                failed_cats.extend(remaining_batch)
            break

    # 3. 对失败的分类逐个重试（降级为单分类 prompt）
    if failed_cats and not rate_limit_hit:
        print(f"\n  🔄 逐个重试 {len(failed_cats)} 个失败分类...")
        for cat_name, cat, trend in failed_cats:
            prompt = build_ai_prompt(cat_name, cat, trend)
            max_retries = 3
            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    _wait_for_api_slot()
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=500,
                        temperature=0.7,
                    )
                    content = response.choices[0].message.content
                    if not content or not content.strip():
                        raise ValueError("API 返回空内容")
                    trends[cat_name]["summary"] = content.strip()
                    print(f"    ✅ {cat_name}")
                    _save_trends_incremental(
                        trend_path, trend_date, prev_date, trends
                    )
                    success = True
                    break
                except Exception as e:
                    print(f"    ⚠️  {cat_name} 第 {attempt} 次失败: {e}")
                    if attempt < max_retries:
                        import time
                        time.sleep(5 * attempt)

            if not success:
                print(f"    ❌ {cat_name} 最终失败")
                old = existing_trends.get(cat_name, {}).get("summary", "")
                if old and not is_rule_summary(old):
                    trends[cat_name]["summary"] = old
                    print(f"    ↩️  保留旧 AI 总结: {cat_name}")
                else:
                    trends[cat_name]["summary"] = generate_trend_summary_text(
                        cat_name, trend
                    )

    if rate_limit_hit:
        for cat_name, cat, trend in failed_cats:
            old = existing_trends.get(cat_name, {}).get("summary", "")
            trends[cat_name]["summary"] = (
                old if old and not is_rule_summary(old)
                else generate_trend_summary_text(cat_name, trend)
            )

    return trends


# ============================================================
#  单榜单构建
# ============================================================

def build_board(board: dict, base_dir: str, args, api_creds: dict) -> dict:
    """构建单个榜单的全部产物。返回供 api/boards.json 汇总的元信息（含最新日期）。"""
    slug = board["slug"]
    name = board["name"]
    data_dir = os.path.join(base_dir, "data", slug)
    snap_dir = os.path.join(data_dir, "snapshots")
    trends_dir = os.path.join(data_dir, "trends")
    os.makedirs(trends_dir, exist_ok=True)

    print(f"\n{'#'*56}\n# 构建榜单：{name} ({slug})\n{'#'*56}")

    snapshots = sorted(glob.glob(os.path.join(snap_dir, "ranks_*.json")))
    if not snapshots:
        print(f"  ⚠️  {slug} 无快照（{snap_dir}），跳过。")
        return None

    # 选择目标快照
    if args.date:
        target_date_compact = args.date.replace("-", "")
        target_path = os.path.join(snap_dir, f"ranks_{target_date_compact}.json")
        if not os.path.exists(target_path):
            print(f"  ⚠️  {slug} 未找到 {args.date} 的快照，跳过。")
            return None
        latest_path = target_path
        target_idx = snapshots.index(target_path) if target_path in snapshots else -1
    else:
        latest_path = snapshots[-1]
        target_idx = len(snapshots) - 1

    latest_data = load_snapshot(latest_path)
    print(f"  目标快照: {os.path.basename(latest_path)} ({latest_data['date']})")

    # 前一天快照
    prev_data, prev_date = None, ""
    if target_idx > 0:
        prev_path = snapshots[target_idx - 1]
        prev_data = load_snapshot(prev_path)
        prev_date = prev_data.get("date", "")
        print(f"  对比快照: {os.path.basename(prev_path)} ({prev_date})")

    # 已有趋势（保留 AI 总结）
    existing_trends = {}
    trend_path = os.path.join(trends_dir, f"{latest_data['date']}.json")
    if os.path.exists(trend_path) and not args.force:
        try:
            with open(trend_path, "r", encoding="utf-8") as f:
                existing_trends = json.load(f).get("trends", {})
        except Exception:
            pass

    # 趋势对比
    if prev_data:
        trends = compare_categories(
            latest_data["categories"], prev_data["categories"]
        )
    else:
        print("  仅有一天数据，无法生成趋势对比。")
        trends = {
            cat["name"]: {
                "new_count": 0, "dropped_count": 0, "new_books": [],
                "dropped_books": [], "top_risers": [], "top_fallers": [],
                "reads_growth": [], "summary": "首日数据，暂无趋势对比。",
            }
            for cat in latest_data["categories"]
        }

    # AI 总结
    if api_creds and not api_creds.get("rate_limited"):
        print(f"  正在使用 {api_creds['model']} 生成 AI 总结...")
        trends = generate_ai_summaries(
            latest_data["categories"], trends,
            api_creds["key"], api_creds["base_url"], api_creds["model"],
            force=args.force, existing_trends=existing_trends,
            trend_path=trend_path, trend_date=latest_data["date"],
            prev_date=prev_date,
            rate_limit_state=api_creds,
        )
    else:
        for cat_name, trend in trends.items():
            old = existing_trends.get(cat_name, {}).get("summary", "")
            if old and not is_rule_summary(old):
                trend["summary"] = old
            elif not trend.get("summary"):
                trend["summary"] = generate_trend_summary_text(cat_name, trend)

    # 组装 latest_ranks
    output = {
        "slug": slug, "name": name,
        "date": latest_data["date"], "prev_date": prev_date,
        "categories": [],
    }
    for cat in latest_data["categories"]:
        output["categories"].append({
            "name": cat["name"],
            "trend": trends.get(cat["name"], {}),
            "books": cat.get("books", []),
        })

    out_path = os.path.join(data_dir, "latest_ranks.json")
    write_json(out_path, output)
    print(f"  ✅ latest_ranks: {out_path}")

    # 静态 API（按 slug 命名空间）
    build_lastest_api(output, base_dir, slug)
    print(f"  ✅ API: api/{slug}/lastest/")

    # 趋势存档
    write_json(trend_path, {
        "date": latest_data["date"], "prev_date": prev_date, "trends": trends,
    })
    print(f"  ✅ 趋势存档: {trend_path}")

    # 全站热点（按榜单的 genre_groups / keywords）
    market_payload = build_market_summary_payload(
        output, trends_dir, board.get("genre_groups"), board.get("keywords", [])
    )
    if api_creds and not api_creds.get("rate_limited"):
        market_payload = enrich_market_summary_with_ai(
            market_payload, api_creds["key"], api_creds["base_url"],
            api_creds["model"], name, rate_limit_state=api_creds
        )
    write_json(os.path.join(data_dir, "market_summary.json"), market_payload)
    print("  ✅ 全站热点: market_summary.json")

    # dates 索引
    date_list = []
    for s in snapshots:
        m = re.search(r"(\d{4})(\d{2})(\d{2})", os.path.basename(s))
        if m:
            date_list.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    write_json(os.path.join(data_dir, "dates.json"),
               {"dates": sorted(date_list)})
    print(f"  ✅ 日期索引: {len(date_list)} 天")

    meta = board_public_meta(board)
    meta.update({"date": latest_data["date"], "prev_date": prev_date,
                 "category_count": len(output["categories"])})
    return meta


# ============================================================
#  主入口：遍历所有启用榜单
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="构建多榜单 latest 数据")
    parser.add_argument("--force", action="store_true",
                        help="强制重新生成所有 AI 总结")
    parser.add_argument("--date", type=str, default="",
                        help="指定目标日期 (YYYY-MM-DD)，默认最新快照")
    parser.add_argument("--board", type=str, default="",
                        help="只构建指定 slug 的榜单，默认全部启用榜单")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # AI 凭据
    api_base_url = os.environ.get("API_BASE_URL", "")
    api_key = os.environ.get("API_KEY", "")
    api_model = os.environ.get("API_MODEL", "")
    api_creds = None
    if api_base_url and api_key and api_model:
        api_creds = {"base_url": api_base_url, "key": api_key, "model": api_model}
        print(f"AI 总结已启用: {api_model} @ {api_base_url}")
    else:
        print("未配置 AI 服务，使用规则摘要替代。")

    boards = enabled_boards()
    if args.board:
        boards = [b for b in boards if b["slug"] == args.board]
    if not boards:
        print("没有可构建的榜单。检查 boards_config.py 的 enabled / init_url。")
        sys.exit(1)

    board_metas = []
    for board in boards:
        try:
            meta = build_board(board, base_dir, args, api_creds)
            if meta:
                board_metas.append(meta)
        except Exception as e:
            print(f"  ❌ 榜单 {board['slug']} 构建失败：{e}")

    # 汇总 api/boards.json
    if board_metas:
        boards_index_path = os.path.join(base_dir, "api", "boards.json")
        os.makedirs(os.path.dirname(boards_index_path), exist_ok=True)
        write_json(boards_index_path, {"boards": board_metas})
        print(f"\n✅ 榜单索引: api/boards.json（{len(board_metas)} 个榜单）")


if __name__ == "__main__":
    main()
