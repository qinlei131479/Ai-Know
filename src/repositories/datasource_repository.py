"""数据源域持久化 Repository（Async）"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.storage.postgres.models_datasource import (
    DataChatRecord,
    Datasource,
    DatasourceField,
    DatasourceTable,
)
from src.utils.datetime_utils import utc_now_naive


class DatasourceRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    # ── Datasource CRUD ──

    async def create_datasource(self, data: dict[str, Any]) -> Datasource:
        ds = Datasource(**data)
        self.db.add(ds)
        await self.db.flush()
        await self.db.refresh(ds)
        return ds

    async def get_datasource_by_id(self, ds_id: int) -> Datasource | None:
        result = await self.db.execute(select(Datasource).where(Datasource.id == ds_id))
        return result.scalar_one_or_none()

    async def list_datasources(self) -> list[Datasource]:
        result = await self.db.execute(select(Datasource).order_by(Datasource.created_at.desc()))
        return list(result.scalars().all())

    async def update_datasource(self, ds_id: int, data: dict[str, Any]) -> Datasource | None:
        ds = await self.get_datasource_by_id(ds_id)
        if ds is None:
            return None
        for key, value in data.items():
            setattr(ds, key, value)
        ds.updated_at = utc_now_naive()
        await self.db.flush()
        await self.db.refresh(ds)
        return ds

    async def delete_datasource(self, ds_id: int) -> bool:
        ds = await self.get_datasource_by_id(ds_id)
        if ds is None:
            return False
        await self.db.delete(ds)
        await self.db.flush()
        return True

    # ── DatasourceTable CRUD ──

    async def list_tables(self, ds_id: int) -> list[DatasourceTable]:
        result = await self.db.execute(
            select(DatasourceTable)
            .options(selectinload(DatasourceTable.fields))
            .where(DatasourceTable.ds_id == ds_id)
            .order_by(DatasourceTable.table_name)
        )
        return list(result.scalars().unique().all())

    async def get_table_by_id(self, table_id: int) -> DatasourceTable | None:
        result = await self.db.execute(
            select(DatasourceTable)
            .options(selectinload(DatasourceTable.fields))
            .where(DatasourceTable.id == table_id)
        )
        return result.scalar_one_or_none()

    async def upsert_table(self, ds_id: int, table_name: str, table_comment: str | None = None) -> DatasourceTable:
        """创建或更新表信息"""
        result = await self.db.execute(
            select(DatasourceTable).where(
                DatasourceTable.ds_id == ds_id,
                DatasourceTable.table_name == table_name,
            )
        )
        table = result.scalar_one_or_none()
        if table:
            if table_comment is not None:
                table.table_comment = table_comment
        else:
            table = DatasourceTable(ds_id=ds_id, table_name=table_name, table_comment=table_comment)
            self.db.add(table)
            await self.db.flush()
            await self.db.refresh(table)
        return table

    async def update_table(self, table_id: int, data: dict[str, Any]) -> DatasourceTable | None:
        table = await self.get_table_by_id(table_id)
        if table is None:
            return None
        for key, value in data.items():
            setattr(table, key, value)
        await self.db.flush()
        return table

    async def delete_tables_not_in(self, ds_id: int, table_names: list[str]) -> None:
        """删除不在给定列表中的表（用于同步）"""
        if table_names:
            await self.db.execute(
                delete(DatasourceTable).where(
                    DatasourceTable.ds_id == ds_id,
                    DatasourceTable.table_name.notin_(table_names),
                )
            )
        else:
            await self.db.execute(delete(DatasourceTable).where(DatasourceTable.ds_id == ds_id))

    # ── DatasourceField CRUD ──

    async def list_fields(self, table_id: int) -> list[DatasourceField]:
        result = await self.db.execute(
            select(DatasourceField)
            .where(DatasourceField.table_id == table_id)
            .order_by(DatasourceField.field_index)
        )
        return list(result.scalars().all())

    async def upsert_field(
        self, ds_id: int, table_id: int, field_name: str, field_type: str | None = None,
        field_comment: str | None = None, field_index: int | None = None,
    ) -> DatasourceField:
        """创建或更新字段信息"""
        result = await self.db.execute(
            select(DatasourceField).where(
                DatasourceField.table_id == table_id,
                DatasourceField.field_name == field_name,
            )
        )
        field = result.scalar_one_or_none()
        if field:
            if field_type is not None:
                field.field_type = field_type
            if field_comment is not None:
                field.field_comment = field_comment
            if field_index is not None:
                field.field_index = field_index
        else:
            field = DatasourceField(
                ds_id=ds_id, table_id=table_id, field_name=field_name,
                field_type=field_type, field_comment=field_comment, field_index=field_index,
            )
            self.db.add(field)
            await self.db.flush()
            await self.db.refresh(field)
        return field

    async def update_field(self, field_id: int, data: dict[str, Any]) -> DatasourceField | None:
        result = await self.db.execute(select(DatasourceField).where(DatasourceField.id == field_id))
        field = result.scalar_one_or_none()
        if field is None:
            return None
        for key, value in data.items():
            setattr(field, key, value)
        await self.db.flush()
        return field

    async def delete_fields_not_in(self, table_id: int, field_names: list[str]) -> None:
        """删除不在给定列表中的字段（用于同步）"""
        if field_names:
            await self.db.execute(
                delete(DatasourceField).where(
                    DatasourceField.table_id == table_id,
                    DatasourceField.field_name.notin_(field_names),
                )
            )
        else:
            await self.db.execute(delete(DatasourceField).where(DatasourceField.table_id == table_id))

    # ── DataChatRecord ──

    async def create_chat_record(self, data: dict[str, Any]) -> DataChatRecord:
        record = DataChatRecord(**data)
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def list_chat_records(
        self, user_id: str, chat_id: str | None = None, limit: int = 50,
    ) -> list[DataChatRecord]:
        query = select(DataChatRecord).where(DataChatRecord.user_id == user_id)
        if chat_id:
            query = query.where(DataChatRecord.chat_id == chat_id)
        query = query.order_by(DataChatRecord.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_chat_sessions(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """获取用户的对话列表（按 chat_id 分组，取最新一条）"""
        from sqlalchemy import func

        subq = (
            select(
                DataChatRecord.chat_id,
                func.max(DataChatRecord.created_at).label("last_time"),
                func.min(DataChatRecord.question).label("first_question"),
                func.max(DataChatRecord.datasource_id).label("datasource_id"),
            )
            .where(DataChatRecord.user_id == user_id)
            .group_by(DataChatRecord.chat_id)
            .order_by(func.max(DataChatRecord.created_at).desc())
            .limit(limit)
            .subquery()
        )
        result = await self.db.execute(select(subq))
        return [
            {
                "chat_id": row.chat_id,
                "last_time": str(row.last_time),
                "first_question": row.first_question,
                "datasource_id": row.datasource_id,
            }
            for row in result.all()
        ]
