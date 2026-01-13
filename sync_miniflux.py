#!/usr/bin/env python3
"""
Miniflux RSS 加星文章同步脚本
将 Miniflux 中收藏的文章同步为本地 Markdown 文件，并通过 rclone 同步到云端
"""

import requests
import re
import logging
import sys
import subprocess
import shutil
import html2text
import yaml
from datetime import datetime
from pathlib import Path

# 脚本所在目录
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_config(config_path=None):
    """加载配置文件"""
    config_file = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    
    if not config_file.exists():
        print(f"❌ 配置文件不存在: {config_file}")
        print(f"   请复制 config.example.yaml 为 config.yaml 并修改配置")
        sys.exit(1)
    
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def setup_logging(config):
    """配置日志"""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO').upper(), logging.INFO)
    log_file = log_config.get('file', '')
    
    handlers = [logging.StreamHandler()]
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )


def clean_html(html):
    """将 HTML 转换为 Markdown"""
    if not html:
        return ""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.body_width = 0
    return h.handle(html)


def sanitize(title):
    """清理文件名中的非法字符"""
    return re.sub(r'[<>:"/\\|?*\n\r\t]', ' ', title).strip()[:80]


def escape_yaml_string(s):
    """转义 YAML 字符串中的特殊字符"""
    if not s:
        return ""
    # 替换反斜杠和双引号
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    return s


def sync_to_cloud(config, temp_path):
    """通过 rclone 将本地文件同步到云端"""
    rclone_config = config.get('rclone', {})
    
    if not rclone_config.get('enabled', False):
        logging.debug("rclone 同步未启用，跳过")
        return True
    
    remote = rclone_config.get('remote', '')
    if not remote:
        logging.warning("⚠️ rclone remote 未配置")
        return False
    
    # 检查 rclone 是否安装
    if not shutil.which('rclone'):
        logging.error("❌ rclone 未安装或不在 PATH 中")
        return False
    
    # 检查临时目录是否有文件需要同步
    temp_dir = Path(temp_path)
    files = list(temp_dir.glob('*.md'))
    if not files:
        logging.debug("没有文件需要同步到云端")
        return True
    
    logging.info(f"正在同步 {len(files)} 个文件到 {remote}...")
    
    try:
        result = subprocess.run(
            ['rclone', 'move', str(temp_dir), remote, '--include', '*.md', '-v'],
            capture_output=True,
            text=True,
            timeout=300  # 5 分钟超时
        )
        
        if result.returncode == 0:
            logging.info(f"✅ 云端同步成功")
            return True
        else:
            logging.error(f"❌ rclone 同步失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logging.error("❌ rclone 同步超时 (5分钟)")
        return False
    except Exception as e:
        logging.warning(f"⚠️ 云端同步失败（文件已保存本地）: {e}")
        return False


def sync(config):
    """主同步逻辑"""
    miniflux_config = config['miniflux']
    sync_config = config.get('sync', {})
    
    host = miniflux_config['host'].rstrip('/')
    api_key = miniflux_config['api_key']
    temp_path = sync_config.get('temp_path', '/tmp/rss_sync')
    limit = sync_config.get('limit', 50)
    unstar = sync_config.get('unstar_after_sync', True)
    
    save_dir = Path(temp_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    
    headers = {
        "X-Auth-Token": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        logging.info(f"正在获取加星文章 (limit={limit})...")
        resp = requests.get(
            f"{host}/v1/entries?starred=true&limit={limit}",
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        entries = resp.json().get('entries', [])
    except requests.RequestException as e:
        logging.error(f"获取文章失败: {e}")
        return 1
    
    if not entries:
        logging.info("没有加星文章需要同步")
        # 仍然尝试同步遗留文件
        sync_to_cloud(config, temp_path)
        return 0
    
    logging.info(f"找到 {len(entries)} 篇加星文章")
    success_count = 0
    fail_count = 0
    synced_entries = []  # 记录成功保存的 entry，用于后续取消收藏
    
    for entry in entries:
        try:
            title = entry.get('title', 'Untitled')
            content = clean_html(entry.get('content', ''))
            url = entry.get('url', '')
            feed = entry.get('feed', {}).get('title', '')
            published = entry.get('published_at', '')[:10] if entry.get('published_at') else ''
            entry_id = entry.get('id', '')
            
            # 生成 Markdown（转义 YAML 特殊字符）
            md = f"""---
title: "{escape_yaml_string(title)}"
link: {url}
source: "{escape_yaml_string(feed)}"
published: {published}
synced: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
tags: [inbox]
status: unread
---

# {title}

> 来源: [{feed}]({url})

{content}
"""
            # 保存到本地临时目录（文件名加入 entry_id 避免冲突）
            filename = f"{sanitize(title)}_{entry_id}.md"
            filepath = save_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md)
            
            logging.info(f"✅ 已保存: {title[:50]}")
            success_count += 1
            synced_entries.append(entry)
            
        except Exception as e:
            logging.error(f"❌ 保存失败: {title[:50]} - {e}")
            fail_count += 1
    
    logging.info(f"本地保存完成: 成功 {success_count} 篇, 失败 {fail_count} 篇")
    
    # 同步到云端（无论本次是否有新文章，都尝试同步遗留文件）
    cloud_ok = sync_to_cloud(config, temp_path)
    
    # 只有云端同步成功后才取消收藏（防止文章丢失）
    if cloud_ok and unstar and synced_entries:
        logging.info(f"正在取消 {len(synced_entries)} 篇文章的收藏...")
        for entry in synced_entries:
            try:
                requests.put(
                    f"{host}/v1/entries/{entry['id']}/bookmark",
                    headers=headers,
                    timeout=10
                )
            except Exception as e:
                logging.warning(f"⚠️ 取消收藏失败: {entry.get('title', '')[:30]} - {e}")
        logging.info("✅ 收藏已取消")
    elif not cloud_ok and synced_entries:
        logging.warning("⚠️ 云端同步失败，保留收藏状态，下次继续尝试")
    
    return 0 if fail_count == 0 else 1


def main():
    """入口函数"""
    import argparse
    
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
