"""数据总结节点 - 使用 LLM 对查询结果进行数据分析总结"""

import json
import re
from collections.abc import AsyncGenerator
from datetime import date, datetime
from decimal import Decimal

from langchain_core.messages import HumanMessage, SystemMessage

from src.data_chat import prompt_builder
from src.data_chat.state import DataChatState
from src.utils import logger


class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def _remove_code_blocks(text: str) -> str:
    """去除 Markdown 代码块标记"""
    if not text:
        return text
    text = re.sub(r"^```[\w]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
    return text.strip()


async def summarizer_stream(
    state: DataChatState, *, llm
) -> AsyncGenerator[tuple[str, str], None]:
    """流式生成数据总结，逐块返回内容

    Yields:
        tuple[str, str]: (chunk_content, full_summary_so_far)
    """
    execution_result = state.get("execution_result")
    if not execution_result or not execution_result.success or not execution_result.data:
        return

    try:
        data_str = json.dumps(execution_result.data, ensure_ascii=False, indent=2, cls=_DecimalEncoder)

        system_prompt, user_prompt = prompt_builder.build_summarizer_prompt(
            data_result=data_str,
            user_query=state.get("user_query", ""),
        )

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

        accumulated = ""
        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            accumulated += content
            yield content, _remove_code_blocks(accumulated)

        logger.info("数据总结流式生成完成")
    except Exception as e:
        logger.error(f"数据总结流式生成异常: {e}", exc_info=True)
        yield f"数据总结生成失败: {e}", ""


async def summarizer(state: DataChatState, *, llm) -> DataChatState:
    """数据总结节点（非流式版本，保持向后兼容）"""
    execution_result = state.get("execution_result")
    if not execution_result or not execution_result.success or not execution_result.data:
        state["report_summary"] = None
        return state

    try:
        data_str = json.dumps(execution_result.data, ensure_ascii=False, indent=2, cls=_DecimalEncoder)

        system_prompt, user_prompt = prompt_builder.build_summarizer_prompt(
            data_result=data_str,
            user_query=state.get("user_query", ""),
        )

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = await llm.ainvoke(messages)
        state["report_summary"] = _remove_code_blocks(response.content)
        logger.info("数据总结生成成功")
    except Exception as e:
        logger.error(f"数据总结异常: {e}", exc_info=True)
        state["report_summary"] = "数据总结生成失败，请稍后重试"

    return state
