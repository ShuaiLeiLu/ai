#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/ai-deploy/src}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
API_HEALTH_URL="${API_HEALTH_URL:-http://127.0.0.1:8000/api/v1/health}"
WEB_HEALTH_URL="${WEB_HEALTH_URL:-http://127.0.0.1:3000}"
API_CONTAINER="${API_CONTAINER:-ai-api}"
WEB_CONTAINER="${WEB_CONTAINER:-ai-web}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-deploy}"
SKIP_PULL=false
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
PRUNE_IMAGES="${PRUNE_IMAGES:-true}"

usage() {
    cat <<'USAGE'
用法: deploy/deploy.sh [选项]

选项:
  --no-pull             跳过拉取代码，使用当前工作区内容部署
  --branch <name>       指定要发布的分支，默认读取 BRANCH 或 main
  --no-migrate          跳过 Alembic 数据库迁移
  --no-prune            跳过 docker image prune
  -h, --help            显示帮助

常用环境变量:
  PROJECT_DIR           项目目录，默认 /opt/ai-deploy/src
  ENV_FILE              deploy/ 下的环境文件名，默认 .env.production
  API_HEALTH_URL        API 健康检查地址
  WEB_HEALTH_URL        Web 健康检查地址
USAGE
}

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
    printf '错误: %s\n' "$*" >&2
    exit 1
}

run() {
    log "+ $*"
    "$@"
}

compose() {
    docker compose --env-file "deploy/${ENV_FILE}" -f "deploy/${COMPOSE_FILE}" "$@"
}

show_failure_context() {
    local exit_code=$?
    log "部署失败，退出码: ${exit_code}"
    if command -v docker >/dev/null 2>&1 && [ -d "${PROJECT_DIR}/deploy" ]; then
        (
            cd "${PROJECT_DIR}/deploy" 2>/dev/null || exit 0
            docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps >&2 || true
            docker logs --tail 120 "${API_CONTAINER}" >&2 || true
            docker logs --tail 120 "${WEB_CONTAINER}" >&2 || true
        )
    fi
    exit "${exit_code}"
}

wait_for_url() {
    local name="$1"
    local url="$2"
    local retries="$3"
    local delay="$4"

    for i in $(seq 1 "${retries}"); do
        if curl -fsS --max-time 5 "${url}" >/dev/null; then
            log "${name} 健康检查通过"
            return 0
        fi
        log "${name} 健康检查未通过，${delay}s 后重试 (${i}/${retries})"
        sleep "${delay}"
    done

    die "${name} 健康检查失败: ${url}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --no-pull)
            SKIP_PULL=true
            shift
            ;;
        --branch)
            [ "$#" -ge 2 ] || die "--branch 需要分支名"
            BRANCH="$2"
            shift 2
            ;;
        --no-migrate)
            RUN_MIGRATIONS=false
            shift
            ;;
        --no-prune)
            PRUNE_IMAGES=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "未知参数: $1"
            ;;
    esac
done

export COMPOSE_PROJECT_NAME
trap show_failure_context ERR

log "=========================================="
log "  赛博投研 Docker 自动发布"
log "=========================================="

[ -d "${PROJECT_DIR}" ] || die "PROJECT_DIR 不存在: ${PROJECT_DIR}"
cd "${PROJECT_DIR}"

command -v git >/dev/null 2>&1 || die "未找到 git"
command -v docker >/dev/null 2>&1 || die "未找到 docker"
docker compose version >/dev/null 2>&1 || die "未找到 docker compose 插件"
command -v curl >/dev/null 2>&1 || die "未找到 curl"
command -v flock >/dev/null 2>&1 || die "未找到 flock"

LOCK_FILE="/tmp/cyber-invest-deploy.lock"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    die "已有发布任务正在运行: ${LOCK_FILE}"
fi

log "[1/7] 准备代码"
if [ "${SKIP_PULL}" = false ]; then
    run git fetch --prune origin "${BRANCH}"
    run git reset --hard "origin/${BRANCH}"
else
    log "跳过拉取代码，当前提交: $(git rev-parse --short HEAD)"
fi

[ -f "deploy/${ENV_FILE}" ] || die "缺少 deploy/${ENV_FILE}，请先写入生产环境变量"

log "[2/7] 校验发布配置"
run compose config --quiet

log "[3/7] 确认 Docker 网络"
docker network inspect deploy_default >/dev/null 2>&1 || run docker network create deploy_default

log "[4/7] 构建镜像"
run compose build --pull api web

log "[5/7] 启动服务"
run compose up -d --remove-orphans api web

if [ "${RUN_MIGRATIONS}" = true ]; then
    log "[6/7] 执行数据库迁移"
    run compose exec -T api sh -c 'cd server && alembic -c alembic.ini upgrade head'
else
    log "[6/7] 跳过数据库迁移"
fi

log "[7/7] 健康检查"
wait_for_url "API" "${API_HEALTH_URL}" 30 3
wait_for_url "Web" "${WEB_HEALTH_URL}" 20 3

if [ "${PRUNE_IMAGES}" = true ]; then
    log "清理悬空镜像"
    docker image prune -f >/dev/null || true
fi

log "=========================================="
log "  部署完成"
log "=========================================="
log "  前端:    https://ai.shuai.help"
log "  API:     https://ai.shuai.help/api/v1"
log "  API文档: https://ai.shuai.help/docs"
log "=========================================="
log "查看日志: cd ${PROJECT_DIR}/deploy && docker compose logs -f"
