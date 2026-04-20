"""重置模拟盘数据 —— 清空持仓/成交/日志，账户资金恢复为 100 万

用法：
  .venv/bin/python server/scripts/reset_trading.py
"""
import asyncio
import sys
from pathlib import Path

# 将项目根目录加入 sys.path 以便导入 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.core.config import get_settings


async def main():
    db_url = get_settings().database_url
    engine = create_async_engine(db_url)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        r1 = await session.execute(text("DELETE FROM trade_records"))
        print(f"trade_records: 删除 {r1.rowcount} 条")
        r2 = await session.execute(text("DELETE FROM positions"))
        print(f"positions: 删除 {r2.rowcount} 条")
        r3 = await session.execute(text("DELETE FROM trade_logs"))
        print(f"trade_logs: 删除 {r3.rowcount} 条")
        r4 = await session.execute(text(
            "UPDATE trading_accounts SET total_asset=1000000, available_cash=1000000, holding_value=0, daily_pnl=0"
        ))
        print(f"trading_accounts: 重置 {r4.rowcount} 个账户")
        r5 = await session.execute(text("UPDATE researchers SET today_pnl=0"))
        print(f"researchers: 重置 {r5.rowcount} 个研究员 today_pnl")
        await session.commit()
    await engine.dispose()
    print("模拟盘数据重置完成!")


if __name__ == "__main__":
    asyncio.run(main())
