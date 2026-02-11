"""Schema 格式化工具 - 将 db_info 字典转换为 M-Schema 字符串供 LLM 使用"""

from typing import Any

# 需要 Schema 前缀的数据库类型
_NEED_SCHEMA_TYPES = {"sqlServer", "pg", "oracle", "dm", "redshift", "kingbase"}

_DB_TYPE_MAP = {
    "mysql": "MySQL",
    "pg": "PostgreSQL",
    "oracle": "Oracle",
    "sqlServer": "Microsoft SQL Server",
    "ck": "ClickHouse",
    "redshift": "AWS Redshift",
    "es": "Elasticsearch",
    "starrocks": "StarRocks",
    "doris": "Apache Doris",
    "dm": "DM",
    "kingbase": "Kingbase",
}


def format_schema_to_m_schema(
    db_info: dict[str, dict[str, Any]],
    db_name: str = "database",
    db_type: str = "mysql",
) -> str:
    """将 db_info 转换为 M-Schema 格式字符串。

    Args:
        db_info: 表结构信息字典，格式为:
            {
                "table_name": {
                    "columns": {"col_name": {"type": "VARCHAR", "comment": "注释"}},
                    "table_comment": "表注释",
                    "foreign_keys": ["t1.f1=t2.f2"],
                }
            }
        db_name: 数据库/Schema 名称
        db_type: 数据库类型代码
    """
    if not db_info:
        return ""

    is_oracle = db_type.lower() == "oracle"
    use_schema = db_type in _NEED_SCHEMA_TYPES

    parts = [f"【DB_ID】 {db_name}\n【Schema】\n"]

    for table_name, table_info in db_info.items():
        display_name = table_name.upper() if is_oracle else table_name

        # 表头
        table_ref = f"{db_name}.{display_name}" if use_schema else display_name
        header = f"# Table: {table_ref}"
        table_comment = (table_info.get("table_comment") or "").strip()
        if table_comment:
            header += f", {table_comment}"

        field_lines = []
        for col_name, col_info in (table_info.get("columns") or {}).items():
            display_col = col_name.upper() if is_oracle else col_name
            col_type = col_info.get("type", "VARCHAR")
            col_comment = (col_info.get("comment") or "").strip()
            line = f"({display_col}:{col_type}, {col_comment})" if col_comment else f"({display_col}:{col_type})"
            field_lines.append(line)

        table_block = f"{header}\n[\n{',\n'.join(field_lines)}\n]\n"

        # 外键关系
        for fk in table_info.get("foreign_keys") or []:
            table_block += f"{fk}\n"

        parts.append(table_block)

    return "".join(parts)


def get_database_engine_info(db_type: str) -> str:
    """获取数据库引擎显示名称"""
    engine_name = _DB_TYPE_MAP.get(db_type, _DB_TYPE_MAP.get(db_type.lower(), "MySQL"))
    default_versions = {
        "MySQL": "8.0",
        "PostgreSQL": "17.6",
        "Oracle": "19c",
        "Microsoft SQL Server": "2019",
        "ClickHouse": "24.0",
    }
    version = default_versions.get(engine_name, "")
    return f"{engine_name} {version}" if version else engine_name
