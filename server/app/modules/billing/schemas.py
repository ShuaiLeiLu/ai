from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.schemas.common import SchemaModel

MembershipLevel = Literal["FREE", "VIP1", "VIP2", "VIP3"]


class MembershipInfo(SchemaModel):
    level: MembershipLevel
    display_name: str
    battery_discount: float
    unlocked_features: list[str]


class BatteryLedgerItem(SchemaModel):
    item_id: str
    change: int
    reason: str
    created_at: datetime


class BatteryPackage(SchemaModel):
    package_id: str
    name: str
    battery_count: int
    price: float
