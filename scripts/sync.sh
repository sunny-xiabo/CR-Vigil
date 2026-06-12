#!/usr/bin/env bash
# =============================================================================
# CR-Vigil 团队同步脚本
# 用法:
#   scripts/sync.sh pull         拉取团队最新数据
#   scripts/sync.sh push "msg"   推送本地数据到团队仓库
#   scripts/sync.sh auto "msg"   pull → 执行命令 → push（一步完成）
#
# 环境变量:
#   CRVIGIL_MODE=team (默认)  启用自动同步
#   CRVIGIL_MODE=personal     跳过同步，数据仅本地保留
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[SYNC]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[SYNC]${NC} $*"; }
log_error() { echo -e "${RED}[SYNC]${NC} $*"; }

SYNC_FILES="data/pr-registry.json reports/"

# =============================================================================
# 检查是否应该同步
# =============================================================================
should_sync() {
    if [ "${CRVIGIL_MODE:-team}" = "personal" ]; then
        log_info "个人模式，跳过同步"
        return 1
    fi
    if ! git remote get-url origin &>/dev/null; then
        log_warn "未配置 Git 远程仓库，跳过同步"
        return 1
    fi
    return 0
}

# =============================================================================
# 拉取
# =============================================================================
do_pull() {
    should_sync || return 0

    log_info "正在拉取团队最新数据..."

    # 暂存本地未提交的变更
    if ! git diff --quiet -- $SYNC_FILES 2>/dev/null; then
        git stash push -- $SYNC_FILES 2>/dev/null || true
        local stashed=true
    else
        local stashed=false
    fi

    # 拉取
    if git pull --rebase origin master 2>/dev/null; then
        log_info "拉取成功"
    else
        log_warn "拉取时出现冲突或失败，请手动处理"
        if [ "$stashed" = true ]; then
            git stash pop 2>/dev/null || true
        fi
        return 1
    fi

    # 恢复暂存
    if [ "$stashed" = true ]; then
        git stash pop 2>/dev/null || log_warn "本地变更与远程冲突，请在编辑器中解决"
    fi
}

# =============================================================================
# 推送
# =============================================================================
do_push() {
    should_sync || return 0
    local msg="${1:-CR-Vigil: sync data and reports}"

    log_info "正在推送数据到团队仓库..."

    git add $SYNC_FILES 2>/dev/null || true

    if git diff --cached --quiet 2>/dev/null; then
        log_info "无变更需要推送"
        return 0
    fi

    git commit -m "$msg" 2>/dev/null || true

    if git push origin master 2>/dev/null; then
        log_info "推送成功"
    else
        log_warn "推送失败，请先执行 sync pull 获取最新数据后重试"
        return 1
    fi
}

# =============================================================================
# 一键同步：pull → 执行命令 → push
# =============================================================================
do_auto() {
    should_sync || {
        shift 2>/dev/null || true
        return 0
    }
    local msg="${1:-CR-Vigil: auto sync}"
    shift 2>/dev/null || true

    do_pull
    log_info "同步完成，数据已就绪"
}

# =============================================================================
# 主入口
# =============================================================================
case "${1:-}" in
    pull)
        do_pull
        ;;
    push)
        do_push "${2:-}"
        ;;
    auto)
        do_auto "${2:-}"
        ;;
    *)
        echo "用法: $0 {pull|push|auto}"
        echo ""
        echo "  pull          拉取团队最新数据"
        echo '  push "msg"    推送本地数据到团队仓库'
        echo '  auto "msg"    pull 后自动 push（配合 Skill 使用）'
        echo ""
        echo "环境变量:"
        echo "  CRVIGIL_MODE=team      团队模式（默认），启用同步"
        echo "  CRVIGIL_MODE=personal  个人模式，跳过同步"
        exit 1
        ;;
esac
