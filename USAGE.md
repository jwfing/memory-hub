# Memory Hub 使用指南

## 快速开始

### 1. 启动服务

```bash
# 1. 启动数据库
cd /Users/fengjunwen/Projects/bookmark.ai
docker-compose up -d

# 2. 激活 Python 环境
cd PythonProject
source .venv/bin/activate

# 3. 初始化数据库（首次运行）
python init_db.py

# 4. 测试服务
python test_server.py

# 5. 运行 MCP Server
python server.py
```

### 2. 配置 Claude Desktop

复制以下配置到 `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "memory-hub": {
      "command": "python",
      "args": ["/Users/fengjunwen/Projects/bookmark.ai/PythonProject/server.py"]
    }
  }
}
```

重启 Claude Desktop 后，Memory Hub 将自动可用。

**注意**: 使用 sentence-transformers 本地模型，无需 OpenAI API Key！

## 常见使用场景

### 场景 1: 保存对话历史

在与 Claude 对话时，可以要求 Claude 保存重要对话:

```
请帮我保存这段对话到 Memory Hub。
我的 user_id 是 "john_doe"，session_id 是 "learning_python_20241225"
```

Claude 会自动调用 `save_conversation` tool。

### 场景 2: 搜索历史对话

```
请在我的历史对话中搜索关于 "Python 异步编程" 的内容。
我的 user_id 是 "john_doe"
```

Claude 会调用 `search_conversations` tool 并返回相关结果。

### 场景 3: 获取最近对话上下文

```
请给我展示最近 20 条对话记录。
user_id: "john_doe"
session_id: "learning_python_20241225"
```

### 场景 4: 分析讨论的主题

```
请分析我最近讨论的主要主题有哪些。
user_id: "john_doe"
```

Claude 会调用 `get_topic_clusters` tool 来识别主题聚类。

### 场景 5: 查找相关概念

```
我之前讨论过 "机器学习" 相关的内容吗？
相关的实体和概念有哪些？
user_id: "john_doe"
```

Claude 会使用 `get_related_entities` tool 查找知识图谱中的相关实体。

## 工作流示例

### 学习记录工作流

1. **开始新的学习会话**
   ```
   今天开始学习 FastAPI 框架。
   请保存这个对话，user_id: "john", session_id: "fastapi_learning_day1"
   ```

2. **记录学习内容**
   ```
   FastAPI 是一个现代化的 Python Web 框架，特点是...
   （Claude 自动保存对话）
   ```

3. **查询之前学过的内容**
   ```
   我之前学习 FastAPI 时记录了哪些内容？
   user_id: "john"
   query: "FastAPI"
   ```

4. **分析学习主题**
   ```
   帮我分析一下这个月我主要学习了哪些技术主题？
   user_id: "john"
   ```

### 项目讨论工作流

1. **记录项目讨论**
   ```
   项目需求：开发一个用户认证系统...
   session_id: "project_auth_system"
   ```

2. **获取项目时间线**
   ```
   显示关于 "认证系统" 项目的所有讨论时间线
   user_id: "john"
   entity_name: "认证系统"
   ```

3. **查找相关决策**
   ```
   我们在认证系统中关于数据库选择有过哪些讨论？
   user_id: "john"
   query: "数据库选择 认证系统"
   ```

## 高级功能

### 手动管理实体

如果 Claude 没有自动识别重要实体，可以手动添加:

```
请为 conversation_id 123 添加一个实体：
- entity_type: "technology"
- entity_name: "FastAPI"
- description: "现代化 Python Web 框架"
```

### 手动管理关系

建立实体间的关系:

```
请在实体 "FastAPI" (ID: 45) 和 "Pydantic" (ID: 46) 之间建立关系：
- relationship_type: "uses"
- weight: 0.9
```

## 数据管理

### 查看统计信息

```
显示 Memory Hub 的统计信息
```

Claude 会读取 `memory://stats` resource。

### 导出数据

```python
# 使用 Python 脚本导出
from memhub.database import SessionLocal, Conversation
import json

db = SessionLocal()
conversations = db.query(Conversation).filter(
    Conversation.user_id == "john_doe"
).all()

# 导出为 JSON
data = [
    {
        "id": c.id,
        "content": c.content,
        "created_at": c.created_at.isoformat()
    }
    for c in conversations
]

with open("export.json", "w") as f:
    json.dump(data, f, indent=2)
```

## 最佳实践

### 1. 使用有意义的 session_id

```
✓ good: "python_learning_week1"
✓ good: "project_auth_2024Q1"
✗ bad: "session1"
✗ bad: "abc123"
```

### 2. 保持 user_id 一致

在所有对话中使用相同的 user_id，这样可以:
- 跨会话搜索
- 构建完整的知识图谱
- 分析长期学习路径

### 3. 定期回顾

```
# 每周回顾
请总结我这周讨论的主要主题
user_id: "john"
days_back: 7

# 每月回顾
请显示我这个月最重要的学习主题
user_id: "john"
days_back: 30
```

### 4. 利用知识图谱

```
# 探索概念关系
请显示与 "机器学习" 相关的所有概念
max_depth: 2

# 发现新联系
请帮我找出我学习的不同主题之间的联系
```

## 故障排除

### 问题: 无法连接数据库

**解决方案:**
```bash
# 检查数据库是否运行
docker ps | grep postgres

# 如果没有运行，启动它
docker-compose up -d

# 检查端口
lsof -i :5632
```

### 问题: 模型下载缓慢

**解决方案:**
1. 首次启动会下载 embedding 模型（约 120MB）
2. 使用国内镜像加速（如需要）
3. 模型会缓存在 `~/.cache/huggingface/`

### 问题: 搜索结果为空

**解决方案:**
1. 确认使用了正确的 user_id
2. 检查是否有保存过对话
3. 降低相似度阈值（在代码中调整）

### 问题: 知识图谱为空

**解决方案:**
1. 需要先手动添加实体
2. 或者等待未来版本的自动实体提取功能

## 性能优化

### 1. 批量保存

如果有大量历史对话要导入:

```python
from memhub.database import SessionLocal, Conversation
from memhub.embeddings import get_embedding_service

db = SessionLocal()
service = get_embedding_service()

# 批量生成 embeddings
texts = [conv["content"] for conv in conversations]
embeddings = service.get_embeddings_batch(texts)

# 批量插入
for conv_data, embedding in zip(conversations, embeddings):
   conv = Conversation(
      user_id=conv_data["user_id"],
      content=conv_data["content"],
      embedding=embedding,
      ...
   )
   db.add(conv)

db.commit()
```

### 2. 索引优化

数据库已经创建了必要的索引，但如果数据量很大（>100万条），可以考虑:
- 定期 VACUUM ANALYZE
- 调整 PostgreSQL 配置
- 使用分区表

## 更多资源

- [README.md](README.md) - 完整文档
- [database.py](memhub/database.py) - 数据模型定义
- [server.py](server.py) - MCP Server 实现
- [MCP 官方文档](https://modelcontextprotocol.io/)
