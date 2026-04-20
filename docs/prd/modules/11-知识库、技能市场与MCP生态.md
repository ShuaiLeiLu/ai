# 模块 PRD：知识库、技能市场与 MCP 生态

## 1. 模块定位

该模块是赛博投研的能力扩展层，用于让研究员脱离单纯提示词能力，转向“有知识、有技能、有工具接入”的复合型 AI Agent。它包括知识库、技能市场、我的技能、MCP市场、我的MCP 等生态能力。

## 2. 模块目标

- 提升研究员能力上限与差异化。
- 让用户通过外挂能力扩展研究员行为。
- 建立平台级供给生态，形成可复用能力市场。
- 为平台后续高级能力和 B 端化打基础。

## 3. 子模块范围

- 我的知识库
- 技能市场
- 我的技能
- MCP市场
- 我的MCP

## 4. 用户故事

- 作为进阶用户，我希望给研究员挂上自己的知识库，让输出更贴近我的研究体系。
- 作为能力创作者，我希望上传技能包供自己或他人复用。
- 作为高级用户，我希望接入 MCP 服务扩展研究员对数据和工具的调用能力。

## 5. 知识库需求

- 创建知识库
- 管理知识库列表
- 供研究员绑定使用
- 后续支持文档入库、检索、更新与删除

## 6. 技能市场需求

- 市场列表、搜索、筛选
- 技能包卡片：名称、版本、作者、简介、标签
- 我的技能：上传、管理、发布状态
- 技能可供研究员编辑器绑定

## 7. MCP 市场需求

- 市场列表、分类筛选、搜索
- MCP 卡片：名称、版本、描述、transportType、工具数量
- 我的MCP：添加、管理、发布
- 供研究员编辑器选择绑定

## 8. 数据模型

| 实体 | 字段 |
| --- | --- |
| KnowledgeBase | id, userId, name, description, status |
| SkillPackage | id, userId, name, version, description, tags, isPublic |
| SkillVersion | id, skillId, version, manifest, status |
| McpServer | id, userId, name, version, description, transportType, toolCount, isPublic |
| McpTool | id, mcpServerId, name, schema |

## 9. 前端需求

- 市场页和“我的”页保持一致的卡片式信息结构。
- 搜索与标签筛选要足够清晰。
- 知识库、技能、MCP 选择器需要与研究员编辑器自然衔接。
- 空态要强调“为什么值得创建/上传”。

## 10. 后端需求

- 知识库 CRUD
- 技能包上传、版本、公开状态
- MCP 服务创建、版本、工具清单、公开状态
- 市场列表与搜索能力
- 与研究员绑定关系查询能力

## 11. 风险与注意事项

- 技能包与 MCP 都属于可扩展能力，必须考虑安全边界。
- 市场内容如果缺少质量治理，会迅速失去可信度。
- 知识库入库和更新需要明确异步状态。

## 12. 验收标准

- 用户可创建知识库。
- 用户可浏览技能市场和 MCP 市场。
- 用户可上传自己的技能和 MCP。
- 研究员编辑器可绑定知识库、技能和 MCP。

## 13. 前端 AI 提示词

> 技术实现约束：严格遵循 [正式技术架构选型文档](/Users/lushuailei/PycharmProjects/ai/docs/architecture/01-正式技术架构选型文档.md)。前端统一使用 `Next.js 14+ App Router`、`React 18+`、`TypeScript`、`Zustand`、`TanStack Query`、`React Hook Form`、`Zod`、`Ant Design`、`Tailwind CSS`、`echarts-for-react`。默认采用服务端与客户端组件分层、接口通过 BFF/HTTP 调用、列表页与详情页具备加载态/空态/错误态、组件需可复用并满足工作台类产品的高信息密度场景。

你是资深前端工程师，请实现“知识库、技能市场、MCP市场”相关页面。要求：

- 知识库列表页与创建入口
- 技能市场与我的技能页
- MCP市场与我的MCP页
- 搜索、筛选、空态与卡片展示
- 可供研究员编辑器复用的选择器组件

请输出统一视觉体系下的页面组件、卡片组件、筛选组件和绑定交互方案。

## 14. 后端 AI 提示词

> 技术实现约束：严格遵循 [正式技术架构选型文档](/Users/lushuailei/PycharmProjects/ai/docs/architecture/01-正式技术架构选型文档.md)。后端统一使用 `FastAPI`、`Python 3.11+`、`Pydantic v2`、`SQLAlchemy 2.0`、`Alembic`、`PostgreSQL`、`Redis`、`Celery`、`Celery Beat`、`SSE`、`OSS/S3`、`pgvector`。所有接口需考虑鉴权、幂等、审计日志、异步任务状态跟踪、缓存策略和错误码规范，输出需符合生产可落地标准。

你是资深后端架构师，请设计“知识库、技能市场、MCP 生态”服务端。要求覆盖：

- 知识库 CRUD 与状态管理
- 技能包上传、版本、公开/私有状态
- MCP 服务与工具清单管理
- 市场搜索、筛选、推荐
- 与研究员的绑定关系

请输出数据模型、接口设计、版本机制、安全边界建议和审核机制预留方案。
