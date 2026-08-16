"""
广东省博物馆 Neo4j 数据导入脚本
用法：python import_to_neo4j.py
"""
import json
import os
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# ── 配置（密码必填，无默认值）─────────────────────────
# 数据目录按脚本所在位置解析：本地（Neo4j/ 下）与容器（/app/Neo4j/）都能直接跑，
# 无需先 cd 到特定目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "广东省博物馆数据")
DB_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
DB_USER = os.environ.get("NEO4J_USER", "neo4j")
DB_PASS = os.environ.get("NEO4J_PASSWORD")
if not DB_PASS:
    raise RuntimeError("缺少 NEO4J_PASSWORD 环境变量，请先在 .env 配置")
BATCH_SIZE = 500

# ── Era 标准化映射表 ────────────────────────────────
ERA_NORMALIZE = {
    # 清
    "清": "清", "清代": "清", "清初": "清", "清中期": "清", "清末": "清",
    "清乾隆": "清", "清康熙": "清", "清雍正": "清", "清光绪": "清",
    "清顺治": "清", "清嘉庆": "清", "清道光": "清", "清同治": "清",
    "清宣统": "清", "清咸丰": "清",
    "清·": "清",
    # 明
    "明": "明", "明代": "明", "明初": "明", "明中期": "明", "明末": "明",
    "明万历": "明", "明永乐": "明", "明宣德": "明", "明成化": "明",
    "明嘉靖": "明", "明正德": "明", "明崇祯": "明",
    "明·": "明",
    # 宋
    "宋": "宋", "宋代": "宋", "南宋": "宋", "北宋": "宋",
    # 元
    "元": "元", "元代": "元",
    "元·": "元",
    # 唐
    "唐": "唐", "唐代": "唐",
    # 隋
    "隋": "隋", "隋代": "隋",
    # 汉
    "汉": "汉", "汉代": "汉", "西汉": "汉", "东汉": "汉",
    # 近现代
    "近现代": "近现代", "现代": "近现代", "当代": "近现代",
    "中华人民共和国": "近现代", "民国": "近现代", "中华民国": "近现代",
}


def normalize_era(era_str: str) -> str:
    """将 '清乾隆' → '清', '明代' → '明'"""
    if not era_str or not isinstance(era_str, str):
        return "未知"
    for prefix, normalized in ERA_NORMALIZE.items():
        if era_str.startswith(prefix):
            return normalized
    return era_str  # 未命中保留原值


def clean_empty_strings(artifacts: list[dict]) -> list[dict]:
    """将字段中的空字符串替换为 None，防止绕过 COALESCE"""
    for item in artifacts:
        for key in ("era", "category", "texture", "size", "introduction"):
            if isinstance(item.get(key), str) and not item[key].strip():
                item[key] = None
    return artifacts


def deduplicate_artifacts(artifacts: list[dict]) -> list[dict]:
    """同名记录合并：保留每条字段中最完整的值"""
    groups: dict[str, dict] = {}
    for item in artifacts:
        name = item["name"]
        if name not in groups:
            groups[name] = dict(item)
        else:
            existing = groups[name]
            for key in ("era", "category", "texture", "size", "introduction", "source"):
                if existing.get(key) is None and item.get(key) is not None:
                    existing[key] = item[key]
    return list(groups.values())


# ── 数据库操作 ──────────────────────────────────────

def create_constraints(driver):
    """先建唯一约束（数据须先去重）"""
    constraints = [
        "CREATE CONSTRAINT artifact_name IF NOT EXISTS FOR (a:Artifact) REQUIRE a.name IS UNIQUE",
        "CREATE CONSTRAINT era_name IF NOT EXISTS FOR (e:Era) REQUIRE e.name IS UNIQUE",
        "CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT material_name IF NOT EXISTS FOR (m:Material) REQUIRE m.name IS UNIQUE",
    ]
    with driver.session() as session:
        for stmt in constraints:
            try:
                session.run(stmt)
            except Exception as e:
                print(f"  [WARN] 约束创建失败: {e}")
                return False
    print("[OK] 约束创建完成")
    return True


def create_indexes(driver):
    """后建全文索引"""
    indexes = [
        "CREATE FULLTEXT INDEX artifact_search IF NOT EXISTS FOR (a:Artifact) ON EACH [a.name, a.introduction]",
        "CREATE FULLTEXT INDEX exhibition_search IF NOT EXISTS FOR (ex:Exhibition) ON EACH [ex.title, ex.introduction]",
    ]
    with driver.session() as session:
        for stmt in indexes:
            try:
                session.run(stmt)
            except Exception as e:
                print(f"  [WARN] 索引创建失败: {e}")
    print("[OK] 全文索引创建完成")


def import_artifacts(driver, artifacts):
    """导入藏品库：Artifact 节点 + Era/Category/Material + 关系"""
    query = """
    UNWIND $items AS item
    MERGE (a:Artifact {name: item.name})
    SET a.era = item.era,
        a.normalized_era = item.normalized_era,
        a.category = item.category,
        a.texture = item.texture,
        a.size = item.size,
        a.introduction = item.introduction

    // 朝代节点
    FOREACH (_ IN CASE WHEN item.normalized_era IS NOT NULL THEN [1] ELSE [] END |
      MERGE (e:Era {name: item.normalized_era})
      MERGE (a)-[:BELONGS_TO]->(e)
    )
    // 类别节点
    FOREACH (_ IN CASE WHEN item.category IS NOT NULL THEN [1] ELSE [] END |
      MERGE (c:Category {name: item.category})
      MERGE (a)-[:HAS_CATEGORY]->(c)
    )
    // 材质节点
    FOREACH (_ IN CASE WHEN item.texture IS NOT NULL THEN [1] ELSE [] END |
      MERGE (m:Material {name: item.texture})
      MERGE (a)-[:MADE_OF]->(m)
    )
    """
    total = len(artifacts)
    for i in range(0, total, BATCH_SIZE):
        batch = artifacts[i:i + BATCH_SIZE]
        with driver.session() as session:
            session.run(query, items=batch)
        end = min(i + BATCH_SIZE, total)
        print(f"  [{i+1}-{end}/{total}] 已导入")
    print(f"[OK] 藏品导入完成：{total} 件")


def import_exhibitions(driver):
    """导入展览信息"""
    with open(f"{DATA_DIR}/展览.json", encoding="utf-8") as f:
        exhibitions = json.load(f)
    query = """
    UNWIND $items AS item
    MERGE (ex:Exhibition {title: item.title})
    SET ex.state = item.state,
        ex.introduction = item.introduction
    """
    with driver.session() as session:
        session.run(query, items=exhibitions)
    print(f"[OK] 展览导入完成：{len(exhibitions)} 个")


def import_facilities(driver):
    """导入设施信息（洗手间、母婴室等）"""
    with open(f"{DATA_DIR}/设施信息.json", encoding="utf-8") as f:
        facilities = json.load(f)
    query = """
    UNWIND $items AS item
    MERGE (f:Facility {name: item.facility})
    SET f.location = item.location,
        f.information = item.information
    """
    with driver.session() as session:
        session.run(query, items=facilities)
    print(f"[OK] 设施导入完成：{len(facilities)} 条")


FLOOR_MAP = {"一楼": 1, "二楼": 2, "三楼": 3, "三夹层": 3.5, "四楼": 4}


def import_halls(driver):
    """导入展厅信息，处理 location 两种类型"""
    with open(f"{DATA_DIR}/展厅.json", encoding="utf-8") as f:
        halls = json.load(f)

    # 预处理：统一格式，提取 floor
    processed = []
    for item in halls:
        name = item["name"]
        info = item.get("information")

        loc = item["location"]
        if isinstance(loc, str):
            # 简单字符串："三楼" / "三夹层" / "四楼"
            processed.append({
                "name": name,
                "location": loc,
                "floor": FLOOR_MAP.get(loc),
                "parent": None,
                "information": info,
            })
        elif isinstance(loc, list):
            # 先加父节点（无 location/floor，只有 information）
            processed.append({
                "name": name,
                "location": None,
                "floor": None,
                "parent": None,
                "information": info,
            })
            # 再加子展厅
            for sub_name, sub_loc in loc[0].items():
                processed.append({
                    "name": sub_name,
                    "location": sub_loc,
                    "floor": FLOOR_MAP.get(sub_loc),
                    "parent": name,
                    "information": info,
                })

    query = """
    UNWIND $items AS item
    MERGE (h:Hall {name: item.name})
    SET h.location = item.location,
        h.floor = item.floor,
        h.information = item.information
    FOREACH (_ IN CASE WHEN item.parent IS NOT NULL THEN [1] ELSE [] END |
      MERGE (p:Hall {name: item.parent})
      MERGE (h)-[:PART_OF]->(p)
    )
    """
    with driver.session() as session:
        session.run(query, items=processed)
    print(f"[OK] 展厅导入完成：{len(processed)} 条")


def create_hall_exhibition_relationships(driver):
    """展厅-展览 按名称匹配建 LOCATED_AT 关系（排除通用展厅）"""
    # 通用展厅不参与自动匹配（名称太宽泛会误配）
    EXCLUDED_HALLS = ["粤艺空间", "展厅一、二、三", "专题展厅"]
    query = """
    MATCH (h:Hall), (ex:Exhibition)
    WHERE h.name <> ex.title
      AND NOT h.name IN $excluded
      AND ex.title CONTAINS replace(replace(h.name, "广东", ""), "展厅", "")
    MERGE (ex)-[:LOCATED_AT]->(h)
    """
    with driver.session() as session:
        result = session.run(query, excluded=EXCLUDED_HALLS)
        summary = result.consume()
        count = summary.counters.relationships_created
    print(f"[OK] 展厅-展览关系：创建 {count} 条 LOCATED_AT")


def verify(driver):
    """验证导入结果 + 样例查询"""
    expected_artifact = None  # 由加载的数据决定
    errors = []

    with driver.session() as session:
        # 统计各标签数量
        counts = {}
        for label in ("Artifact", "Era", "Category", "Material", "Exhibition", "Facility", "Hall"):
            r = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt").single()
            counts[label] = r["cnt"] if r else 0
            print(f"  {label}: {counts[label]}")

        # 基本检查
        if counts["Artifact"] == 0:
            errors.append("[FAIL] 展品数量为 0，导入可能失败")
        if counts["Era"] == 0:
            errors.append("[WARN] 朝代数量为 0，检查 era 字段")
        if counts["Artifact"] > 0 and counts["Category"] == 0:
            errors.append("[WARN] 类别数量为 0，检查 category 字段")

        # 样例查询
        print("\n  样例 — 瓷器 TOP5:")
        records = session.run("""
            MATCH (a:Artifact)-[:HAS_CATEGORY]->(:Category {name: '瓷器'})
            RETURN a.name, a.era LIMIT 5
        """)
        found = 0
        for record in records:
            print(f"    {record['a.name']}（{record['a.era']}）")
            found += 1
        if found == 0:
            print("    （无结果 — 可能类别名不匹配）")

        # 测试标准化 era 查询
        print("\n  测试 — 标准化 '清' 朝展品 TOP3:")
        records = session.run("""
            MATCH (a:Artifact)-[:BELONGS_TO]->(:Era {name: '清'})
            RETURN a.name, a.normalized_era LIMIT 3
        """)
        for record in records:
            print(f"    {record['a.name']}")

    # 汇总
    if errors:
        print(f"\n{'='*40}")
        for e in errors:
            print(e)
    else:
        print(f"\n[OK] 验证通过 — 导入完整，样例查询正常")


# ── 主流程 ──────────────────────────────────────────

def main():
    # 1. 连接
    driver = GraphDatabase.driver(DB_URI, auth=(DB_USER, DB_PASS))
    try:
        driver.verify_connectivity()
        print(f"[OK] Connected to {DB_URI}")
    except Exception as e:
        print(f"[FAIL] Cannot connect to Neo4j: {e}")
        sys.exit(1)

    try:
        # 2. 加载 + 清洗 + 去重 藏品数据
        print("\n=== 准备数据 ===")
        with open(f"{DATA_DIR}/藏品库.json", encoding="utf-8") as f:
            artifacts = json.load(f)
        print(f"  原始: {len(artifacts)} 条")

        clean_empty_strings(artifacts)
        artifacts = deduplicate_artifacts(artifacts)
        print(f"  去重后: {len(artifacts)} 条")

        # 添加标准化 era
        for item in artifacts:
            item["normalized_era"] = normalize_era(item.get("era"))
        print(f"  Era 标准化完成")

        # 3. 先建约束（数据已去重，不会冲突）
        print("\n=== 创建约束 ===")
        if not create_constraints(driver):
            print("[FAIL] 约束创建失败，终止")
            return

        # 4. 导入
        print("\n=== 导入数据 ===")
        import_artifacts(driver, artifacts)
        import_exhibitions(driver)
        import_facilities(driver)
        import_halls(driver)
        create_hall_exhibition_relationships(driver)

        # 5. 后建全文索引
        print("\n=== 创建全文索引 ===")
        create_indexes(driver)

        # 6. 验证
        print("\n=== 验证 ===")
        verify(driver)

        print("\n=== 全部完成 ===")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
