# Miniflux RSS 同步工具

将 Miniflux 中加星的文章自动转换为 Markdown，并通过 rclone 同步到 OneDrive/Obsidian。

## 工作流程

```
Miniflux (加星) → Python 脚本 (HTML→MD) → 临时目录 → rclone → OneDrive/Obsidian
```

## 快速开始

### 1. 前置要求

- VPS / Linux 服务器
- Python 3.8+
- rclone（可选，用于云端同步）

### 2. 安装 rclone（如需云端同步）

```bash
# 安装 rclone
curl https://rclone.org/install.sh | sudo bash

# 配置 OneDrive（按提示操作）
rclone config
# 选择 "onedrive"，完成 OAuth 授权

# 验证配置
rclone lsd onedrive:/
```

### 3. 一键部署

```bash
git clone <your-repo> /tmp/rss-sync
cd /tmp/rss-sync
sudo bash install.sh
```

### 4. 配置

编辑配置文件：

```bash
sudo nano /opt/rss-sync/config.yaml
```

必须修改的配置项：

```yaml
miniflux:
  host: "https://your-miniflux-server.com"
  api_key: "your_api_key_here"  # Miniflux → 设置 → API Keys

rclone:
  enabled: true
  remote: "onedrive:/path/to/your/obsidian/inbox"  # 你的 Obsidian 目录
```

### 5. 测试运行

```bash
# 手动运行一次
sudo systemctl start rss-sync.service

# 查看日志
sudo journalctl -u rss-sync.service -f
```

## 常用命令

```bash
# 查看定时任务状态
systemctl status rss-sync.timer
systemctl list-timers rss-sync.timer

# 停止/启动定时任务
systemctl stop rss-sync.timer
systemctl start rss-sync.timer

# 查看日志
journalctl -u rss-sync.service
tail -f /var/log/rss_sync.log

# 更新到最新版本
cd /path/to/sync-vps && git pull
sudo bash install.sh update

# 卸载
sudo bash install.sh uninstall
```

## 目录结构

```
/opt/rss-sync/
├── sync_miniflux.py    # 主脚本
├── config.yaml         # 配置文件
├── requirements.txt    # Python 依赖
└── venv/               # Python 虚拟环境
```

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `miniflux.host` | Miniflux 服务器地址 | - |
| `miniflux.api_key` | API Key | - |
| `sync.temp_path` | 临时保存目录 | `/root/rss_sync/temp_inbox` |
| `sync.limit` | 每次获取最大文章数 | 50 |
| `sync.unstar_after_sync` | 同步后取消收藏 | true |
| `rclone.enabled` | 是否启用云端同步 | true |
| `rclone.remote` | rclone 目标路径 | - |
| `logging.file` | 日志文件路径 | `/var/log/rss_sync.log` |
| `logging.level` | 日志级别 | INFO |

## 生成的 Markdown 格式

```markdown
---
title: "文章标题"
link: https://example.com/article
source: "RSS 源名称"
published: 2026-01-13
synced: 2026-01-13 10:30:00
tags: [inbox]
status: unread
---

# 文章标题

> 来源: [RSS 源名称](https://example.com/article)

文章正文内容...
```

## 故障排查

### rclone 同步失败

```bash
# 检查 rclone 配置
rclone listremotes
rclone lsd onedrive:/

# 手动测试同步
rclone move /root/rss_sync/temp_inbox onedrive:/your/obsidian/inbox --include "*.md" -v
```

### 权限问题

```bash
# 检查目录权限
ls -la /root/rss_sync/
ls -la /root/.config/rclone/
```

## License

MIT
