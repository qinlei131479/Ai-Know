"""推荐问题生成节点 - 根据表结构和用户查询推荐相关问题"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from src.data_chat import prompt_builder
from src.data_chat.schema_formatter import format_schema_to_m_schema
from src.data_chat.state import DataChatState
from src.utils import logger


async def recommender(state: DataChatState, *, llm, ds_type: str = "mysql") -> DataChatState:
    """推荐问题生成节点"""
    db_info = state.get("db_info", {})
    if not db_info:
        state["recommended_questions"] = []
        return state

    try:
        schema_str = format_schema_to_m_schema(db_info=db_info, db_name="", db_type=ds_type)

        system_prompt, user_prompt = prompt_builder.build_guess_prompt(
            schema=schema_str,
            question=state.get("user_query", ""),
        )

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = await llm.ainvoke(messages)

        content = response.content.strip()
        # 清理 JSON
        if "```json" in content:
            content = content.split("```json")[1]
        if "```" in content:
            content = content.split("```")[0]
        content = content.strip()

        questions = json.loads(content)
        if isinstance(questions, list):
            state["recommended_questions"] = questions[:4]
        else:
            state["recommended_questions"] = []

        logger.info(f"推荐问题生成成功: {len(state['recommended_questions'])} 个")
    except Exception as e:
        logger.error(f"推荐问题生成异常: {e}", exc_info=True)
        state["recommended_questions"] = []

    return state
