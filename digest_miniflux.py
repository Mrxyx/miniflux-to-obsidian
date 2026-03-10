#!/usr/bin/env python3
"""
Miniflux AI 导读服务
定时轮询 Miniflux 未处理文章，生成中文导读并回写到文章内容顶部
"""

import argparse
import fcntl
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

from lib.config import load_config, setup_logging
from lib.miniflux import MinifluxClient
from lib.digest import generate_digest, build_digest_html, has_digest


# 状态文件：记录上次处理到的 entry_id，避免重复处理
STATE_FILE = Path(__file__).resolve().parent / "digest_state.json"
LOCK_FILE = Path(__file__).resolve().parent / "digest.lock"


def load_state():
    """加载处理状态"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"last_entry_id": 0, "processed_count": 0}


def save_state(state):
    """原子写入处理状态：write-to-temp + os.replace()"""
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=STATE_FILE.parent, suffix='.tmp', prefix='digest_state_'
        )
        with os.fdopen(fd, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, STATE_FILE)
    except OSError as e:
        logging.warning(f"保存状态失败: {e}")
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def process_entries(config, client, entries):
    """处理一批文章，生成导读并回写"""
    claude_config = config.get('claude', {})
    success = 0
    skip = 0
    fail = 0

    for entry in entries:
        entry_id = entry['id']
        title = entry.get('title', 'Untitled')
        content = entry.get('content', '')
        feed_title = entry.get('feed', {}).get('title', '')

        # 已有导读标记，跳过（不调 AI）
        if has_digest(content):
            skip += 1
            continue

        # 内容为空，跳过
        if not content or not content.strip():
            logging.info(f"跳过（内容为空）: {title[:50]}")
            skip += 1
            continue

        # 生成导读
        digest_result = generate_digest(claude_config, title, content, feed_title)
        if not digest_result:
            logging.warning(f"导读生成失败: {title[:50]}")
            fail += 1
            continue

        # 拼接：导读 HTML + 原始内容
        digest_html = build_digest_html(digest_result)
        new_content = digest_html + content

        # 回写到 Miniflux
        if client.update_entry_content(entry_id, new_content):
            logging.info(f"✅ 导读已写入: {title[:50]}")
            success += 1
        else:
            logging.error(f"❌ 回写失败: {title[:50]}")
            fail += 1

        # 限速
        time.sleep(1)

    return success, skip, fail


def run_digest(config):
    """主逻辑：拉取未读文章 → 生成导读 → 回写
    不使用游标，每轮直接查 unread 文章，靠 HTML 标记做幂等。
    """
    miniflux_config = config['miniflux']
    digest_config = config.get('digest', {})

    batch_size = digest_config.get('batch_size', 20)

    client = MinifluxClient(
        host=miniflux_config['host'],
        api_key=miniflux_config['api_key']
    )

    # 直接拉取未读且没有导读标记的文章
    # Miniflux API 不支持按内容过滤，所以拉一批 unread，代码侧跳过已有标记的
    logging.info(f"拉取未读文章 (limit={batch_size})...")
    entries = client.get_entries(
        limit=batch_size,
        status="unread",
    )

    if entries is None:
        logging.error("获取文章失败")
        return 1

    if not entries:
        logging.info("没有新文章需要处理")
        return 0

    logging.info(f"获取到 {len(entries)} 篇文章，开始生成导读...")

    success, skip, fail = process_entries(config, client, entries)

    logging.info(f"本轮完成: 成功 {success}, 跳过 {skip}, 失败 {fail}")
    return 0 if fail == 0 else 1


def main():
    parser = argparse.ArgumentParser(description='Miniflux AI 导读生成服务')
    parser.add_argument('-c', '--config', help='配置文件路径', default=None)
    parser.add_argument('--reset', action='store_true', help='重置处理状态，从头开始')
    args = parser.parse_args()

    config = load_config(args.config)

    # 导读服务使用独立日志文件
    digest_config = config.get('digest', {})
    digest_log = digest_config.get('log_file', '')
    if digest_log:
        config = dict(config)
        config['logging'] = dict(config.get('logging', {}))
        config['logging']['file'] = digest_log

    setup_logging(config)

    if args.reset:
        logging.info("reset 参数已废弃，当前版本不使用游标")

    # 文件锁：防止多个实例并发运行
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logging.info("另一个实例正在运行，跳过本轮")
        lock_fd.close()
        sys.exit(0)

    try:
        logging.info("=" * 40)
        logging.info("Miniflux AI 导读服务开始")

        exit_code = run_digest(config)

        logging.info("Miniflux AI 导读服务结束")
        logging.info("=" * 40)

        sys.exit(exit_code)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


if __name__ == "__main__":
    main()
