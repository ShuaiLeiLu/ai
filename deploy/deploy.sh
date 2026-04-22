#!/bin/bash
set -e

echo "=========================================="
echo "  赛博投研 Docker 部署脚本"
echo "=========================================="

PROJECT_DIR="/opt/cyber-invest"

# 1. 停止并删除旧的非 Docker 服务
echo "[1/5] 停止旧服务..."
# 停止可能存在的 uvicorn / celery / next 进程
pkill -f "uvicorn" 2>/dev/null || true
pkill -f "celery" 2>/dev/null || true
pkill -f "next" 2>/dev/null || true
pkill -f "node.*server.js" 2>/dev/null || true

# 停止可能存在的旧 Docker 容器
if [ -f "$PROJECT_DIR/deploy/docker-compose.yml" ]; then
    cd "$PROJECT_DIR/deploy"
    docker compose down --remove-orphans 2>/dev/null || true
fi

# 停止系统服务（如果存在）
systemctl stop cyber-invest-api 2>/dev/null || true
systemctl stop cyber-invest-web 2>/dev/null || true
systemctl stop cyber-invest-worker 2>/dev/null || true
systemctl stop cyber-invest-beat 2>/dev/null || true
systemctl disable cyber-invest-api 2>/dev/null || true
systemctl disable cyber-invest-web 2>/dev/null || true
systemctl disable cyber-invest-worker 2>/dev/null || true
systemctl disable cyber-invest-beat 2>/dev/null || true

# 停止系统级 PostgreSQL / Redis / MinIO（如果存在）
systemctl stop postgresql 2>/dev/null || true
systemctl stop redis 2>/dev/null || true
systemctl stop minio 2>/dev/null || true
systemctl disable postgresql 2>/dev/null || true
systemctl disable redis 2>/dev/null || true
systemctl disable minio 2>/dev/null || true

echo "[1/5] 旧服务已停止"

# 2. 构建镜像
echo "[2/5] 构建 Docker 镜像..."
cd "$PROJECT_DIR/deploy"
docker compose build --no-cache

# 3. 启动基础设施（先等 DB 和 Redis 就绪）
echo "[3/5] 启动基础设施..."
docker compose up -d postgres redis minio
echo "等待数据库就绪..."
sleep 10

# 4. 运行数据库迁移
echo "[4/5] 运行数据库迁移..."
docker compose run --rm api alembic -c server/alembic.ini upgrade head || echo "迁移跳过或已是最新"

# 5. 启动全部服务
echo "[5/5] 启动全部服务..."
docker compose up -d

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo "  前端:    http://43.155.204.215"
echo "  API:     http://43.155.204.215/api/v1"
echo "  API文档: http://43.155.204.215/docs"
echo "  MinIO:   http://43.155.204.215:9001"
echo "=========================================="
echo ""
echo "查看日志: cd $PROJECT_DIR/deploy && docker compose logs -f"
