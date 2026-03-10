"""AI 导读生成 — 为 Miniflux 文章生成中文导读区块"""

import html
import json
import logging
import re
import string

import html2text

from .ai import create_client


DIGEST_PROMPT_TEMPLATE = string.Template("""你是一个专业的技术文章分析助手。请分析以下 RSS 文章，生成中文导读。

标题：$title
来源：$feed_title
内容：
$content

请返回以下 JSON 格式（直接返回 JSON，不要 markdown 代码块）：
{
    "category": "大类 → 小类",
    "core_point": "一句话说清楚文章的核心观点或结论",
    "key_points": ["要点1", "要点2", "要点3"],
    "analysis_scope": "这篇文章对哪些领域或方面进行了分析",
    "impact": "可能带来的收益、影响或启发",
    "read_time_min": 8,
    "read_advice": "精读/扫读/跳过"
}

分类参考（大类 → 小类）：
- AI/LLM → 模型训练、推理优化、Agent、RAG、提示词工程、多模态
- 编程/开发 → 前端、后端、移动端、架构设计、性能优化、DevOps
- 工具/效率 → 开发工具、自动化、工作流
- 系统/底层 → 操作系统、网络、数据库、分布式、计算机组成
- 产品/商业 → 产品设计、增长、商业模式、行业分析
- 个人成长 → 职业发展、学习方法、思维模型
- 开源/社区 → 开源项目、技术社区、开发者生态
- 其他 → 不属于以上分类的

阅读建议判断标准：
- 精读：有深度洞察、独特观点、对读者方向直接相关
- 扫读：有参考价值但不需要逐字读，看要点就够
- 跳过：信息密度低、与读者方向关系不大，看核心观点即可

要点提炼要求：每个要点一句话，抓住文章骨架，不要泛泛而谈。
""")

# 导读 HTML 模板
DIGEST_HTML = """<div style="background:#f0f7ff;border-left:4px solid #1a73e8;padding:12px 16px;margin-bottom:20px;border-radius:4px;font-size:14px;line-height:1.6;">
<b>📌 AI 导读</b><br/>
<b>分类：</b>{category}<br/>
<b>核心观点：</b>{core_point}<br/>
<b>关键要点：</b><br/>
{key_points_html}
<b>涉及领域：</b>{analysis_scope}<br/>
<b>收益/影响：</b>{impact}<br/>
<b>⏱ 预估 {read_time_min} 分钟 | 建议：{read_advice}</b>
</div>
<hr/>
"""

# 标记已处理的隐藏标签
DIGEST_MARKER = '<!-- ai-digest-done -->'


def _fix_json_quotes(s):
    """修复 AI 返回 JSON 中值内未转义的双引号。
    例如: "core_point": "用"Artificial Grokon"暗示..."
    替换为: "core_point": "用「Artificial Grokon」暗示..."
    """
    # 匹配 JSON 字符串值中的未转义引号：
    # 在 ": " 之后的字符串值内部，将成对的裸引号替换为中文引号
    def replace_inner_quotes(m):
        value = m.group(1)
        # 替换值内部的未转义双引号为中文引号
        # 简单策略：将 " 前后都不是 JSON 结构字符的引号替换
        fixed = re.sub(r'(?<!\\)"(?![:,\]\}\s*$])', '\u201c', value)
        return fixed

    # 更可靠的方式：逐字符解析修复
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(s):
        c = s[i]
        if escape_next:
            result.append(c)
            escape_next = False
            i += 1
            continue

        if c == '\\':
            result.append(c)
            escape_next = True
            i += 1
            continue

        if c == '"':
            if not in_string:
                in_string = True
                result.append(c)
            else:
                # 看后面是不是 JSON 结构字符（说明这个引号是字符串结束符）
                rest = s[i+1:].lstrip()
                if not rest or rest[0] in ':,}]':
                    in_string = False
                    result.append(c)
                else:
                    # 这是值内部的未转义引号，替换为中文引号
                    result.append('\u201c')
            i += 1
            continue

        result.append(c)
        i += 1

    return ''.join(result)


def _html_to_text(html_content):
    """将 HTML 转为纯文本，避免截断时切在标签中间"""
    if not html_content:
        return ""
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.body_width = 0
    return h.handle(html_content)


def generate_digest(claude_config, title, content, feed_title):
    """调用 AI 生成导读 JSON"""
    api_key = claude_config.get('api_key', '')
    if not api_key or api_key == 'your_api_key_here':
        logging.debug("Claude API Key 未配置，跳过导读生成")
        return None

    model = claude_config.get('model', 'claude-haiku-4-5')

    # HTML → 纯文本后再截取，避免切在标签中间
    plain_text = _html_to_text(content)
    content_preview = plain_text[:5000]

    prompt = DIGEST_PROMPT_TEMPLATE.safe_substitute(
        title=title,
        feed_title=feed_title,
        content=content_preview,
    )

    try:
        client = create_client(claude_config)
        message = client.messages.create(
            model=model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = message.content[0].text.strip()
        # 清理各种 AI 返回格式：```json ... ```、json\n{...}、纯文本包裹等
        result_text = re.sub(r'^\s*```(?:json)?\s*\n?', '', result_text)
        result_text = re.sub(r'\n?\s*```\s*$', '', result_text)
        # 处理 AI 返回 "json\n{...}" 格式（无反引号）
        result_text = re.sub(r'^\s*json\s*\n', '', result_text)
        result_text = result_text.strip()

        # 尝试直接解析，失败则修复常见 JSON 问题后重试
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # 兜底 1：尝试用 regex 提取第一个完整 JSON 对象
            match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if match:
                json_str = match.group()
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    # 兜底 2：修复 AI 常见的未转义双引号问题
                    # 将 JSON 字符串值内的未转义双引号替换为中文引号
                    fixed = _fix_json_quotes(json_str)
                    try:
                        result = json.loads(fixed)
                    except json.JSONDecodeError as e:
                        logging.warning(f"导读 JSON 解析失败: {e}, raw: {result_text[:200]}")
                        return None
            else:
                logging.warning(f"导读返回中未找到 JSON: {result_text[:200]}")
                return None

        logging.debug(f"导读生成完成: {title[:40]}")
        return result

    except json.JSONDecodeError as e:
        logging.warning(f"导读 JSON 解析失败: {e}, raw: {result_text[:200]}")
        return None
    except Exception as e:
        logging.warning(f"导读生成失败: {e}")
        return None


def build_digest_html(digest_result):
    """将导读 JSON 转为 HTML 区块，所有字段做 HTML 转义防 XSS"""
    if not digest_result:
        return ""

    key_points = digest_result.get('key_points', [])
    key_points_html = ''.join(
        f'&nbsp;&nbsp;• {html.escape(str(p))}<br/>' for p in key_points
    )

    return DIGEST_MARKER + '\n' + DIGEST_HTML.format(
        category=html.escape(str(digest_result.get('category', '未分类'))),
        core_point=html.escape(str(digest_result.get('core_point', ''))),
        key_points_html=key_points_html,
        analysis_scope=html.escape(str(digest_result.get('analysis_scope', ''))),
        impact=html.escape(str(digest_result.get('impact', ''))),
        read_time_min=html.escape(str(digest_result.get('read_time_min', '?'))),
        read_advice=html.escape(str(digest_result.get('read_advice', '扫读'))),
    )


def has_digest(content):
    """检查文章是否已有导读标记"""
    return DIGEST_MARKER in (content or '')
