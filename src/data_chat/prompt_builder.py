"""Prompt 构建器 - 从 YAML 模板加载和构建各类提示词"""

import json
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

import yaml

_TEMPLATE_DIR = Path(__file__).parent / "templates"


@cache
def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_template() -> dict:
    return _load_yaml(_TEMPLATE_DIR / "template.yaml")["template"]


# ── SQL 生成 ──


def build_sql_prompt(
    *,
    schema: str,
    question: str,
    engine: str,
    terminologies: str = "",
    sql_examples: str = "",
    error_msg: str = "",
    current_time: str | None = None,
) -> tuple[str, str]:
    """构建 SQL 生成提示词，返回 (system_prompt, user_prompt)"""
    tpl = _get_template()["sql"]
    system_prompt = tpl["system"].format(
        engine=engine,
        schema=schema,
        terminologies=terminologies,
        sql_examples=sql_examples,
    )
    user_prompt = tpl["user"].format(
        question=question,
        error_msg=error_msg,
        current_time=current_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return system_prompt, user_prompt


# ── 图表配置 ──


def build_chart_prompt(
    *,
    sql: str,
    question: str,
    chart_type: str = "",
) -> tuple[str, str]:
    """构建图表配置生成提示词"""
    tpl = _get_template()["chart"]
    return tpl["system"], tpl["user"].format(question=question, sql=sql, chart_type=chart_type)


# ── 推荐问题 ──


def build_guess_prompt(
    *,
    schema: str,
    question: str = "",
) -> tuple[str, str]:
    """构建推荐问题生成提示词"""
    tpl = _get_template()["guess"]
    return tpl["system"], tpl["user"].format(schema=schema, question=question)


# ── 数据总结 ──


def build_summarizer_prompt(
    *,
    data_result: str,
    user_query: str,
    current_time: str | None = None,
) -> tuple[str, str]:
    """构建数据总结提示词"""
    tpl = _get_template()["summarizer"]
    user_prompt = tpl["user"].format(
        data_result=data_result,
        user_query=user_query,
        current_time=current_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return tpl["system"], user_prompt


# ── 数据源选择 ──


def build_datasource_prompt(
    *,
    question: str,
    datasource_list: list[dict[str, Any]],
) -> tuple[str, str]:
    """构建数据源选择提示词"""
    tpl = _get_template()["datasource"]
    return tpl["system"], tpl["user"].format(
        question=question,
        data=json.dumps(datasource_list, ensure_ascii=False),
    )


# ── 术语格式化 ──


def format_terminologies(terms: list[dict[str, Any]]) -> str:
    """将术语列表格式化为 XML 格式字符串"""
    if not terms:
        return ""
    lines = ["<terminologies>"]
    for t in terms:
        lines.append("  <terminology>")
        lines.append(f"    <words><word>{t.get('word', '')}</word></words>")
        lines.append(f"    <description>{t.get('description', '')}</description>")
        lines.append("  </terminology>")
    lines.append("</terminologies>")
    return "\n".join(lines)


def format_sql_examples(examples: list[dict[str, Any]]) -> str:
    """将 SQL 示例列表格式化为 XML 格式字符串"""
    if not examples:
        return ""
    lines = ["<sql-examples>"]
    for ex in examples:
        lines.append("  <sql-example>")
        lines.append(f"    <question>{ex.get('question', '')}</question>")
        lines.append(f"    <suggestion-answer>{ex.get('sql_text', '')}</suggestion-answer>")
        lines.append("  </sql-example>")
    lines.append("</sql-examples>")
    return "\n".join(lines)
