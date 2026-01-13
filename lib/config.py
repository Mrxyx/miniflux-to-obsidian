"""配置加载与日志设置"""

import logging
import sys
import yaml
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
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
