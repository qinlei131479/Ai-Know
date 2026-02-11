"""SQL 执行节点 - 在目标数据源上执行生成的 SQL"""

from src.data_chat.state import DataChatState, ExecutionResult
from src.services import datasource_connector as connector
from src.utils import logger


async def sql_executor(state: DataChatState, *, ds_type: str, ds_config: dict) -> DataChatState:
    """SQL 执行节点

    Args:
        state: 工作流状态
        ds_type: 数据源类型
        ds_config: 解密后的数据源配置
    """
    sql = (state.get("generated_sql") or "").strip()
    if not sql:
        state["execution_result"] = ExecutionResult(success=False, error="SQL 为空，无法执行")
        return state

    try:
        logger.info("执行 SQL 查询")
        data = await connector.execute_query(ds_type, ds_config, sql)
        state["execution_result"] = ExecutionResult(success=True, data=data)
        logger.info(f"SQL 执行成功，返回 {len(data)} 条记录")
    except Exception as e:
        error_msg = f"执行 SQL 失败: {e}"
        logger.error(error_msg, exc_info=True)
        state["execution_result"] = ExecutionResult(success=False, error=str(e))

    return state
