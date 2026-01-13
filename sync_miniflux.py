#!/usr/bin/env python3
"""
Miniflux RSS 加星文章同步脚本
将 Miniflux 中收藏的文章同步为本地 Markdown 文件，并通过 rclone 同步到云端
"""

import argparse
import logging
import sys
from pathlib import Path

from lib.config import load_config, setup_logging
from lib.ai import analyze_with_claude
from lib.markdown import clean_html, sanitize, generate_markdown
from lib.cloud import sync_to_cloud
from lib.miniflux import MinifluxClient


def process_entry(config, entry):
    """处理单篇文章，返回 (文件名, markdown内容) 或 None"""
    title = entry.get('title', 'Untitled')
    raw_content = entry.get('content', '')
    feed_title = entry.get('feed', {}).get('title', '')

    # HTML 转 Markdown
    clean_content = clean_html(raw_content)

    # AI 分析
    ai_result = analyze_with_claude(config, title, clean_content, feed_title)

    # 生成 Markdown
    md = generate_markdown(entry, ai_result, clean_content)

    # 文件名：优先使用 AI 生成的智能标题
    if ai_result and ai_result.get('smart_title'):
        file_title = ai_result['smart_title']
    else:
        file_title = title

    filename = f"📥 {sanitize(file_title)}"
    return filename, md


def sync(config):
    """主同步逻辑"""
    miniflux_config = config['miniflux']
    sync_config = config.get('sync', {})

    temp_path = sync_config.get('temp_path', '/tmp/rss_sync')
    unstar = sync_config.get('unstar_after_sync', True)

    save_dir = Path(temp_path)
    save_dir.mkdir(parents=True, exist_ok=True)

    # 初始化 Miniflux 客户端
    client = MinifluxClient(
        host=miniflux_config['host'],
        api_key=miniflux_config['api_key']
    )

    # 获取加星文章
    limit = sync_config.get('limit', 50)
    entries = client.get_starred_entries(limit)

    if entries is None:
        return 1

    if not entries:
        logging.info("没有加星文章需要同步")
        sync_to_cloud(config, temp_path)
        return 0

    # 处理每篇文章
    success_count = 0
    fail_count = 0
    synced_entries = []
    used_filenames = set()

    for entry in entries:
        try:
            result = process_entry(config, entry)
            if not result:
                fail_count += 1
                continue

            filename, md = result

            # 处理文件名冲突
            base_filename = filename
            counter = 1
            while filename in used_filenames:
                filename = f"{base_filename}_{counter}"
                counter += 1
            used_filenames.add(filename)

            # 保存文件
            filepath = save_dir / f"{filename}.md"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md)

            logging.info(f"✅ 已保存: {filename}")
            success_count += 1
            synced_entries.append(entry)

        except Exception as e:
            title = entry.get('title', 'Unknown')[:50]
            logging.error(f"❌ 保存失败: {title} - {e}")
            fail_count += 1

    logging.info(f"本地保存完成: 成功 {success_count} 篇, 失败 {fail_count} 篇")

    # 云端同步
    cloud_ok = sync_to_cloud(config, temp_path)

    # 取消收藏（仅云端同步成功后）
    if cloud_ok and unstar and synced_entries:
        client.unstar_entries(synced_entries)
    elif not cloud_ok and synced_entries:
        logging.warning("⚠️ 云端同步失败，保留收藏状态，下次继续尝试")

    return 0 if fail_count == 0 else 1


def main():
    """入口函数"""
    parser = argparse.ArgumentParser(description='Miniflux RSS 加星文章同步工具')
    parser.add_argument('-c', '--config', help='配置文件路径', default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config)

    logging.info("=" * 40)
    logging.info("Miniflux RSS 同步开始")

    exit_code = sync(config)

    logging.info("Miniflux RSS 同步结束")
    logging.info("=" * 40)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
