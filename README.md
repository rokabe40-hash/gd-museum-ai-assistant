# 广东省博物馆讲解 AI 后端

面向游客的讲解/馆务问答服务。回答由两部分拼接：**图谱客观事实**（朝代、材质、尺寸，来自 Neo4j）+ **向量背景故事**（来自 RAG 检索），最后由 LLM 统一组装成通俗回答。

## 功能

- **混合检索**：图查询（Neo4j）提供结构化事实，向量检索（Qdrant + DashScope）提供背景故事，LLM 组装。
- **意图分流**：闲聊（chitchat）、馆务（facility）、内容问答（museum_query）三类意图自动路由。
- **馆务问答**：BM25 中文检索（2-gram 分词）命中 FAQ 章节，严格基于资料回答、不捏造。
- **楼层导览**：`三楼有什么展厅` 等按楼层列出展厅（`list_halls(floor=N)`）。
- **完整溯源**：回答附带 `reasoning_steps`（思考链）与 `citations`（引用来源）。
- **单元/集成测试**：`pytest` 快速单测 + `pytest -m integration` 全栈回归。

## 架构

LangGraph 状态机，6 个节点：

```
START → intent_parser_node
           ├─ chitchat  → chitchat_node          → END
           ├─ facility  → facility_node           → END（BM25 检 FAQ）
           └─ museum_query → graph_retrieval_node → vector_retrieval_node → generate_answer_node → END
```

- `graph_retrieval_node`：按 `entity_type`（artifact/exhibition/hall/floor）从 Neo4j 取客观事实。
- `vector_retrieval_node`：RAG 混合检索取背景故事。
- `generate_answer_node`：LLM 综合"图谱事实 + 向量故事"生成回答。
- `reasoning_log` 用 LangGraph reducer 累加，API 返回完整步骤链。

## 目录结构

```
├── main.py                 # FastAPI + LangGraph 后端（唯一入口）
├── faq_builder.py          # FAQ JSON → Markdown（BM25 索引源）
├── requirements.txt        # 根项目运行时依赖
├── pytest.ini              # 测试配置（默认跳过集成）
├── .env.example            # 环境变量模板
├── tests/                  # 单测（节点/分词/BM25/楼层）+ 集成
├── Neo4j/
│   ├── museum_graph.py     # MuseumGraph 查询接口
│   ├── import_to_neo4j.py  # 数据导入脚本
│   ├── 广东省博物馆数据/     # 图谱原始数据
│   └── NEO4J_README.md     # 图库详细文档
└── RAG/                    # RAG 子项目（uv 管理，可编辑安装）
    ├── src/museum_rag/     # 检索/嵌入/存储
    ├── data/               # 向量库、缓存、评测集
    └── README.md           # RAG 详细文档
```

## 快速开始

### 环境要求

- Python 3.12+
- Neo4j（本地 Neo4j Desktop 或远程实例，需已导入数据）
- Qdrant 向量库（本地文件库默认，或托管服务）
- DashScope 嵌入服务 + DeepSeek LLM 的密钥

### 安装依赖

```bash
pip install -r requirements.txt
pip install -e RAG          # RAG 子项目（勿装 whl，会读不到配置）
```

### 配置环境变量

```bash
cp .env.example .env        # 填入 DEEPSEEK_KEY、NEO4J_*、CORS_ORIGINS
cp RAG/.env.example RAG/.env  # 填入 DASHSCOPE_API_KEY 等（若不存在）
```

所有配置均可通过环境变量注入，本地 `.env` 不覆盖已存在的进程环境变量，方便云端部署。

### 数据导入（仅首次）

**Neo4j 图谱**（需先在 Neo4j 建库、记下密码）：

```bash
cd Neo4j && python import_to_neo4j.py
```

**RAG 向量库**（数据已交付时可跳过）：

```bash
cd RAG && museum-rag normalize && museum-rag chunk && museum-rag index
```

### 启动

```bash
uvicorn main:app --reload
```

启动时 lifespan 会连接 Neo4j 并 `verify()`（连不上则 fail-fast 拒绝启动）。访问 `http://127.0.0.1:8000/docs` 查看 Swagger。

## API

`POST /chat`，请求：

```json
{ "query": "端砚是什么年代的？" }
```

响应：

```json
{
  "query": "端砚是什么年代的？",
  "status": "success",
  "answer": "端砚是宋代的……",
  "reasoning_steps": [
    { "step": 1, "tool_used": "intent_parser", "action_input": "端砚是什么年代的？", "observation": "识别意图=museum_query, 实体=端砚, 类型=artifact" },
    { "step": 2, "tool_used": "graph_retrieval (Neo4j)", "action_input": "端砚", "observation": "图谱命中[artifact]: 端砚" }
  ],
  "citations": [
    { "source_type": "graph", "content": "端砚 | 宋代 | 石 | 长18.5cm | 文房四宝之首……" },
    { "source_type": "vector", "content": "端砚背景故事……" }
  ]
}
```

- `reasoning_steps`：完整思考链（意图 → 各检索节点 → 生成）。
- `citations`：`source_type` 为 `graph` / `vector` / `facility`。

> 鉴权：若已配置 `API_ACCESS_KEYS`，请求需带 `X-API-Key` 请求头，否则返回 401。

## 测试

```bash
pytest                      # 59 个快速单测（节点/分词/BM25 召回/楼层解析，不打外网）
pytest -m integration       # 5 个端到端用例（需全栈在线）
```

> 注意：Qdrant 本地库有独占文件锁，跑集成测试前先停掉开发服务器（否则报 `Storage folder already accessed`）。

## 部署

代码侧已就绪，剩余为环境侧事项：

- **Neo4j / Qdrant 托管**：`NEO4J_URI/USER/PASSWORD` 与 `QDRANT_MODE/URL` 环境变量已支持远程；迁移数据与向量索引。
- **密钥注入**：`DEEPSEEK_KEY`、`DASHSCOPE_*` 走平台环境变量，`.env` 与密钥绝不进镜像/仓库。
- **访问鉴权**：设置 `API_ACCESS_KEYS`（逗号分隔）后 `/chat` 要求请求头 `X-API-Key` 匹配，防第三方消耗付费 token；留空则仅限本地开发。
- **限流与探活**：`/health` 供 Docker HEALTHCHECK / 负载均衡探测；`RATE_LIMIT_MAX`、`RATE_LIMIT_WINDOW_SECONDS` 控制 `/chat` 按客户端 IP 滑动窗口限流；`TRUST_PROXY_XFF=1` 仅在后端置于可信反代之后开启（否则该头可被伪造绕过限流）。
- **CORS**：`CORS_ORIGINS` 逗号分隔配置前端域名，`*` 时自动关闭 credentials。
- **Windows 兼容**：`sys.stdout.reconfigure` 仅在 win32 生效，Linux 无影响。

## 参考文档

- [Neo4j 图数据库文档](Neo4j/NEO4J_README.md) — 图模型、MuseumGraph 接口、数据导入
- [RAG 检索模块文档](RAG/README.md) — 文档构建、向量索引、评测
