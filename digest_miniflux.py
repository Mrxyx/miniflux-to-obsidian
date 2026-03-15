#!/usr/bin/env python3
"""
Miniflux AI 导读服务
全量扫描未读文章，筛选未处理的，生成中文导读并回写到文章内容顶部
"""

import argparse
import fcntl
import logging
import signal
import sys
import time
from pathlib import Path

from lib.config import load_config, setup_logging
from lib.miniflux import MinifluxClient
from lib.digest import generate_digest, build_digest_html, has_digest


LOCK_FILE = Path(__file__).resolve().parent / "digest.lock"

# 软超时 5 分钟
MAX_RUNTIME_SEC = 300

# 优雅退出标志
_shutdown = False


def handle_sigterm(sig, frame):
    global _shutdown
    logging.info("收到 SIGTERM，准备优雅退出")
    _shutdown = True


def scan_unread_entries(client, start_time):
    """全量扫描所有未读文章，返回需要处理的 entry 列表。
    使用 after_entry_id 游标分页（不持久化，仅用于单次扫描翻页）。
    扫描成本极低（几秒 + 几次 API 调用）。
    """
    todo = []
    last_id = None
    page_size = 100
    # 扫描阶段最多用一半时间
    scan_timeout = MAX_RUNTIME_SEC * 0.5

    while True:
        if _shutdown:
            break
        if time.monotonic() - start_time > scan_timeout:
            logging.warning("扫描阶段超时，使用已扫描结果")
            break

        entries = client.get_entries(
            limit=page_size,
            status="unread",
            after_entry_id=last_id,
        )
        if entries is None:
            logging.error("API 请求失败，终止扫描")
            return None
        if not entries:
            break

        last_id = entries[-1]['id']

        for entry in entries:
            content = entry.get('content', '')
            if has_digest(content):
                continue
            if not content or not content.strip():
                continue
            todo.append(entry)

    return todo


def process_entries(config, client, entries, start_time):
    """逐篇处理文章，生成导读并回写。超时或收到 SIGTERM 则提前退出。"""
    claude_config = config.get('claude', {})
    success = 0
    fail = 0

    for entry in entries:
        # 超时或退出信号检查
        if _shutdown or time.monotonic() - start_time > MAX_RUNTIME_SEC:
            logging.info("超时或收到退出信号，停止处理")
            break

        entry_id = entry['id']
        title = entry.get('title', 'Untitled')
        content = entry.get('content', '')
        feed_title = entry.get('feed', {}).get('title', '')

        # 二次检查：扫描到处理之间可能已被其他途径处理
        if has_digest(content):
            continue

        digest_result = generate_digest(claude_config, title, content, feed_title)
        if not digest_result:
            logging.warning(f"导读生成失败: {title[:50]}")
            fail += 1
            continue

        digest_html = build_digest_html(digest_result)
        new_content = digest_html + content

        if client.update_entry_content(entry_id, new_content):
            logging.info(f"✅ 导读已写入: {title[:50]}")
            success += 1
        else:
            logging.error(f"❌ 回写失败: {title[:50]}")
            fail += 1

        # 限速
        time.sleep(1)

    return success, fail


def run_digest(config):
    """主逻辑：全量扫描未读 → 筛选未处理 → 生成导读 → 回写"""
    miniflux_config = config['miniflux']
    digest_config = config.get('digest', {})
    max_process = digest_config.get('max_process_per_run', 30)

    client = MinifluxClient(
        host=miniflux_config['host'],
        api_key=miniflux_config['api_key']
    )

    start_time = time.monotonic()

    # 阶段 1：全量扫描，筛选出需要处理的文章
    logging.info("扫描未读文章...")
    todo = scan_unread_entries(client, start_time)

    if todo is None:
        return 1
    if not todo:
        logging.info("所有未读文章均已有导读")
        return 0

    # 截取本轮最多处理的数量
    batch = todo[:max_process]
    scan_time = time.monotonic() - start_time

    logging.info(f"扫描完成 ({scan_time:.1f}s): 待处理 {len(todo)} 篇, 本轮处理 {len(batch)} 篇")

    # 阶段 2：逐篇生成导读并回写
    success, fail = process_entries(config, client, batch, start_time)

    logging.info(f"本轮完成: 成功 {success}, 失败 {fail}, 剩余待处理 {len(todo) - success}")
    return 0 if fail == 0 else 1


def main():
    parser = argparse.ArgumentParser(description='Miniflux AI 导读生成服务')
    parser.add_argument('-c', '--config', help='配置文件路径', default=None)
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

    # 注册 SIGTERM 处理
    signal.signal(signal.SIGTERM, handle_sigterm)

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
