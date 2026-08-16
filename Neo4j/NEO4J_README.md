# Neo4j 图数据库 — 项目文档

> 广东省博物馆 AI 讲解系统 · 具身智能数据实验室暑期项目

---

## 一、数据清单

### 已入库的数据文件

| 文件 | 来源 | 规模 | 用途 |
|---|---|---|---|
| `藏品库.json` | 广东省博物馆官网 | 3730 条 | 展品主数据 → `Artifact` 节点 |
| `展览.json` | 广东省博物馆官网 | 78 条 | 当前/常设/回顾展 → `Exhibition` 节点 |
| `设施信息.json` | 广东省博物馆官网 | 20 条 | 洗手间/母婴室/咖啡厅 → `Facility` 节点 |
| `展厅.json` | 广东省博物馆官网 | 8 条 | 展厅物理空间 → `Hall` 节点 |

### 未入库的数据文件（由 RAG 组处理）

| 文件 | 内容 | 去向 |
|---|---|---|
| `藏品总目.json` | ~17 万条简化索引（仅 id/name/category/era） | RAG 组可选导入 |
| `基本信息.json` | 博物馆简介 + 大事记 | RAG 组向量库 |
| `参观信息.json` | 开放时间/预约/交通/导览 | RAG 组向量库 |

### 数据质量概况

| 字段 | 非空率 | 说明 |
|---|---|---|
| `name` | 100% | 3,730 条，2978 个唯一名（380 组重名） |
| `era` | 99% (37 null) | **287 个不同值**，格式不统一（`"清康熙三十二年"` vs `"清代"` vs `"18世纪"`） |
| `category` | 86% (518 null) | 38 个类别（`"瓷器"` `"书法、绘画"` `"家具"` 等） |
| `texture` | 70% (1121 null) | 材质字段（`"瓷"` `"纸"` `"木"` 等） |
| `introduction` | **0.1%** (4 条非空) | 绝大多数展品无介绍文本 |
| `source` | 98% (60 null) | 录入来源 |

---

## 二、图数据模型

### ER 图

```
┌──────────┐       ┌──────────┐       ┌──────────┐
│   Era    │       │ Category │       │ Material │
│  朝代    │       │  类别    │       │  材质    │
└────┬─────┘       └────┬─────┘       └────┬─────┘
     │ BELONGS_TO       │ HAS_CATEGORY     │ MADE_OF
     ▼                  ▼                  ▼
┌──────────────────────────────────────────────────┐
│                   Artifact 展品                   │
│  {name, era, category, texture, size, intro}     │
└──────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐
│  Exhibition  │     │   Facility   │
│  展览        │     │  设施        │
│  {title,     │     │  {name,      │
│   state,     │     │   location,  │
│   intro}     │     │   info}      │
└──────┬───────┘     └──────────────┘
       │ LOCATED_AT
       ▼
┌──────────────┐     ┌──────────────┐
│     Hall     │────▶│     Hall     │
│   展厅       │     │  子展厅      │
│  {name,      │     │  {name,      │
│   location,  │     │   location,  │
│   floor}     │     │   floor}     │
└──────────────┘     └──────────────┘
```

### 展厅与展览的关系

展厅（Hall）是**物理空间**，展览（Exhibition）是**内容事件**。系统通过 `LOCATED_AT` 关系将展览关联到对应展厅：

| 展厅 (Hall) | 关联展览 (Exhibition) |
|---|---|
| 广东历史文化展厅 | 【常设展览】广东历史文化陈列 |
| 广东自然资源展厅 | 【常设展览】粤山秀水 丰物岭南——广东省自然资源展览 |
| 潮州木雕展厅 | 【常设展览】漆木精华——潮州木雕艺术展览 |
| 端砚展厅 | 【常设展览】紫石凝英——端砚艺术展览 + 众乐之乐——何崇甘捐赠九晕太极端砚展 |
| 陶瓷展厅 | 【常设展览】土火之艺——馆藏历代陶瓷展览 |

### 约束与索引

```cypher
-- 唯一约束
CREATE CONSTRAINT artifact_name  IF NOT EXISTS FOR (a:Artifact) REQUIRE a.name IS UNIQUE
CREATE CONSTRAINT era_name       IF NOT EXISTS FOR (e:Era)      REQUIRE e.name IS UNIQUE
CREATE CONSTRAINT category_name  IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE
CREATE CONSTRAINT material_name  IF NOT EXISTS FOR (m:Material) REQUIRE m.name IS UNIQUE

-- 全文索引（Lucene）
CREATE FULLTEXT INDEX artifact_search   IF NOT EXISTS FOR (a:Artifact)  ON EACH [a.name, a.introduction]
CREATE FULLTEXT INDEX exhibition_search IF NOT EXISTS FOR (ex:Exhibition) ON EACH [ex.title, ex.introduction]
```

---

## 三、Python 接口约定

### 文件结构

```
 ...\具身智能实验室\
├── import_to_neo4j.py    # 数据导入脚本（一次性运行）
├── museum_graph.py       # 查询接口类（供 FastAPI 调用）
└── NEO4J_README.md       # 本文档
```

### MuseumGraph 方法签名

**FastAPI 集成示例（lifespan 模式）：**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from museum_graph import MuseumGraph

@asynccontextmanager
async def lifespan(app: FastAPI):
    graph = MuseumGraph()
    await graph.verify()          # 启动时检查连通性
    app.state.graph = graph
    yield
    await graph.close()           # 关闭时释放连接池

app = FastAPI(lifespan=lifespan)

@app.get("/api/artifacts")
async def search_era(request: Request, era: str):
    return await request.app.state.graph.search_by_era(era)
```

**所有方法均为 async，调用时需加 `await`：**

```python
from museum_graph import MuseumGraph

async with MuseumGraph() as graph:
    # ═══ 展品查询 ═══
    await graph.search_by_era("明", limit=20)              # → list[dict]
    await graph.search_by_category("瓷器", limit=20)        # → list[dict]
    await graph.search_by_material("瓷", limit=20)          # → list[dict]
    await graph.get_artifact_context("青花海水龙纹瓶")       # → dict | None
    await graph.get_related_artifacts("青花海水龙纹瓶")      # → list[dict]
    await graph.fulltext_search_artifact("青花", limit=10)  # → list[dict]

    # ═══ 展览查询 ═══
    await graph.get_exhibitions(state="current")            # → list[dict]
    await graph.fulltext_search_exhibition("文艺复兴")       # → list[dict]

    # ═══ 设施查询（支持俗称别名，如"咖啡"→"餐饮服务"） ═══
    await graph.get_facility("咖啡")                        # → list[dict]  支持别名
    await graph.get_facility("卫生间")                      # → list[dict]  返回全部匹配
    await graph.list_facilities()                           # → list[dict]

    # ═══ 展厅查询 ═══
    await graph.get_hall("端砚展厅")                        # → dict | None
    await graph.list_halls()                                # → list[dict]
    await graph.list_halls(floor=3)                         # → list[dict]
    await graph.get_exhibitions_in_hall("端砚展厅")          # → list[dict]
    await graph.get_hall_for_exhibition("...展览名")          # → dict | None

    # ═══ 统计 ═══
    await graph.get_stats()                                 # → dict
```

### 返回数据格式示例

```python
# search_by_era("清") 返回:
[{
    "name": "清乾隆广彩十三行通景图大碗",
    "era": "清乾隆",
    "category": "瓷器",
    "texture": "瓷",
    "intro": None          # 可能是 null
}, ...]

# get_facility("卫生间") 返回:
[{
    "name": "男卫生间",
    "location": ["一楼西门通道", ...],  # ⚠ 列表类型
    "info": None
}, {
    "name": "女卫生间",
    ...
}]

# get_artifact_context 返回:
{
    "name": "...",
    "era": "...",
    "category": "...",
    "texture": "...",
    "size": "...",
    "introduction": "...",
    "era_name": "...",        # Era 节点名（与 era 字段相同）
    "category_name": "...",
    "material_name": "..."
}
```

---

## 四、环境部署

### Neo4j Desktop 2.x

| 配置项 | 值 |
|---|---|
| 版本 | Neo4j Desktop 2.2.1+ |
| DBMS 版本 | 2026.06.0 |
| 连接地址 | `bolt://localhost:7687` |
| 用户名 | `neo4j`（不可修改） |
| 密码 | 由环境变量 `NEO4J_PASSWORD` 注入（绝不写死） |
| 默认数据库 | `neo4j` |

### Python 环境

| 依赖 | 版本 |
|---|---|
| Python | 3.12.10 |
| neo4j (driver) | 6.2.0 |

### 数据导入命令

```powershell
cd "E:\具身智能实验室"
python import_to_neo4j.py
```

