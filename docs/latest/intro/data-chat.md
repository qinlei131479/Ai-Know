# 数据问答 (Text2SQL)

数据问答是 Yuxi-Know 新增的功能模块，融合了 Text2SQL 技术，支持用户使用自然语言查询关系型数据库，并自动生成 SQL、执行查询、展示图表和数据摘要。

## 功能概览

| 功能 | 说明 |
|------|------|
| **多数据源管理** | 支持 MySQL、PostgreSQL、Oracle、SQL Server、ClickHouse、达梦、Doris、StarRocks、Kingbase、Redshift 等数据库 |
| **自然语言问答** | 基于 LLM 将自然语言自动转换为 SQL 查询 |
| **智能图表** | 自动推荐图表类型，支持 ECharts 柱状图、折线图、饼图 |
| **数据摘要** | 对查询结果生成 Markdown 格式的分析摘要 |
| **术语库** | 业务术语定义，辅助 LLM 理解领域概念 |
| **SQL 示例** | Few-shot 示例，提升 SQL 生成准确率 |
| **推荐问题** | 基于表结构自动推荐相关问题 |

## 快速开始

### 1. 添加数据源

进入 Web 界面 → 侧边栏「数据源」页面 → 点击「新建数据源」：

1. 填写数据源名称和类型
2. 配置连接信息（主机、端口、用户名、密码、数据库名）
3. 点击「测试连接」确认连通性
4. 保存后点击「同步」将表结构同步到系统

### 2. 管理表结构

点击数据源卡片进入详情页：

- **左侧面板**：显示所有数据表，可通过开关控制哪些表参与问答
- **字段列表**：可为字段添加自定义注释，帮助 LLM 更准确理解字段含义
- **数据预览**：直接预览表中数据

### 3. 配置术语和 SQL 示例（可选）

在数据源详情页的「术语管理」和「SQL 示例」标签页中：

- **术语**：定义业务术语（如"GMV = 成交总额"），帮助 LLM 理解业务语言
- **SQL 示例**：提供问题-SQL 对照，作为 Few-shot 示例提升生成质量

### 4. 开始数据问答

进入侧边栏「数据问答」页面：

1. 从顶部下拉框选择已配置的数据源
2. 输入自然语言问题（如"最近一个月销售额最高的前10个产品"）
3. 系统自动执行：表结构检索 → SQL 生成 → SQL 执行 → 图表配置 + 数据总结
4. 查看结果：SQL 语句、数据表格、可视化图表、分析摘要

## 架构说明

### 工作流程

```
用户提问
  ↓
Schema 检索 (BM25 匹配相关表)
  ↓
SQL 生成 (LLM + 术语 + 示例)
  ↓
SQL 执行 (连接外部数据源)
  ↓
┌──────────────┬──────────────┬──────────────┐
│  图表配置     │  数据总结     │  推荐问题     │
│  (ECharts)   │  (Markdown)  │  (LLM 生成)  │
└──────────────┴──────────────┴──────────────┘
  ↓
SSE 流式返回前端
```

### 后端模块结构

```
src/data_chat/           # 数据问答核心模块
├── state.py             # 工作流状态定义
├── service.py           # 工作流编排 + SSE 输出
├── prompt_builder.py    # Prompt 构建
├── schema_formatter.py  # 表结构格式化 (M-Schema)
├── templates/
│   └── template.yaml    # Prompt 模板
└── nodes/
    ├── schema_inspector.py  # BM25 表检索
    ├── sql_generator.py     # LLM SQL 生成
    ├── sql_executor.py      # SQL 执行
    ├── chart_generator.py   # 图表配置生成
    ├── summarizer.py        # 数据总结
    └── recommender.py       # 问题推荐

src/services/
├── datasource_service.py    # 数据源业务逻辑
├── datasource_connector.py  # 多数据库连接器
└── datasource_crypto.py     # 连接配置加密
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATASOURCE_ENCRYPT_KEY` | 数据源连接配置的 Fernet 加密密钥 | 空（使用 base64 降级） |

生成加密密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将生成的密钥写入 `.env` 文件中的 `DATASOURCE_ENCRYPT_KEY` 字段。

## 支持的数据库驱动

系统内置了 MySQL 和 PostgreSQL 驱动。其他数据库需要额外安装对应的 Python 驱动包：

| 数据库 | 驱动包 | 安装方式 |
|--------|--------|----------|
| MySQL | `pymysql` | 已内置 |
| PostgreSQL | `psycopg2-binary` | 已内置 |
| Oracle | `oracledb` | `pip install oracledb` |
| SQL Server | `pymssql` | `pip install pymssql` |
| ClickHouse | `clickhouse-connect` | `pip install clickhouse-connect` |
| 达梦 | `dmPython` | 参考达梦官方文档 |
| Elasticsearch | `elasticsearch` | `pip install elasticsearch` |
| Redshift | `redshift_connector` | `pip install redshift_connector` |

> 在 Docker 环境中，可在 `pyproject.toml` 的 `dependencies` 中添加对应包，然后重新构建镜像。
