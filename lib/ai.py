"""Claude AI 文章分析"""

import json
import logging
import re


def create_client(claude_config):
    """创建 Anthropic 客户端"""
    import anthropic

    api_key = claude_config.get('api_key', '')
    base_url = claude_config.get('base_url', '')

    if base_url:
        return anthropic.Anthropic(api_key=api_key, base_url=base_url)
    else:
        return anthropic.Anthropic(api_key=api_key)


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

    # 截取内容，避免 token 过多
    content_preview = content[:3000] if len(content) > 3000 else content

    prompt = f"""分析以下 RSS 文章，返回 JSON 格式结果：

标题：{title}
来源：{feed_title}
内容：
{content_preview}

请返回以下 JSON 格式（直接返回 JSON，不要 markdown 代码块）：
{{
    "smart_title": "简洁的中文标题（15字以内，适合做文件名）",
    "summary": "一两句话概括文章核心内容",
    "topics": ["主题1", "主题2"],
    "reason": "猜测用户收藏这篇文章的原因"
}}

主题参考：AI/LLM、编程/开发、工具/效率、提示词工程、技术架构、个人成长、产品设计、行业动态、开源项目、教程指南
"""

    try:
        client = create_client(claude_config)

        message = client.messages.create(
            model=model,
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        result_text = message.content[0].text.strip()
        # 移除可能的 markdown 代码块包裹
        if result_text.startswith('```'):
            result_text = re.sub(r'^```(?:json)?\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)
        # 尝试解析 JSON
        result = json.loads(result_text)
        logging.debug(f"AI 分析完成: {result.get('smart_title', '')}")
        return result

    except json.JSONDecodeError as e:
        logging.warning(f"AI 返回结果解析失败: {e}")
        return None
    except Exception as e:
        logging.warning(f"Claude API 调用失败: {e}")
        return None
