# Cache All Page Sections Progress

## Recovery

任务: 页面版块数据全部缓存化，页面读接口直接读缓存。
形态: single-full
进度: 4/4
当前: Completion audit and verification
验证: `python -m pytest server/tests --ignore=server/tests/test_rqalpha_adapter.py` -> 89 passed
文件: `.codex-tasks/cache-all-page-sections/TODO.csv`
下一步: 汇报结果；完整测试仍需补齐缺失的 `app.modules.trading.rqalpha_adapter` 后才能全量无忽略运行。

## Notes

- 已实现外部数据重点路径：preopen、news-analysis、event-driven。
- 已新增通用 Redis 页面缓存 helper：`server/app/modules/page_cache.py`。
- 已给 researchers workbench overview 增加用户维度 Redis cache-aside。
- 完整测试当前受已知缺失模块 `app.modules.trading.rqalpha_adapter` 阻塞。

## Final Audit

- Frontend page read APIs audited via `rg -n "http<" web/features web/app`.
- Cache-first page reads now cover:
  - preopen
  - news-analysis
  - event-driven themes / detail / they-say / access-status
  - trading account / positions / records / logs / stats / all / portfolio
  - documents list / hot / detail / comments
  - community post list / detail / comments / mention config
  - billing membership / ledger / packages
  - ecosystem knowledge bases / skills / MCP servers
  - researchers market / detail / mine / workbench split reads / overview
  - tasks list / runs / run logs
- Excluded from page-section data cache requirement:
  - auth login/register/me
  - system health
  - explicit POST action endpoints such as unlock, hire, create, update, run, reflect, order
- Verification:
  - `python -m pytest server/tests --ignore=server/tests/test_rqalpha_adapter.py`: 89 passed.
  - `python -m pytest server/tests`: fails at collection because `app.modules.trading.rqalpha_adapter` is missing.
