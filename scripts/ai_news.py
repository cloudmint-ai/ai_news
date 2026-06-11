#!/usr/bin/env python3
"""
AI 新闻日报 — 查询新闻并直接输出到聊天

用法:
  python3 ai_news.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]

输出:
  stdout：完整的新闻内容（Markdown 格式），Hermes 读取后直接发送给用户
  stderr：进度信息
  失败时 stderr 输出错误信息，exit code 1
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ========== 配置 ==========
INSIGHT_API = "https://api.cloudmint.cn/insight/daily_paper/range"
INSIGHT_API_KEY = "ovi0d2qk46g*m"
BJT = timezone(timedelta(hours=8))


# ==================== 查询与格式化 ====================

def parse_args():
    """解析日期参数"""
    parser = argparse.ArgumentParser(description="AI 新闻日报")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD（默认同 start）")
    args = parser.parse_args()

    today = datetime.now(BJT).strftime("%Y-%m-%d")
    start = args.start or today
    end = args.end or start

    try:
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        print("❌ 日期格式错误，请使用 YYYY-MM-DD 格式", file=sys.stderr)
        sys.exit(1)

    if e < s:
        print("❌ 结束日期不能早于开始日期", file=sys.stderr)
        sys.exit(1)

    if (e - s).days > 6:
        print(f"❌ 最大查询范围为 7 天（含首尾），当前选择了 {(e - s).days + 1} 天",
              file=sys.stderr)
        sys.exit(1)

    return start, end


def fetch_news(start, end):
    """查询 insight API，返回 JSON 数据"""
    url = f"{INSIGHT_API}?start_date={start}&end_date={end}"
    req = urllib.request.Request(url, headers={"key": INSIGHT_API_KEY})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 401:
                print("❌ API 认证失败（key 无效）", file=sys.stderr)
                sys.exit(1)
            if resp.status != 200:
                print(f"❌ API 返回错误: HTTP {resp.status}", file=sys.stderr)
                sys.exit(1)
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        print(f"❌ 网络请求失败: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)


def deduplicate_items(items):
    """按 link 去重"""
    seen = set()
    result = []
    for item in items:
        link = item.get("link")
        if link and link not in seen:
            seen.add(link)
            result.append(item)
    return result


def format_markdown(data, start, end):
    """将 API 数据格式化为 Markdown"""
    if not data:
        return f"📭 {start} ~ {end} 暂无新闻数据"

    lines = []
    total_items = 0
    categories_with_data = 0
    global_index = 0  # 跨分类连续编号

    for category in data:
        name = category.get("category", "未分类")
        items = deduplicate_items(category.get("items", []))
        if not items:
            continue

        categories_with_data += 1
        count = len(items)
        total_items += count
        lines.append(f"### {name}（{count} 条）\n")

        for item in items:
            global_index += 1
            content = item.get("content", "").replace("##", "")
            link = item.get("link", "").replace("##", "")
            lines.append(f"{global_index}. {content} [详情]({link})")

        lines.append("")

    lines.append("---")
    lines.append(f"📊 共 {total_items} 条新闻 | 覆盖 {categories_with_data} 个分类")
    return "\n".join(lines)


# ==================== 主函数 ====================

def main():
    # 1. 解析日期
    start, end = parse_args()

    # 2. 查询新闻
    print(f"📡 正在查询 {start} ~ {end} 的新闻...", file=sys.stderr)
    data = fetch_news(start, end)

    # 3. 格式化并直接输出到 stdout
    md_text = format_markdown(data, start, end)
    print(md_text)


if __name__ == "__main__":
    main()
