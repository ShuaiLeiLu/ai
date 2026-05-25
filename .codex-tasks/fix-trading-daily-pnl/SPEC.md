# Task Specification

## Task Shape

- **Shape**: `single-full`

## Goals

- Fix the simulated trading detail account summary so "今日盈亏" reflects the current account's persisted daily mark-to-market PnL, not a multi-day delta from the last replay equity node.

## Non-Goals

- Do not redesign the trading detail UI.
- Do not change order execution formulas unless directly required by the daily PnL display bug.

## Constraints

- Python backend with pytest.
- Keep the change scoped to account summary serialization and tests.

## Environment

- **Project root**: `D:\AI\jirui`
- **Language/runtime**: `Python`
- **Package manager**: `pip requirements`
- **Test framework**: `pytest`
- **Build command**: `n/a for this fix`
- **Existing test file**: `server/tests/test_trading_detail_service.py`

## Risk Assessment

- [x] Breaking changes to existing code: account display PnL semantics change from derived recent PnL back to current daily snapshot PnL.
- [x] External dependencies: no live market dependency needed for focused tests.

## Deliverables

- `server/tests/test_trading_detail_service.py` regression coverage.
- `server/app/modules/trading/service.py` account serialization fix.

## Done-When

- [x] Account endpoints expose persisted `daily_pnl` for today's summary.
- [x] Total PnL and total return remain based on initial capital.
- [x] Focused trading detail tests pass.

## Final Validation Command

```bash
pytest server/tests/test_trading_detail_service.py --tb=short
```
