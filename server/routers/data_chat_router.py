"""数据问答 API 路由 - Text2SQL 流式问答"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from src.data_chat.service import get_recommended_questions, list_chat_sessions, run_data_chat
from src.storage.postgres.models_business import User

data_chat = APIRouter(prefix="/data-chat", tags=["data-chat"])


class DataChatRequest(BaseModel):
    """数据问答请求"""

    query: str
    datasource_id: int
    chat_id: str | None = None
    model: str | None = None  # 可选模型指定


class RecommendRequest(BaseModel):
    """推荐问题请求"""

    datasource_id: int
    question: str = ""
    model: str | None = None


@data_chat.post("/chat")
async def chat_stream(
    req: DataChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """数据问答（SSE 流式输出）"""
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
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """获取数据问答对话列表"""
    sessions = await list_chat_sessions(db, str(current_user.id), limit)
    return {"code": 0, "data": sessions}


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
