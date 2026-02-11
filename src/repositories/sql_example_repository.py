"""SQL 示例库 Repository（Async）"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.postgres.models_datasource import SqlExample
from src.utils.datetime_utils import utc_now_naive


class SqlExampleRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create(self, data: dict[str, Any]) -> SqlExample:
        example = SqlExample(**data)
        self.db.add(example)
        await self.db.flush()
        await self.db.refresh(example)
        return example

    async def get_by_id(self, example_id: int) -> SqlExample | None:
        result = await self.db.execute(select(SqlExample).where(SqlExample.id == example_id))
        return result.scalar_one_or_none()

    async def list_all(self, enabled_only: bool = False) -> list[SqlExample]:
        query = select(SqlExample).order_by(SqlExample.created_at.desc())
        if enabled_only:
            query = query.where(SqlExample.enabled.is_(True))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_datasource(self, datasource_id: int) -> list[SqlExample]:
        query = (
            select(SqlExample)
            .where(SqlExample.datasource_id == datasource_id, SqlExample.enabled.is_(True))
            .order_by(SqlExample.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, example_id: int, data: dict[str, Any]) -> SqlExample | None:
        example = await self.get_by_id(example_id)
        if example is None:
            return None
        for key, value in data.items():
            setattr(example, key, value)
        example.updated_at = utc_now_naive()
        await self.db.flush()
        await self.db.refresh(example)
        return example

    async def delete(self, example_id: int) -> bool:
        example = await self.get_by_id(example_id)
        if example is None:
            return False
        await self.db.delete(example)
        await self.db.flush()
        return True
