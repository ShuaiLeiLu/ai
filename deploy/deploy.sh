#!/bin/bash
set -euo pipefail

echo "=========================================="
echo "  赛博投研 Docker 部署脚本"
echo "=========================================="

PROJECT_DIR="${PROJECT_DIR:-/opt/ai-deploy/src}"
BRANCH="${BRANCH:-main}"
SKIP_PULL=false

if [ "${1:-}" = "--no-pull" ]; then
    SKIP_PULL=true
fi

cd "$PROJECT_DIR"

if [ "$SKIP_PULL" = false ]; then
    echo "[1/5] 拉取最新代码..."
    git fetch origin "$BRANCH"
    git reset --hard "origin/$BRANCH"
else
    echo "[1/5] 跳过拉取代码"
fi

if [ ! -f deploy/.env.production ]; then
    echo "缺少 deploy/.env.production，请先从 GitHub Actions Secret 写入生产环境变量。" >&2
    exit 1
fi

echo "[2/5] 确认 Docker 网络..."
docker network inspect deploy_default >/dev/null 2>&1 || docker network create deploy_default

echo "[3/5] 构建 Docker 镜像..."
cd "$PROJECT_DIR/deploy"
docker compose build --pull api web

echo "[4/5] 替换线上容器..."
docker rm -f ai-api ai-web 2>/dev/null || true
docker compose up -d api web

echo "[5/5] 健康检查..."
for i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/api/v1/health >/dev/null; then
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "API 健康检查失败" >&2
        docker logs --tail 120 ai-api >&2 || true
        exit 1
    fi
    sleep 3
done

for i in $(seq 1 20); do
    if curl -fsS http://127.0.0.1:3000 >/dev/null; then
        break
    fi
    if [ "$i" -eq 20 ]; then
        echo "Web 健康检查失败" >&2
        docker logs --tail 120 ai-web >&2 || true
        exit 1
    fi
    sleep 3
done
docker image prune -f >/dev/null || true

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo "  前端:    https://ai.shuai.help"
echo "  API:     https://ai.shuai.help/api/v1"
echo "  API文档: https://ai.shuai.help/docs"
echo "=========================================="
echo ""
echo "查看日志: cd $PROJECT_DIR/deploy && docker compose logs -f"
