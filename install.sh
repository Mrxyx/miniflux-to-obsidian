#!/bin/bash
#
# Miniflux RSS 同步工具 - 一键部署脚本
# 用法: 
#   安装: sudo bash install.sh
#   更新: sudo bash install.sh update
#   卸载: sudo bash install.sh uninstall
#

set -e

# ================= 配置 =================
INSTALL_DIR="/opt/rss-sync"
SERVICE_NAME="rss-sync"
GITHUB_REPO="https://github.com/Mrxyx/miniflux-to-obsidian.git"
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
    
    # 复制 lib 目录
    if [ -d "${SCRIPT_DIR}/lib" ]; then
        cp -r "${SCRIPT_DIR}/lib" "${INSTALL_DIR}/"
    fi
    
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

# 更新函数
update() {
    info "正在更新 ${SERVICE_NAME}..."
    
    # 检查安装目录是否存在
    if [ ! -d "${INSTALL_DIR}" ]; then
        error "未找到安装目录 ${INSTALL_DIR}，请先运行安装"
    fi
    
    # 创建临时目录
    TMP_DIR=$(mktemp -d)
    trap "rm -rf ${TMP_DIR}" EXIT
    
    # 从 GitHub 克隆最新代码
    info "从 GitHub 拉取最新代码..."
    if ! git clone --depth 1 "${GITHUB_REPO}" "${TMP_DIR}" 2>/dev/null; then
        # 如果 GITHUB_REPO 未配置，尝试从当前目录更新
        if [ -f "${SCRIPT_DIR}/sync_miniflux.py" ]; then
            info "使用本地代码更新..."
            TMP_DIR="${SCRIPT_DIR}"
        else
            error "无法获取更新，请检查 GITHUB_REPO 配置或从代码目录运行"
        fi
    fi
    
    # 备份当前配置
    if [ -f "${INSTALL_DIR}/config.yaml" ]; then
        cp "${INSTALL_DIR}/config.yaml" "${INSTALL_DIR}/config.yaml.bak"
        info "已备份配置文件"
    fi
    
    # 更新脚本文件
    info "更新脚本文件..."
    cp "${TMP_DIR}/sync_miniflux.py" "${INSTALL_DIR}/"
    cp "${TMP_DIR}/requirements.txt" "${INSTALL_DIR}/"
    
    # 复制 lib 目录（如果存在）
    if [ -d "${TMP_DIR}/lib" ]; then
        rm -rf "${INSTALL_DIR}/lib"
        cp -r "${TMP_DIR}/lib" "${INSTALL_DIR}/"
        info "已更新 lib 模块"
    fi
    
    # 检查配置文件是否有新增配置项
    if [ -f "${TMP_DIR}/config.example.yaml" ]; then
        cp "${TMP_DIR}/config.example.yaml" "${INSTALL_DIR}/config.example.yaml"
    fi
    
    # 更新 systemd 配置
    info "更新 systemd 配置..."
    cp "${TMP_DIR}/systemd/rss-sync.service" /etc/systemd/system/
    cp "${TMP_DIR}/systemd/rss-sync.timer" /etc/systemd/system/
    systemctl daemon-reload
    
    # 更新 Python 依赖
    info "更新 Python 依赖..."
    cd "${INSTALL_DIR}"
    ./venv/bin/pip install -r requirements.txt -q
    
    # 重启定时任务
    info "重启定时任务..."
    systemctl restart ${SERVICE_NAME}.timer
    
    echo ""
    echo "=========================================="
    echo -e "${GREEN}✅ 更新完成！${NC}"
    echo "=========================================="
    echo ""
    echo "📝 配置文件保留在: ${INSTALL_DIR}/config.yaml"
    echo "📦 备份文件: ${INSTALL_DIR}/config.yaml.bak"
    echo ""
    echo -e "${YELLOW}⚠️  请检查是否有新增配置项：${NC}"
    echo "   diff ${INSTALL_DIR}/config.yaml ${INSTALL_DIR}/config.example.yaml"
    echo ""
    echo "🔧 测试运行:"
    echo "   systemctl start ${SERVICE_NAME}.service"
    echo "   journalctl -u ${SERVICE_NAME}.service -f"
    echo ""
    
    exit 0
}

# 显示帮助
show_help() {
    echo "用法: sudo bash install.sh [命令]"
    echo ""
    echo "命令:"
    echo "  (无)        首次安装"
    echo "  update      更新到最新版本"
    echo "  uninstall   卸载服务"
    echo "  help        显示此帮助"
    echo ""
    exit 0
}

# 主函数
main() {
    echo ""
    echo "=========================================="
    echo "  Miniflux RSS 同步工具 - 安装脚本"
    echo "=========================================="
    echo ""
    
    get_script_dir
    
    case "$1" in
        uninstall|--uninstall)
            check_root
            uninstall
            ;;
        update|--update)
            check_root
            update
            ;;
        help|--help|-h)
            show_help
            ;;
        "")
            check_root
            check_python
            check_rclone
            install_files
            setup_venv
            install_systemd
            enable_timer
            print_usage
            ;;
        *)
            error "未知命令: $1\n运行 'bash install.sh help' 查看帮助"
            ;;
    esac
}

main "$@"
