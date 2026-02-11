"""多数据源连接器

统一适配 MySQL / PostgreSQL / Oracle / SQL Server / ClickHouse / 达梦 / Doris / StarRocks /
Elasticsearch / Kingbase / AWS Redshift 等数据库的连接、元数据获取和 SQL 执行。

由于各数据库驱动多为同步实现，通过 asyncio.to_thread 包装为异步接口。
"""

import asyncio
import json
import logging
import urllib.parse
from decimal import Decimal
from enum import Enum
from typing import Any

import pymysql
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


# ── 数据库类型枚举 ──


class ConnectType(Enum):
    sqlalchemy = "sqlalchemy"
    py_driver = "py_driver"


class DBType(Enum):
    """数据库类型枚举"""

    mysql = ("mysql", "MySQL", "`", "`", ConnectType.sqlalchemy)
    pg = ("pg", "PostgreSQL", '"', '"', ConnectType.sqlalchemy)
    oracle = ("oracle", "Oracle", '"', '"', ConnectType.sqlalchemy)
    sqlServer = ("sqlServer", "SQL Server", "[", "]", ConnectType.sqlalchemy)
    ck = ("ck", "ClickHouse", '"', '"', ConnectType.sqlalchemy)
    dm = ("dm", "达梦", '"', '"', ConnectType.py_driver)
    doris = ("doris", "Apache Doris", "`", "`", ConnectType.py_driver)
    redshift = ("redshift", "AWS Redshift", '"', '"', ConnectType.py_driver)
    es = ("es", "Elasticsearch", '"', '"', ConnectType.py_driver)
    kingbase = ("kingbase", "Kingbase", '"', '"', ConnectType.py_driver)
    starrocks = ("starrocks", "StarRocks", "`", "`", ConnectType.py_driver)

    def __init__(self, type_code: str, db_name: str, prefix: str, suffix: str, connect_type: ConnectType):
        self.type_code = type_code
        self.db_name = db_name
        self.prefix = prefix
        self.suffix = suffix
        self.connect_type = connect_type

    @classmethod
    def get(cls, ds_type: str) -> "DBType":
        for db in cls:
            if db.type_code.lower() == ds_type.lower():
                return db
        raise ValueError(f"不支持的数据库类型: {ds_type}")

    @classmethod
    def all_types(cls) -> list[dict[str, str]]:
        return [{"code": db.type_code, "name": db.db_name} for db in cls]


# ── 连接 URI 构建 ──


def _build_uri(ds_type: str, config: dict[str, Any]) -> str:
    host = config.get("host", "")
    port = config.get("port", 3306)
    username = urllib.parse.quote(config.get("username", ""))
    password = urllib.parse.quote(config.get("password", ""))
    database = config.get("database", "")
    extra = config.get("extraJdbc", "")
    mode = config.get("mode", "service_name")

    suffix = f"?{extra}" if extra else ""

    match ds_type:
        case "mysql":
            return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}{suffix}"
        case "pg":
            return f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}{suffix}"
        case "oracle":
            if mode == "service_name":
                base = f"oracle+oracledb://{username}:{password}@{host}:{port}?service_name={database}"
                return f"{base}&{extra}" if extra else base
            return f"oracle+oracledb://{username}:{password}@{host}:{port}/{database}{suffix}"
        case "sqlServer":
            return f"mssql+pymssql://{username}:{password}@{host}:{port}/{database}{suffix}"
        case "ck":
            return f"clickhouse+http://{username}:{password}@{host}:{port}/{database}{suffix}"
        case _:
            raise ValueError(f"不支持 SQLAlchemy 连接的数据源类型: {ds_type}")


def _make_engine(ds_type: str, config: dict[str, Any]):
    uri = _build_uri(ds_type, config)
    timeout = config.get("timeout", 30)

    if ds_type == "oracle":
        return create_engine(uri, pool_pre_ping=True)
    elif ds_type == "sqlServer":
        return create_engine(
            uri, pool_pre_ping=True,
            connect_args={"timeout": timeout, "login_timeout": timeout, "encryption": "off"},
        )
    else:
        return create_engine(uri, pool_pre_ping=True, connect_args={"connect_timeout": timeout})


# ── 表列表查询 SQL ──

_TABLE_SQL: dict[str, str] = {
    "mysql": """
        SELECT TABLE_NAME, TABLE_COMMENT
        FROM information_schema.TABLES WHERE TABLE_SCHEMA = :param
    """,
    "pg": """
        SELECT c.relname AS TABLE_NAME,
               COALESCE(d.description, obj_description(c.oid)) AS TABLE_COMMENT
        FROM pg_class c
        LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_description d ON d.objoid = c.oid AND d.objsubid = 0
        WHERE n.nspname = :param AND c.relkind IN ('r','v','p','m')
              AND c.relname NOT LIKE 'pg_%' AND c.relname NOT LIKE 'sql_%'
        ORDER BY c.relname
    """,
    "oracle": """
        SELECT DISTINCT t.TABLE_NAME AS "TABLE_NAME",
               NVL(c.COMMENTS, '') AS "TABLE_COMMENT"
        FROM (
            SELECT TABLE_NAME, 'TABLE' AS OBJECT_TYPE FROM ALL_TABLES WHERE OWNER = :param
            UNION ALL SELECT VIEW_NAME, 'VIEW' FROM ALL_VIEWS WHERE OWNER = :param
            UNION ALL SELECT MVIEW_NAME, 'MATERIALIZED VIEW' FROM ALL_MVIEWS WHERE OWNER = :param
        ) t LEFT JOIN ALL_TAB_COMMENTS c
          ON t.TABLE_NAME = c.TABLE_NAME AND c.TABLE_TYPE = t.OBJECT_TYPE AND c.OWNER = :param
        ORDER BY t.TABLE_NAME
    """,
    "sqlServer": """
        SELECT TABLE_NAME AS [TABLE_NAME],
               ISNULL(ep.value, '') AS [TABLE_COMMENT]
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN sys.extended_properties ep
          ON ep.major_id = OBJECT_ID(t.TABLE_SCHEMA + '.' + t.TABLE_NAME)
             AND ep.minor_id = 0 AND ep.name = 'MS_Description'
        WHERE t.TABLE_TYPE IN ('BASE TABLE','VIEW') AND t.TABLE_SCHEMA = :param
    """,
    "ck": """
        SELECT name, comment FROM system.tables
        WHERE database = :param AND engine NOT IN ('Dictionary') ORDER BY name
    """,
}

# ── 字段列表查询 SQL ──

_FIELD_SQL: dict[str, str] = {
    "mysql": """
        SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = :p1 AND TABLE_NAME = :p2
    """,
    "pg": """
        SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod),
               col_description(c.oid, a.attnum)
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = :p1 AND c.relname = :p2 AND a.attnum > 0 AND NOT a.attisdropped
    """,
    "oracle": """
        SELECT col.COLUMN_NAME AS "COLUMN_NAME",
               (CASE WHEN col.DATA_TYPE IN ('VARCHAR2','CHAR','NVARCHAR2','NCHAR')
                     THEN col.DATA_TYPE || '(' || col.DATA_LENGTH || ')'
                     WHEN col.DATA_TYPE = 'NUMBER' AND col.DATA_PRECISION IS NOT NULL
                     THEN col.DATA_TYPE || '(' || col.DATA_PRECISION ||
                          CASE WHEN col.DATA_SCALE > 0 THEN ',' || col.DATA_SCALE END || ')'
                     ELSE col.DATA_TYPE END) AS "DATA_TYPE",
               NVL(com.COMMENTS, '') AS "COLUMN_COMMENT"
        FROM ALL_TAB_COLUMNS col LEFT JOIN ALL_COL_COMMENTS com
          ON col.OWNER = com.OWNER AND col.TABLE_NAME = com.TABLE_NAME AND col.COLUMN_NAME = com.COLUMN_NAME
        WHERE col.OWNER = :p1 AND col.TABLE_NAME = :p2
    """,
    "sqlServer": """
        SELECT COLUMN_NAME AS [COLUMN_NAME], DATA_TYPE AS [DATA_TYPE],
               ISNULL(EP.value,'') AS [COLUMN_COMMENT]
        FROM INFORMATION_SCHEMA.COLUMNS C
        LEFT JOIN sys.extended_properties EP
          ON EP.major_id = OBJECT_ID(C.TABLE_SCHEMA + '.' + C.TABLE_NAME)
          AND EP.minor_id = C.ORDINAL_POSITION AND EP.name = 'MS_Description'
        WHERE C.TABLE_SCHEMA = :p1 AND C.TABLE_NAME = :p2
    """,
    "ck": """
        SELECT name AS COLUMN_NAME, type AS DATA_TYPE, comment AS COLUMN_COMMENT
        FROM system.columns WHERE database = :p1 AND table = :p2
    """,
}


# ── 内部同步实现 ──


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("latin-1", errors="ignore")
    return str(value) if value is not None else ""


def _process_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return value


def _get_schema_param(ds_type: str, config: dict[str, Any]) -> str:
    """获取 schema/database 参数"""
    if ds_type in ("sqlServer", "pg", "oracle", "dm", "redshift", "kingbase"):
        return config.get("dbSchema") or config.get("database", "")
    return config.get("database", "")


def _test_connection_sync(ds_type: str, config: dict[str, Any]) -> tuple[bool, str]:
    try:
        db = DBType.get(ds_type)
        timeout = config.get("timeout", 30)

        if db.connect_type == ConnectType.sqlalchemy:
            engine = _make_engine(ds_type, config)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, ""
        else:
            return _test_native_connection(ds_type, config, timeout)
    except Exception as e:
        logger.error(f"连接测试失败: {e}")
        return False, str(e)


def _test_native_connection(ds_type: str, config: dict[str, Any], timeout: int) -> tuple[bool, str]:
    host = config.get("host", "")
    port = config.get("port", 3306)
    username = config.get("username", "")
    password = config.get("password", "")
    database = config.get("database", "")

    match ds_type:
        case "dm":
            import dmPython
            with dmPython.connect(user=username, password=password, server=host, port=port) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1", timeout=timeout)
                    cur.fetchall()
        case "doris" | "starrocks":
            with pymysql.connect(user=username, passwd=password, host=host, port=port,
                                 db=database, connect_timeout=timeout, read_timeout=timeout) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        case "redshift":
            import redshift_connector
            with redshift_connector.connect(host=host, port=port, database=database,
                                            user=username, password=password, timeout=timeout) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        case "kingbase":
            import psycopg2
            with psycopg2.connect(host=host, port=port, database=database,
                                  user=username, password=password, connect_timeout=timeout) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        case "es":
            from elasticsearch import Elasticsearch
            es = Elasticsearch([host], basic_auth=(username, password), verify_certs=False)
            if not es.ping():
                return False, "Elasticsearch 连接失败"
        case _:
            return False, f"不支持的数据源类型: {ds_type}"

    return True, ""


def _get_tables_sync(ds_type: str, config: dict[str, Any]) -> list[dict[str, str]]:
    db = DBType.get(ds_type)
    param = _get_schema_param(ds_type, config)
    timeout = config.get("timeout", 30)
    tables: list[dict[str, str]] = []

    if db.connect_type == ConnectType.sqlalchemy and ds_type in _TABLE_SQL:
        engine = _make_engine(ds_type, config)
        with engine.connect() as conn:
            result = conn.execute(text(_TABLE_SQL[ds_type]), {"param": param})
            for row in result.fetchall():
                tables.append({"tableName": _decode(row[0]), "tableComment": _decode(row[1])})
    elif ds_type in ("doris", "starrocks"):
        host, port = config.get("host", ""), config.get("port", 3306)
        with pymysql.connect(user=config.get("username", ""), passwd=config.get("password", ""),
                             host=host, port=port, db=config.get("database", ""),
                             connect_timeout=timeout, read_timeout=timeout) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s",
                    (param,),
                )
                for row in cur.fetchall():
                    tables.append({"tableName": _decode(row[0]), "tableComment": _decode(row[1])})
    elif ds_type == "es":
        from elasticsearch import Elasticsearch
        es = Elasticsearch([config.get("host", "")],
                           basic_auth=(config.get("username", ""), config.get("password", "")),
                           verify_certs=False)
        for idx in es.cat.indices(format="json") or []:
            tables.append({"tableName": idx.get("index", ""), "tableComment": ""})
    elif ds_type == "dm":
        import dmPython
        with dmPython.connect(user=config.get("username", ""), password=config.get("password", ""),
                              server=config.get("host", ""), port=config.get("port", 5236)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name, comments FROM all_tab_comments"
                    " WHERE owner = :param AND (table_type='TABLE' OR table_type='VIEW')",
                    {"param": param}, timeout=timeout,
                )
                for row in cur.fetchall():
                    tables.append({"tableName": _decode(row[0]), "tableComment": _decode(row[1])})
    elif ds_type in ("kingbase", "redshift"):
        _get_tables_pg_like(ds_type, config, param, timeout, tables)
    else:
        raise ValueError(f"不支持的数据源类型: {ds_type}")

    return tables


def _get_tables_pg_like(ds_type: str, config: dict[str, Any], param: str, timeout: int, tables: list):
    """PostgreSQL 兼容数据库获取表列表"""
    if ds_type == "kingbase":
        import psycopg2
        with psycopg2.connect(
            host=config.get("host", ""), port=config.get("port", 54321),
            database=config.get("database", ""), user=config.get("username", ""),
            password=config.get("password", ""),
            options=f"-c statement_timeout={timeout * 1000}",
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT c.relname, COALESCE(d.description, obj_description(c.oid))
                    FROM pg_class c LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
                    LEFT JOIN pg_description d ON d.objoid = c.oid AND d.objsubid = 0
                    WHERE n.nspname = '{param}' AND c.relkind IN ('r','v','p','m')
                    AND c.relname NOT LIKE 'pg_%' AND c.relname NOT LIKE 'sql_%' ORDER BY c.relname
                """)
                for row in cur.fetchall():
                    tables.append({"tableName": _decode(row[0]), "tableComment": _decode(row[1])})
    elif ds_type == "redshift":
        import redshift_connector
        with redshift_connector.connect(
            host=config.get("host", ""), port=config.get("port", 5439),
            database=config.get("database", ""), user=config.get("username", ""),
            password=config.get("password", ""), timeout=timeout,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT relname, obj_description(relfilenode::regclass, 'pg_class') "
                    "FROM pg_class WHERE relkind IN ('r','p','f') "
                    "AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %s)",
                    (param,),
                )
                for row in cur.fetchall():
                    tables.append({"tableName": _decode(row[0]), "tableComment": _decode(row[1])})


def _get_fields_sync(ds_type: str, config: dict[str, Any], table_name: str) -> list[dict[str, Any]]:
    db = DBType.get(ds_type)
    param = _get_schema_param(ds_type, config)
    timeout = config.get("timeout", 30)
    fields: list[dict[str, Any]] = []

    if db.connect_type == ConnectType.sqlalchemy and ds_type in _FIELD_SQL:
        engine = _make_engine(ds_type, config)
        with engine.connect() as conn:
            result = conn.execute(text(_FIELD_SQL[ds_type]), {"p1": param, "p2": table_name})
            for idx, row in enumerate(result.fetchall()):
                fields.append({
                    "fieldName": _decode(row[0]), "fieldType": _decode(row[1]),
                    "fieldComment": _decode(row[2]), "fieldIndex": idx,
                })
    elif ds_type in ("doris", "starrocks"):
        host, port = config.get("host", ""), config.get("port", 3306)
        with pymysql.connect(user=config.get("username", ""), passwd=config.get("password", ""),
                             host=host, port=port, db=config.get("database", ""),
                             connect_timeout=timeout, read_timeout=timeout) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT"
                    " FROM INFORMATION_SCHEMA.COLUMNS"
                    " WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                    (param, table_name),
                )
                for idx, row in enumerate(cur.fetchall()):
                    fields.append({
                        "fieldName": _decode(row[0]), "fieldType": _decode(row[1]),
                        "fieldComment": _decode(row[2]), "fieldIndex": idx,
                    })
    elif ds_type == "es":
        from elasticsearch import Elasticsearch
        es = Elasticsearch([config.get("host", "")],
                           basic_auth=(config.get("username", ""), config.get("password", "")),
                           verify_certs=False)
        mapping = es.indices.get_mapping(index=table_name)
        props = mapping.get(table_name, {}).get("mappings", {}).get("properties", {})
        for idx, (name, cfg) in enumerate(props.items()):
            fields.append({
                "fieldName": name, "fieldType": cfg.get("type", ",".join(cfg.keys())),
                "fieldComment": "", "fieldIndex": idx,
            })
    else:
        # dm / kingbase / redshift 等可按需扩展
        raise ValueError(f"字段获取暂不支持: {ds_type}")

    return fields


def _execute_query_sync(ds_type: str, config: dict[str, Any], sql: str) -> list[dict[str, Any]]:
    # 去除末尾分号
    sql = sql.rstrip(";").strip()
    db = DBType.get(ds_type)
    timeout = config.get("timeout", 30)

    if db.connect_type == ConnectType.sqlalchemy:
        engine = _make_engine(ds_type, config)
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            return [{col: _process_value(row[i]) for i, col in enumerate(columns)} for row in result.fetchall()]

    # 原生驱动
    host, port = config.get("host", ""), config.get("port", 3306)
    username, password = config.get("username", ""), config.get("password", "")
    database = config.get("database", "")

    def _rows_to_dicts(cursor) -> list[dict[str, Any]]:
        columns = [d[0] for d in cursor.description]
        return [{col: _process_value(row[i]) for i, col in enumerate(columns)} for row in cursor.fetchall()]

    match ds_type:
        case "doris" | "starrocks":
            with pymysql.connect(user=username, passwd=password, host=host, port=port,
                                 db=database, connect_timeout=timeout, read_timeout=timeout) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    return _rows_to_dicts(cur)
        case "dm":
            import dmPython
            with dmPython.connect(user=username, password=password, server=host, port=port) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, timeout=timeout)
                    return _rows_to_dicts(cur)
        case "kingbase":
            import psycopg2
            with psycopg2.connect(host=host, port=port, database=database, user=username,
                                  password=password, options=f"-c statement_timeout={timeout * 1000}") as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    return _rows_to_dicts(cur)
        case "redshift":
            import redshift_connector
            with redshift_connector.connect(host=host, port=port, database=database,
                                            user=username, password=password, timeout=timeout) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    return _rows_to_dicts(cur)
        case "es":
            import requests
            from base64 import b64encode
            host_url = host.rstrip("/")
            creds = b64encode(f"{username}:{password}".encode()).decode()
            resp = requests.post(
                f"{host_url}/_sql?format=json",
                data=json.dumps({"query": sql}),
                headers={"Content-Type": "application/json", "Authorization": f"Basic {creds}"},
                verify=False, timeout=timeout,
            )
            res = resp.json()
            if res.get("error"):
                raise RuntimeError(json.dumps(res))
            columns = [c.get("name") for c in res.get("columns", [])]
            return [{col: _process_value(row[i]) for i, col in enumerate(columns)} for row in res.get("rows", [])]
        case _:
            raise ValueError(f"不支持的数据源类型: {ds_type}")


def _preview_table_sync(
    ds_type: str, config: dict[str, Any], table_name: str, limit: int = 100,
) -> list[dict[str, Any]]:
    """预览表数据"""
    db = DBType.get(ds_type)
    quoted_name = f"{db.prefix}{table_name}{db.suffix}"

    if ds_type == "oracle":
        sql = f"SELECT * FROM {quoted_name} WHERE ROWNUM <= {limit}"
    elif ds_type == "sqlServer":
        sql = f"SELECT TOP {limit} * FROM {quoted_name}"
    else:
        sql = f"SELECT * FROM {quoted_name} LIMIT {limit}"

    return _execute_query_sync(ds_type, config, sql)


# ── 异步公开接口 ──


async def test_connection(ds_type: str, config: dict[str, Any]) -> tuple[bool, str]:
    """测试数据源连接（异步）"""
    return await asyncio.to_thread(_test_connection_sync, ds_type, config)


async def get_tables(ds_type: str, config: dict[str, Any]) -> list[dict[str, str]]:
    """获取数据源表列表（异步）"""
    return await asyncio.to_thread(_get_tables_sync, ds_type, config)


async def get_fields(ds_type: str, config: dict[str, Any], table_name: str) -> list[dict[str, Any]]:
    """获取指定表的字段列表（异步）"""
    return await asyncio.to_thread(_get_fields_sync, ds_type, config, table_name)


async def execute_query(ds_type: str, config: dict[str, Any], sql: str) -> list[dict[str, Any]]:
    """执行 SQL 查询（异步）"""
    return await asyncio.to_thread(_execute_query_sync, ds_type, config, sql)


async def preview_table(
    ds_type: str, config: dict[str, Any], table_name: str, limit: int = 100,
) -> list[dict[str, Any]]:
    """预览表数据（异步）"""
    return await asyncio.to_thread(_preview_table_sync, ds_type, config, table_name, limit)
