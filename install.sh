#!/bin/bash
#
# Miniflux RSS 同步工具 - 一键部署脚本
# 用法: sudo bash install.sh
#

set -e

# ================= 配置 =================
INSTALL_DIR="/opt/rss-sync"
SERVICE_NAME="rss-sync"
# ========================================

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 检查 root 权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "请使用 root 权限运行此脚本: sudo bash install.sh"
    fi
}

# 检查 Python3
check_python() {
    if ! command -v python3 &> /dev/null; then
        error "未找到 Python3，请先安装: apt install python3 python3-venv"
    fi
    info "Python3 版本: $(python3 --version)"
}

# 检查 rclone
check_rclone() {
    if ! command -v rclone &> /dev/null; then
        warn "未找到 rclone，如需云端同步请安装: curl https://rclone.org/install.sh | sudo bash"
        warn "安装后运行 'rclone config' 配置 OneDrive"
    else
        info "rclone 版本: $(rclone version | head -1)"
        # 检查是否有配置的 remote
        REMOTES=$(rclone listremotes 2>/dev/null || true)
        if [ -z "$REMOTES" ]; then
            warn "rclone 未配置任何 remote，请运行 'rclone config' 添加 OneDrive"
        else
            info "已配置的 remotes: ${REMOTES}"
        fi
    fi
}

# 获取脚本所在目录
get_script_dir() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
}

# 安装到目标目录
install_files() {
    info "安装文件到 ${INSTALL_DIR}..."
    
    mkdir -p "${INSTALL_DIR}"
    
    # 复制文件
    cp "${SCRIPT_DIR}/sync_miniflux.py" "${INSTALL_DIR}/"
    cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
    
    # 如果配置文件不存在，复制示例配置
    if [ ! -f "${INSTALL_DIR}/config.yaml" ]; then
        cp "${SCRIPT_DIR}/config.example.yaml" "${INSTALL_DIR}/config.yaml"
        warn "已创建配置文件 ${INSTALL_DIR}/config.yaml，请修改配置！"
    else
        info "配置文件已存在，跳过"
    fi
}

# 创建 Python 虚拟环境并安装依赖
setup_venv() {
    info "创建 Python 虚拟环境..."
    
    cd "${INSTALL_DIR}"
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    info "安装 Python 依赖..."
    ./venv/bin/pip install --upgrade pip -q
    ./venv/bin/pip install -r requirements.txt -q
}

# 安装 systemd 服务
install_systemd() {
    info "安装 systemd 服务..."
    
    cp "${SCRIPT_DIR}/systemd/rss-sync.service" /etc/systemd/system/
    cp "${SCRIPT_DIR}/systemd/rss-sync.timer" /etc/systemd/system/
    
    systemctl daemon-reload
}

# 启用定时任务
enable_timer() {
    info "启用定时任务..."
    
    systemctl enable ${SERVICE_NAME}.timer
    systemctl start ${SERVICE_NAME}.timer
    
    info "定时任务状态:"
    systemctl status ${SERVICE_NAME}.timer --no-pager || true
}

# 打印使用说明
print_usage() {
    echo ""
    echo "=========================================="
    echo -e "${GREEN}✅ 安装完成！${NC}"
    echo "=========================================="
    echo ""
    echo "📁 安装目录: ${INSTALL_DIR}"
    echo "📝 配置文件: ${INSTALL_DIR}/config.yaml"
    echo ""
    echo "🔧 使用方法:"
    echo "   1. 编辑配置文件:"
    echo "      nano ${INSTALL_DIR}/config.yaml"
    echo ""
    echo "   2. 手动测试运行:"
    echo "      systemctl start ${SERVICE_NAME}.service"
    echo "      journalctl -u ${SERVICE_NAME}.service -f"
    echo ""
    echo "   3. 查看定时任务状态:"
    echo "      systemctl status ${SERVICE_NAME}.timer"
    echo "      systemctl list-timers ${SERVICE_NAME}.timer"
    echo ""
    echo "   4. 停止/启动定时任务:"
    echo "      systemctl stop ${SERVICE_NAME}.timer"
    echo "      systemctl start ${SERVICE_NAME}.timer"
    echo ""
    echo "   5. 查看日志:"
    echo "      journalctl -u ${SERVICE_NAME}.service"
    echo "      tail -f /var/log/rss_sync.log"
    echo ""
}

# 卸载函数
uninstall() {
    warn "正在卸载 ${SERVICE_NAME}..."
    
    systemctl stop ${SERVICE_NAME}.timer 2>/dev/null || true
    systemctl disable ${SERVICE_NAME}.timer 2>/dev/null || true
    
    rm -f /etc/systemd/system/${SERVICE_NAME}.service
    rm -f /etc/systemd/system/${SERVICE_NAME}.timer
    systemctl daemon-reload
    
    read -p "是否删除安装目录 ${INSTALL_DIR}? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "${INSTALL_DIR}"
        info "已删除安装目录"
    fi
    
    info "卸载完成"
    exit 0
}

# 主函数
main() {
    echo ""
    echo "=========================================="
    echo "  Miniflux RSS 同步工具 - 安装脚本"
    echo "=========================================="
    echo ""
    
    # 检查是否卸载
    if [ "$1" = "uninstall" ] || [ "$1" = "--uninstall" ]; then
        check_root
        uninstall
    fi
    
    check_root
    check_python
    check_rclone
    get_script_dir
    install_files
    setup_venv
    install_systemd
    enable_timer
    print_usage
}

main "$@"
