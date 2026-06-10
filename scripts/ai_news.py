#!/usr/bin/env python3
"""
AI 新闻日报 — 查询新闻并自动写入飞书文档

用法:
  python3 ai_news.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]

输出:
  stdout 第 1 行：飞书文档链接
  stdout 第 2 行：统计信息
  stderr：进度信息 + 临时文件路径（用于清理）
  失败时 stderr 输出错误信息，exit code 1
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ========== 配置 ==========
INSIGHT_API = "https://api.cloudmint.cn/insight/daily_paper/range"
INSIGHT_API_KEY = "ovi0d2qk46g*m"
FEISHU_API = "https://open.feishu.cn/open-apis"
MAX_BATCH = 50
BJT = timezone(timedelta(hours=8))
OUTPUT_DIR = "/tmp/ai-news-output"


# ==================== 第一部分：查询新闻 ====================

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


# ==================== 第二部分：写入飞书文档 ====================

def find_env_path():
    """定位 Hermes .env 文件"""
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        path = os.path.join(hermes_home, ".env")
        if os.path.exists(path):
            return path

    for dirname in [".hermes-2", ".hermes"]:
        path = os.path.expanduser(f"~/{dirname}/.env")
        if os.path.exists(path):
            return path

    return None


def load_env():
    """从 .env 加载飞书凭证"""
    env_path = find_env_path()
    if not env_path:
        print(
            "❌ 找不到 Hermes 环境文件。\n"
            "   请设置 HERMES_HOME 环境变量，或确保以下文件之一存在：\n"
            "     ~/.hermes-2/.env\n"
            "     ~/.hermes/.env",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def feishu_api(method, path, token=None, body=None):
    """发送飞书 API 请求"""
    url = f"{FEISHU_API}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            if result.get("code") != 0:
                msg = result.get("msg", "未知错误")
                print(f"❌ 飞书 API 错误 [{path}]: code={result.get('code')}, {msg}",
                      file=sys.stderr)
                sys.exit(1)
            # 认证 API 没有 data 字段，文档 API 有
            if "data" in result:
                return result["data"]
            return result
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()[:500]
        except Exception:
            pass
        print(f"❌ 飞书 API HTTP 错误 [{path}]: {e.code} {body_text}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ 网络请求失败 [{path}]: {e}", file=sys.stderr)
        sys.exit(1)


def get_token(app_id, app_secret):
    """获取 tenant_access_token"""
    data = feishu_api("POST", "/auth/v3/tenant_access_token/internal", body={
        "app_id": app_id,
        "app_secret": app_secret,
    })
    token = data.get("tenant_access_token")
    if not token:
        print("❌ 获取 tenant_access_token 失败", file=sys.stderr)
        sys.exit(1)
    return token


def create_doc(token, title):
    """创建飞书文档，返回 document_id"""
    data = feishu_api("POST", "/docx/v1/documents", token, {"title": title})
    doc = data.get("document", {})
    doc_id = doc.get("document_id")
    if not doc_id:
        print("❌ 创建文档失败：未返回 document_id", file=sys.stderr)
        sys.exit(1)
    return doc_id


def write_blocks(token, doc_id, blocks):
    """分批写入 blocks"""
    total = len(blocks)
    for i in range(0, total, MAX_BATCH):
        batch = blocks[i:i + MAX_BATCH]
        batch_num = i // MAX_BATCH + 1
        total_batches = (total + MAX_BATCH - 1) // MAX_BATCH
        print(f"  写入第 {batch_num}/{total_batches} 批（{len(batch)} 个 block）...",
              file=sys.stderr)
        feishu_api(
            "POST",
            f"/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
            token,
            {"children": batch, "index": i},
        )


# ==================== Markdown → Feishu Blocks ====================

def md_to_blocks(md_text):
    """Markdown 转飞书 block 列表"""
    blocks = []
    for line in md_text.strip().split("\n"):
        line = line.strip()
        if not line or line == "---":
            continue

        # ## 标题跳过（文档已有标题）
        if line.startswith("## "):
            continue
        elif line.startswith("### "):
            blocks.append(_heading(4, "heading2", line[4:]))
        elif re.match(r"^\d+\.", line):
            # 编号列表项：1. 内容 [详情](url) — 保留编号
            match = re.match(r"^(\d+\.\s*.+?)\s*\[详情\]\((.+?)\)$", line)
            if match:
                blocks.append(_text_with_link(match.group(1), match.group(2)))
            else:
                blocks.append(_text(content))
        elif line.startswith("- "):
            content = line[2:]
            match = re.match(r"^(.+?)\s*\[详情\]\((.+?)\)$", content)
            if match:
                blocks.append(_text_with_link(match.group(1), match.group(2)))
            else:
                blocks.append(_text(content))
        else:
            blocks.append(_text(line))
    return blocks


def _heading(block_type, key, content):
    return {
        "block_type": block_type,
        key: {
            "elements": [{"text_run": {"content": content}}],
        },
    }


def _text(content):
    return {
        "block_type": 2,
        "text": {
            "elements": [{"text_run": {"content": content}}],
        },
    }


def _text_with_link(content, url):
    return {
        "block_type": 2,
        "text": {
            "elements": [
                {"text_run": {"content": content + " "}},
                {
                    "text_run": {
                        "content": "详情",
                        "text_element_style": {
                            "bold": False,
                            "italic": False,
                            "strikethrough": False,
                            "underline": False,
                            "inline_code": False,
                            "link": {"url": url},
                        },
                    },
                },
            ],
        },
    }


def extract_stats(md_text):
    """从 Markdown 提取统计数字"""
    match = re.search(
        r"📊\s*共\s*(\d+)\s*条新闻\s*\|\s*覆盖\s*(\d+)\s*个分类",
        md_text,
    )
    if match:
        return match.group(1), match.group(2)
    return "?", "?"


# ==================== 主函数 ====================

def main():
    # 1. 解析日期
    start, end = parse_args()

    # 2. 查询新闻
    print(f"📡 正在查询 {start} ~ {end} 的新闻...", file=sys.stderr)
    data = fetch_news(start, end)

    # 3. 格式化 Markdown
    md_text = format_markdown(data, start, end)

    # 4. 写入临时文件
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if start == end:
        filename = f"AI日报_{start}.md"
    else:
        filename = f"AI日报_{start}_至_{end}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"  临时文件: {filepath}", file=sys.stderr)

    # 5. 加载飞书凭证
    load_env()
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        print("❌ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET", file=sys.stderr)
        sys.exit(1)

    # 6. 创建飞书文档
    print("📄 正在创建飞书文档...", file=sys.stderr)
    token = get_token(app_id, app_secret)

    # 确定标题
    if start == end:
        title = f"AI日报 | {start}"
    else:
        title = f"AI日报 | {start} ~ {end}"

    doc_id = create_doc(token, title)
    print(f"  文档 ID: {doc_id}", file=sys.stderr)

    # 7. 写入 blocks
    blocks = md_to_blocks(md_text)
    if not blocks:
        print("⚠️ 内容为空，跳过写入", file=sys.stderr)
    else:
        print(f"  共 {len(blocks)} 个 block", file=sys.stderr)
        write_blocks(token, doc_id, blocks)

    # 8. stdout 输出：第 1 行 URL，第 2 行统计
    doc_url = f"https://feishu.cn/docx/{doc_id}"
    total, categories = extract_stats(md_text)
    print(doc_url)
    print(f"📊 共 {total} 条新闻 | 覆盖 {categories} 个分类")


if __name__ == "__main__":
    main()
