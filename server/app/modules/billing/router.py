from __future__ import annotations

from fastapi import APIRouter, Query

from app.modules.billing.schemas import BatteryLedgerItem, BatteryPackage, MembershipInfo
from app.modules.billing.service import BillingService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/billing", tags=["billing"])
service = BillingService()


@router.get("/membership")
async def get_membership() -> ApiResponse[MembershipInfo]:
    return ApiResponse(data=service.get_membership())


@router.get("/battery/ledger")
async def list_battery_ledger(
    limit: int = Query(default=50, ge=1, le=200),
) -> ApiResponse[ListResponse[BatteryLedgerItem]]:
    items = service.list_ledger(limit=limit)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/battery/packages")
async def list_battery_packages() -> ApiResponse[ListResponse[BatteryPackage]]:
    items = service.list_packages()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
