"""图表配置生成节点 - 使用 LLM 根据 SQL 和执行结果生成图表配置"""

import json
from datetime import date, datetime
from decimal import Decimal

from langchain_core.messages import HumanMessage, SystemMessage

from src.data_chat import prompt_builder
from src.data_chat.state import DataChatState
from src.utils import logger


def _convert_value(v):
    """转换数据类型为 JSON 可序列化格式"""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    return v


def _prepare_data(data: list[dict]) -> list[dict]:
    """将数据转换为 JSON 可序列化格式"""
    return [{k: _convert_value(v) for k, v in row.items()} for row in data]


def _clean_json_response(text: str) -> str:
    if "```json" in text:
        text = text.split("```json")[1]
    if "```" in text:
        text = text.split("```")[0]
    return text.strip()


async def chart_generator(state: DataChatState, *, llm) -> DataChatState:
    """图表配置生成节点"""
    execution_result = state.get("execution_result")
    if not execution_result or not execution_result.success or not execution_result.data:
        return state

    try:
        generated_sql = state.get("generated_sql", "")
        user_query = state.get("user_query", "")
        chart_type = state.get("chart_type", "table")

        system_prompt, user_prompt = prompt_builder.build_chart_prompt(
            sql=generated_sql,
            question=user_query,
            chart_type=chart_type,
        )

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = await llm.ainvoke(messages)

        content = _clean_json_response(response.content)
        chart_config = json.loads(content)

        if isinstance(chart_config, dict):
            if "type" not in chart_config:
                chart_config["type"] = chart_type

            # value 字段统一小写，确保与 SQL 结果列名匹配
            for col in chart_config.get("columns") or []:
                if isinstance(col, dict) and col.get("value"):
                    col["value"] = col["value"].lower()
            axis = chart_config.get("axis")
            if isinstance(axis, dict):
                for key in ("x", "y", "series"):
                    item = axis.get(key)
                    if isinstance(item, dict) and item.get("value"):
                        item["value"] = item["value"].lower()

            state["chart_config"] = chart_config

            # 构建 render_data：将执行结果转换为前端可用的格式
            data = _prepare_data(execution_result.data)
            columns = []
            if chart_config.get("type") == "table" and chart_config.get("columns"):
                columns = chart_config["columns"]
            elif data:
                columns = [{"name": k, "value": k} for k in data[0].keys()]
            state["render_data"] = {"columns": columns, "data": data}

            logger.info(f"图表配置生成成功, type={chart_config.get('type')}")
        else:
            state["chart_config"] = None

    except json.JSONDecodeError as e:
        logger.error(f"图表配置 JSON 解析失败: {e}")
        # 降级：仍然生成 render_data（表格格式）
        if execution_result.data:
            data = _prepare_data(execution_result.data)
            columns = [{"name": k, "value": k} for k in data[0].keys()] if data else []
            state["render_data"] = {"columns": columns, "data": data}
            state["chart_config"] = {"type": "table", "title": "", "columns": columns}
    except Exception as e:
        logger.error(f"图表配置生成异常: {e}", exc_info=True)

    return state
