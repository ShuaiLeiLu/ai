# Cyber Invest Foundation

赛博投研项目基础工程骨架，采用：

- 前端：Next.js + React + TypeScript + Ant Design + Tailwind CSS
- 后端：FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 基础设施：Docker Compose + Postgres + Redis + MinIO

## 目录结构

- `web/`：前端应用
- `server/`：后端服务
- `docs/`：PRD、架构与审计文档
- `compose.yaml`：本地基础设施编排
- `Makefile`：开发命令入口

## 快速开始

1. 复制环境变量模板：`cp .env.example .env`
2. 启动本地基础设施：`make up`
3. 安装前端依赖：`make install-web`
4. 安装后端依赖：`make install-server`
5. 运行前端：`make dev-web`
6. 运行后端：`make dev-api`
7. 运行异步任务：`make dev-worker`
8. 运行定时任务：`make dev-beat`

## 相关文档

- [正式技术架构选型文档](/Users/lushuailei/PycharmProjects/ai/docs/architecture/01-正式技术架构选型文档.md)
- [赛博投研总PRD](/Users/lushuailei/PycharmProjects/ai/docs/prd/00-赛博投研总PRD.md)
- [产品体验审计](/Users/lushuailei/PycharmProjects/ai/docs/audit/产品体验审计.md)
