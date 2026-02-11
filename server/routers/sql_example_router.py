"""SQL 示例管理 API"""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_admin_user, get_db, get_required_user
from src.repositories.sql_example_repository import SqlExampleRepository
from src.storage.postgres.models_business import User

sql_example = APIRouter(prefix="/sql-example", tags=["sql-example"])


@sql_example.get("/list")
async def list_sql_examples(
    datasource_id: int | None = None,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 SQL 示例列表"""
    repo = SqlExampleRepository(db)
    if datasource_id:
        examples = await repo.list_by_datasource(datasource_id)
    else:
        examples = await repo.list_all()
    return {"examples": [e.to_dict() for e in examples]}


@sql_example.post("/create")
async def create_sql_example(
    question: str = Body(...),
    sql_text: str = Body(...),
    datasource_id: int = Body(None),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """创建 SQL 示例"""
    repo = SqlExampleRepository(db)
    example = await repo.create({
        "question": question,
        "sql_text": sql_text,
        "datasource_id": datasource_id,
    })
    await db.commit()
    return {"message": "创建成功", "example": example.to_dict()}


@sql_example.put("/{example_id}")
async def update_sql_example(
    example_id: int,
    data: dict = Body(...),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 SQL 示例"""
    repo = SqlExampleRepository(db)
    example = await repo.update(example_id, data)
    if example is None:
        raise HTTPException(status_code=404, detail="SQL 示例不存在")
    await db.commit()
    return {"message": "更新成功", "example": example.to_dict()}


@sql_example.delete("/{example_id}")
async def delete_sql_example(
    example_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除 SQL 示例"""
    repo = SqlExampleRepository(db)
    ok = await repo.delete(example_id)
    if not ok:
        raise HTTPException(status_code=404, detail="SQL 示例不存在")
    await db.commit()
    return {"message": "删除成功"}
