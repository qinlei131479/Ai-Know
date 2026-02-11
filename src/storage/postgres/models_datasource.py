"""PostgreSQL 数据源相关模型 - 数据源管理、术语库、SQL 示例、数据问答记录"""

from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.storage.postgres.models_business import Base
from src.utils.datetime_utils import format_utc_datetime, utc_now_naive


class Datasource(Base):
    """数据源"""

    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="数据源名称")
    description = Column(Text, nullable=True, comment="描述")
    ds_type = Column(String(50), nullable=False, comment="数据源类型")
    type_name = Column(String(50), nullable=True, comment="类型显示名称")
    configuration = Column(Text, nullable=False, comment="连接配置信息(加密)")
    status = Column(String(20), nullable=True, default="pending", comment="状态: success, failed, pending")
    table_count = Column(String(50), nullable=True, comment="表数量统计: selected/total")
    table_relation = Column(JSON, nullable=True, comment="表关系(JSON)")
    created_by = Column(String(64), nullable=True, comment="创建人 user_id")
    created_at = Column(DateTime, default=utc_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, comment="更新时间")

    # 关联
    tables = relationship("DatasourceTable", back_populates="datasource", cascade="all, delete-orphan")

    def to_dict(self, decrypt_config: bool = False) -> dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ds_type": self.ds_type,
            "type_name": self.type_name,
            "status": self.status,
            "table_count": self.table_count,
            "table_relation": self.table_relation,
            "created_by": self.created_by,
            "created_at": format_utc_datetime(self.created_at),
            "updated_at": format_utc_datetime(self.updated_at),
        }
        if decrypt_config:
            from src.services.datasource_crypto import decrypt_datasource_config

            try:
                result["configuration"] = decrypt_datasource_config(self.configuration)
            except Exception:
                result["configuration"] = {}
        return result


class DatasourceTable(Base):
    """数据源表信息"""

    __tablename__ = "datasource_tables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ds_id = Column(
        Integer, ForeignKey("datasources.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="数据源ID",
    )
    table_name = Column(String(255), nullable=False, comment="表名")
    table_comment = Column(Text, nullable=True, comment="表注释(来自数据库)")
    custom_comment = Column(Text, nullable=True, comment="自定义注释")
    checked = Column(Boolean, default=True, comment="是否选中参与问答")
    embedding = Column(Text, nullable=True, comment="表结构 embedding")

    # 关联
    datasource = relationship("Datasource", back_populates="tables")
    fields = relationship("DatasourceField", back_populates="table", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_datasource_tables_ds_table", "ds_id", "table_name", unique=True),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ds_id": self.ds_id,
            "table_name": self.table_name,
            "table_comment": self.table_comment,
            "custom_comment": self.custom_comment,
            "checked": bool(self.checked),
        }


class DatasourceField(Base):
    """数据源字段信息"""

    __tablename__ = "datasource_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ds_id = Column(
        Integer, ForeignKey("datasources.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="数据源ID",
    )
    table_id = Column(
        Integer, ForeignKey("datasource_tables.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="表ID",
    )
    field_name = Column(String(255), nullable=False, comment="字段名")
    field_type = Column(String(100), nullable=True, comment="字段类型")
    field_comment = Column(Text, nullable=True, comment="字段注释(来自数据库)")
    custom_comment = Column(Text, nullable=True, comment="自定义注释")
    field_index = Column(Integer, nullable=True, comment="字段顺序")
    checked = Column(Boolean, default=True, comment="是否选中")

    # 关联
    table = relationship("DatasourceTable", back_populates="fields")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ds_id": self.ds_id,
            "table_id": self.table_id,
            "field_name": self.field_name,
            "field_type": self.field_type,
            "field_comment": self.field_comment,
            "custom_comment": self.custom_comment,
            "field_index": self.field_index,
            "checked": bool(self.checked),
        }


class Terminology(Base):
    """术语表 - 业务术语定义，辅助 Text2SQL 理解"""

    __tablename__ = "terminologies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(255), nullable=False, comment="术语名称")
    description = Column(Text, nullable=True, comment="术语描述/解释")
    specific_ds = Column(Boolean, default=False, comment="是否指定特定数据源")
    datasource_ids = Column(JSON, nullable=True, comment="关联的数据源ID列表")
    enabled = Column(Boolean, default=True, comment="是否启用")
    embedding = Column(Text, nullable=True, comment="术语向量数据(JSON 数组字符串)")
    created_at = Column(DateTime, default=utc_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, comment="更新时间")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "word": self.word,
            "description": self.description,
            "specific_ds": bool(self.specific_ds) if self.specific_ds is not None else False,
            "datasource_ids": self.datasource_ids or [],
            "enabled": bool(self.enabled) if self.enabled is not None else True,
            "created_at": format_utc_datetime(self.created_at),
            "updated_at": format_utc_datetime(self.updated_at),
        }


class SqlExample(Base):
    """SQL 示例表 - Few-shot 示例，提升 SQL 生成质量"""

    __tablename__ = "sql_examples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    datasource_id = Column(
        Integer, ForeignKey("datasources.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="关联数据源ID",
    )
    question = Column(String(512), nullable=False, comment="问题描述")
    sql_text = Column(Text, nullable=False, comment="示例SQL")
    enabled = Column(Boolean, default=True, comment="是否启用")
    embedding = Column(Text, nullable=True, comment="问题向量数据(JSON 数组字符串)")
    created_at = Column(DateTime, default=utc_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, comment="更新时间")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "datasource_id": self.datasource_id,
            "question": self.question,
            "sql_text": self.sql_text,
            "enabled": bool(self.enabled) if self.enabled is not None else True,
            "created_at": format_utc_datetime(self.created_at),
            "updated_at": format_utc_datetime(self.updated_at),
        }


class DataChatRecord(Base):
    """数据问答记录"""

    __tablename__ = "data_chat_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True, comment="用户ID")
    chat_id = Column(String(100), nullable=False, index=True, comment="对话ID(同一轮对话)")
    message_id = Column(String(100), nullable=True, comment="消息ID")
    question = Column(Text, nullable=True, comment="用户问题")
    answer = Column(Text, nullable=True, comment="AI 回答摘要")
    datasource_id = Column(
        Integer, ForeignKey("datasources.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="数据源ID",
    )
    sql_statement = Column(Text, nullable=True, comment="生成的SQL语句")
    query_result = Column(JSON, nullable=True, comment="查询结果数据(JSON)")
    chart_config = Column(JSON, nullable=True, comment="图表配置(JSON)")
    qa_type = Column(String(50), nullable=True, comment="问答类型: data/excel/general")
    file_key = Column(String(255), nullable=True, comment="文件 MinIO key(Excel 问答)")
    created_at = Column(DateTime, default=utc_now_naive, index=True, comment="创建时间")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "question": self.question,
            "answer": self.answer,
            "datasource_id": self.datasource_id,
            "sql_statement": self.sql_statement,
            "query_result": self.query_result,
            "chart_config": self.chart_config,
            "qa_type": self.qa_type,
            "file_key": self.file_key,
            "created_at": format_utc_datetime(self.created_at),
        }
