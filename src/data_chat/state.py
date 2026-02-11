"""数据问答 Agent 状态定义"""

from typing import Any

from pydantic import BaseModel
from typing_extensions import TypedDict


class ExecutionResult(BaseModel):
    """SQL 执行结果"""

    success: bool
    data: list[dict[str, Any]] | None = None
    error: str | None = None


class DataChatState(TypedDict, total=False):
    """Text2SQL 工作流状态"""

    # 输入
    user_query: str  # 用户问题
    datasource_id: int | None  # 数据源ID（可选，未指定时自动选择）
    user_id: str | None  # 用户ID
    chat_id: str | None  # 对话ID

    # 表结构检索阶段
    db_info: dict  # 检索到的表结构信息
    bm25_tokens: list[str]  # BM25 分词结果

    # SQL 生成阶段
    generated_sql: str | None  # 生成的 SQL
    chart_type: str | None  # 推荐的图表类型
    used_tables: list[str] | None  # SQL 使用的表名列表

    # SQL 执行阶段
    execution_result: ExecutionResult | None  # SQL 执行结果

    # 结果处理阶段
    chart_config: dict[str, Any] | None  # 图表配置（ECharts 格式）
    render_data: dict[str, Any] | None  # 渲染数据
    report_summary: str | None  # 数据总结
    recommended_questions: list[str] | None  # 推荐问题列表

    # 内部传递（由 service 层预加载）
    _terminologies_str: str  # 术语文本
    _sql_examples_str: str  # SQL 示例文本

    # 异常
    error_message: str | None  # 异常信息
