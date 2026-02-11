"""数据源管理业务服务"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.datasource_repository import DatasourceRepository
from src.services import datasource_connector as connector
from src.services.datasource_crypto import decrypt_datasource_config, encrypt_datasource_config
from src.utils import logger


async def create_datasource(
    session: AsyncSession,
    name: str,
    ds_type: str,
    configuration: dict[str, Any],
    description: str | None = None,
    type_name: str | None = None,
    created_by: str | None = None,
    selected_tables: list[str] | None = None,
) -> dict[str, Any]:
    """创建数据源并同步表结构"""
    repo = DatasourceRepository(session)

    # 测试连接
    ok, err = await connector.test_connection(ds_type, configuration)
    status = "success" if ok else "failed"

    encrypted_config = encrypt_datasource_config(configuration)
    ds = await repo.create_datasource({
        "name": name,
        "ds_type": ds_type,
        "type_name": type_name or connector.DBType.get(ds_type).db_name,
        "configuration": encrypted_config,
        "description": description,
        "status": status,
        "created_by": created_by,
    })
    await session.commit()

    # 如果连接成功，同步表结构
    if ok:
        try:
            await sync_datasource_tables(
                session, ds.id, configuration,
                selected_tables=selected_tables,
            )
        except Exception as e:
            logger.warning(f"创建数据源后同步表结构失败: {e}")

    return ds.to_dict()


async def update_datasource(
    session: AsyncSession,
    ds_id: int,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """更新数据源"""
    repo = DatasourceRepository(session)
    ds = await repo.get_datasource_by_id(ds_id)
    if ds is None:
        return None

    # 如果更新了连接配置，重新测试连接
    if "configuration" in data and isinstance(data["configuration"], dict):
        config = data["configuration"]
        ok, _ = await connector.test_connection(ds.ds_type, config)
        data["status"] = "success" if ok else "failed"
        data["configuration"] = encrypt_datasource_config(config)

    updated = await repo.update_datasource(ds_id, data)
    await session.commit()
    return updated.to_dict() if updated else None


async def delete_datasource(session: AsyncSession, ds_id: int) -> bool:
    repo = DatasourceRepository(session)
    result = await repo.delete_datasource(ds_id)
    await session.commit()
    return result


async def list_datasources(session: AsyncSession) -> list[dict[str, Any]]:
    repo = DatasourceRepository(session)
    ds_list = await repo.list_datasources()
    return [ds.to_dict() for ds in ds_list]


async def get_datasource_detail(session: AsyncSession, ds_id: int, decrypt: bool = False) -> dict[str, Any] | None:
    repo = DatasourceRepository(session)
    ds = await repo.get_datasource_by_id(ds_id)
    if ds is None:
        return None
    return ds.to_dict(decrypt_config=decrypt)


async def test_datasource_connection(ds_type: str, configuration: dict[str, Any]) -> dict[str, Any]:
    """测试数据源连接"""
    ok, err = await connector.test_connection(ds_type, configuration)
    return {"success": ok, "message": err if not ok else "连接成功"}


async def get_tables_by_config(ds_type: str, configuration: dict[str, Any]) -> list[dict[str, str]]:
    """根据配置获取表列表（不保存到数据库）"""
    return await connector.get_tables(ds_type, configuration)


async def get_fields_by_config(ds_type: str, configuration: dict[str, Any], table_name: str) -> list[dict[str, Any]]:
    """根据配置获取字段列表（不保存到数据库）"""
    return await connector.get_fields(ds_type, configuration, table_name)


async def sync_datasource_tables(
    session: AsyncSession, ds_id: int, config: dict[str, Any] | None = None,
    selected_tables: list[str] | None = None,
) -> dict[str, Any]:
    """同步数据源的表结构到数据库

    Args:
        selected_tables: 用户选中的表名列表。若提供，仅选中的表 checked=True，其余为 False。
    """
    repo = DatasourceRepository(session)
    ds = await repo.get_datasource_by_id(ds_id)
    if ds is None:
        raise ValueError(f"数据源不存在: {ds_id}")

    if config is None:
        config = decrypt_datasource_config(ds.configuration)

    # 获取远程表列表
    remote_tables = await connector.get_tables(ds.ds_type, config)
    remote_table_names = [t["tableName"] for t in remote_tables]

    # 删除不再存在的表
    await repo.delete_tables_not_in(ds_id, remote_table_names)

    selected_set = set(selected_tables) if selected_tables is not None else None

    # 同步每个表和字段
    synced_count = 0
    for t_info in remote_tables:
        table_name = t_info["tableName"]
        table = await repo.upsert_table(ds_id, table_name, t_info.get("tableComment"))
        synced_count += 1

        # 根据选择列表更新 checked 状态
        if selected_set is not None:
            checked = table_name in selected_set
            if table.checked != checked:
                await repo.update_table(table.id, {"checked": checked})

        # 同步字段
        try:
            remote_fields = await connector.get_fields(
                ds.ds_type, config, table_name,
            )
            field_names = [f["fieldName"] for f in remote_fields]
            await repo.delete_fields_not_in(table.id, field_names)

            for f_info in remote_fields:
                await repo.upsert_field(
                    ds_id=ds_id, table_id=table.id,
                    field_name=f_info["fieldName"],
                    field_type=f_info.get("fieldType"),
                    field_comment=f_info.get("fieldComment"),
                    field_index=f_info.get("fieldIndex"),
                )
        except Exception as e:
            logger.warning(f"同步表 {table_name} 的字段失败: {e}")

    # 更新表数量统计
    all_tables = await repo.list_tables(ds_id)
    checked_count = sum(1 for t in all_tables if t.checked)
    await repo.update_datasource(
        ds_id, {"table_count": f"{checked_count}/{len(all_tables)}"},
    )
    await session.commit()

    return {"synced": synced_count, "total": len(remote_tables)}


async def get_table_list(session: AsyncSession, ds_id: int) -> list[dict[str, Any]]:
    """获取数据源的表列表"""
    repo = DatasourceRepository(session)
    tables = await repo.list_tables(ds_id)
    return [t.to_dict() for t in tables]


async def get_field_list(session: AsyncSession, table_id: int) -> list[dict[str, Any]]:
    """获取表的字段列表"""
    repo = DatasourceRepository(session)
    fields = await repo.list_fields(table_id)
    return [f.to_dict() for f in fields]


async def update_table_info(session: AsyncSession, table_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """更新表信息（自定义注释、是否选中等）"""
    repo = DatasourceRepository(session)
    table = await repo.update_table(table_id, data)
    await session.commit()
    return table.to_dict() if table else None


async def update_field_info(session: AsyncSession, field_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """更新字段信息（自定义注释、是否选中等）"""
    repo = DatasourceRepository(session)
    field = await repo.update_field(field_id, data)
    await session.commit()
    return field.to_dict() if field else None


async def preview_table_data(
    session: AsyncSession, ds_id: int, table_name: str, limit: int = 100,
) -> list[dict[str, Any]]:
    """预览表数据"""
    repo = DatasourceRepository(session)
    ds = await repo.get_datasource_by_id(ds_id)
    if ds is None:
        raise ValueError(f"数据源不存在: {ds_id}")

    config = decrypt_datasource_config(ds.configuration)
    return await connector.preview_table(ds.ds_type, config, table_name, limit)


async def save_table_relation(session: AsyncSession, ds_id: int, relation: dict[str, Any]) -> dict[str, Any] | None:
    """保存表关系"""
    repo = DatasourceRepository(session)
    ds = await repo.update_datasource(ds_id, {"table_relation": relation})
    await session.commit()
    return ds.to_dict() if ds else None
