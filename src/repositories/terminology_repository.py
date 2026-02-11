"""术语库 Repository（Async）"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.postgres.models_datasource import Terminology
from src.utils.datetime_utils import utc_now_naive


class TerminologyRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create(self, data: dict[str, Any]) -> Terminology:
        term = Terminology(**data)
        self.db.add(term)
        await self.db.flush()
        await self.db.refresh(term)
        return term

    async def get_by_id(self, term_id: int) -> Terminology | None:
        result = await self.db.execute(select(Terminology).where(Terminology.id == term_id))
        return result.scalar_one_or_none()

    async def list_all(self, enabled_only: bool = False) -> list[Terminology]:
        query = select(Terminology).order_by(Terminology.created_at.desc())
        if enabled_only:
            query = query.where(Terminology.enabled.is_(True))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_datasource(self, datasource_id: int) -> list[Terminology]:
        """获取与指定数据源关联的术语（包括非指定数据源的通用术语）"""
        all_terms = await self.list_all(enabled_only=True)
        return [
            t for t in all_terms
            if not t.specific_ds or (t.datasource_ids and datasource_id in t.datasource_ids)
        ]

    async def update(self, term_id: int, data: dict[str, Any]) -> Terminology | None:
        term = await self.get_by_id(term_id)
        if term is None:
            return None
        for key, value in data.items():
            setattr(term, key, value)
        term.updated_at = utc_now_naive()
        await self.db.flush()
        await self.db.refresh(term)
        return term

    async def delete(self, term_id: int) -> bool:
        term = await self.get_by_id(term_id)
        if term is None:
            return False
        await self.db.delete(term)
        await self.db.flush()
        return True
