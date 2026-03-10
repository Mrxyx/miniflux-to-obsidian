"""Claude AI 文章分析"""

import json
import logging
import re
import string


def create_client(claude_config):
    """创建 Anthropic 客户端"""
    import anthropic

    api_key = claude_config.get('api_key', '')
    base_url = claude_config.get('base_url', '')

    if base_url:
        return anthropic.Anthropic(api_key=api_key, base_url=base_url)
    else:
        return anthropic.Anthropic(api_key=api_key)


# ---- 公共 JSON 解析 ----

def _fix_json_quotes(s):
    """修复 AI 返回 JSON 中值内未转义的双引号。
    逐字符状态机：判断引号是 JSON 结构符还是值内裸引号，
    将后者替换为左双引号 U+201C 使 json.loads 能通过。
    """
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
                rest = s[i+1:].lstrip()
                if not rest or rest[0] in ':,}]':
                    in_string = False
                    result.append(c)
                else:
                    result.append('\u201c')
            i += 1
            continue
        result.append(c)
        i += 1

    return ''.join(result)


def parse_ai_json(text):
    """解析 AI 返回的 JSON 文本，三层兜底：
    1. 清理格式后直接 json.loads
    2. regex 提取第一个 {...} 再 json.loads
    3. _fix_json_quotes 修复裸引号后再 json.loads
    返回 dict 或 None。
    """
    if not text:
        return None

    s = text.strip()
    # 清理 ```json ... ``` 包裹（含前导空格/换行）
    s = re.sub(r'^\s*```(?:json)?\s*\n?', '', s)
    s = re.sub(r'\n?\s*```\s*$', '', s)
    # 清理裸 json 前缀
    s = re.sub(r'^\s*json\s*\n', '', s)
    s = s.strip()

    # 第一层：直接解析
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # 第二层：regex 提取第一个完整 JSON 对象
    match = re.search(r'\{.*\}', s, re.DOTALL)
    if match:
        json_str = match.group()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # 第三层：修复未转义双引号
        fixed = _fix_json_quotes(json_str)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            logging.warning(f"AI JSON 解析失败（已尝试修复）: {e}, raw: {text[:200]}")
            return None

    logging.warning(f"AI 返回中未找到 JSON: {text[:200]}")
    return None


# ---- 收藏同步 AI 分析 ----

_ANALYZE_PROMPT = string.Template("""分析以下 RSS 文章，返回 JSON 格式结果：

标题：$title
来源：$feed_title
内容：
$content

请返回以下 JSON 格式（直接返回 JSON，不要 markdown 代码块）：
{
    "smart_title": "简洁的中文标题（15字以内，适合做文件名）",
    "summary": "一两句话概括文章核心内容",
    "topics": ["主题1", "主题2"],
    "reason": "猜测用户收藏这篇文章的原因"
}

主题参考：AI/LLM、编程/开发、工具/效率、提示词工程、技术架构、个人成长、产品设计、行业动态、开源项目、教程指南
""")


def analyze_with_claude(config, title, content, feed_title):
    """使用 Claude API 分析文章内容"""
    claude_config = config.get('claude', {})

    if not claude_config.get('enabled', False):
        return None

    api_key = claude_config.get('api_key', '')
    if not api_key or api_key == 'your_api_key_here':
        logging.debug("Claude API Key 未配置，跳过 AI 分析")
        return None

    model = claude_config.get('model', 'claude-opus-4-5')
    content_preview = content[:3000]

    prompt = _ANALYZE_PROMPT.safe_substitute(
        title=title,
        feed_title=feed_title,
        content=content_preview,
    )

    try:
        client = create_client(claude_config)
        message = client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        result = parse_ai_json(message.content[0].text)
        if result:
            logging.debug(f"AI 分析完成: {result.get('smart_title', '')}")
        return result

    except Exception as e:
        logging.warning(f"Claude API 调用失败: {e}")
        return None
