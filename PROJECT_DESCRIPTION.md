# 语析 - Yuxi-Know 项目描述

## 项目概述

**语析（Yuxi-Know）** 是一款基于大模型的智能知识库与知识图谱智能体开发平台，融合了 RAG（检索增强生成）技术与知识图谱技术。该项目基于 **LangGraph v1 + Vue.js + FastAPI + LightRAG** 架构构建，完全通过 Docker Compose 进行管理，支持热重载开发。

- **项目版本**: 0.5.0.dev
- **开源协议**: MIT License

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **智能体开发** | 基于 LangGraph v1 的多智能体架构，支持子智能体、工具调用与中间件机制 |
| **知识库（RAG）** | 多格式文档上传，支持 Embedding / Rerank 配置及知识库评估 |
| **知识图谱** | 基于 LightRAG 的图谱构建与可视化，支持属性图谱并参与智能体推理 |
| **平台与工程化** | Vue + FastAPI 架构，支持暗黑模式、Docker 与生产级部署 |

---

## 技术架构

### 技术栈

#### 后端技术栈

| 技术 | 用途 |
|------|------|
| **FastAPI** | Web 框架 |
| **Python 3.12+** | 运行时 |
| **LangGraph v1** | 智能体框架 |
| **LightRAG** | 知识图谱引擎 |
| **LangChain** | LLM 集成 |
| **PostgreSQL** | 关系型数据库 |
| **Milvus** | 向量数据库 |
| **Neo4j** | 图数据库 |
| **MinIO** | 对象存储 |

#### 前端技术栈

| 技术 | 用途 |
|------|------|
| **Vue.js 3** | 框架 |
| **Ant Design Vue** | UI 组件库 |
| **Pinia** | 状态管理 |
| **Vue Router** | 路由 |
| **Vite** | 构建工具 |
| **ECharts** | 图表可视化 |
| **@antv/g6** | 图谱可视化 |

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue.js)                         │
│  HomeView │ LoginView │ DashboardView │ AgentView │ ...     │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                      后端 (FastAPI)                          │
│  Routers │ Agents │ Knowledge │ Services │ Repositories     │
└────────┬────────────┬────────────┬────────────┬─────────────┘
         │            │            │            │
    ┌────▼────┐  ┌────▼────┐  ┌────▼────┐    ┌──▼────────┐
    │PostgreSQL│ │ Milvus  │  │  Neo4j  │    │  MinIO    │
    └─────────┘  └─────────┘  └─────────┘    └───────────┘
```

---

## 功能模块

### 1. 智能体系统 (Agents)

项目基于 LangGraph v1 构建了完整的多智能体开发框架，包含以下核心模块：

| 模块 | 文件路径 | 功能说明 |
|------|----------|----------|
| **ChatBot** | `src/agents/chatbot/` | 基础聊天智能体 |
| **Deep Agent** | `src/agents/deep_agent/` | 深度分析智能体，支持 todo、文件渲染、文件下载 |
| **Reporter** | `src/agents/reporter/` | 报告生成智能体 |
| **公共组件** | `src/agents/common/` | 工具(tools)、中间件(middlewares)、工具包(toolkits)、子智能体(subagents) |

#### 智能体核心能力

- **工具调用**: 支持自定义工具扩展，集成 MySQL 数据库工具
- **中间件机制**: 
  - `summary_middleware` - 总结中间件
  - `runtime_config_middleware` - 运行时配置中间件
  - `attachment_middleware` - 附件处理中间件
  - `dynamic_tool_middleware` - 动态工具中间件
  - `context_middlewares` - 上下文中间件
- **子智能体**: 支持_calc_agent等子智能体协同工作

### 2. 知识库系统 (Knowledge Base)

支持多类型知识库构建与管理，采用 RAG 技术实现智能检索：

| 模块 | 文件路径 | 功能说明 |
|------|----------|----------|
| **Milvus 实现** | `src/knowledge/implementations/milvus.py` | 基于 Milvus 的向量知识库 |
| **LightRAG 实现** | `src/knowledge/implementations/lightrag.py` | 知识图谱增强的 RAG |
| **管理器** | `src/knowledge/manager.py` | 知识库生命周期管理 |
| **工厂** | `src/knowledge/factory.py` | 知识库实例工厂 |
| **上传服务** | `src/knowledge/services/upload_graph_service.py` | 图谱上传处理 |
| **适配器** | `src/knowledge/adapters/` | 多种解析适配器 |

#### 知识库特性

- 支持 PDF / Word / Markdown / 图片等多格式文档
- 支持 Embedding / Rerank 模型配置
- 支持知识库评估功能
- 支持文件夹/压缩包批量上传

### 3. 知识图谱系统 (Graph)

基于 LightRAG 实现知识图谱构建与可视化：

| 功能 | 说明 |
|------|------|
| **自动构建** | 自动从文档中抽取实体和关系 |
| **手动构建** | 支持上传预构建的图谱文件 |
| **属性图谱** | 支持节点和边的属性定义 |
| **可视化** | 基于 @antv/g6 的图谱可视化 |
| **推理增强** | 图谱信息参与智能体推理过程 |

### 4. 文档解析系统

集成先进的文档解析技术：

| 服务 | 说明 |
|------|------|
| **MinerU** | 高精度文档解析，支持 PDF、Office 文档 |
| **PaddleX OCR** | 图片文字识别 (OCR) |
| **Docling** | Office 文件 (docx/xlsx/pptx) 解析 |

### 5. API 路由模块

项目包含 16 个功能完整的 API 路由模块：

| | 文件路径 | 路由模块 功能说明 |
|----------|----------|----------|
| **认证** | `server/routers/auth_router.py` | 用户登录、注册、权限管理 |
| **聊天** | `server/routers/chat_router.py` | 智能体对话接口 |
| **数据聊天** | `server/routers/data_chat_router.py` | 数据库智能问答 |
| **仪表盘** | `server/routers/dashboard_router.py` | 管理仪表盘统计 |
| **数据源** | `server/routers/datasource_router.py` | 外部数据源管理 |
| **部门** | `server/routers/department_router.py` | 组织架构管理 |
| **评估** | `server/routers/evaluation_router.py` | 知识库评估功能 |
| **图谱** | `server/routers/graph_router.py` | 知识图谱管理 |
| **知识库** | `server/routers/knowledge_router.py` | 知识库 CRUD 操作 |
| **思维导图** | `server/routers/mindmap_router.py` | 思维导图生成 |
| **MCP** | `server/routers/mcp_router.py` | MCP 工具集成 |
| **SQL 示例** | `server/routers/sql_example_router.py` | SQL 查询示例 |
| **系统** | `server/routers/system_router.py` | 系统配置与健康检查 |
| **任务** | `server/routers/task_router.py` | 异步任务管理 |
| **术语** | `server/routers/terminology_router.py` | 术语库管理 |

### 6. 前端页面模块

| 页面 | 文件路径 | 功能说明 |
|------|----------|----------|
| **首页** | `web/src/views/HomeView.vue` | 首页概览 |
| **登录** | `web/src/views/LoginView.vue` | 用户登录 |
| **仪表盘** | `web/src/views/DashboardView.vue` | 管理仪表盘 |
| **智能体** | `web/src/views/AgentView.vue` | 智能体管理 |
| **数据聊天** | `web/src/views/DataChatView.vue` | 数据库问答 |
| **数据源** | `web/src/views/DatasourceView.vue` | 数据源管理 |
| **数据库** | `web/src/views/DataBaseView.vue` | 数据库管理 |
| **图谱** | `web/src/views/GraphView.vue` | 知识图谱可视化 |

---

## 基础设施

### Docker 服务架构

项目通过 Docker Compose 编排以下服务：

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| **API** | `api-dev` | 5050 | FastAPI 后端服务 |
| **Web** | `web-dev` | 5173 | Vue.js 前端服务 |
| **Graph** | `graph` | 7474, 7687 | Neo4j 图数据库 |
| **Postgres** | `postgres` | 25432 | PostgreSQL 数据库 |
| **Milvus** | `milvus` | 19530, 9091 | 向量数据库 |
| **MinIO** | `milvus-minio` | 9000, 9001 | 对象存储 |
| **etcd** | `milvus-etcd-dev` | 2379 | Milvus 依赖 |
| **MinerU VLLM** | `mineru-vllm-server` | 30000 | 文档解析 (可选) |
| **MinerU API** | `mineru-api` | 30001 | 文档解析 API (可选) |
| **PaddleX** | `paddlex-ocr` | 8080 | OCR 服务 (可选) |

### 配置文件

| 文件 | 说明 |
|------|------|
| `.env` | 环境变量配置 |
| `docker-compose.yml` | Docker 服务编排 |
| `pyproject.toml` | Python 项目依赖 |
| `web/package.json` | 前端项目依赖 |

---

## 项目目录结构

```
Yuxi-Know/
├── server/                    # FastAPI 后端
│   ├── main.py              # 应用入口
│   ├── routers/             # API 路由模块
│   └── utils/               # 工具函数
├── src/                     # 核心业务逻辑
│   ├── agents/              # 智能体实现
│   │   ├── chatbot/         # 聊天智能体
│   │   ├── deep_agent/     # 深度分析智能体
│   │   ├── reporter/       # 报告生成智能体
│   │   └── common/         # 公共组件
│   ├── knowledge/           # 知识库模块
│   │   ├── implementations/# 知识库实现
│   │   ├── services/       # 业务服务
│   │   └── adapters/       # 解析适配器
│   ├── storage/             # 存储层
│   ├── services/            # 业务服务层
│   ├── repositories/        # 数据访问层
│   ├── models/              # 数据模型
│   ├── plugins/             # 文档解析插件
│   ├── config/              # 配置模块
│   └── utils/               # 工具函数
├── web/                     # Vue.js 前端
│   ├── src/
│   │   ├── views/           # 页面视图
│   │   ├── components/      # Vue 组件
│   │   ├── stores/          # Pinia 状态管理
│   │   ├── router/          # Vue Router 配置
│   │   ├── apis/            # API 接口定义
│   │   └── assets/          # 静态资源
│   └── package.json
├── docker/                   # Docker 配置
│   └── volumes/             # 数据卷
├── docs/                     # 项目文档
├── scripts/                  # 脚本工具
├── test/                     # 测试代码
├── saves/                    # 保存的文件
├── models/                   # 本地模型
├── docker-compose.yml        # Docker 编排
└── README.md                 # 项目说明
```

---

## 使用场景

语析平台可以用于：

1. **构建企业知识库**: 将 PDF、Word、Markdown 等文档快速转化为可推理的知识库
2. **智能问答系统**: 基于 RAG + 知识图谱的智能问答，支持数据库问答
3. **知识图谱构建**: 自动或手动构建知识图谱，用于智能体推理
4. **多智能体开发**: 使用 LangGraph v1 构建复杂的多智能体系统
5. **文档智能解析**: 高精度解析各类文档，提取关键信息
6. **数据分析助手**: 连接数据库，通过自然语言进行数据查询和分析

---

## 快速开始

```bash
# 初始化项目
./scripts/init.sh

# 启动所有服务
docker compose up --build
```

*本文档最后更新于 2026年3月*
