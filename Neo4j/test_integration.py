"""
联调测试脚本（异步版）— 供 FastAPI 组验证 Neo4j 接口
运行：python test_integration.py
"""
import asyncio
from museum_graph import MuseumGraph


async def main():
    graph = MuseumGraph()
    await graph.verify()
    print("=== 1. 连接测试 ===")
    stats = await graph.get_stats()
    print(f"  数据库状态: {stats}")

    print("\n=== 2. 展品查询测试 ===")
    results = await graph.search_by_era("清")
    print(f"  搜'清'朝展品: {len(results)} 条")
    if results:
        print(f"  首条: {results[0]['name']}")

    print("\n=== 3. 单个展品上下文 ===")
    ctx = await graph.get_artifact_context("明万历青花平步青云图碗")
    if ctx:
        print(f"  {ctx['name']} | 朝代={ctx['era']} | 类别={ctx['category']}")

    print("\n=== 4. 关联展品 ===")
    related = await graph.get_related_artifacts("明万历青花平步青云图碗")
    print(f"  关联: {len(related)} 条")

    print("\n=== 5. 展厅查询 ===")
    halls = await graph.list_halls(floor=3)
    print(f"  三楼展厅: {[h['name'] for h in halls]}")
    ex_in_hall = await graph.get_exhibitions_in_hall("端砚展厅")
    print(f"  端砚展厅内展览: {len(ex_in_hall)} 个")

    print("\n=== 6. 设施查询（别名测试） ===")
    fac = await graph.get_facility("咖啡")
    print(f"  搜'咖啡': {[f['name'] for f in fac]}")
    fac2 = await graph.get_facility("卫生间")
    print(f"  搜'卫生间': {[f['name'] for f in fac2]}")

    print("\n=== 7. 全文搜索 ===")
    results = await graph.fulltext_search_artifact("青花")
    print(f"  搜'青花': {len(results)} 条")

    await graph.close()
    print("\n=== 全部通过 ===")


if __name__ == "__main__":
    asyncio.run(main())
