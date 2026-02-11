"""表结构检索节点 - 从元数据库获取数据源表结构信息并通过 BM25 筛选最相关的表"""

import re

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data_chat.state import DataChatState
from src.storage.postgres.models_datasource import DatasourceField, DatasourceTable
from src.utils import logger

# 返回最大表数量
_TABLE_RETURN_COUNT = 6


def _tokenize(text_str: str) -> list[str]:
    """对中文/英文文本进行分词"""
    filtered = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", text_str)
    return [t.strip() for t in jieba.lcut(filtered, cut_all=False) if t.strip()]


def _build_document(table_name: str, table_info: dict) -> str:
    """构建检索文档（表名 + 注释 + 字段名 + 字段注释）"""
    parts = [table_name]
    if table_info.get("table_comment"):
        parts.append(table_info["table_comment"])
    for col_name, col_info in table_info.get("columns", {}).items():
        parts.append(col_name)
        if col_info.get("comment"):
            parts.append(col_info["comment"])
    return " ".join(parts)


async def _fetch_table_info_from_db(
    session: AsyncSession,
    datasource_id: int,
) -> dict[str, dict]:
    """从元数据库获取数据源下所有已勾选的表和字段信息"""
    # 获取已选中的表
    result = await session.execute(
        select(DatasourceTable).where(
            DatasourceTable.ds_id == datasource_id,
            DatasourceTable.checked.is_(True),
        )
    )
    tables = result.scalars().all()

    if not tables:
        return {}

    # 批量获取所有字段
    table_ids = [t.id for t in tables]
    result = await session.execute(
        select(DatasourceField).where(
            DatasourceField.ds_id == datasource_id,
            DatasourceField.table_id.in_(table_ids),
            DatasourceField.checked.is_(True),
        )
    )
    all_fields = result.scalars().all()

    # 按 table_id 分组
    fields_by_table: dict[int, list] = {}
    for f in all_fields:
        fields_by_table.setdefault(f.table_id, []).append(f)

    table_info: dict[str, dict] = {}
    for table in tables:
        table_fields = fields_by_table.get(table.id, [])
        if not table_fields:
            continue

        columns = {}
        for f in table_fields:
            columns[f.field_name] = {
                "type": f.field_type or "",
                "comment": f.custom_comment or f.field_comment or "",
            }

        table_info[table.table_name] = {
            "columns": columns,
            "foreign_keys": [],
            "table_comment": table.custom_comment or table.table_comment or "",
        }

    return table_info


def _bm25_retrieve(
    all_table_info: dict[str, dict],
    user_query: str,
    top_k: int = _TABLE_RETURN_COUNT,
) -> dict[str, dict]:
    """使用 BM25 对表进行相关性排序并返回 top_k"""
    if not user_query or not all_table_info:
        return dict(list(all_table_info.items())[:top_k])

    table_names = list(all_table_info.keys())
    corpus = [_build_document(name, all_table_info[name]) for name in table_names]
    tokenized_corpus = [_tokenize(doc) for doc in corpus]
    query_tokens = _tokenize(user_query)

    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query_tokens)

    # 增强：查询词出现在表注释中提升分数
    for i, name in enumerate(table_names):
        if scores[i] <= 0:
            continue
        comment = all_table_info[name].get("table_comment", "")
        comment_tokens = _tokenize(comment)
        overlap = set(query_tokens) & set(comment_tokens)
        if overlap:
            overlap_ratio = len(overlap) / max(len(set(query_tokens)), 1)
            scores[i] += scores[i] * overlap_ratio * 1.5

    # 排序并取 top_k
    scored = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    selected = [table_names[idx] for idx, score in scored[:top_k] if score > 0]

    # 如果 BM25 没有匹配结果，退回前 top_k
    if not selected:
        selected = table_names[:top_k]

    return {name: all_table_info[name] for name in selected}


async def schema_inspector(state: DataChatState, *, session: AsyncSession) -> DataChatState:
    """表结构检索节点：获取数据源元数据并通过 BM25 筛选最相关的表"""
    datasource_id = state.get("datasource_id")
    user_query = (state.get("user_query") or "").strip()

    if not datasource_id:
        state["db_info"] = {}
        state["error_message"] = "未指定数据源"
        return state

    try:
        all_table_info = await _fetch_table_info_from_db(session, datasource_id)

        if not all_table_info:
            state["db_info"] = {}
            state["error_message"] = "数据源没有已选中的表，请先在数据源管理中同步表结构"
            return state

        # BM25 检索
        filtered = _bm25_retrieve(all_table_info, user_query, _TABLE_RETURN_COUNT)

        # 记录分词
        state["bm25_tokens"] = _tokenize(user_query) if user_query else []
        state["db_info"] = filtered

        logger.info(f"表结构检索完成，共 {len(all_table_info)} 张表，筛选出 {len(filtered)} 张")
    except Exception as e:
        logger.error(f"表结构检索失败: {e}", exc_info=True)
        state["db_info"] = {}
        state["error_message"] = f"获取表结构失败: {e}"

    return state
