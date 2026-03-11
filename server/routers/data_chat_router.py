"""对话 API 路由 - 支持多种问答模式"""

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from src.data_chat.service import get_recommended_questions, list_chat_sessions, run_data_chat
from src.services.chat_stream_service import run_common_chat, run_file_chat, run_report_chat
from src.storage.postgres.models_business import User

data_chat = APIRouter(prefix="/data-chat", tags=["data-chat"])

# 问答模式枚举
class QAMode:
    COMMON_QA = "COMMON_QA"  # 智能问答
    DATABASE_QA = "DATABASE_QA"  # 数据问答
    FILEDATA_QA = "FILEDATA_QA"  # 表格问答
    REPORT_QA = "REPORT_QA"  # 深度问数


class DataChatRequest(BaseModel):
    """数据问答请求"""

    query: str
    datasource_id: int | None = None  # 数据问答模式必需
    chat_id: str | None = None
    model: str | None = None  # 可选模型指定
    qa_type: str = "COMMON_QA"  # 问答模式: COMMON_QA, DATABASE_QA, FILEDATA_QA, REPORT_QA
    uuid: str | None = None  # 客户端生成的唯一ID
    file_list: list | None = None  # 表格问答模式使用的文件列表


class RecommendRequest(BaseModel):
    """推荐问题请求"""

    datasource_id: int
    question: str = ""
    model: str | None = None


class SessionRenameRequest(BaseModel):
    title: str


@data_chat.post("/chat")
async def chat_stream(
    req: DataChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """统一对话接口 - 支持多种问答模式（SSE 流式输出）

    qa_type:
        - COMMON_QA: 智能问答（通用大模型对话）
        - DATABASE_QA: 数据问答（Text2SQL）
        - FILEDATA_QA: 表格问答（上传Excel文件分析）
        - REPORT_QA: 深度问数（基于Skill的深度分析）
    """
    qa_type = req.qa_type or QAMode.DATABASE_QA

    # 根据问答类型路由到不同的处理函数
    if qa_type == QAMode.COMMON_QA:
        # 智能问答：使用通用对话Agent
        return StreamingResponse(
            run_common_chat(
                session=db,
                query=req.query,
                current_user=current_user,
                chat_id=req.chat_id,
                msg_uuid=req.uuid,
                model_spec=req.model,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    elif qa_type == QAMode.DATABASE_QA:
        # 数据问答：使用Text2SQL
        if not req.datasource_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="数据问答模式需要指定 datasource_id")

        return StreamingResponse(
            run_data_chat(
                session=db,
                query=req.query,
                datasource_id=req.datasource_id,
                user_id=str(current_user.id),
                chat_id=req.chat_id,
                model_spec=req.model,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    elif qa_type == QAMode.FILEDATA_QA:
        # 表格问答：使用文件分析Agent
        return StreamingResponse(
            run_file_chat(
                session=db,
                query=req.query,
                user_id=str(current_user.id),
                chat_id=req.chat_id,
                msg_uuid=req.uuid,
                model_spec=req.model,
                file_list=req.file_list or [],
                current_user=current_user,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    elif qa_type == QAMode.REPORT_QA:
        # 深度问数：使用报告Agent
        return StreamingResponse(
            run_report_chat(
                session=db,
                query=req.query,
                datasource_id=req.datasource_id,
                user_id=str(current_user.id),
                chat_id=req.chat_id,
                model_spec=req.model,
                current_user=current_user,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"不支持的问答类型: {qa_type}")


@data_chat.post("/recommend")
async def recommend_questions(
    req: RecommendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """获取推荐问题"""
    questions = await get_recommended_questions(
        session=db,
        datasource_id=req.datasource_id,
        question=req.question,
        model_spec=req.model,
    )
    return {"code": 0, "data": questions}


@data_chat.get("/sessions")
async def chat_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    qa_type: str = Query(default=None, description="问答模式过滤"),
    search: str = Query(default=None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """获取对话历史列表（支持分页和搜索）"""
    sessions, total = await list_chat_sessions(
        db,
        str(current_user.id),
        page_size,
        page,
        qa_type=qa_type,
        search_text=search
    )
    total_pages = (total + page_size - 1) // page_size
    return {
        "code": 0,
        "data": sessions,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    }


@data_chat.get("/sessions/{chat_id}/records")
async def chat_session_records(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """获取指定对话的历史记录"""
    from src.repositories.datasource_repository import DatasourceRepository

    repo = DatasourceRepository(db)
    records = await repo.list_chat_records(str(current_user.id), chat_id=chat_id, limit=100)
    # 按时间正序返回，便于前端展示对话顺序
    data = [r.to_dict() for r in reversed(records)]
    return {"code": 0, "data": data}


@data_chat.patch("/sessions/{chat_id}")
async def rename_chat_session(
    chat_id: str,
    req: SessionRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """重命名会话"""
    repo = DatasourceRepository(db)
    ok = await repo.rename_chat_session(user_id=str(current_user.id), chat_id=chat_id, title=req.title)
    if not ok:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="会话不存在")
    await db.commit()
    return {"code": 0, "data": True}


@data_chat.delete("/sessions/{chat_id}")
async def delete_chat_session(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """删除会话（软删）"""
    repo = DatasourceRepository(db)
    ok = await repo.delete_chat_session(user_id=str(current_user.id), chat_id=chat_id)
    if not ok:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="会话不存在")
    await db.commit()
    return {"code": 0, "data": True}
