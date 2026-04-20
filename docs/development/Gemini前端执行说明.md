# Gemini前端执行说明

## 1. 环境变量
在当前终端设置：

```bash
export GOOGLE_GEMINI_BASE_URL="https://你的网关地址"
export GEMINI_API_KEY="你的key"
```

## 2. 执行脚本
使用统一脚本执行指定提示词：

```bash
./scripts/run_gemini_frontend_task.sh <提示词文件路径>
```

可选模型参数：

```bash
./scripts/run_gemini_frontend_task.sh <提示词文件路径> gemini-2.5-pro
```

## 3. 批次执行建议
- 批次A：`盘前速览 -> 资讯分析 -> AI研究员 -> 任务编排`
- 批次B：`人才市场与编辑器 -> 文档中心 -> 社区 -> 文件夹笔记`
- 批次C：`模拟交易 -> Webhook -> 知识库/技能/MCP -> 账户与会员`

## 4. 每批完成后必做校验
```bash
cd web && npm run typecheck && npm run lint && npm run build
```

## 5. 联调约束
- 页面必须直接对接 `/api/v1` 真实接口。
- 列表接口按 `data.items` 渲染，总数按 `data.total` 渲染。
- 错误态统一展示后端 `detail`。

