# 广东省博物馆讲解 AI 助手「粤博智游」

面向游客的智能讲解与馆务问答系统：游客用自然语言提问，系统结合**知识图谱客观事实**与**向量检索背景故事**，由大语言模型生成通俗、生动、带引用溯源的回答。已部署云端，在线可体验。

## 在线体验 Demo

本项目已部署至阿里云，提供在线可体验的完整系统：游客端对话界面（Streamlit）+ API 交互调试（Swagger）。

> **Demo 链接随提交邮件一并提供，不在公开仓库展示。** 线上问答会调用付费大模型服务，公开放出链接易被扫描/滥用消耗 token。如需体验，请使用提交邮件中的链接，或按下方「快速开始」本地运行。

## 核心功能

- **混合检索问答**：图查询（Neo4j）提供朝代 / 材质 / 尺寸等客观事实，向量检索（Qdrant + DashScope）提供背景故事，LLM 统一组装成游客可读的回答。
- **意图分流**：自动识别 闲聊（chitchat）/ 馆务（facility）/ 内容问答（museum_query）三类意图并路由到对应处理节点。
- **馆务问答**：BM25 中文 2-gram 检索命中 FAQ（洗手间、开放时间、导览等），严格基于资料回答、不捏造。
- **引用溯源**：回答附带 `citations`（graph / vector / facility），游客可查看"这句话来自哪件藏品 / 哪份馆务资料"。
- **楼层导览**：`三楼有什么展厅` 等按楼层列出展厅。
- **多轮聊天前端**：Streamlit 界面，欢迎卡、推荐问题、流式回答、清空对话。

## 技术架构

LangGraph 状态机（6 个节点）：

```
START → intent_parser_node
           ├─ chitchat  → chitchat_node          → END
           ├─ facility  → facility_node           → END（BM25 检 FAQ）
           └─ museum_query → graph_retrieval_node → vector_retrieval_node → generate_answer_node → END
```

**技术栈**：FastAPI · LangGraph · Neo4j 知识图谱 · Qdrant 向量库 · DashScope Embedding · DeepSeek LLM · Streamlit · Docker Compose

- `intent_parser_node`：DeepSeek 识别意图与实体（artifact / exhibition / hall / floor）。
- `graph_retrieval_node`：从 Neo4j 取结构化客观事实；兜底命中要求名字含关键字，防止简介蹭中（如"端砚"误命中"端石琴石砚"）。
- `vector_retrieval_node`：RAG 混合检索取背景故事。
- `generate_answer_node`：LLM 综合"图谱事实 + 向量故事"生成回答；推荐类问题引导介绍馆藏经典；明确禁止以"去服务台咨询"敷衍收尾。

回答质量经过多轮打磨：防幻觉（严格基于资料）、防甩锅（位置信息直接给出）、防冷门（推荐锚定镇馆藏品）、防重影（前端渲染修复）。

## 目录结构

```
├── main.py                 # FastAPI + LangGraph 后端（唯一入口）
├── frontend/               # Streamlit 前端「粤博智游」
│   ├── app.py              # 页面入口
│   └── components/         # 聊天状态 / API 客户端 / UI 组件
├── faq_builder.py          # FAQ JSON → Markdown（BM25 索引源）
├── Dockerfile              # 后端生产镜像（Gunicorn + Uvicorn worker，非 root）
├── docker-compose.yml      # 一键编排 app + neo4j + qdrant + frontend
├── DEPLOY.md               # 云端部署手册
├── requirements.txt        # 根项目运行时依赖
├── tests/                  # 单测（节点/分词/BM25/楼层）+ 集成
├── Neo4j/                  # 图谱查询接口与原始数据
└── RAG/                    # 检索/嵌入/向量存储子项目
```

## 快速开始（本地运行）

### 环境要求

Python 3.12+、Neo4j（已导入数据）、Qdrant、DashScope + DeepSeek 密钥。

### 安装与配置

```bash
pip install -r requirements.txt
pip install -e RAG                    # RAG 子项目（勿装 whl，会读不到配置）

cp .env.example .env                  # 填 DEEPSEEK_KEY、NEO4J_*、CORS_ORIGINS、API_ACCESS_KEYS
cp RAG/.env.example RAG/.env          # 填 DASHSCOPE_API_KEY
export API_KEY=你的密钥               # 前端本地运行需与后端 API_ACCESS_KEYS 一致
```

### 首次数据导入

```bash
cd Neo4j && python import_to_neo4j.py                     # 构建图谱
cd RAG && museum-rag normalize && museum-rag chunk && museum-rag index   # 构建向量库
```

### 启动

```bash
uvicorn main:app --reload             # 后端 http://127.0.0.1:8000/docs
streamlit run frontend/app.py         # 前端 http://127.0.0.1:8501
```

## API

`POST /chat`（若配置了 `API_ACCESS_KEYS`，请求需带 `X-API-Key` 请求头）：

```json
{ "query": "端砚是什么年代的？" }
```

响应：

```json
{
  "query": "端砚是什么年代的？",
  "status": "success",
  "answer": "端砚从唐代起即为贡品……",
  "reasoning_steps": [
    { "step": 1, "tool_used": "intent_parser", "action_input": "端砚是什么年代的？", "observation": "识别意图=museum_query, 实体=端砚, 类型=artifact" }
  ],
  "citations": [
    { "source_type": "graph", "content": "端石琴石砚 | 清同治至光绪 | 石 | ……" },
    { "source_type": "vector", "content": "宋端石太史砚 | ……" }
  ]
}
```

- `answer`：最终回答（前端主展示字段）。
- `citations`：引用溯源，`source_type` 为 `graph`（图谱事实）/ `vector`（背景故事）/ `facility`（馆务）。
- `reasoning_steps`：完整思考链（意图 → 各检索节点 → 生成），一般调试用。

## 测试

```bash
pytest                      # 68 个快速单测（节点/分词/BM25/楼层，不打外网）
pytest -m integration       # 端到端用例（需全栈在线）
```

## 部署

一键 Docker 编排（`app` + `neo4j` + `qdrant` + `frontend`）：

```bash
cp .env.example .env        # 填 DEEPSEEK_KEY / NEO4J_PASSWORD / DASHSCOPE_* / API_ACCESS_KEYS / API_KEY
docker compose up -d --build
```

首次数据初始化（仅一次）：
```bash
docker compose run --rm --user 0 app python Neo4j/import_to_neo4j.py
docker compose run --rm --user 0 app sh -c "museum-rag normalize && museum-rag chunk && museum-rag index"
```

详细步骤（阿里云、防火墙、数据迁移、安全收敛）见 [`DEPLOY.md`](DEPLOY.md)。

## 团队

谢恩泽 · 吴弘翔 · 王智勇 · 雷仕鹏 · 陈宣乐

## 参考文档

- [Neo4j 图数据库文档](Neo4j/NEO4J_README.md) — 图模型、MuseumGraph 接口、数据导入
- [RAG 检索模块文档](RAG/README.md) — 文档构建、向量索引、评测
- [云端部署手册](DEPLOY.md) — 阿里云单机 Docker 部署
