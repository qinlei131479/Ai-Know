from fastapi import APIRouter

from server.routers.auth_router import auth
from server.routers.chat_router import chat
from server.routers.dashboard_router import dashboard
from server.routers.data_chat_router import data_chat
from server.routers.datasource_router import datasource
from server.routers.department_router import department
from server.routers.graph_router import graph
from server.routers.knowledge_router import knowledge
from server.routers.evaluation_router import evaluation
from server.routers.mcp_router import mcp
from server.routers.mindmap_router import mindmap
from server.routers.sql_example_router import sql_example
from server.routers.system_router import system
from server.routers.task_router import tasks
from server.routers.terminology_router import terminology

router = APIRouter()

# 注册路由结构
router.include_router(system)  # /api/system/*
router.include_router(auth)  # /api/auth/*
router.include_router(chat)  # /api/chat/*
router.include_router(dashboard)  # /api/dashboard/*
router.include_router(department)  # /api/departments/*
router.include_router(knowledge)  # /api/knowledge/*
router.include_router(evaluation)  # /api/evaluation/*
router.include_router(mindmap)  # /api/mindmap/*
router.include_router(graph)  # /api/graph/*
router.include_router(tasks)  # /api/tasks/*
router.include_router(mcp)  # /api/system/mcp-servers/*
router.include_router(data_chat)  # /api/data-chat/*
router.include_router(datasource)  # /api/datasource/*
router.include_router(terminology)  # /api/terminology/*
router.include_router(sql_example)  # /api/sql-example/*
