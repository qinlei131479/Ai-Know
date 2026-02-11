"""数据源管理 API"""

import traceback

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_admin_user, get_db, get_required_user
from src.services import datasource_service as ds_svc
from src.services.datasource_connector import DBType
from src.storage.postgres.models_business import User
from src.utils import logger

datasource = APIRouter(prefix="/datasource", tags=["datasource"])


# ── 数据源 CRUD ──


@datasource.get("/types")
async def get_datasource_types(current_user: User = Depends(get_required_user)):
    """获取支持的数据源类型列表"""
    return {"types": DBType.all_types()}


@datasource.get("/list")
async def list_datasources(
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据源列表"""
    try:
        return {"datasources": await ds_svc.list_datasources(db)}
    except Exception as e:
        logger.error(f"获取数据源列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@datasource.get("/{ds_id}")
async def get_datasource(
    ds_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据源详情（含解密配置，仅管理员）"""
    result = await ds_svc.get_datasource_detail(db, ds_id, decrypt=True)
    if result is None:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return result


@datasource.post("/create")
async def create_datasource(
    name: str = Body(...),
    ds_type: str = Body(...),
    configuration: dict = Body(...),
    description: str = Body(None),
    type_name: str = Body(None),
    selected_tables: list[str] | None = Body(None),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """创建数据源（仅管理员）"""
    try:
        result = await ds_svc.create_datasource(
            db, name=name, ds_type=ds_type, configuration=configuration,
            description=description, type_name=type_name,
            created_by=str(current_user.user_id),
            selected_tables=selected_tables,
        )
        return {"message": "创建成功", "datasource": result}
    except Exception as e:
        logger.error(f"创建数据源失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@datasource.put("/{ds_id}")
async def update_datasource(
    ds_id: int,
    data: dict = Body(...),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新数据源（仅管理员）"""
    try:
        result = await ds_svc.update_datasource(db, ds_id, data)
        if result is None:
            raise HTTPException(status_code=404, detail="数据源不存在")
        return {"message": "更新成功", "datasource": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新数据源失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@datasource.delete("/{ds_id}")
async def delete_datasource(
    ds_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除数据源（仅管理员）"""
    ok = await ds_svc.delete_datasource(db, ds_id)
    if not ok:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"message": "删除成功"}


# ── 连接测试 ──


@datasource.post("/check")
async def check_connection(
    ds_type: str = Body(...),
    configuration: dict = Body(...),
    current_user: User = Depends(get_admin_user),
):
    """测试数据源连接"""
    return await ds_svc.test_datasource_connection(ds_type, configuration)


# ── 表结构管理 ──


@datasource.post("/{ds_id}/sync")
async def sync_tables(
    ds_id: int,
    selected_tables: list[str] | None = Body(None, embed=True),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """同步数据源表结构"""
    try:
        result = await ds_svc.sync_datasource_tables(
            db, ds_id, selected_tables=selected_tables,
        )
        return {"message": "同步成功", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"同步表结构失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@datasource.get("/{ds_id}/tables")
async def get_tables(
    ds_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据源的表列表"""
    return {"tables": await ds_svc.get_table_list(db, ds_id)}


@datasource.get("/table/{table_id}/fields")
async def get_fields(
    table_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """获取表的字段列表"""
    return {"fields": await ds_svc.get_field_list(db, table_id)}


@datasource.put("/table/{table_id}")
async def update_table(
    table_id: int,
    data: dict = Body(...),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新表信息（自定义注释、是否选中等）"""
    result = await ds_svc.update_table_info(db, table_id, data)
    if result is None:
        raise HTTPException(status_code=404, detail="表不存在")
    return result


@datasource.put("/field/{field_id}")
async def update_field(
    field_id: int,
    data: dict = Body(...),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新字段信息"""
    result = await ds_svc.update_field_info(db, field_id, data)
    if result is None:
        raise HTTPException(status_code=404, detail="字段不存在")
    return result


# ── 数据预览与表关系 ──


@datasource.post("/{ds_id}/preview")
async def preview_data(
    ds_id: int,
    table_name: str = Body(...),
    limit: int = Body(100),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """预览表数据"""
    try:
        data = await ds_svc.preview_table_data(db, ds_id, table_name, limit)
        return {"data": data, "total": len(data)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"预览数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@datasource.post("/{ds_id}/table-relation")
async def save_table_relation(
    ds_id: int,
    relation: dict = Body(...),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """保存表关系"""
    result = await ds_svc.save_table_relation(db, ds_id, relation)
    if result is None:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"message": "保存成功"}


@datasource.get("/{ds_id}/table-relation")
async def get_table_relation(
    ds_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """获取表关系"""
    detail = await ds_svc.get_datasource_detail(db, ds_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"relation": detail.get("table_relation") or {}}


# ── 不保存到数据库的临时操作 ──


@datasource.post("/tables-by-config")
async def get_tables_by_config(
    ds_type: str = Body(...),
    configuration: dict = Body(...),
    current_user: User = Depends(get_admin_user),
):
    """根据配置获取表列表（不保存）"""
    try:
        tables = await ds_svc.get_tables_by_config(ds_type, configuration)
        return {"tables": tables}
    except Exception as e:
        logger.error(f"获取表列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@datasource.post("/fields-by-config")
async def get_fields_by_config(
    ds_type: str = Body(...),
    configuration: dict = Body(...),
    table_name: str = Body(...),
    current_user: User = Depends(get_admin_user),
):
    """根据配置获取字段列表（不保存）"""
    try:
        fields = await ds_svc.get_fields_by_config(ds_type, configuration, table_name)
        return {"fields": fields}
    except Exception as e:
        logger.error(f"获取字段列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
