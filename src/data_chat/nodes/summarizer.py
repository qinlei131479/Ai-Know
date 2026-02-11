"""数据总结节点 - 使用 LLM 对查询结果进行数据分析总结"""

import json
import re
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


async def summarizer(state: DataChatState, *, llm) -> DataChatState:
    """数据总结节点"""
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
