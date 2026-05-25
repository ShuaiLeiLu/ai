# Progress Log

## Session Start

- **Date**: 2026-05-25
- **Task name**: `fix-trading-daily-pnl`
- **Task dir**: `.codex-tasks/fix-trading-daily-pnl/`
- **Spec**: See SPEC.md
- **Plan**: See TODO.csv
- **Environment**: Python / FastAPI service / pytest

## Context Recovery Block

- **Current milestone**: #4 - Run focused verification
- **Current status**: DONE
- **Last completed**: #4 - Run focused verification
- **Current artifact**: `server/app/modules/trading/service.py`
- **Key context**: Screenshot shows total asset 1.2508M but today PnL +49,445.67 / +4.09%. `_account_to_schema` derives daily PnL from replay equity, so when the last replay point is older than yesterday it displays a multi-day account delta as today's PnL.
- **Known issues**: Existing unrelated dirty files: `server/tests/test_preopen_snapshots.py`, `server/tests/test_daily_review_readonly.py`.
- **Next action**: Report completion with verification evidence.

## Milestone 1: Identify Daily PnL Root Cause

- **Status**: DONE
- **What was done**:
  - Traced the trading detail UI values to `acct.daily_pnl`.
  - Traced backend serialization to `_account_to_schema()` and `_derive_recent_pnl()`.
- **Key decision**:
  - The fix belongs in backend account serialization because all account consumers receive the same bad summary field.
- **Next step**: Milestone 2 - Add failing daily PnL regression test.

## Milestone 2: Add Failing Daily PnL Regression Test

- **Status**: DONE
- **What was done**:
  - Added `test_async_get_account_uses_current_snapshot_daily_pnl`.
- **Validation**: `pytest server/tests/test_trading_detail_service.py -k current_snapshot_daily_pnl --tb=short` failed before the production fix with `49445.67 == -19130.0`.
- **Next step**: Milestone 3 - Fix account serialization PnL source.

## Milestone 3: Fix Account Serialization PnL Source

- **Status**: DONE
- **What was done**:
  - Removed replay-derived recent PnL from `_account_to_schema`.
  - Serialized persisted `account.daily_pnl` as the account summary's daily PnL.
  - Updated schema comment and existing account tests to the corrected daily PnL semantics.
- **Next step**: Milestone 4 - Run focused verification.

## Milestone 4: Run Focused Verification

- **Status**: DONE
- **Validation**:
  - `pytest server/tests/test_trading_detail_service.py -k "account or portfolio or current_snapshot_daily_pnl or persisted_daily_pnl" --tb=short` -> 5 passed.
  - `git diff --check -- server/app/modules/trading/service.py server/app/modules/trading/schemas.py server/tests/test_trading_detail_service.py` -> exit 0.
  - `pytest server/tests/test_trading_detail_service.py --tb=short` -> 15 passed.

## Final Summary

- **Completed**: The daily PnL display bug is fixed for account/portfolio summary serialization, and the trading detail service test file passes.
- **Files modified**:
  - `server/app/modules/trading/service.py`
  - `server/app/modules/trading/schemas.py`
  - `server/tests/test_trading_detail_service.py`
