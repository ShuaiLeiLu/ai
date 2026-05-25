from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.container import get_container
from app.core.security import get_current_user_id
from app.modules.billing.schemas import BatteryLedgerItem, BatteryPackage, MembershipInfo
from app.modules.billing.service import BillingService
from app.modules.page_cache import load_cached, save_cached
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/billing", tags=["billing"])
service = BillingService()
_CACHE_TTL_SECONDS = 120
_MEMBERSHIP_ADAPTER = TypeAdapter(MembershipInfo)
_LEDGER_ADAPTER = TypeAdapter(list[BatteryLedgerItem])
_PACKAGES_ADAPTER = TypeAdapter(list[BatteryPackage])


async def _load_billing_cache(name: str, adapter: TypeAdapter):
    try:
        redis = get_container().redis.get_client()
        return await load_cached(redis, name, adapter)
    except Exception:
        return None


async def _save_billing_cache(name: str, data: object) -> None:
    try:
        redis = get_container().redis.get_client()
        await save_cached(redis, name, data, ttl_seconds=_CACHE_TTL_SECONDS)
    except Exception:
        return


@router.get("/membership")
async def get_membership(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[MembershipInfo]:
    if not session:
        return ApiResponse(data=MembershipInfo(
            level="FREE",
            display_name="未开通",
            battery_discount=1.0,
            unlocked_features=[],
        ))
    cache_name = f"billing:membership:{user_id}"
    cached = await _load_billing_cache(cache_name, _MEMBERSHIP_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_membership(session, user_id)
    await _save_billing_cache(cache_name, data)
    return ApiResponse(data=data)


@router.get("/battery/ledger")
async def list_battery_ledger(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[BatteryLedgerItem]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = f"billing:battery-ledger:{user_id}:limit={limit}"
    cached = await _load_billing_cache(cache_name, _LEDGER_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_ledger(session, user_id, limit=limit)
    await _save_billing_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/battery/packages")
async def list_battery_packages(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[BatteryPackage]]:
    cached = await _load_billing_cache("billing:battery-packages", _PACKAGES_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_packages(session)
    await _save_billing_cache("billing:battery-packages", items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
