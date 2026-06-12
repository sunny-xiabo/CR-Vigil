#!/usr/bin/env bash
# =============================================================================
# GitLab MR 数据采集脚本
# 用法: ./scripts/collect-mr-data.sh <MR_URL>
#
# 示例: ./scripts/collect-mr-data.sh \
#         https://gitlab.example.com/your-group/your-project/-/merge_requests/27
#
# 输出: 标准 JSON Schema 的 PR 数据写入 data/pr-registry.json
#       并输出采集摘要到 stdout
#
# 依赖环境变量:
#   GITLAB_TOKEN  - GitLab Personal Access Token（必填）
#   GITLAB_HOST   - GitLab 实例地址（可选，从 MR URL 自动解析）
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 加载通用 API 函数
source "${SCRIPT_DIR}/gitlab-api.sh"

# 输出文件
REGISTRY_FILE="${PROJECT_ROOT}/data/pr-registry.json"
TEMP_DIR="${PROJECT_ROOT}/data/tmp"

# =============================================================================
# 解析 MR URL
# =============================================================================
parse_mr_url() {
    local url="$1"

    # 格式: https://<host>/<project_path>/-/merge_requests/<iid>
    # 示例: https://gitlab.example.com/your-group/your-project/-/merge_requests/27

    # 提取 host
    MR_HOST=$(echo "$url" | sed -E 's|https?://([^/]+)/.*|\1|')
    MR_HOST="https://${MR_HOST}"

    # 提取 /-/merge_requests/ 之前的部分作为 project_path
    MR_PROJECT_PATH=$(echo "$url" | sed -E 's|https?://[^/]+/(.*)/-/merge_requests/.*|\1|')

    # 提取 merge_requests 后面的数字作为 IID
    MR_IID=$(echo "$url" | sed -E 's|.*/merge_requests/([0-9]+).*|\1|')

    if [ -z "$MR_PROJECT_PATH" ] || [ -z "$MR_IID" ]; then
        log_error "无法解析 MR URL: $url"
        log_error "期望格式: https://<host>/<project_path>/-/merge_requests/<iid>"
        return 1
    fi

    log_info "GitLab 实例: $MR_HOST"
    log_info "项目路径:   $MR_PROJECT_PATH"
    log_info "MR 编号:    $MR_IID"

    # 覆盖全局 GITLAB_HOST（用 URL 中的 host）
    GITLAB_HOST="$MR_HOST"
    GITLAB_API_BASE="${GITLAB_HOST}/api/v4"

    # URL 编码 project_path
    PROJECT_ID=$(urlencode "$MR_PROJECT_PATH")
    log_info "项目 ID:    $PROJECT_ID"
}

# =============================================================================
# 解析 CI 模式配置
# =============================================================================
resolve_ci_mode() {
    log_info "正在解析 CI 模式配置..."

    # 默认值
    CI_MODE="auto"

    # 优先级 1: 按项目配置 CRVIGIL_CI_MODE_MAP
    if [ -n "${CRVIGIL_CI_MODE_MAP:-}" ]; then
        # 用项目短名称匹配（URL 最后一段）
        local project_short
        project_short=$(echo "$MR_PROJECT_PATH" | awk -F/ '{print $NF}')
        local mapped_mode
        mapped_mode=$(echo "$CRVIGIL_CI_MODE_MAP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('${project_short}',''))" 2>/dev/null || echo "")
        if [ -n "$mapped_mode" ] && [ "$mapped_mode" != "null" ]; then
            CI_MODE="$mapped_mode"
            log_info "  按项目配置 (CRVIGIL_CI_MODE_MAP): $project_short -> $CI_MODE"
            return
        fi
    fi

    # 优先级 2: 全局配置 CRVIGIL_CI_MODE
    if [ -n "${CRVIGIL_CI_MODE:-}" ]; then
        CI_MODE="$CRVIGIL_CI_MODE"
        log_info "  按全局配置 (CRVIGIL_CI_MODE): $CI_MODE"
        return
    fi

    log_info "  使用默认模式: $CI_MODE"
}

# =============================================================================
# 自动检测 CI 管线是否存在
# =============================================================================
auto_detect_ci() {
    # 在 collect_pipeline_data 之后调用
    # 根据 CI 数据的有无自动判定
    if [ "$CI_MODE" != "auto" ]; then
        return
    fi

    local has_ci="false"

    # 检查是否有流水线 URL
    if [ -n "$PIPELINE_URL" ]; then
        has_ci="true"
    fi

    # 检查是否有单元测试数据
    if [ "$UT_TOTAL" -gt 0 ] 2>/dev/null; then
        has_ci="true"
    fi

    # 检查是否有冒烟测试数据
    if [ "$SMOKE_TOTAL" -gt 0 ] 2>/dev/null; then
        has_ci="true"
    fi

    if [ "$has_ci" = "true" ]; then
        CI_MODE="enabled"
        log_info "CI 自动检测: 发现 CI 数据 -> 模式切换为 enabled"
    else
        CI_MODE="disabled"
        log_info "CI 自动检测: 未发现 CI 数据 -> 模式切换为 disabled（门禁一将标记为 N/A）"
    fi
}

# =============================================================================
# 采集 MR 元信息
# =============================================================================
collect_mr_metadata() {
    log_info "正在获取 MR 元信息..."

    local mr_json
    mr_json=$(gitlab_api_get_single "/projects/${PROJECT_ID}/merge_requests/${MR_IID}") || return 1

    MR_TITLE=$(echo "$mr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['title'])" 2>/dev/null || echo "")
    MR_AUTHOR=$(echo "$mr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['author']['name'])" 2>/dev/null || echo "")
    MR_CREATED=$(echo "$mr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['created_at'])" 2>/dev/null || echo "")
    MR_UPDATED=$(echo "$mr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['updated_at'])" 2>/dev/null || echo "")
    MR_STATE=$(echo "$mr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])" 2>/dev/null || echo "")
    MR_WEB_URL=$(echo "$mr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['web_url'])" 2>/dev/null || echo "$url")
    MR_DESCRIPTION=$(echo "$mr_json" | python3 -c "import sys,json; print(json.load(sys.stdin).get('description',''))" 2>/dev/null || echo "")
    MR_SOURCE_BRANCH=$(echo "$mr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['source_branch'])" 2>/dev/null || echo "")
    MR_TARGET_BRANCH=$(echo "$mr_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['target_branch'])" 2>/dev/null || echo "")

    # 保存完整 JSON 备用
    echo "$mr_json" > "${TEMP_DIR}/mr_full.json"

    log_info "  MR 标题: $MR_TITLE"
    log_info "  作者:    $MR_AUTHOR"
    log_info "  状态:    $MR_STATE"
    log_info "  分支:    $MR_SOURCE_BRANCH -> $MR_TARGET_BRANCH"
}

# =============================================================================
# 解析 AI 声明
# =============================================================================
parse_ai_declaration() {
    local desc="$1"
    log_info "正在解析 AI 声明..."

    # 初始化默认值
    AI_USED="false"
    AI_DECLARED="false"
    AI_PERCENTAGE=0
    AI_TOOLS="未知"
    AI_MODULES="未知"

    # 检测是否包含 AI 声明模板
    if echo "$desc" | grep -qi "AI.*辅助\|AI.*声明\|AI.*使用\|AI.*占比\|AI.*生成"; then
        AI_DECLARED="true"

        # 提取占比
        local pct
        pct=$(echo "$desc" | grep -oiE "AI[^0-9]*[0-9]+%" | head -1 | grep -oE '[0-9]+' || echo "0")
        if [ "$pct" != "0" ] && [ -n "$pct" ]; then
            AI_PERCENTAGE="$pct"
            AI_USED="true"
        fi

        # 提取工具
        local tools
        tools=$(echo "$desc" | grep -iE "使用工具|AI.*工具" | head -1 | sed -E 's/.*[：:]\s*//' | sed 's/^[- ]*//' || echo "")
        if [ -n "$tools" ]; then
            AI_TOOLS="$tools"
        fi

        # 提取模块
        local modules
        modules=$(echo "$desc" | grep -iE "主要模块|生成.*模块|涉及.*模块|AI.*模块" | head -1 | sed -E 's/.*[：:]\s*//' | sed 's/^[- ]*//' || echo "")
        if [ -n "$modules" ]; then
            AI_MODULES="$modules"
        fi
    else
        # 检查是否有 AI 代码特征（快速启发式）
        # 如果 diff 中包含 AI 常见模式，但没有声明，标记为 suspected
        AI_DECLARED="false"
        AI_USED="unknown"
    fi

    log_info "  AI 已使用:   $AI_USED"
    log_info "  AI 已声明:   $AI_DECLARED"
    log_info "  AI 占比:     ${AI_PERCENTAGE}%"
    log_info "  AI 工具:     $AI_TOOLS"
    log_info "  AI 模块:     $AI_MODULES"
}

# =============================================================================
# 采集流水线（CI）结果
# =============================================================================
collect_pipeline_data() {
    log_info "正在获取 CI 流水线数据..."

    # 默认值
    UT_TOTAL=0; UT_PASSED=0; UT_FAILED=0; UT_PASS_RATE=0
    COVERAGE_PCT=0
    BLOCKER_COUNT=-1; CRITICAL_COUNT=-1
    SMOKE_TOTAL=0; SMOKE_PASSED=0; SMOKE_FAILED=0; SMOKE_PASS_RATE=0
    PIPELINE_URL=""

    # 获取最新流水线
    local pipelines_json
    pipelines_json=$(gitlab_api_get "/projects/${PROJECT_ID}/merge_requests/${MR_IID}/pipelines" 2>/dev/null) || {
        log_warn "  无法获取流水线列表（可能需要 CI 权限）"
        return
    }

    local pipeline_count
    pipeline_count=$(echo "$pipelines_json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

    if [ "$pipeline_count" = "0" ] || [ "$pipeline_count" = "null" ] || [ -z "$pipelines_json" ] || [ "$pipelines_json" = "[]" ]; then
        log_warn "  未找到流水线"
        return
    fi

    # 取最新一条成功的（或直接取第一条）
    local pipeline_id
    pipeline_id=$(echo "$pipelines_json" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data[0]['id'])" 2>/dev/null || echo "")
    local pipeline_web_url
    pipeline_web_url=$(echo "$pipelines_json" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data[0]['web_url'])" 2>/dev/null || echo "")

    PIPELINE_URL="$pipeline_web_url"

    if [ -z "$pipeline_id" ]; then
        log_warn "  无法获取流水线 ID"
        return
    fi

    log_info "  流水线 ID: $pipeline_id"

    # 获取 Jobs
    local jobs_json
    jobs_json=$(gitlab_api_get "/projects/${PROJECT_ID}/pipelines/${pipeline_id}/jobs" 2>/dev/null) || {
        log_warn "  无法获取 Pipeline Jobs"
        return
    }

    # 遍历 Jobs，按名称模式匹配

    # 解析 Job 名称映射（自定义 > 默认）
    local ut_pattern="unit.?test|ut[^a-z]"
    local cov_pattern="coverage|cov[^a-z]"
    local scan_pattern="sonar|lint|static.?scan|code.?scan"
    local smoke_pattern="smoke"

    if [ -n "${CRVIGIL_JOB_MAPPING:-}" ]; then
        local mapped
        mapped=$(echo "$CRVIGIL_JOB_MAPPING" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('unit_test',''))" 2>/dev/null || echo "")
        [ -n "$mapped" ] && [ "$mapped" != "null" ] && ut_pattern="$mapped"
        mapped=$(echo "$CRVIGIL_JOB_MAPPING" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('coverage',''))" 2>/dev/null || echo "")
        [ -n "$mapped" ] && [ "$mapped" != "null" ] && cov_pattern="$mapped"
        mapped=$(echo "$CRVIGIL_JOB_MAPPING" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('static_scan',''))" 2>/dev/null || echo "")
        [ -n "$mapped" ] && [ "$mapped" != "null" ] && scan_pattern="$mapped"
        mapped=$(echo "$CRVIGIL_JOB_MAPPING" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('smoke_test',''))" 2>/dev/null || echo "")
        [ -n "$mapped" ] && [ "$mapped" != "null" ] && smoke_pattern="$mapped"
        log_info "  使用自定义 Job 匹配: UT=${ut_pattern}, Cov=${cov_pattern}, Scan=${scan_pattern}, Smoke=${smoke_pattern}"
    fi

    local job_count
    job_count=$(echo "$jobs_json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

    for i in $(seq 0 $((job_count - 1))); do
        local job_name job_status
        job_name=$(echo "$jobs_json" | python3 -c "import sys,json; d=json.load(sys.stdin)[$i]; print(d.get('name',''))" 2>/dev/null || echo "")
        job_status=$(echo "$jobs_json" | python3 -c "import sys,json; d=json.load(sys.stdin)[$i]; print(d.get('status',''))" 2>/dev/null || echo "")

        # 匹配单元测试
        if echo "$job_name" | grep -qiE "$ut_pattern"; then
            if [ "$job_status" = "success" ]; then
                UT_PASS_RATE=100; UT_PASSED=1; UT_TOTAL=1
            else
                UT_PASS_RATE=0; UT_FAILED=1; UT_TOTAL=1
            fi
            log_info "  单元测试 Job [$job_name]: $job_status"
        fi

        # 匹配覆盖率
        if echo "$job_name" | grep -qiE "$cov_pattern"; then
            if [ "$job_status" = "success" ]; then
                # 尝试从 Job 日志中提取覆盖率数字
                local job_id
                job_id=$(echo "$jobs_json" | python3 -c "import sys,json; d=json.load(sys.stdin)[$i]; print(d.get('id',''))" 2>/dev/null || echo "")
                if [ -n "$job_id" ]; then
                    local trace
                    trace=$(gitlab_get_job_trace "$PROJECT_ID" "$job_id" 500 2>/dev/null || echo "")
                    local cov
                    cov=$(echo "$trace" | grep -oiE 'Coverage[:\s]*[0-9]+\.?[0-9]*%' | tail -1 | grep -oE '[0-9]+\.?[0-9]*' || echo "")
                    if [ -n "$cov" ]; then
                        COVERAGE_PCT="$cov"
                    else
                        # 尝试从 pipeline 的 coverage 字段获取
                        COVERAGE_PCT=$(echo "$pipelines_json" | python3 -c "import sys,json; d=json.load(sys.stdin)[0]; print(d.get('coverage','0').rstrip('%'))" 2>/dev/null || echo "0")
                    fi
                fi
            fi
            log_info "  覆盖率 Job [$job_name]: $job_status, 覆盖率: ${COVERAGE_PCT}%"
        fi

        # 匹配静态扫描
        if echo "$job_name" | grep -qiE "$scan_pattern"; then
            if [ "$job_status" = "success" ]; then
                BLOCKER_COUNT=0; CRITICAL_COUNT=0
            fi
            log_info "  静态扫描 Job [$job_name]: $job_status"
        fi

        # 匹配冒烟测试
        if echo "$job_name" | grep -qiE "$smoke_pattern"; then
            if [ "$job_status" = "success" ]; then
                SMOKE_PASS_RATE=100; SMOKE_PASSED=1; SMOKE_TOTAL=1
            else
                SMOKE_PASS_RATE=0; SMOKE_FAILED=1; SMOKE_TOTAL=1
            fi
            log_info "  冒烟测试 Job [$job_name]: $job_status"
        fi
    done

    log_info "  CI 采集完成: UT=${UT_PASS_RATE}%, Cov=${COVERAGE_PCT}%, Blocker=${BLOCKER_COUNT}, Smoke=${SMOKE_PASS_RATE}%"
}

# =============================================================================
# 采集审查数据
# =============================================================================
collect_review_data() {
    log_info "正在获取 Code Review 数据..."

    REVIEWER=""
    REVIEWER_LEVEL="junior"
    SUBSTANTIVE_COMMENTS=0
    REVIEW_APPROVED_AT=""
    IS_SELF_REVIEW="false"

    # 获取 Notes（评论）
    local notes_json
    notes_json=$(gitlab_api_get "/projects/${PROJECT_ID}/merge_requests/${MR_IID}/notes?sort=asc" 2>/dev/null) || {
        log_warn "  无法获取评论列表"
        return
    }

    # 过滤 system=false 的评论，排除作者自己的
    # 提取非系统评论的作者和内容
    local notes_count
    notes_count=$(echo "$notes_json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

    local reviewer_found=""
    local total_non_system=0
    local substantive=0

    for i in $(seq 0 $((notes_count - 1))); do
        local is_system note_author note_body
        is_system=$(echo "$notes_json" | python3 -c "import sys,json; d=json.load(sys.stdin)[$i]; print(d.get('system',True))" 2>/dev/null || echo "True")
        note_author=$(echo "$notes_json" | python3 -c "import sys,json; d=json.load(sys.stdin)[$i]; print(d.get('author',{}).get('name',''))" 2>/dev/null || echo "")
        note_body=$(echo "$notes_json" | python3 -c "import sys,json; d=json.load(sys.stdin)[$i]; print(d.get('body',''))" 2>/dev/null || echo "")

        if [ "$is_system" != "True" ]; then
            total_non_system=$((total_non_system + 1))

            # 第一个非作者的非系统评论者 = 审查人
            if [ -z "$reviewer_found" ] && [ "$note_author" != "$MR_AUTHOR" ]; then
                REVIEWER="$note_author"
                reviewer_found="true"
            fi

            # 检测实质性评论：去掉 LGTM/OK/+1/好的 等形式用语后还有技术内容
            local clean_body
            clean_body=$(echo "$note_body" | sed -E 's/LGTM|Looks Good|OK|\+1|好的|没问题|通过|Approved//gi' | tr -d '[:space:]')
            if [ ${#clean_body} -ge 10 ]; then
                substantive=$((substantive + 1))
            fi
        fi
    done

    if [ -n "$REVIEWER" ] && [ "$REVIEWER" = "$MR_AUTHOR" ]; then
        IS_SELF_REVIEW="true"
    fi

    SUBSTANTIVE_COMMENTS=$substantive

    # 获取审批状态
    local approvals_json
    approvals_json=$(gitlab_api_get_single "/projects/${PROJECT_ID}/merge_requests/${MR_IID}/approvals" 2>/dev/null) || {
        log_warn "  无法获取审批状态（可能需要 Premium 版本）"
    }

    if [ -n "${approvals_json:-}" ]; then
        local approved_by approved_at
        approved_by=$(echo "$approvals_json" | python3 -c "import sys,json; d=json.load(sys.stdin); names=[u['user']['name'] for u in d.get('approved_by',[])]; print(','.join(names))" 2>/dev/null || echo "")
        approved_at=$(echo "$approvals_json" | python3 -c "import sys,json; d=json.load(sys.stdin); dates=[u.get('approved_at','') for u in d.get('approved_by',[])]; print(dates[0] if dates else '')" 2>/dev/null || echo "")

        if [ -n "$approved_by" ]; then
            REVIEWER="$approved_by"
            REVIEW_APPROVED_AT="$approved_at"
            # 如果被审批通过，审查人至少是 senior
            REVIEWER_LEVEL="senior"
        fi
    fi

    # 从 data/reviewer-levels.json 查询审查人级别
    if [ -n "$REVIEWER" ]; then
        local level_config="${PROJECT_ROOT}/data/reviewer-levels.json"
        if [ -f "$level_config" ]; then
            local queried_level
            queried_level=$(python3 -c "
import sys, json
try:
    with open('$level_config') as f:
        d = json.load(f)
        reviewer_lower = '$REVIEWER'.lower()
        d_lower = {k.lower(): v for k, v in d.items()}
        print(d_lower.get(reviewer_lower, ''))
except Exception:
    print('')
" 2>/dev/null || echo "")
            if [ -n "$queried_level" ]; then
                REVIEWER_LEVEL="$queried_level"
            fi
        fi
    fi

    log_info "  审查人:        ${REVIEWER:-未找到}"
    log_info "  是否自审:      $IS_SELF_REVIEW"
    log_info "  实质性评论数:  $SUBSTANTIVE_COMMENTS"
    log_info "  审查人级别:    $REVIEWER_LEVEL"
    log_info "  批准时间:      ${REVIEW_APPROVED_AT:-未批准}"
}

# =============================================================================
# 组装标准 JSON 并写入 registry
# =============================================================================
write_registry() {
    log_info "正在生成标准化 JSON..."

    local pr_id="MR-${MR_IID}-${MR_PROJECT_PATH##*/}"
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%S%z)

    # 通过环境变量安全传递数据给 Python（避免 shell 注入）
    export PR_ID="$pr_id"
    export MR_TITLE MR_AUTHOR MR_WEB_URL MR_CREATED MR_UPDATED MR_STATE
    export CI_MODE
    export AI_USED AI_DECLARED AI_PERCENTAGE AI_TOOLS AI_MODULES
    export REVIEWER REVIEWER_LEVEL SUBSTANTIVE_COMMENTS REVIEW_APPROVED_AT
    export PIPELINE_URL
    export UT_TOTAL UT_PASSED UT_FAILED UT_PASS_RATE
    export COVERAGE_PCT
    export BLOCKER_COUNT CRITICAL_COUNT
    export SMOKE_TOTAL SMOKE_PASSED SMOKE_FAILED SMOKE_PASS_RATE
    export REGISTRY_FILE
    export TIMESTAMP="$timestamp"

    python3 << 'PYEOF'
import json, os, sys

# 从环境变量安全读取所有数据
def env_str(key, default=''):
    return os.environ.get(key, default)

def env_int(key, default=0):
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default

def env_bool(key):
    val = os.environ.get(key, 'false').lower()
    return val in ('true', '1', 'yes')

# MR 元信息
mr_title = env_str('MR_TITLE')
mr_author = env_str('MR_AUTHOR')
mr_web_url = env_str('MR_WEB_URL')
mr_created = env_str('MR_CREATED')
mr_updated = env_str('MR_UPDATED')
mr_state = env_str('MR_STATE')
ci_mode = env_str('CI_MODE', 'auto')

# AI 声明
ai_used_val = env_str('AI_USED')
if ai_used_val in ('true', 'false'):
    ai_used = ai_used_val == 'true'
else:
    ai_used = True  # unknown → True (保守)
ai_declared = env_bool('AI_DECLARED')
ai_pct = env_int('AI_PERCENTAGE')
ai_tools = env_str('AI_TOOLS', '未知')
ai_modules = env_str('AI_MODULES', '未知')

# Review
reviewer = env_str('REVIEWER')
reviewer_level = env_str('REVIEWER_LEVEL', 'junior')
substantive = env_int('SUBSTANTIVE_COMMENTS')
approved_at = env_str('REVIEW_APPROVED_AT') or None

# CI
pipeline_url = env_str('PIPELINE_URL')
ut_total = env_int('UT_TOTAL')
ut_passed = env_int('UT_PASSED')
ut_failed = env_int('UT_FAILED')
ut_pass_rate = env_int('UT_PASS_RATE')
coverage_pct = env_int('COVERAGE_PCT')
blocker_count = env_int('BLOCKER_COUNT', -1)
critical_count = env_int('CRITICAL_COUNT', -1)
smoke_total = env_int('SMOKE_TOTAL')
smoke_passed = env_int('SMOKE_PASSED')
smoke_failed = env_int('SMOKE_FAILED')
smoke_pass_rate = env_int('SMOKE_PASS_RATE')

# 构建 PR 记录
pr_record = {
    'pr_id': env_str('PR_ID'),
    'title': mr_title,
    'author': mr_author,
    'url': mr_web_url,
    'created_at': mr_created,
    'updated_at': mr_updated,
    'status': mr_state,
    'ci_mode': ci_mode,
    'ai_usage': {
        'used': ai_used,
        'declared': ai_declared,
        'percentage': ai_pct,
        'tools': [ai_tools],
        'modules': [ai_modules]
    },
    'review': {
        'reviewer': reviewer,
        'reviewer_level': reviewer_level,
        'substantive_comments': substantive,
        'review_approved_at': approved_at,
        'checklist': {
            'ck_01': None, 'ck_02': None, 'ck_03': None, 'ck_04': None,
            'ck_05': None, 'ck_06': None, 'ck_07': None, 'ck_08': None,
            'ck_09': None, 'ck_10': None, 'ck_11': None, 'ck_12': None
        }
    },
    'ci': {
        'pipeline_url': pipeline_url,
        'unit_test': {
            'total': ut_total, 'passed': ut_passed,
            'failed': ut_failed, 'pass_rate': ut_pass_rate
        },
        'coverage': {
            'incremental_coverage_pct': coverage_pct, 'threshold': 70
        },
        'static_scan': {
            'blocker_count': blocker_count, 'critical_count': critical_count,
            'warning_count': 0, 'tool': 'sonar'
        },
        'smoke_test': {
            'total': smoke_total, 'passed': smoke_passed,
            'failed': smoke_failed, 'pass_rate': smoke_pass_rate
        }
    },
    'declaration': {
        'ci_proof_provided': False,
        'ci_proof_url': pipeline_url,
        'cr_approval_link': mr_web_url,
        'self_inspection': {
            'submitted': False, 'signed_by': '', 'signed_date': None,
            'checks': {
                'ci_passed': False, 'cr_completed': False,
                'boundary_verified': False, 'self_tested': False,
                'no_known_blockers': False
            }
        }
    },
    'gates': {
        'gate_1': {'status': 'PENDING', 'details': {}},
        'gate_2': {'status': 'PENDING', 'details': {}},
        'gate_3': {'status': 'PENDING', 'details': {}},
        'gate_4': {'status': 'N/A', 'details': {}}
    },
    'gates_summary': {
        'gate_1': 'PENDING',
        'gate_2': 'PENDING',
        'gate_3': 'PENDING',
        'gate_4': 'N/A'
    },
    'verdict': 'PENDING',
    'blocking_reasons': [],
    'ai_percentage': ai_pct,
    'reviewer': reviewer,
    'violations': 0,
    'last_updated': env_str('TIMESTAMP'),
    'history': [{'timestamp': mr_updated, 'event': 'data_collected', 'details': 'Data collected from GitLab API'}]
}

# 读取现有 registry
registry_file = env_str('REGISTRY_FILE')
if os.path.exists(registry_file):
    with open(registry_file) as f:
        registry = json.load(f)
else:
    registry = {'updated_at': '', 'prs': []}

# 更新或新增
updated = False
for i, pr in enumerate(registry['prs']):
    if pr.get('pr_id') == pr_record['pr_id']:
        # 保留违规计数
        pr_record['violations'] = pr.get('violations', 0)
        pr_record['history'] = pr.get('history', []) + pr_record['history']
        registry['prs'][i] = pr_record
        updated = True
        break

if not updated:
    registry['prs'].append(pr_record)

registry['updated_at'] = env_str('TIMESTAMP')

with open(registry_file, 'w') as f:
    json.dump(registry, f, ensure_ascii=False, indent=2)

print(f'OK: {len(registry["prs"])} PR(s) in registry')
PYEOF

    local rc=$?
    if [ $rc -eq 0 ]; then
        log_info "已更新 registry: $REGISTRY_FILE"
    else
        log_error "registry 写入失败 (exit code: $rc)"
    fi
}

# =============================================================================
# 主流程
# =============================================================================
main() {
    local mr_url="${1:-}"

    if [ -z "$mr_url" ]; then
        log_error "缺少参数: 请提供 GitLab MR URL"
        echo "用法: $0 <MR_URL>"
        echo "示例: $0 https://gitlab.example.com/org/project/-/merge_requests/27"
        exit 1
    fi

    echo ""
    log_info "=============================================="
    log_info "  CR-Vigil: GitLab MR 数据采集"
    log_info "=============================================="
    echo ""

    # 初始化
    check_gitlab_token || exit 1
    mkdir -p "$TEMP_DIR"

    # 执行采集
    parse_mr_url "$mr_url" || exit 1
    echo ""
    resolve_ci_mode
    echo ""
    collect_mr_metadata || exit 1
    echo ""
    parse_ai_declaration "$MR_DESCRIPTION"
    echo ""
    collect_pipeline_data
    echo ""
    auto_detect_ci  # 在 CI 数据采集之后运行，auto 模式自动判定
    echo ""
    collect_review_data
    echo ""

    # 写入
    write_registry

    echo ""
    log_info "=============================================="
    log_info "  采集完成"
    log_info "  数据摘要:"
    log_info "    MR:      ${MR_TITLE}"
    log_info "    作者:    ${MR_AUTHOR}"
    log_info "    AI 占比: ${AI_PERCENTAGE}%"
    log_info "    审查人:  ${REVIEWER:-未找到}"
    log_info "    CI 模式:  ${CI_MODE}"
    log_info "    CI 状态: pipeline=${PIPELINE_URL:-无}"
    log_info "=============================================="
    echo ""

    # 返回 registry 文件路径供 Skill 使用
    echo "$REGISTRY_FILE"
}

main "$@"
