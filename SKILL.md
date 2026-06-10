---
name: ai-news
description: 查询 AI 新闻日报，支持按日期范围查询，按分类分组展示，自动生成飞书文档
version: 4.0.0
dependencies:
  - python3
---

# AI 新闻日报查询

## 〇、安装前提

### 目录结构

```
<skill目录>/ai-news/
├── SKILL.md
└── scripts/
    └── ai_news.py
```

### 飞书应用权限

在飞书开放平台 → 应用管理 → 权限管理中，开通 `docx:document` 权限。

### 环境变量配置

在 Hermes 的 `.env` 文件中确保包含：

```bash
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
```

> 脚本自动查找 `$HERMES_HOME/.env`、`~/.hermes-2/.env`、`~/.hermes/.env`。


## 一、触发条件

- 关键词："查新闻"、"AI新闻"、"今日日报"、"AI日报"、"最近X天新闻"
- 命令：`/ai-news`
- 语义：想了解 AI 领域最新动态


## 二、执行步骤

> **路径解析（重要）**：执行前必须先调用 `skill_view(name="ai-news")` 获取安装目录，拼接 `scripts/ai_news.py` 构造完整路径。禁止硬编码绝对路径。

### 步骤 1：解析日期

从用户消息中提取日期，格式必须为 `YYYY-MM-DD`：

| 用户说 | 参数 |
|--------|------|
| 未指定日期 | 不传参数（默认今天） |
| "今天的新闻" | `--start YYYY-MM-DD` |
| "最近3天的新闻" | `--start 3天前 --end 今天` |
| "6月1日到7日" | `--start 2026-06-01 --end 2026-06-07` |

### 步骤 2：执行脚本

使用 **terminal** 执行：

```bash
python3 <安装目录>/scripts/ai_news.py \
  --start 2026-06-01 --end 2026-06-07
```

> 不传参数则默认查询今天。`--end` 不传则等于 `--start`。

**脚本自动完成全部工作：**
1. 查询 insight API 获取新闻数据
2. 创建飞书文档并写入内容（标题、分类、带链接的条目）
3. stdout 输出两行结果

**stdout 输出示例：**
```
https://feishu.cn/docx/xxxxxx
📊 共 156 条新闻 | 覆盖 7 个分类
```

**stderr 会输出临时文件路径**（如 `临时文件: /tmp/ai-news-output/AI日报_2026-06-01.md`），用于后续清理。

### 步骤 3：发送结果

1. 读取 stdout 第 1 行（飞书文档链接）和第 2 行（统计信息）
2. 从 stderr 中找到临时文件路径，执行 `rm` 删除
3. 以下面的格式发送给用户：

```
📰 AI 日报已生成，共 X 条新闻，覆盖 Y 个分类
[📄 点击查看完整日报](飞书文档链接)
```

**⚠️ 工具限制：**

- 必须使用 **terminal** 工具
- **禁止使用 execute_code**（沙盒无法读取 .env）

**禁止做以下操作：**

- ❌ 在聊天中直接展示新闻内容（会截断）
- ❌ 对新闻内容做修改、总结、精简
- ❌ 返回裸 URL，必须使用 `[文字](URL)` 格式
- ❌ 跳过删除临时文件

**错误场景**：stderr 输出错误信息，exit code 非 0 → 告知用户

**空数据场景**：脚本仍会创建飞书文档（内容为"暂无新闻数据"）→ 正常发送链接


## 三、输出示例

### 成功场景

脚本 stdout：
```
https://feishu.cn/docx/xxxxx
📊 共 156 条新闻 | 覆盖 7 个分类
```

用户在聊天中看到：
```
📰 AI 日报已生成，共 156 条新闻，覆盖 7 个分类
[📄 点击查看完整日报](https://feishu.cn/docx/xxxxx)
```

### 错误场景

stderr 输出（exit code 非 0）：
```
❌ 日期格式错误，请使用 YYYY-MM-DD 格式
❌ 最大查询范围为 7 天（含首尾），当前选择了 10 天
❌ API 认证失败（key 无效）
❌ 找不到 Hermes 环境文件
❌ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET
❌ 飞书 API 错误
```

将错误信息告知用户。


## 四、输出规则（最高优先级）

本 skill 的设计原则是 **飞书文档交付**，不是 **聊天展示**。

| ✅ 必须做 | ❌ 禁止做 |
|-----------|-----------|
| 发送飞书文档链接 | 在聊天中展示新闻内容 |
| 使用 `[文字](URL)` 格式 | 返回裸 URL |
| 包含统计信息 | 修改或精简新闻内容 |
| 删除临时文件 | 跳过清理步骤 |

**原因**：飞书聊天框有字数限制，70+ 条新闻会被截断。飞书文档无限制，支持下载和分享。


## 五、注意事项

1. **API 认证**：insight API key 已内置在脚本中；飞书凭证需在 `.env` 中配置
2. **查询范围**：最大 7 天（含首尾）
3. **时区**：北京时间（UTC+8）
4. **去重**：按 link 去重，保留第一次出现
5. **空数据**：API key 无效时仍返回空列表，连续多天"暂无新闻"可能是 key 过期


## 六、调试方法

### 6.1 手动测试

```bash
# 查询今天
python3 <安装目录>/scripts/ai_news.py

# 查询指定范围
python3 <安装目录>/scripts/ai_news.py --start 2026-06-01 --end 2026-06-07
```

成功时 stdout 输出文档链接 + 统计信息。

### 6.2 常见错误

| 错误 | 原因 |
|------|------|
| `找不到 Hermes 环境文件` | .env 不存在，需创建或设置 HERMES_HOME |
| `缺少 FEISHU_APP_ID` | .env 中未配置飞书凭证 |
| `飞书 API 错误` | 凭证无效或权限不足（需 `docx:document`） |
| `API 认证失败` | insight API key 过期 |

### 6.3 清理临时文件

```bash
ls -la /tmp/ai-news-output/
rm -f /tmp/ai-news-output/*.md
```
