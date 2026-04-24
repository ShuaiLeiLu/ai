# Trading Detail And AI Researcher Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the trading detail page accurate, fast, and readable first, then turn the AI researcher overview into the real workstation entry built around researcher cards, hot documents, and public trading rankings.

**Architecture:** Keep read paths snapshot-first: trading detail reads only DB/Redis snapshots and lazily loads heavy history data, while the workstation overview reuses the existing aggregated workbench endpoint for the overview state and only loads per-researcher portfolio summaries when a researcher is selected. Backend work stays inside the current trading/researcher modules; frontend work stays inside the existing trading and researcher-workbench feature folders.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, Redis cache, Next.js App Router, React Query, TypeScript, Ant Design, Tailwind CSS

---

## File Structure

### Backend files

- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/service.py`
  - Freeze the detail-page read path around account snapshots, lazy history loading, and consistent AI log payload shaping.
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/router.py`
  - Keep the detail page on split endpoints and remove any accidental dependency on `/trading/all` from the plan.
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/schemas.py`
  - Add any lightweight fields needed by the detail page or overview summary without dragging heavy history payloads into the wrong screen.
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/researchers/service.py`
  - Ensure workbench overview aggregation is the preferred overview data source and contains all overview fields needed by the redesigned page.
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/researchers/schemas.py`
  - Tighten the workbench overview contract if the page needs status text or extra summary fields.
- Test: `/Users/lushuailei/PycharmProjects/ai/server/tests/test_trading_detail_service.py`
  - Add trading read-path tests covering snapshot reads, lazy history fetches, and AI log shaping.
- Test: `/Users/lushuailei/PycharmProjects/ai/server/tests/test_workbench_overview_service.py`
  - Add overview aggregation tests so the page can rely on a single overview payload.

### Frontend files

- Modify: `/Users/lushuailei/PycharmProjects/ai/web/features/trading/hooks/index.ts`
  - Keep hooks split and ensure heavy queries are opt-in only.
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/features/trading/components/TradingDetailClient.tsx`
  - Rebuild the page layout around account summary, sidebar, log-first view, and lazy history loading.
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/features/researcher-workbench/hooks/index.ts`
  - Make `useWorkbenchOverview` the default overview hook and avoid parallel duplicate queries on the overview screen.
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/app/(workstation)/workstation/ai-researcher/page.tsx`
  - Rebuild the page so total overview uses the aggregate endpoint while selected researchers use a lightweight trading portfolio summary.
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/types/researcher-workbench.ts`
  - Update overview types if the API contract changes.

### Verification commands

- Backend targeted tests: `cd /Users/lushuailei/PycharmProjects/ai/server && pytest tests/test_trading_detail_service.py tests/test_workbench_overview_service.py -v`
- Backend compile check: `cd /Users/lushuailei/PycharmProjects/ai && python3 -m compileall server/app`
- Frontend typecheck: `cd /Users/lushuailei/PycharmProjects/ai && corepack pnpm --dir web typecheck`
- Browser smoke test:
  - `http://localhost:3000/workstation/trading/r_b08dba104a`
  - `http://localhost:3000/workstation/ai-researcher`

### Constraint note

The web app does not currently have a frontend unit-test runner configured in `package.json`, so frontend verification in this plan uses TypeScript typecheck plus manual browser QA. Backend changes should still be protected with pytest coverage.

### Task 1: Lock Trading Detail Read Paths To Snapshot Data

**Files:**
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/service.py`
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/router.py`
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/schemas.py`
- Test: `/Users/lushuailei/PycharmProjects/ai/server/tests/test_trading_detail_service.py`

- [ ] **Step 1: Write the failing backend tests for snapshot-first detail reads**

```python
import pytest
from types import SimpleNamespace

from app.modules.trading.service import TradingService


@pytest.mark.asyncio
async def test_async_get_portfolio_uses_snapshot_without_refresh(monkeypatch):
    service = TradingService()
    session = SimpleNamespace()
    account = SimpleNamespace(
        id="acct_1",
        total_asset=998000.0,
        available_cash=120000.0,
        holding_value=878000.0,
        daily_pnl=3200.0,
    )

    async def fake_resolve_account_model(*_args, **_kwargs):
        return account

    async def fake_list_positions(*_args, **_kwargs):
        return []

    async def fail_refresh(*_args, **_kwargs):
        raise AssertionError("detail read path must not trigger refresh")

    monkeypatch.setattr(service, "_resolve_account_model", fake_resolve_account_model)
    monkeypatch.setattr(service, "async_list_positions", fake_list_positions)
    monkeypatch.setattr(service, "_refresh_account_snapshot", fail_refresh, raising=False)

    data = await service.async_get_portfolio(session, "u_demo", "r_demo")

    assert data.account.total_asset == 998000.0
    assert data.account.daily_pnl == 3200.0
    assert data.positions == []


@pytest.mark.asyncio
async def test_async_get_stats_uses_cached_account_total_asset(monkeypatch):
    service = TradingService()
    session = SimpleNamespace()
    account = SimpleNamespace(id="acct_1", total_asset=1005000.0)

    async def fake_resolve_account_model(*_args, **_kwargs):
        return account

    async def fake_load_records(*_args, **_kwargs):
        return []

    monkeypatch.setattr(service, "_resolve_account_model", fake_resolve_account_model)
    monkeypatch.setattr(service, "_load_account_records", fake_load_records)

    stats = await service.async_get_stats(session, "acct_1")

    assert stats.total_asset == 1005000.0
```

- [ ] **Step 2: Run the tests to verify they fail on the current code**

Run: `cd /Users/lushuailei/PycharmProjects/ai/server && pytest tests/test_trading_detail_service.py -v`

Expected: FAIL because `tests/test_trading_detail_service.py` does not exist yet.

- [ ] **Step 3: Create the test file and implement the minimal snapshot-first service changes**

```python
# /Users/lushuailei/PycharmProjects/ai/server/tests/test_trading_detail_service.py
import pytest
from types import SimpleNamespace

from app.modules.trading.service import TradingService


@pytest.mark.asyncio
async def test_async_get_portfolio_uses_snapshot_without_refresh(monkeypatch):
    service = TradingService()
    session = SimpleNamespace()
    account = SimpleNamespace(
        id="acct_1",
        total_asset=998000.0,
        available_cash=120000.0,
        holding_value=878000.0,
        daily_pnl=3200.0,
    )

    async def fake_resolve_account_model(*_args, **_kwargs):
        return account

    async def fake_list_positions(*_args, **_kwargs):
        return []

    async def fail_refresh(*_args, **_kwargs):
        raise AssertionError("detail read path must not trigger refresh")

    monkeypatch.setattr(service, "_resolve_account_model", fake_resolve_account_model)
    monkeypatch.setattr(service, "async_list_positions", fake_list_positions)
    monkeypatch.setattr(service, "_refresh_account_snapshot", fail_refresh, raising=False)

    data = await service.async_get_portfolio(session, "u_demo", "r_demo")

    assert data.account.total_asset == 998000.0
    assert data.account.daily_pnl == 3200.0
    assert data.positions == []


@pytest.mark.asyncio
async def test_async_get_stats_uses_cached_account_total_asset(monkeypatch):
    service = TradingService()
    session = SimpleNamespace()
    account = SimpleNamespace(id="acct_1", total_asset=1005000.0)

    async def fake_resolve_account_model(*_args, **_kwargs):
        return account

    async def fake_load_records(*_args, **_kwargs):
        return []

    monkeypatch.setattr(service, "_resolve_account_model", fake_resolve_account_model)
    monkeypatch.setattr(service, "_load_account_records", fake_load_records)

    stats = await service.async_get_stats(session, "acct_1")

    assert stats.total_asset == 1005000.0
```

```python
# /Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/service.py
async def async_get_portfolio(self, session: AsyncSession, user_id: str, researcher_id: str) -> TradingPortfolioData:
    account = await self._resolve_account_model(session, user_id, researcher_id)
    positions = await self.async_list_positions(session, account.id, cache_only=True)
    return TradingPortfolioData(
        account=TradingAccount(
            account_id=account.id,
            initial_capital=self._infer_initial_capital(account),
            total_asset=float(account.total_asset),
            available_cash=float(account.available_cash),
            holding_value=float(account.holding_value),
            daily_pnl=float(account.daily_pnl),
        ),
        positions=positions,
    )


async def async_get_stats(self, session: AsyncSession, account_id: str) -> TradingStats:
    account = await session.get(AccountModel, account_id)
    records = await self._load_account_records(session, account_id)
    replay = self._replay_records(records, self._infer_initial_capital(account))
    return self._build_stats_from_replay(
        replay=replay,
        total_asset=float(account.total_asset),
        initial_capital=self._infer_initial_capital(account),
    )
```

- [ ] **Step 4: Run the backend tests again**

Run: `cd /Users/lushuailei/PycharmProjects/ai/server && pytest tests/test_trading_detail_service.py -v`

Expected: PASS for both new tests.

- [ ] **Step 5: Commit the backend snapshot-read work**

```bash
git add \
  /Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/service.py \
  /Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/router.py \
  /Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/schemas.py \
  /Users/lushuailei/PycharmProjects/ai/server/tests/test_trading_detail_service.py
git commit -m "fix: stabilize trading detail snapshot reads"
```

### Task 2: Make Trading Detail Heavy Data Lazy And AI Logs Structured

**Files:**
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/service.py`
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/schemas.py`
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/features/trading/hooks/index.ts`
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/features/trading/components/TradingDetailClient.tsx`
- Test: `/Users/lushuailei/PycharmProjects/ai/server/tests/test_trading_detail_service.py`

- [ ] **Step 1: Extend the backend tests to lock AI log structure and lazy history expectations**

```python
@pytest.mark.asyncio
async def test_async_list_logs_keeps_reflection_sections(monkeypatch):
    service = TradingService()
    session = SimpleNamespace()

    async def fake_load_logs(*_args, **_kwargs):
        return [
            SimpleNamespace(
                id="log_1",
                log_type="analysis",
                title="买入复盘",
                content="## 交易复盘\n- 买入原因\n\n## 执行反思\n- 成交正常\n\n## 次日展望\n- 观察开盘强弱",
                created_at=None,
                trade_group_id="g1",
            )
        ]

    monkeypatch.setattr(service, "_load_trade_logs", fake_load_logs, raising=False)
    items = await service.async_list_logs(session, "acct_1", limit=20)

    assert "交易复盘" in items[0].content
    assert "执行反思" in items[0].content
    assert "次日展望" in items[0].content
```

- [ ] **Step 2: Run the targeted tests to confirm the new case fails first**

Run: `cd /Users/lushuailei/PycharmProjects/ai/server && pytest tests/test_trading_detail_service.py::test_async_list_logs_keeps_reflection_sections -v`

Expected: FAIL until the test file includes the new case and the loader path is aligned.

- [ ] **Step 3: Update service shaping and frontend hooks so history queries are opt-in only**

```python
# /Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/schemas.py
class TradeLogItem(SchemaModel):
    log_id: str
    log_type: str
    title: str
    content: str
    created_at: datetime
    trade_records: list[TradeRecord] = Field(default_factory=list)
```

```ts
// /Users/lushuailei/PycharmProjects/ai/web/features/trading/hooks/index.ts
export const useTradingRecordsWhenEnabled = (researcherId?: string, enabled = true) =>
  useQuery({
    queryKey: [featureKey, 'records', researcherId ?? 'default'],
    queryFn: () => api.getTradingRecords(researcherId),
    enabled: Boolean(researcherId) && enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

export const useTradingStatsWhenEnabled = (researcherId?: string, enabled = true) =>
  useQuery({
    queryKey: [featureKey, 'stats', researcherId ?? 'default'],
    queryFn: () => api.getTradingStats(researcherId),
    enabled: Boolean(researcherId) && enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
```

```tsx
// /Users/lushuailei/PycharmProjects/ai/web/features/trading/components/TradingDetailClient.tsx
const shouldLoadHistory = mainTab === 'history';
const shouldLoadLogs = mainTab === 'log';

const accountQuery = useTradingAccountWhenEnabled(researcherId, true);
const positionsQuery = useTradingPositionsWhenEnabled(researcherId, true);
const logsQuery = useTradingLogsWhenEnabled(researcherId, shouldLoadLogs);
const recordsQuery = useTradingRecordsWhenEnabled(researcherId, shouldLoadHistory || sideTab === 'history');
const statsQuery = useTradingStatsWhenEnabled(researcherId, shouldLoadHistory);
```

- [ ] **Step 4: Rebuild the trading detail layout around log-first reading**

```tsx
// /Users/lushuailei/PycharmProjects/ai/web/features/trading/components/TradingDetailClient.tsx
return (
  <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
    <aside className="rounded-2xl bg-white p-3">
      <PositionSidebar
        positions={positions}
        records={records}
        activeSymbol={activeSymbol}
        onSelect={setActiveSymbol}
        tab={sideTab}
        onTabChange={setSideTab}
      />
    </aside>
    <section className="space-y-4">
      <AccountSummaryCard account={account} />
      {mainTab === 'log' ? <TradeLogPanel logs={logs} /> : <HistoryPanel stats={stats} records={records} />}
    </section>
  </div>
);
```

- [ ] **Step 5: Run backend tests, frontend typecheck, and a browser smoke check**

Run: `cd /Users/lushuailei/PycharmProjects/ai/server && pytest tests/test_trading_detail_service.py -v`

Expected: PASS

Run: `cd /Users/lushuailei/PycharmProjects/ai && corepack pnpm --dir web typecheck`

Expected: PASS with no TypeScript errors

Run in browser: open `http://localhost:3000/workstation/trading/r_b08dba104a`

Expected:
- account summary renders before history charts
- switching to history triggers the heavy requests
- log cards render the three AI sections cleanly

- [ ] **Step 6: Commit the trading detail lazy-load and UI polish work**

```bash
git add \
  /Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/service.py \
  /Users/lushuailei/PycharmProjects/ai/server/app/modules/trading/schemas.py \
  /Users/lushuailei/PycharmProjects/ai/web/features/trading/hooks/index.ts \
  /Users/lushuailei/PycharmProjects/ai/web/features/trading/components/TradingDetailClient.tsx \
  /Users/lushuailei/PycharmProjects/ai/server/tests/test_trading_detail_service.py
git commit -m "feat: polish trading detail experience"
```

### Task 3: Make Workbench Overview Use One Aggregated Overview Query

**Files:**
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/researchers/service.py`
- Modify: `/Users/lushuailei/PycharmProjects/ai/server/app/modules/researchers/schemas.py`
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/features/researcher-workbench/hooks/index.ts`
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/features/researcher-workbench/api/index.ts`
- Test: `/Users/lushuailei/PycharmProjects/ai/server/tests/test_workbench_overview_service.py`

- [ ] **Step 1: Write the failing overview aggregation tests**

```python
import pytest
from types import SimpleNamespace

from app.modules.researchers.service import ResearcherService


@pytest.mark.asyncio
async def test_async_get_workbench_overview_combines_three_sections(monkeypatch):
    service = ResearcherService()
    session = SimpleNamespace()

    async def fake_hired(*_args, **_kwargs):
        return [SimpleNamespace(researcher_id="r1", name="小市值轮动")]

    async def fake_docs(*_args, **_kwargs):
        return [SimpleNamespace(id="d1", title="今日复盘")]

    async def fake_rankings(*_args, **_kwargs):
        return [SimpleNamespace(researcher_id="r1", name="小市值轮动")]

    monkeypatch.setattr(service, "async_list_workbench_hired", fake_hired)
    monkeypatch.setattr(service, "_load_hot_documents_for_workbench", fake_docs, raising=False)
    monkeypatch.setattr(service, "async_list_public_rankings", fake_rankings)

    overview = await service.async_get_workbench_overview(session, "u_demo", sort_by="today")

    assert len(overview.hired) == 1
    assert len(overview.hot_documents) == 1
    assert len(overview.rankings) == 1
```

- [ ] **Step 2: Run the overview tests to verify they fail first**

Run: `cd /Users/lushuailei/PycharmProjects/ai/server && pytest tests/test_workbench_overview_service.py -v`

Expected: FAIL because the file does not exist yet.

- [ ] **Step 3: Create the overview test file and align the service/schema contract**

```python
# /Users/lushuailei/PycharmProjects/ai/server/tests/test_workbench_overview_service.py
import pytest
from types import SimpleNamespace

from app.modules.researchers.service import ResearcherService


@pytest.mark.asyncio
async def test_async_get_workbench_overview_combines_three_sections(monkeypatch):
    service = ResearcherService()
    session = SimpleNamespace()

    async def fake_hired(*_args, **_kwargs):
        return [SimpleNamespace(researcher_id="r1", name="小市值轮动")]

    async def fake_docs(*_args, **_kwargs):
        return [SimpleNamespace(id="d1", title="今日复盘")]

    async def fake_rankings(*_args, **_kwargs):
        return [SimpleNamespace(researcher_id="r1", name="小市值轮动")]

    monkeypatch.setattr(service, "async_list_workbench_hired", fake_hired)
    monkeypatch.setattr(service, "_load_hot_documents_for_workbench", fake_docs, raising=False)
    monkeypatch.setattr(service, "async_list_public_rankings", fake_rankings)

    overview = await service.async_get_workbench_overview(session, "u_demo", sort_by="today")

    assert len(overview.hired) == 1
    assert len(overview.hot_documents) == 1
    assert len(overview.rankings) == 1
```

```python
# /Users/lushuailei/PycharmProjects/ai/server/app/modules/researchers/schemas.py
class WorkbenchOverview(SchemaModel):
    hired: list[WorkbenchHiredResearcher] = Field(default_factory=list)
    hot_documents: list[WorkbenchHotDocument] = Field(default_factory=list)
    rankings: list[WorkbenchPublicRankItem] = Field(default_factory=list)
    quick_actions: list[WorkbenchQuickAction] = Field(default_factory=list)
    risk_disclaimer: str
    partial_failures: list[str] = Field(default_factory=list)
```

```python
# /Users/lushuailei/PycharmProjects/ai/server/app/modules/researchers/service.py
async def async_get_workbench_overview(self, session: AsyncSession, user_id: str, sort_by: WorkbenchRankSortBy):
    hired = await self.async_list_workbench_hired(session, user_id)
    hot_documents = await self._load_hot_documents_for_workbench(session)
    rankings = await self.async_list_public_rankings(session, sort_by=sort_by)
    return WorkbenchOverview(
        hired=hired,
        hot_documents=hot_documents,
        rankings=rankings,
        quick_actions=[],
        risk_disclaimer="模拟盘收益不代表未来表现",
        partial_failures=[],
    )
```

- [ ] **Step 4: Make the frontend overview hook prefer the aggregate endpoint**

```ts
// /Users/lushuailei/PycharmProjects/ai/web/features/researcher-workbench/hooks/index.ts
export const useWorkbenchOverview = (sortBy: RankSortBy = 'today', enabled = true) =>
  useQuery({
    queryKey: [featureKey, 'overview', sortBy],
    queryFn: () => getWorkbenchOverview(sortBy),
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
```

- [ ] **Step 5: Run the overview backend tests**

Run: `cd /Users/lushuailei/PycharmProjects/ai/server && pytest tests/test_workbench_overview_service.py -v`

Expected: PASS

- [ ] **Step 6: Commit the overview aggregation cleanup**

```bash
git add \
  /Users/lushuailei/PycharmProjects/ai/server/app/modules/researchers/service.py \
  /Users/lushuailei/PycharmProjects/ai/server/app/modules/researchers/schemas.py \
  /Users/lushuailei/PycharmProjects/ai/web/features/researcher-workbench/hooks/index.ts \
  /Users/lushuailei/PycharmProjects/ai/web/features/researcher-workbench/api/index.ts \
  /Users/lushuailei/PycharmProjects/ai/server/tests/test_workbench_overview_service.py
git commit -m "refactor: consolidate researcher overview data"
```

### Task 4: Rebuild AI Researcher Overview As The Main Workstation Entry

**Files:**
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/app/(workstation)/workstation/ai-researcher/page.tsx`
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/features/trading/hooks/index.ts`
- Modify: `/Users/lushuailei/PycharmProjects/ai/web/types/researcher-workbench.ts`

- [ ] **Step 1: Replace parallel overview queries with the aggregate workbench query**

```tsx
const overviewQuery = useWorkbenchOverview(rankSortBy, canLoadWorkbench);
const hiredResearchers = overviewQuery.data?.hired ?? [];
const hotDocuments = overviewQuery.data?.hot_documents ?? [];
const publicRankings = overviewQuery.data?.rankings ?? [];
```

- [ ] **Step 2: Keep per-researcher trading data lightweight**

```tsx
const portfolioQuery = useTradingPortfolio(activeResearcherId ?? undefined, Boolean(activeResearcherId));
const account = portfolioQuery.data?.account;
const positions = portfolioQuery.data?.positions ?? [];
```

- [ ] **Step 3: Rebuild the page layout around three overview blocks**

```tsx
return (
  <div className="grid min-h-[calc(100vh-96px)] grid-cols-[240px_minmax(0,1fr)] gap-4">
    <SidePanel
      researchers={hiredResearchers}
      loading={overviewQuery.isLoading}
      activeId={activeResearcherId}
      onSelect={setActiveResearcherId}
    />
    {activeResearcherId ? (
      <ResearcherDetailView researcher={activeResearcher} account={account} positions={positions} />
    ) : (
      <OverviewLanding
        documents={hotDocuments}
        rankings={publicRankings}
        loading={overviewQuery.isLoading}
      />
    )}
  </div>
);
```

- [ ] **Step 4: Run frontend typecheck and browser verification**

Run: `cd /Users/lushuailei/PycharmProjects/ai && corepack pnpm --dir web typecheck`

Expected: PASS

Run in browser: open `http://localhost:3000/workstation/ai-researcher`

Expected:
- overview opens with researcher cards, hot documents, and rankings
- overview requests `workbench/overview` instead of three separate overview requests
- selecting a researcher only adds the lightweight portfolio request

- [ ] **Step 5: Commit the overview page redesign**

```bash
git add \
  /Users/lushuailei/PycharmProjects/ai/web/app/'(workstation)'/workstation/ai-researcher/page.tsx \
  /Users/lushuailei/PycharmProjects/ai/web/features/trading/hooks/index.ts \
  /Users/lushuailei/PycharmProjects/ai/web/types/researcher-workbench.ts
git commit -m "feat: redesign ai researcher workstation overview"
```

### Task 5: Final Verification, Regression Check, And Handoff

**Files:**
- Modify: `/Users/lushuailei/PycharmProjects/ai/docs/superpowers/specs/2026-04-24-trading-detail-and-ai-researcher-overview-design.md` (only if the implementation reveals a required design correction)
- Modify: `/Users/lushuailei/PycharmProjects/ai/docs/superpowers/plans/2026-04-24-trading-detail-and-ai-researcher-overview.md` (checkbox tracking only, optional)

- [ ] **Step 1: Run the full backend checks**

Run: `cd /Users/lushuailei/PycharmProjects/ai/server && pytest tests/test_trading_detail_service.py tests/test_workbench_overview_service.py -v`

Expected: PASS

Run: `cd /Users/lushuailei/PycharmProjects/ai && python3 -m compileall server/app`

Expected: PASS with no syntax errors

- [ ] **Step 2: Run the full frontend check**

Run: `cd /Users/lushuailei/PycharmProjects/ai && corepack pnpm --dir web typecheck`

Expected: PASS

- [ ] **Step 3: Run browser regression on both pages**

Check `http://localhost:3000/workstation/trading/r_b08dba104a`

Expected:
- account summary loads first
- current positions render without waiting on history
- history tab loads charts only after selection
- AI log cards render markdown sections cleanly

Check `http://localhost:3000/workstation/ai-researcher`

Expected:
- total overview loads with one overview query
- no heavy trading detail request is fired on overview load
- selecting a researcher shows latest artifacts plus lightweight trading summary

- [ ] **Step 4: Capture final notes and commit any plan/spec corrections if needed**

```bash
git status --short
```

Expected: only intentional implementation files remain modified.

- [ ] **Step 5: Final commit**

```bash
git add /Users/lushuailei/PycharmProjects/ai
git commit -m "feat: finish trading detail and overview overhaul"
```
