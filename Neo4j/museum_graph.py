"""
博物馆 Neo4j 图数据库查询接口（异步版）
供 FastAPI 后端直接调用

用法（FastAPI lifespan）:
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from museum_graph import MuseumGraph

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        graph = MuseumGraph()
        app.state.graph = graph
        yield
        await graph.close()

    app = FastAPI(lifespan=lifespan)

    @app.get("/api/artifacts")
    async def search(era: str):
        return await app.state.graph.search_by_era(era)

环境变量:
    NEO4J_URI      默认 bolt://localhost:7687
    NEO4J_USER     默认 neo4j
    NEO4J_PASSWORD 必填（无默认值，缺失直接报错）
    NEO4J_DATABASE 默认 neo4j
"""
import os
from neo4j import AsyncGraphDatabase, RoutingControl
from neo4j.exceptions import Neo4jError
from typing import Optional


# 设施俗称 → 正式名称 映射（搜俗称时同时匹配正式名）
_FACILITY_ALIASES: dict[str, list[str]] = {
    "咖啡": ["餐饮服务", "咖啡厅"],
    "厕所": ["卫生间", "洗手间"],
    "洗手间": ["卫生间"],
    "卫生间": ["洗手间"],
    "文创": ["购物服务", "纪念品商店"],
    "商店": ["购物服务"],
    "行李": ["寄存服务"],
    "寄存": ["寄存服务"],
    "轮椅": ["便民轮椅"],
    "婴儿车": ["婴儿车"],
    "充电宝": ["充电宝"],
    "wifi": ["无线网络"],
    "无线网": ["无线网络"],
    "医务": ["医疗救助"],
    "母婴": ["母婴室"],
}


class MuseumGraph:
    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        database: str = None,
    ):
        self._uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.environ.get("NEO4J_USER", "neo4j")
        self._password = password or os.environ.get("NEO4J_PASSWORD")
        if not self._password:
            raise ValueError("缺少 NEO4J_PASSWORD 环境变量，请先配置")
        self._database = database or os.environ.get("NEO4J_DATABASE", "neo4j")

        self.driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )

    async def verify(self):
        """启动时调用一次，验证数据库连通性"""
        await self.driver.verify_connectivity()

    async def close(self):
        await self.driver.close()

    async def __aenter__(self):
        await self.verify()
        return self

    async def __aexit__(self, *args):
        await self.close()

    def _db(self):
        """快捷取 database 名"""
        return self._database

    # ── 展品查询 ──────────────────────────────────────

    async def search_by_era(self, era: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """按朝代查询展品（优先匹配标准化 era，模糊匹配原始 era）"""
        limit = max(0, limit)
        offset = max(0, offset)
        query = """
        MATCH (a:Artifact)-[:BELONGS_TO]->(e:Era)
        WHERE e.name = $era OR e.name CONTAINS $era
        RETURN a.name AS name, a.era AS era, a.category AS category,
               a.texture AS texture, a.introduction AS intro
        ORDER BY a.name
        SKIP $offset LIMIT $limit
        """
        records, _, _ = await self.driver.execute_query(
            query, era=era, limit=limit, offset=offset,
            database_=self._db(), routing_=RoutingControl.READ,
        )
        return [dict(r) for r in records]

    async def search_by_category(self, category: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """按类别查询展品"""
        limit = max(0, limit)
        offset = max(0, offset)
        query = """
        MATCH (a:Artifact)-[:HAS_CATEGORY]->(c:Category {name: $category})
        RETURN a.name AS name, a.era AS era, a.texture AS texture,
               a.introduction AS intro
        ORDER BY a.name
        SKIP $offset LIMIT $limit
        """
        records, _, _ = await self.driver.execute_query(
            query, category=category, limit=limit, offset=offset,
            database_=self._db(), routing_=RoutingControl.READ,
        )
        return [dict(r) for r in records]

    async def search_by_material(self, material: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """按材质查询展品（如"瓷""纸""木"）"""
        limit = max(0, limit)
        offset = max(0, offset)
        query = """
        MATCH (a:Artifact)-[:MADE_OF]->(m:Material {name: $material})
        RETURN a.name AS name, a.era AS era, a.category AS category
        ORDER BY a.name
        SKIP $offset LIMIT $limit
        """
        records, _, _ = await self.driver.execute_query(
            query, material=material, limit=limit, offset=offset,
            database_=self._db(), routing_=RoutingControl.READ,
        )
        return [dict(r) for r in records]

    async def get_artifact_context(self, name: str) -> Optional[dict]:
        """查单个展品完整信息 + 所有关联"""
        query = """
        MATCH (a:Artifact {name: $name})
        OPTIONAL MATCH (a)-[:BELONGS_TO]->(e:Era)
        OPTIONAL MATCH (a)-[:HAS_CATEGORY]->(c:Category)
        OPTIONAL MATCH (a)-[:MADE_OF]->(m:Material)
        RETURN a.name AS name, a.era AS era, a.category AS category,
               a.texture AS texture, a.size AS size,
               a.introduction AS introduction,
               e.name AS era_name, c.name AS category_name,
               m.name AS material_name
        """
        record = await self.driver.execute_query(
            query, name=name,
            database_=self._db(), routing_=RoutingControl.READ,
            result_transformer_=lambda r: r.single(strict=False),
        )
        return dict(record) if record else None

    async def get_related_artifacts(self, name: str, limit: int = 10) -> list[dict]:
        """查关联展品（同类别、同朝代）"""
        query = """
        MATCH (a:Artifact {name: $name})
        OPTIONAL MATCH (a)-[:HAS_CATEGORY]->(c:Category)<-[:HAS_CATEGORY]-(by_cat:Artifact)
        WHERE by_cat.name <> $name
        OPTIONAL MATCH (a)-[:BELONGS_TO]->(e:Era)<-[:BELONGS_TO]-(by_era:Artifact)
        WHERE by_era.name <> $name
        WITH [x IN collect(DISTINCT by_cat) WHERE x IS NOT NULL] AS cats,
             [x IN collect(DISTINCT by_era) WHERE x IS NOT NULL] AS eras
        UNWIND (cats + eras) AS related
        RETURN DISTINCT related.name AS name, related.era AS era,
               CASE WHEN related IN cats THEN '同类别' ELSE '同朝代' END AS relation
        LIMIT $limit
        """
        records, _, _ = await self.driver.execute_query(
            query, name=name, limit=limit,
            database_=self._db(), routing_=RoutingControl.READ,
        )
        return [dict(r) for r in records]

    async def fulltext_search_artifact(self, keyword: str, limit: int = 10) -> list[dict]:
        """全文搜索展品；索引不可用时回退到 CONTAINS 模糊匹配"""
        try:
            query = """
            CALL db.index.fulltext.queryNodes("artifact_search", $keyword)
            YIELD node, score
            WHERE score > 0.5
            RETURN node.name AS name, node.era AS era,
                   node.category AS category, node.introduction AS intro,
                   score
            ORDER BY score DESC
            LIMIT $limit
            """
            records, _, _ = await self.driver.execute_query(
                query, keyword=keyword, limit=limit,
                database_=self._db(), routing_=RoutingControl.READ,
            )
            results = [dict(r) for r in records]
            if results:
                return results
        except Neo4jError as e:
            # 仅索引不存在时回退；其他错误（连接/语法）直接抛出
            err = str(e).lower()
            if "no such fulltext" not in err and "index does not exist" not in err:
                raise

        # 回退：CONTAINS 模糊匹配
        fallback = """
        MATCH (a:Artifact)
        WHERE a.name CONTAINS $keyword
           OR (a.introduction IS NOT NULL AND a.introduction CONTAINS $keyword)
        RETURN a.name AS name, a.era AS era, a.category AS category,
               a.introduction AS intro
        LIMIT $limit
        """
        records, _, _ = await self.driver.execute_query(
            fallback, keyword=keyword, limit=limit,
            database_=self._db(), routing_=RoutingControl.READ,
        )
        return [dict(r) for r in records]

    # ── 展览查询 ──────────────────────────────────────

    async def get_exhibitions(self, state: Optional[str] = None,
                              limit: int = 50, offset: int = 0) -> list[dict]:
        """获取展览列表，可筛选 state: current/permanent/review"""
        limit = max(0, limit)
        offset = max(0, offset)
        if state:
            query = """
            MATCH (ex:Exhibition {state: $state})
            RETURN ex.title AS title, ex.state AS state,
                   left(ex.introduction, 200) AS brief
            ORDER BY ex.title
            SKIP $offset LIMIT $limit
            """
            records, _, _ = await self.driver.execute_query(
                query, state=state, limit=limit, offset=offset,
                database_=self._db(), routing_=RoutingControl.READ,
            )
        else:
            query = """
            MATCH (ex:Exhibition)
            RETURN ex.title AS title, ex.state AS state,
                   left(ex.introduction, 200) AS brief
            ORDER BY ex.title
            SKIP $offset LIMIT $limit
            """
            records, _, _ = await self.driver.execute_query(
                query, limit=limit, offset=offset,
                database_=self._db(), routing_=RoutingControl.READ,
            )
        return [dict(r) for r in records]

    async def fulltext_search_exhibition(self, keyword: str, limit: int = 5) -> list[dict]:
        """全文搜索展览内容；索引不可用时回退到 CONTAINS"""
        try:
            query = """
            CALL db.index.fulltext.queryNodes("exhibition_search", $keyword)
            YIELD node, score
            RETURN node.title AS title, node.state AS state, score
            ORDER BY score DESC
            LIMIT $limit
            """
            records, _, _ = await self.driver.execute_query(
                query, keyword=keyword, limit=limit,
                database_=self._db(), routing_=RoutingControl.READ,
            )
            results = [dict(r) for r in records]
            if results:
                return results
        except Neo4jError as e:
            err = str(e).lower()
            if "no such fulltext" not in err and "index does not exist" not in err:
                raise

        # 回退
        fallback = """
        MATCH (ex:Exhibition)
        WHERE ex.title CONTAINS $keyword
           OR ex.introduction CONTAINS $keyword
        RETURN ex.title AS title, ex.state AS state
        LIMIT $limit
        """
        records, _, _ = await self.driver.execute_query(
            fallback, keyword=keyword, limit=limit,
            database_=self._db(), routing_=RoutingControl.READ,
        )
        return [dict(r) for r in records]

    # ── 设施查询 ──────────────────────────────────────

    async def get_facility(self, keyword: str, limit: int = 5) -> list[dict]:
        """
        查设施信息，支持俗称别名（如"咖啡"→"餐饮服务"）。
        返回所有匹配的设施列表（男/女/无障碍卫生间都会返回）。
        """
        limit = max(0, limit)
        # 扩展关键词：原词 + 别名
        keywords = [keyword]
        for alias, targets in _FACILITY_ALIASES.items():
            if alias in keyword:
                keywords.extend(targets)

        query = """
        MATCH (f:Facility)
        WHERE any(kw IN $keywords WHERE f.name CONTAINS kw)
        RETURN f.name AS name, f.location AS location,
               f.information AS info
        LIMIT $limit
        """
        records, _, _ = await self.driver.execute_query(
            query, keywords=keywords, limit=limit,
            database_=self._db(), routing_=RoutingControl.READ,
        )
        return [dict(r) for r in records]

    async def list_facilities(self) -> list[dict]:
        """列出所有设施"""
        query = """
        MATCH (f:Facility)
        RETURN f.name AS name, f.location AS location
        ORDER BY f.name
        """
        records, _, _ = await self.driver.execute_query(
            query, database_=self._db(), routing_=RoutingControl.READ,
        )
        return [dict(r) for r in records]

    # ── 展厅查询 ──────────────────────────────────────

    async def get_hall(self, name: str) -> Optional[dict]:
        """查单个展厅信息"""
        query = """
        MATCH (h:Hall {name: $name})
        RETURN h.name AS name, h.location AS location,
               h.floor AS floor, h.information AS info
        """
        record = await self.driver.execute_query(
            query, name=name,
            database_=self._db(), routing_=RoutingControl.READ,
            result_transformer_=lambda r: r.single(strict=False),
        )
        return dict(record) if record else None

    async def list_halls(self, floor: float = None) -> list[dict]:
        """列出所有展厅，可按楼层筛选（floor=3 / 3.5 / 4）"""
        if floor is not None:
            query = """
            MATCH (h:Hall {floor: $floor})
            RETURN h.name AS name, h.location AS location,
                   h.floor AS floor, h.information AS info
            ORDER BY h.name
            """
            records, _, _ = await self.driver.execute_query(
                query, floor=floor,
                database_=self._db(), routing_=RoutingControl.READ,
            )
        else:
            query = """
            MATCH (h:Hall)
            RETURN h.name AS name, h.location AS location,
                   h.floor AS floor, h.information AS info
            ORDER BY h.floor, h.name
            """
            records, _, _ = await self.driver.execute_query(
                query, database_=self._db(), routing_=RoutingControl.READ,
            )
        return [dict(r) for r in records]

    async def get_exhibitions_in_hall(self, hall_name: str) -> list[dict]:
        """查某展厅内的所有展览"""
        query = """
        MATCH (ex:Exhibition)-[:LOCATED_AT]->(h:Hall {name: $hall_name})
        RETURN ex.title AS title, ex.state AS state,
               left(ex.introduction, 200) AS brief
        ORDER BY ex.state, ex.title
        """
        records, _, _ = await self.driver.execute_query(
            query, hall_name=hall_name,
            database_=self._db(), routing_=RoutingControl.READ,
        )
        return [dict(r) for r in records]

    async def get_hall_for_exhibition(self, exhibition_title: str) -> Optional[dict]:
        """查某展览在哪个展厅"""
        query = """
        MATCH (ex:Exhibition {title: $title})-[:LOCATED_AT]->(h:Hall)
        RETURN h.name AS hall_name, h.location AS location, h.floor AS floor
        """
        record = await self.driver.execute_query(
            query, title=exhibition_title,
            database_=self._db(), routing_=RoutingControl.READ,
            result_transformer_=lambda r: r.single(strict=False),
        )
        return dict(record) if record else None

    # ── 统计查询 ──────────────────────────────────────

    async def get_stats(self) -> dict:
        """获取数据库统计信息（空库安全）"""
        query = """
        OPTIONAL MATCH (a:Artifact)  WITH count(a) AS artifact_count
        OPTIONAL MATCH (e:Era)       WITH artifact_count, count(e) AS era_count
        OPTIONAL MATCH (c:Category)  WITH artifact_count, era_count, count(c) AS category_count
        OPTIONAL MATCH (m:Material)  WITH artifact_count, era_count, category_count, count(m) AS material_count
        OPTIONAL MATCH (h:Hall)      WITH artifact_count, era_count, category_count, material_count, count(h) AS hall_count
        OPTIONAL MATCH (f:Facility)  RETURN artifact_count, era_count, category_count, material_count, hall_count, count(f) AS facility_count
        """
        record = await self.driver.execute_query(
            query, database_=self._db(), routing_=RoutingControl.READ,
            result_transformer_=lambda r: r.single(strict=False),
        )
        return dict(record) if record else {
            "artifact_count": 0, "era_count": 0,
            "category_count": 0, "material_count": 0,
            "hall_count": 0, "facility_count": 0,
        }
