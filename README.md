# 极睿智投 / Cyber Invest

极睿智投是一个面向 A 股投研与轻量化模拟交易的 AI 投研平台。项目以“AI 研究员”为核心，把盘前速览、资讯分析、策略任务编排、模拟盘、知识库与 MCP 生态整合到同一个工作台中，帮助用户更快完成市场观察、研究沉淀和策略验证。

> 中文是本仓库的主文档语言。English readers can jump to [English](#english) for a brief overview and links to the Chinese source documents.

## 核心能力

- `AI 研究员工作台`：管理研究员、查看今日表现、策略运行状态和模拟盘结果。
- `盘前速览`：基于 Redis 快照聚合热点新闻、市场指标、涨停天梯、行业板块和异动数据。
- `资讯分析`：接入 AKShare、金十 MCP 等数据源，提供快讯、新闻、热点股票和 AI 解读。
- `任务编排`：支持一次性、间隔、Cron 任务，结合交易日判断和调度器自动执行。
- `模拟交易`：轻量化模拟盘，支持账户、持仓、交易记录、交易日志和账户快照。
- `策略引擎`：内置小市值轮动、情绪超短等策略入口，并对外部行情请求做串行锁和超时保护。
- `知识库与生态`：预留知识库、技能市场、MCP 市场等扩展模块。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Next.js 14, React 18, TypeScript, Ant Design, Tailwind CSS, ECharts, Zustand, TanStack Query |
| 后端 | FastAPI, SQLAlchemy 2.x, Alembic, APScheduler, Celery, Pydantic Settings |
| 数据 | PostgreSQL + pgvector, Redis, MinIO/S3 |
| 数据源 | AKShare, Jin10 MCP, OpenAI-compatible LLM API |
| 部署 | Docker, Docker Compose, Nginx/Caddy 反向代理 |

## 目录结构

```text
.
├── web/                  # Next.js 前端应用
├── server/               # FastAPI 后端、Alembic 迁移、测试与脚本
├── docs/                 # PRD、架构、开发说明、审计文档
├── deploy/               # 生产/服务器部署示例配置
├── compose.yaml          # 本地基础设施：PostgreSQL、Redis、MinIO
├── Makefile              # 常用开发命令
├── package.json          # 根工作区脚本
└── README.md             # 项目入口文档
```

## 快速开始

### 1. 准备依赖

建议环境：

- `Python 3.11+`
- `Node.js 20+`
- `pnpm 9+`
- `Docker / Docker Compose`

安装前端依赖：

```bash
make install-web
```

安装后端依赖：

```bash
make install-server
```

如果你不用 `Makefile`，也可以手动执行：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r server/requirements-dev.txt

cd web
pnpm install
```

### 2. 配置环境变量

复制后端环境变量模板：

```bash
cp server/.env.example server/.env
```

复制前端环境变量模板：

```bash
cp web/.env.example web/.env
```

最少需要确认以下配置：

```env
DATABASE_URL=postgresql+asyncpg://cyber_invest:cyber_invest@localhost:5432/cyber_invest
REDIS_URL=redis://localhost:6379/2
OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_MODEL=
```

### 3. 启动本地基础设施

```bash
make up
```

该命令会启动：

- PostgreSQL / pgvector
- Redis
- MinIO

停止基础设施：

```bash
make down
```

### 4. 执行数据库迁移

```bash
. .venv/bin/activate
cd server
python -m alembic upgrade head
```

### 5. 启动后端

```bash
make dev-api
```

默认地址：

- API: `http://127.0.0.1:8000`
- API v1: `http://127.0.0.1:8000/api/v1`

也可以直接运行：

```bash
. .venv/bin/activate
uvicorn app.main:create_app --factory --reload --app-dir server --port 8000
```

### 6. 启动前端

```bash
make dev-web
```

默认地址：

```text
http://localhost:3000
```

## 常用命令

```bash
make help             # 查看可用命令
make dev-web          # 启动前端开发服务
make dev-api          # 启动后端开发服务
make test-api         # 运行后端测试
make lint-web         # 前端 lint
make typecheck-web    # 前端 TypeScript 检查
make up               # 启动本地基础设施
make down             # 停止本地基础设施
```

根目录也提供了前端脚本：

```bash
pnpm dev:web
pnpm build:web
pnpm lint:web
pnpm typecheck:web
```

## 测试与构建

后端测试：

```bash
. .venv/bin/activate
pytest server/tests -q
```

后端语法检查：

```bash
python3 -m compileall server/app
```

前端构建：

```bash
cd web
pnpm build
```

## Docker 部署

本地基础设施使用根目录 `compose.yaml`：

```bash
docker compose up -d
```

完整部署示例位于 `deploy/`：

```bash
cd deploy
cp .env.production.example .env.production
docker compose -f docker-compose.yml up -d --build
```

生产环境需要特别确认：

- `SECRET_KEY` 必须替换为强随机值。
- `DEBUG=false`。
- `DATABASE_URL`、`REDIS_URL`、`OPENAI_*`、`S3_*` 使用真实配置。
- 不要把真实 `.env`、API Key 或数据库密码提交到 Git。

## 数据与调度说明

- 后端通过 APScheduler 运行盘前快照、行情缓存、模拟盘快照、策略任务等定时任务。
- 外部行情数据源不稳定时，系统会对 AKShare/东方财富/腾讯行情请求做串行锁与超时保护，避免并发请求拖死 API。
- 盘前速览接口优先读取 Redis 快照，后台任务定时刷新快照，页面请求不直接打外部行情源。
- Alembic 负责数据库结构迁移，新增表结构必须通过新的迁移版本提交。

## 重要文档

- [产品功能说明](docs/赛博投研产品功能说明.md)
- [总 PRD](docs/prd/00-赛博投研总PRD.md)
- [PRD 模块索引](docs/prd/README.md)
- [正式技术架构选型文档](docs/architecture/01-正式技术架构选型文档.md)
- [基础工程启动说明](docs/development/基础工程启动说明.md)
- [后端工厂模式架构说明](docs/development/后端工厂模式架构说明.md)
- [后端联调接口清单](docs/development/后端联调接口清单.md)
- [产品体验审计](docs/audit/产品体验审计.md)

## English

Cyber Invest is an AI-assisted research and lightweight paper-trading platform for A-share market workflows. It combines AI researcher workspaces, pre-market snapshots, news analysis, task orchestration, paper trading, knowledge-base features, and MCP integrations.

The canonical documentation is maintained in Chinese to avoid duplicated and drifting content. Please refer to the Chinese sections above and these source documents:

- [Product Overview](docs/赛博投研产品功能说明.md)
- [Main PRD](docs/prd/00-赛博投研总PRD.md)
- [Architecture](docs/architecture/01-正式技术架构选型文档.md)
- [Development Startup Guide](docs/development/基础工程启动说明.md)

For local setup, follow [快速开始](#快速开始). For deployment, follow [Docker 部署](#docker-部署).
