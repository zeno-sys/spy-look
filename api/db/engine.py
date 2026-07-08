from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from config import DB_URL

# 导入 ORM 模型，确保 metadata 包含全部表定义
import db.models  # noqa: F401

async_engine: AsyncEngine = create_async_engine(DB_URL, echo=False)
async_session_factory = AsyncSession


async def init_db() -> None:
    # 以 ORM 为准建表；schema 变更时删除 api/spy_look.db 后重启，不做 ALTER TABLE 补丁
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory(async_engine) as session:
        yield session
