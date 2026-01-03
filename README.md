# Memory Hub MCP Server

一个基于 MCP (Model Context Protocol) 的个人记忆中心服务器，用于保存和分析与 Claude/ChatGPT 等 AI 助手的对话历史。

## 功能特性

### 核心功能
- **用户认证**: 用户注册、登录、JWT token 认证
- **对话存储**: 自动保存用户与 AI 的对话历史
- **向量检索 (RAG)**: 使用语义搜索快速找到相关对话
- **知识图谱**: 自动构建实体关系图，分析对话中的主题和概念
- **多平台支持**: 支持 Claude、ChatGPT 等多个平台

### 存储能力
- **Vector 存储**: 使用 PostgreSQL + pgvector 存储对话 embeddings
- **Graph 存储**: 使用关系表构建知识图谱
- **高效检索**: 支持语义搜索、主题搜索、时间线查询等

## 架构设计

```
Memory Hub MCP Server
├── 数据层 (PostgreSQL + pgvector)
│   ├── conversations (对话 + embeddings)
│   ├── entities (实体)
│   ├── relationships (关系)
│   └── summaries (摘要)
├── 服务层
│   ├── EmbeddingService (向量生成)
│   ├── RAGService (检索服务)
│   └── GraphService (图分析)
└── MCP 接口层
    ├── save_conversation
    ├── search_conversations
    ├── get_related_entities
    └── 更多 tools...
```

## 安装步骤

### 1. 环境准备

确保已安装:
- Python 3.11+
- PostgreSQL (通过 docker-compose 已配置)

### 2. 启动数据库

```bash
# 在项目根目录启动 PostgreSQL
cd ..
docker-compose up -d
```

数据库配置:
- Host: localhost
- Port: 5632
- Database: memhub
- User: postgres
- Password: itsnothing

### 3. 安装依赖

```bash
cd PythonProject
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. 配置环境变量（可选）

```bash
cp .env.example .env
```

默认配置已经可以使用，如需自定义 embedding 模型可以编辑 `.env` 文件:

```
# 可选：更改 embedding 模型
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSIONS=384
```

### 5. 初始化数据库

```bash
python database.py
```

### 6. 运行 MCP Server

```bash
python server.py
```

## MCP Server 配置

在 Claude Desktop 或其他 MCP 客户端中添加配置:

**Claude Desktop 配置** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "memory-hub": {
      "command": "python",
      "args": ["/path/to/PythonProject/server.py"]
    }
  }
}
```

**注意**: 使用 sentence-transformers 本地模型，无需 API Key 配置！

## 可用 Tools

### 1. 用户认证

**register_user**
- 注册新用户账号
- 参数: username, email, password, full_name

**login_user**
- 用户登录并获取 JWT token
- 参数: username, password

**verify_token**
- 验证 JWT token
- 参数: token

**get_user_info**
- 获取当前用户信息
- 参数: token

**update_password**
- 修改用户密码
- 参数: token, old_password, new_password

### 2. 对话管理

**save_conversation**
- 保存对话消息并自动生成 embedding
- 参数: user_id, session_id, role, content, platform, metadata

### 3. 检索功能

**search_conversations**
- 使用语义搜索查找相关对话
- 参数: query, user_id, limit, session_id, platform, days_back

**get_recent_context**
- 获取最近的对话上下文
- 参数: user_id, session_id, limit

**search_by_topic**
- 根据主题搜索对话
- 参数: topic, user_id, limit

### 4. 知识图谱

**get_related_entities**
- 获取与指定实体相关的其他实体
- 参数: entity_name, user_id, max_depth, limit

**get_entity_importance**
- 获取最重要的实体（基于图中心性）
- 参数: user_id, limit

**get_topic_clusters**
- 识别主题聚类
- 参数: user_id, min_cluster_size

**get_timeline**
- 获取对话时间线
- 参数: user_id, entity_name, limit

### 5. 手动管理

**add_entity**
- 手动添加实体
- 参数: conversation_id, entity_type, entity_name, description

**add_relationship**
- 手动添加实体关系
- 参数: source_entity_id, target_entity_id, relationship_type, weight

## 使用示例

### 保存对话

```python
{
  "user_id": "user_123",
  "session_id": "session_456",
  "role": "user",
  "content": "今天学习了 Python 的异步编程",
  "platform": "claude"
}
```

### 搜索对话

```python
{
  "query": "Python 异步编程",
  "user_id": "user_123",
  "limit": 5
}
```

### 获取主题聚类

```python
{
  "user_id": "user_123",
  "min_cluster_size": 3
}
```

## 数据模型

### Users
- 用户账号信息
- 包含加密密码、邮箱等
- 支持激活/停用状态

### Conversations
- 存储所有对话消息
- 包含 embedding 向量用于语义搜索
- 支持按用户、会话、平台、时间筛选

### Entities
- 从对话中提取的实体
- 类型: person, topic, concept 等
- 每个实体都有 embedding

### Relationships
- 实体间的关系
- 支持权重和类型
- 用于构建知识图谱

### Summaries
- 对话摘要
- 支持会话摘要、每日摘要、主题摘要等

## 开发

### 运行测试

```bash
pytest tests/
```

### 数据库迁移

如需修改数据库结构，更新 `database.py` 中的模型定义后:

```bash
python database.py
```

## 技术栈

- **MCP**: Model Context Protocol
- **数据库**: PostgreSQL + pgvector
- **向量化**: sentence-transformers (本地运行，无需 API Key)
- **图分析**: NetworkX
- **ORM**: SQLAlchemy
- **异步**: asyncio

## Embedding 模型

默认使用 `paraphrase-multilingual-MiniLM-L12-v2` (384维，支持中英文)

可选模型:
- `all-MiniLM-L6-v2`: 快速，384维，仅英文
- `all-mpnet-base-v2`: 高质量，768维，仅英文
- `paraphrase-multilingual-mpnet-base-v2`: 高质量，768维，多语言

修改 `.env` 或 `config.py` 中的 `EMBEDDING_MODEL` 配置即可切换。

## 注意事项

1. **无需 API Key**: 使用本地 sentence-transformers，完全免费
2. **首次启动**: 会自动下载 embedding 模型（约 120MB）
3. 确保 PostgreSQL 已安装 pgvector 扩展
4. 首次运行需要初始化数据库
5. 建议定期备份数据库

## 未来计划

- [ ] 自动实体提取（使用 NLP）
- [ ] 对话摘要生成
- [ ] 多用户权限管理
- [ ] Web 界面
- [ ] 导出/导入功能
- [ ] 更多图分析算法

## License

MIT
