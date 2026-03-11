"""数据源域持久化 Repository（Async）"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.storage.postgres.models_datasource import (
    DataChatRecord,
    DataChatSession,
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

    async def upsert_chat_session(
        self,
        *,
        user_id: str,
        chat_id: str,
        qa_type: str | None,
        title: str | None = None,
        datasource_id: int | None = None,
    ) -> DataChatSession:
        result = await self.db.execute(select(DataChatSession).where(DataChatSession.chat_id == chat_id))
        session = result.scalar_one_or_none()
        if session is None:
            session = DataChatSession(
                user_id=str(user_id),
                chat_id=chat_id,
                title=title,
                datasource_id=datasource_id,
                qa_type=qa_type,
                status="active",
            )
            self.db.add(session)
        else:
            # 仅在首次创建时用问题做标题；后续不覆盖用户重命名的 title
            if session.title in (None, "", "新对话") and title:
                session.title = title
            if datasource_id is not None:
                session.datasource_id = datasource_id
            if qa_type is not None:
                session.qa_type = qa_type
            session.updated_at = utc_now_naive()
            if session.status == "deleted":
                session.status = "active"

        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def rename_chat_session(self, *, user_id: str, chat_id: str, title: str) -> bool:
        result = await self.db.execute(
            select(DataChatSession).where(
                DataChatSession.chat_id == chat_id,
                DataChatSession.user_id == str(user_id),
                DataChatSession.status == "active",
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        session.title = str(title).strip()[:255]
        session.updated_at = utc_now_naive()
        await self.db.flush()
        return True

    async def delete_chat_session(self, *, user_id: str, chat_id: str) -> bool:
        result = await self.db.execute(
            select(DataChatSession).where(
                DataChatSession.chat_id == chat_id,
                DataChatSession.user_id == str(user_id),
                DataChatSession.status == "active",
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        session.status = "deleted"
        session.updated_at = utc_now_naive()
        await self.db.flush()
        return True

    async def list_chat_records(
        self, user_id: str, chat_id: str | None = None, limit: int = 50,
    ) -> list[DataChatRecord]:
        query = select(DataChatRecord).where(DataChatRecord.user_id == user_id)
        if chat_id:
            query = query.where(DataChatRecord.chat_id == chat_id)
        query = query.order_by(DataChatRecord.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_chat_sessions(
        self,
        user_id: str,
        limit: int = 50,
        page: int = 1,
        qa_type: str | None = None,
        search_text: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """获取用户的对话列表（支持分页、问答模式过滤、搜索、重命名/删除）

        Args:
            user_id: 用户ID
            limit: 每页数量
            page: 页码
            qa_type: 问答模式过滤
            search_text: 搜索关键词

        Returns:
            tuple: (会话列表, 总数)
        """
        from sqlalchemy import func

        query = select(DataChatSession).where(
            DataChatSession.user_id == str(user_id),
            DataChatSession.status == "active",
        )

        if qa_type:
            query = query.where(DataChatSession.qa_type == qa_type)

        if search_text:
            query = query.where(DataChatSession.title.ilike(f"%{search_text}%"))

        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = int(count_result.scalar() or 0)

        offset = (page - 1) * limit
        query = query.order_by(DataChatSession.updated_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        items = list(result.scalars().all())
        sessions = [
            {
                "chat_id": s.chat_id,
                "last_time": str(s.updated_at or s.created_at),
                "title": s.title,
                "datasource_id": s.datasource_id,
                "qa_type": s.qa_type,
            }
            for s in items
        ]

        return sessions, total
