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
curl -sL https://raw.githubusercontent.com/Mrxyx/miniflux-to-obsidian/main/install.sh | sudo bash
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
# 更新到最新版本（一条命令）
rss-sync-update

# 查看定时任务状态
systemctl status rss-sync.timer
systemctl list-timers rss-sync.timer

# 停止/启动定时任务
systemctl stop rss-sync.timer
systemctl start rss-sync.timer

# 查看日志
journalctl -u rss-sync.service
tail -f /var/log/rss_sync.log

# 卸载
curl -sL https://raw.githubusercontent.com/Mrxyx/miniflux-to-obsidian/main/install.sh | sudo bash -s uninstall
```

## 目录结构

```
/opt/rss-sync/
├── sync_miniflux.py      # 主脚本
├── lib/                  # 功能模块
│   ├── ai.py             # Claude AI 分析
│   ├── cloud.py          # rclone 云端同步
│   ├── config.py         # 配置加载
│   ├── markdown.py       # Markdown 生成
│   └── miniflux.py       # Miniflux API
├── config.yaml           # 配置文件
├── config.example.yaml   # 配置示例
├── requirements.txt      # Python 依赖
└── venv/                 # Python 虚拟环境
```

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `miniflux.host` | Miniflux 服务器地址 | - |
| `miniflux.api_key` | API Key | - |
| `claude.enabled` | 是否启用 AI 分析 | false |
| `claude.base_url` | API 地址（留空用官方） | - |
| `claude.api_key` | Claude API Key | - |
| `claude.model` | 模型名称 | claude-sonnet-4-20250514 |
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
source: Miniflux
imported: 2026-01-13
tags: [inbox]
original_url: "https://example.com/article"
author: "作者名"
feed: "RSS 源名称"
published: 2026-01-13
---

# 文章标题

> 来源: [RSS 源名称](https://example.com/article)

> [!ai]- AI 初筛（点击展开）
> **摘要**：文章摘要内容
> **主题**：AI/LLM, 编程/开发
> **收藏原因**：猜测用户收藏原因

## 原始内容

文章正文内容...

## 阅读状态
- [ ] 未读
- [ ] 已快速扫读
- [ ] 已精读

## 备注

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
