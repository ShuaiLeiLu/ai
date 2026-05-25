# Fix Preopen Realtime

## Goal
Make the preopen dashboard reflect current trading-session data instead of showing a hardcoded previous trading day in the limit-up ladder modal.

## Findings
- Frontend `LimitUpLadderCard` hardcodes `2026-05-22`, `2026-05-21`, `2026-05-20` and sample promotion/failure pools.
- Backend preopen router names helpers `*_or_live`, but `_load_list_or_live` discards the `fetch` callback and only reads Redis snapshots.
- React Query `staleTime` does not poll; an already open dashboard can remain stale.
