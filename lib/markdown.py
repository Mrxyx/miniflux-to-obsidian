"""Markdown 生成与文本处理"""

import re
import html2text
from datetime import datetime


def clean_html(html):
    """将 HTML 转换为 Markdown"""
    if not html:
        return ""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0
    return h.handle(html)


def sanitize(title, max_length=80):
    """清理文件名中的非法字符"""
    if not title:
        return "Untitled"
    safe_title = re.sub(r'[<>:"/\\|?*\n\r\t]', '', title).strip()
    if len(safe_title) > max_length:
        safe_title = safe_title[:max_length].rsplit(' ', 1)[0]
    return safe_title.strip()


def escape_yaml_string(s):
    """转义 YAML 字符串中的特殊字符"""
    if not s:
        return ""
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    return s


def generate_markdown(entry, ai_result, clean_content):
    """生成 Obsidian 格式的 Markdown"""
    title = entry.get('title', 'Untitled')
    url = entry.get('url', '')
    author = entry.get('author', '')
    feed = entry.get('feed', {})
    feed_title = feed.get('title', '')
    category = feed.get('category', {}).get('title', '')
    published_at = entry.get('published_at', '')

    # 解析发布日期
    try:
        pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        date_str = pub_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        date_str = datetime.now().strftime('%Y-%m-%d')

    # AI 分析结果（如果有）
    ai_section = ""
    if ai_result:
        summary = ai_result.get('summary', '')
        topics = ai_result.get('topics', [])
        reason = ai_result.get('reason', '')
        topics_str = ', '.join(topics) if topics else '待分类'

        ai_section = f"""
> [!ai]- AI 初筛（点击展开）
> **摘要**：{summary}
> **主题**：{topics_str}
> **收藏原因**：{reason}
"""

    md = f"""---
source: Miniflux
imported: {datetime.now().strftime('%Y-%m-%d')}
tags: [inbox]
original_url: "{url}"
author: "{escape_yaml_string(author)}"
feed: "{escape_yaml_string(feed_title)}"
category: "{escape_yaml_string(category)}"
published: {date_str}
---

# {title}

> 来源: [{feed_title}]({url})

{ai_section}## 原始内容

{clean_content}

## 阅读状态
- [ ] 未读
- [ ] 已快速扫读
- [ ] 已精读

## 备注

"""
    return md
