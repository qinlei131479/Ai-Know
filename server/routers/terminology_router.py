"""术语管理 API"""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_admin_user, get_db, get_required_user
from src.repositories.terminology_repository import TerminologyRepository
from src.storage.postgres.models_business import User

terminology = APIRouter(prefix="/terminology", tags=["terminology"])


@terminology.get("/list")
async def list_terminologies(
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """获取术语列表"""
    repo = TerminologyRepository(db)
    terms = await repo.list_all()
    return {"terminologies": [t.to_dict() for t in terms]}


@terminology.post("/create")
async def create_terminology(
    word: str = Body(...),
    description: str = Body(None),
    specific_ds: bool = Body(False),
    datasource_ids: list[int] = Body(None),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """创建术语"""
    repo = TerminologyRepository(db)
    term = await repo.create({
        "word": word,
        "description": description,
        "specific_ds": specific_ds,
        "datasource_ids": datasource_ids,
    })
    await db.commit()
    return {"message": "创建成功", "terminology": term.to_dict()}


@terminology.put("/{term_id}")
async def update_terminology(
    term_id: int,
    data: dict = Body(...),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新术语"""
    repo = TerminologyRepository(db)
    term = await repo.update(term_id, data)
    if term is None:
        raise HTTPException(status_code=404, detail="术语不存在")
    await db.commit()
    return {"message": "更新成功", "terminology": term.to_dict()}


@terminology.delete("/{term_id}")
async def delete_terminology(
    term_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除术语"""
    repo = TerminologyRepository(db)
    ok = await repo.delete(term_id)
    if not ok:
        raise HTTPException(status_code=404, detail="术语不存在")
    await db.commit()
    return {"message": "删除成功"}
