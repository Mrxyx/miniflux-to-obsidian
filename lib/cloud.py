"""rclone 云端同步"""

import logging
import shutil
import subprocess
from pathlib import Path


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
            logging.info("✅ 云端同步成功")
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
