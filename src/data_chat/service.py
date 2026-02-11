"""数据问答服务 - 编排 Text2SQL 工作流并以 SSE 格式流式输出

SSE 数据格式:
  data:{"dataType":"step_progress","data":{...}}\n\n
  data:{"dataType":"answer","data":{"content":"..."}}\n\n
  data:{"dataType":"bus_data","data":{...}}\n\n
"""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.common.models import load_chat_model
from src.data_chat import prompt_builder
from src.data_chat.nodes.chart_generator import chart_generator
from src.data_chat.nodes.recommender import recommender
from src.data_chat.nodes.schema_inspector import schema_inspector
from src.data_chat.nodes.sql_executor import sql_executor
from src.data_chat.nodes.sql_generator import sql_generator
from src.data_chat.nodes.summarizer import summarizer
from src.data_chat.state import DataChatState
from src.repositories.datasource_repository import DatasourceRepository
from src.services.datasource_crypto import decrypt_datasource_config
from src.storage.postgres.models_datasource import (
    Datasource,
    SqlExample,
    Terminology,
)
from src.utils import logger

# ── SSE 格式化 ──

_STEP_NAMES = {
    "schema_inspector": "表结构检索...",
    "sql_generator": "SQL 生成...",
    "sql_executor": "SQL 执行...",
    "chart_generator": "图表配置...",
    "summarizer": "数据总结...",
    "recommender": "推荐问题...",
}


def _sse(data_type: str, data: Any) -> str:
    """构建 SSE 消息"""
    return "data:" + json.dumps({"dataType": data_type, "data": data}, ensure_ascii=False) + "\n\n"


def _sse_step(step: str, status: str, progress_id: str) -> str:
    return _sse("step_progress", {
        "type": "step_progress",
        "step": step,
        "stepName": _STEP_NAMES.get(step, step),
        "status": status,
        "progressId": progress_id,
    })


def _sse_answer(content: str) -> str:
    return _sse("answer", {"content": content})


def _sse_bus_data(data: Any) -> str:
    return _sse("bus_data", data)


def _sse_error(message: str) -> str:
    return _sse("answer", {"content": message, "messageType": "error"})


def _sse_end(chat_id: str | None = None) -> str:
    return _sse("stream_end", {"chat_id": chat_id} if chat_id else {})


# ── 辅助查询 ──


async def _load_terminologies(session: AsyncSession, datasource_id: int) -> str:
    """加载与数据源相关的术语"""
    result = await session.execute(
        select(Terminology).where(Terminology.enabled.is_(True))
    )
    terms = result.scalars().all()

    # 筛选全局术语或与该数据源关联的术语
    filtered = []
    for t in terms:
        if not t.specific_ds:
            filtered.append({"word": t.word, "description": t.description})
        elif t.datasource_ids and datasource_id in (t.datasource_ids if isinstance(t.datasource_ids, list) else []):
            filtered.append({"word": t.word, "description": t.description})

    return prompt_builder.format_terminologies(filtered)


async def _load_sql_examples(session: AsyncSession, datasource_id: int) -> str:
    """加载与数据源相关的 SQL 示例"""
    result = await session.execute(
        select(SqlExample).where(
            SqlExample.enabled.is_(True),
            (SqlExample.datasource_id == datasource_id) | (SqlExample.datasource_id.is_(None)),
        )
    )
    examples = result.scalars().all()
    return prompt_builder.format_sql_examples([
        {"question": ex.question, "sql_text": ex.sql_text} for ex in examples
    ])


async def _get_datasource(session: AsyncSession, datasource_id: int) -> Datasource | None:
    result = await session.execute(
        select(Datasource).where(Datasource.id == datasource_id)
    )
    return result.scalar_one_or_none()


# ── 工作流执行 ──


async def run_data_chat(
    *,
    session: AsyncSession,
    query: str,
    datasource_id: int,
    user_id: str | None = None,
    chat_id: str | None = None,
    model_spec: str | None = None,
) -> AsyncGenerator[str, None]:
    """运行数据问答工作流，以 SSE 格式流式输出结果。

    Args:
        session: 异步数据库会话
        query: 用户问题
        datasource_id: 数据源 ID
        user_id: 用户 ID
        chat_id: 对话 ID（同一轮对话）
        model_spec: 模型规格（如 "openai/gpt-4o"），为空时使用默认模型
    """
    from src import config as sys_config

    chat_id = chat_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    # 加载模型
    model_name = model_spec or sys_config.default_model
    try:
        llm = load_chat_model(model_name)
    except Exception as e:
        yield _sse_error(f"模型加载失败: {e}")
        yield _sse_end()
        return

    # 获取数据源信息
    ds = await _get_datasource(session, datasource_id)
    if not ds:
        yield _sse_error("数据源不存在")
        yield _sse_end()
        return
    if ds.status != "success":
        yield _sse_error("数据源连接状态异常，请先测试连接")
        yield _sse_end()
        return

    try:
        ds_config = decrypt_datasource_config(ds.configuration)
    except Exception as e:
        yield _sse_error(f"数据源配置解密失败: {e}")
        yield _sse_end()
        return

    ds_type = ds.ds_type

    # 初始化状态
    state: DataChatState = {
        "user_query": query,
        "datasource_id": datasource_id,
        "user_id": user_id,
        "chat_id": chat_id,
    }

    # ── Step 1: 表结构检索 ──
    step = "schema_inspector"
    pid = str(uuid.uuid4())
    yield _sse_step(step, "start", pid)
    try:
        state = await schema_inspector(state, session=session)
        yield _sse_step(step, "complete", pid)

        if state.get("error_message") and not state.get("db_info"):
            yield _sse_error(state["error_message"])
            yield _sse_end()
            return
    except Exception as e:
        logger.error(f"schema_inspector 异常: {e}", exc_info=True)
        yield _sse_step(step, "complete", pid)
        yield _sse_error(f"表结构检索失败: {e}")
        yield _sse_end()
        return

    # 预加载术语和 SQL 示例
    try:
        state["_terminologies_str"] = await _load_terminologies(session, datasource_id)
        state["_sql_examples_str"] = await _load_sql_examples(session, datasource_id)
    except Exception as e:
        logger.warning(f"加载术语/示例失败: {e}")
        state["_terminologies_str"] = ""
        state["_sql_examples_str"] = ""

    # ── Step 2: SQL 生成 ──
    step = "sql_generator"
    pid = str(uuid.uuid4())
    yield _sse_step(step, "start", pid)
    try:
        state = await sql_generator(state, llm=llm, ds_type=ds_type, ds_config=ds_config)
        yield _sse_step(step, "complete", pid)

        if not state.get("generated_sql"):
            yield _sse_answer(state.get("error_message") or "无法生成 SQL")
            yield _sse_end()
            # 保存记录
            await _save_chat_record(session, state, user_id, chat_id, message_id)
            yield _sse_end(chat_id)
            return
    except Exception as e:
        logger.error(f"sql_generator 异常: {e}", exc_info=True)
        yield _sse_step(step, "complete", pid)
        yield _sse_error(f"SQL 生成失败: {e}")
        yield _sse_end(chat_id)
        return

    # ── Step 3: SQL 执行 ──
    step = "sql_executor"
    pid = str(uuid.uuid4())
    yield _sse_step(step, "start", pid)
    try:
        state = await sql_executor(state, ds_type=ds_type, ds_config=ds_config)
        yield _sse_step(step, "complete", pid)

        execution_result = state.get("execution_result")
        if not execution_result or not execution_result.success:
            error = execution_result.error if execution_result else "执行失败"
            yield _sse_answer(f"SQL 执行失败: {error[:200]}")
            await _save_chat_record(session, state, user_id, chat_id, message_id)
            yield _sse_end(chat_id)
            return
    except Exception as e:
        logger.error(f"sql_executor 异常: {e}", exc_info=True)
        yield _sse_step(step, "complete", pid)
        yield _sse_error(f"SQL 执行失败: {e}")
        yield _sse_end(chat_id)
        return

    # ── Step 4-6: 并行执行图表配置 + 数据总结 + 推荐问题 ──
    chart_pid = str(uuid.uuid4())
    summarizer_pid = str(uuid.uuid4())
    recommender_pid = str(uuid.uuid4())

    yield _sse_step("chart_generator", "start", chart_pid)
    yield _sse_step("summarizer", "start", summarizer_pid)
    yield _sse_step("recommender", "start", recommender_pid)

    # 并行执行三个任务
    async def _chart_task():
        return await chart_generator(state.copy(), llm=llm)

    async def _summarizer_task():
        return await summarizer(state.copy(), llm=llm)

    async def _recommender_task():
        return await recommender(state.copy(), llm=llm, ds_type=ds_type)

    try:
        chart_result, summary_result, recommend_result = await asyncio.gather(
            _chart_task(), _summarizer_task(), _recommender_task(),
            return_exceptions=True,
        )

        # 合并结果到 state
        if isinstance(chart_result, dict):
            state.update(chart_result)
        elif isinstance(chart_result, Exception):
            logger.error(f"chart_generator 异常: {chart_result}")

        if isinstance(summary_result, dict):
            state.update(summary_result)
        elif isinstance(summary_result, Exception):
            logger.error(f"summarizer 异常: {summary_result}")

        if isinstance(recommend_result, dict):
            state.update(recommend_result)
        elif isinstance(recommend_result, Exception):
            logger.error(f"recommender 异常: {recommend_result}")

    except Exception as e:
        logger.error(f"并行任务异常: {e}", exc_info=True)

    yield _sse_step("chart_generator", "complete", chart_pid)
    yield _sse_step("summarizer", "complete", summarizer_pid)
    yield _sse_step("recommender", "complete", recommender_pid)

    # ── 按顺序输出结果：总结 → 图表数据 → 推荐问题 ──

    # 1. 数据总结
    report_summary = state.get("report_summary")
    if report_summary:
        yield _sse_answer(report_summary)

    # 2. 图表/表格数据
    render_data = state.get("render_data")
    chart_config = state.get("chart_config")
    if render_data:
        bus_payload = {
            "chart_config": chart_config,
            "render_data": render_data,
            "sql": state.get("generated_sql", ""),
        }
        yield _sse_bus_data(bus_payload)

    # 3. 推荐问题
    recommended = state.get("recommended_questions")
    if recommended:
        yield _sse_bus_data({"recommended_questions": recommended})

    # ── 保存对话记录 ──
    await _save_chat_record(session, state, user_id, chat_id, message_id)

    yield _sse_end(chat_id)


async def _save_chat_record(
    session: AsyncSession,
    state: DataChatState,
    user_id: str | None,
    chat_id: str,
    message_id: str,
) -> None:
    """保存数据问答记录"""
    try:
        repo = DatasourceRepository(session)
        await repo.create_chat_record({
            "user_id": user_id or "",
            "chat_id": chat_id,
            "message_id": message_id,
            "question": state.get("user_query", ""),
            "answer": state.get("report_summary", ""),
            "datasource_id": state.get("datasource_id"),
            "sql_statement": state.get("generated_sql"),
            "query_result": state.get("render_data"),
            "chart_config": state.get("chart_config"),
            "qa_type": "data",
        })
        await session.commit()
    except Exception as e:
        logger.warning(f"保存对话记录失败: {e}")


# ── 推荐问题独立接口 ──


async def get_recommended_questions(
    *,
    session: AsyncSession,
    datasource_id: int,
    question: str = "",
    model_spec: str | None = None,
) -> list[str]:
    """获取推荐问题（用于初始化页面时显示）"""
    from src import config as sys_config

    model_name = model_spec or sys_config.default_model
    llm = load_chat_model(model_name)

    state: DataChatState = {
        "user_query": question,
        "datasource_id": datasource_id,
    }

    # 获取表结构
    state = await schema_inspector(state, session=session)
    if not state.get("db_info"):
        return []

    ds = await _get_datasource(session, datasource_id)
    ds_type = ds.ds_type if ds else "mysql"

    state = await recommender(state, llm=llm, ds_type=ds_type)
    return state.get("recommended_questions", [])


# ── 对话历史 ──


async def list_chat_sessions(
    session: AsyncSession,
    user_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """获取用户的数据问答对话列表"""
    repo = DatasourceRepository(session)
    return await repo.list_chat_sessions(user_id, limit)
