#!/usr/bin/env bash
# =============================================================================
# GitLab API 通用请求封装
# 用法: source scripts/gitlab-api.sh
#
# 依赖环境变量:
#   GITLAB_HOST  - GitLab 实例地址，默认 https://gitlab.example.com
#   GITLAB_TOKEN - GitLab Personal Access Token（必填）
#
# 提供的函数:
#   gitlab_api_get <endpoint>         - GET 请求，自动分页，返回合并后的 JSON 数组
#   gitlab_api_get_single <endpoint>  - GET 请求，返回单页 JSON（非数组）
#   check_gitlab_token                - 校验 Token 是否已配置
#   urlencode <string>                - URL 编码
# =============================================================================

set -euo pipefail

# --- 配置 ---
GITLAB_HOST="${GITLAB_HOST:-https://gitlab.example.com}"
GITLAB_API_BASE="${GITLAB_HOST}/api/v4"
PER_PAGE=100

# --- 颜色定义 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*" >&2; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# =============================================================================
# 校验 Token
# =============================================================================
check_gitlab_token() {
    if [ -z "${GITLAB_TOKEN:-}" ]; then
        log_error "未设置 GITLAB_TOKEN 环境变量"
        log_error "请在终端执行: export GITLAB_TOKEN=\"your-token-here\""
        log_error "获取 Token: ${GITLAB_HOST}/-/profile/personal_access_tokens"
        log_error "需要的权限: read_api, read_repository"
        return 1
    fi
    return 0
}

# =============================================================================
# URL 编码（简化版，处理 / 和特殊字符）
# =============================================================================
urlencode() {
    local input="$1"
    # 先替换 % 防止二次编码
    input="${input//%/%%}"
    # 用 Python 做 URL 编码（macOS 兼容）
    python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$input" 2>/dev/null || {
        # 降级: 仅处理最常见的 /
        echo "${input//\//%2F}"
    }
}

# =============================================================================
# 核心请求函数: 分页 GET
# =============================================================================
gitlab_api_get() {
    local endpoint="$1"
    local page=1
    local result=""
    local total_pages=1

    # 智能选择分隔符：endpoint 已含 ? 则用 &，否则用 ?
    local join_char="?"
    if [[ "$endpoint" == *"?"* ]]; then
        join_char="&"
    fi

    while [ "$page" -le "$total_pages" ]; do
        local url="${GITLAB_API_BASE}${endpoint}${join_char}per_page=${PER_PAGE}&page=${page}"
        local response

        response=$(curl -s -w "\n%{http_code}" \
            --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
            --header "Content-Type: application/json" \
            "$url" 2>/dev/null) || {
            log_error "GitLab API 请求失败: $url"
            return 1
        }

        local http_code
        http_code=$(echo "$response" | tail -1)
        local body
        body=$(echo "$response" | sed '$d')

        if [ "$http_code" != "200" ]; then
            log_error "GitLab API 返回 HTTP ${http_code}: ${url}"
            log_error "响应: $(echo "$body" | head -c 500)"
            return 1
        fi

        # 提取总页数（从响应头，如果 curl 支持 -i）
        local total_header
        total_header=$(curl -s -I \
            --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
            "$url" 2>/dev/null | grep -i "x-total-pages:" | awk '{print $2}' | tr -d '\r' || echo "1")
        total_pages="${total_header:-1}"

        if [ "$page" -eq 1 ]; then
            result="$body"
        else
            # 合并 JSON 数组: 去掉首个 [ 和最后 ]，追加
            local body_trimmed
            body_trimmed=$(echo "$body" | sed 's/^\[//' | sed 's/\]$//')
            if [ -n "$body_trimmed" ]; then
                result="${result%\]},${body_trimmed}]"
            fi
        fi

        page=$((page + 1))
    done

    echo "$result"
}

# =============================================================================
# 单页 GET（用于非数组返回值）
# =============================================================================
gitlab_api_get_single() {
    local endpoint="$1"
    local url="${GITLAB_API_BASE}${endpoint}"
    local response

    response=$(curl -s -w "\n%{http_code}" \
        --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
        --header "Content-Type: application/json" \
        "$url" 2>/dev/null) || {
        log_error "GitLab API 请求失败: $url"
        return 1
    }

    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" != "200" ]; then
        log_error "GitLab API 返回 HTTP ${http_code}: ${url}"
        log_error "响应: $(echo "$body" | head -c 500)"
        return 1
    fi

    echo "$body"
}

# =============================================================================
# 获取 Pipeline Job 的日志（截取最后 N 行）
# =============================================================================
gitlab_get_job_trace() {
    local project_id="$1"
    local job_id="$2"
    local lines="${3:-200}"

    local endpoint="/projects/${project_id}/jobs/${job_id}/trace"
    local url="${GITLAB_API_BASE}${endpoint}"

    curl -s --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" "$url" 2>/dev/null | tail -"$lines"
}
