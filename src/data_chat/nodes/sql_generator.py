"""SQL 生成节点 - 使用 LLM 根据表结构和用户问题生成 SQL"""

import json
import re
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from src.data_chat import prompt_builder
from src.data_chat.schema_formatter import format_schema_to_m_schema, get_database_engine_info
from src.data_chat.state import DataChatState
from src.utils import logger


def _clean_json_response(text: str) -> str:
    """清理 LLM 返回的 JSON 字符串"""
    if "```json" in text:
        text = text.split("```json")[1]
    if "```" in text:
        text = text.split("```")[0]
    return text.strip()


def _parse_llm_json(response_content: str) -> dict | None:
    """解析 LLM 返回的 JSON，支持修复常见转义问题"""
    content = _clean_json_response(response_content)

    # 先尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 修复 SQL 中的无效转义序列
    try:
        fixed = re.sub(
            r'("sql"\s*:\s*")(.*?)(")',
            lambda m: f'{m.group(1)}{re.sub(r"\\\\\s*\n\\s*", " ", m.group(2))}{m.group(3)}',
            content,
            flags=re.DOTALL,
        )
        return json.loads(fixed)
    except (json.JSONDecodeError, Exception):
        pass

    # 尝试正则提取 JSON 对象
    try:
        json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except (json.JSONDecodeError, Exception):
        pass

    return None


async def sql_generator(
    state: DataChatState, *, llm, ds_type: str = "mysql", ds_config: dict | None = None,
) -> DataChatState:
    """SQL 生成节点

    Args:
        state: 工作流状态
        llm: LangChain ChatModel 实例
        ds_type: 数据源类型
        ds_config: 解密后的数据源配置（用于获取 db_name）
    """
    db_info = state.get("db_info", {})
    if not db_info:
        state["generated_sql"] = None
        state["error_message"] = state.get("error_message") or "没有可用的表结构信息"
        return state

    try:
        # 获取 db_name（schema 名称）
        db_name = "database"
        if ds_config:
            db_schema = ds_config.get("dbSchema")
            database = ds_config.get("database")
            if ds_type in ("pg", "oracle", "sqlServer", "dm", "redshift", "kingbase") and db_schema:
                db_name = db_schema
            else:
                db_name = database or db_schema or "database"

        # 格式化 Schema
        schema_str = format_schema_to_m_schema(db_info=db_info, db_name=db_name, db_type=ds_type)
        engine = get_database_engine_info(ds_type)

        # 获取术语和 SQL 示例（从 state 中传入，在 graph 层准备）
        terminologies_str = state.get("_terminologies_str", "")
        sql_examples_str = state.get("_sql_examples_str", "")

        system_prompt, user_prompt = prompt_builder.build_sql_prompt(
            schema=schema_str,
            question=state["user_query"],
            engine=engine,
            terminologies=terminologies_str,
            sql_examples=sql_examples_str,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = await llm.ainvoke(messages)
        result = _parse_llm_json(response.content)

        if result and result.get("success", True):
            state["generated_sql"] = result.get("sql", "")
            state["chart_type"] = result.get("chart-type", result.get("chart_type", "table"))
            if "tables" in result and isinstance(result["tables"], list):
                state["used_tables"] = result["tables"]
            logger.info(f"SQL 生成成功, chart_type={state.get('chart_type')}")
        elif result:
            error_msg = result.get("message", "无法生成 SQL")
            logger.warning(f"SQL 生成失败: {error_msg}")
            state["generated_sql"] = None
            state["error_message"] = error_msg
        else:
            logger.error(f"解析 LLM 响应失败: {response.content[:300]}")
            state["generated_sql"] = None
            state["error_message"] = "无法解析 AI 返回的 SQL 结果"

    except Exception as e:
        logger.error(f"SQL 生成异常: {e}", exc_info=True)
        state["generated_sql"] = None
        state["error_message"] = f"SQL 生成失败: {e}"

    return state
