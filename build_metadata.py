"""
构建 Metadata 特征映射表
读取 有详细介绍的藏品.json → 批量调用 LLM 提取结构化特征 → 输出 metadata_mapping.json

用法: python build_metadata.py
"""

import asyncio
import json
import os
import traceback
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 配置区（密钥一律从环境变量读取，绝不硬编码）
# ============================================================
API_KEY = os.environ.get("DEEPSEEK_KEY", "")
if not API_KEY:
    raise RuntimeError("缺少 DEEPSEEK_KEY 环境变量，请在 .env 中配置")
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-v4-flash"

MAX_CONCURRENT = 1
BATCH_SIZE = 5
MAX_TOKENS = 4096
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2

# ============================================================
# Prompt 模板
# ============================================================

SYSTEM_PROMPT = """你是博物馆藏品特征提取器。根据藏品的名称和介绍，提取结构化特征。

返回一个 JSON 对象，格式如下:
{
  "items": [
    {
      "artifact_name": "原始名称(原样保留)",
      "features": {
        "material": ["材质列表，如 木/瓷/铜/石/玉/象牙/丝/纸/银/陶/竹/牙骨角/..."],
        "technique": ["工艺列表，如 雕刻/金漆/刺绣/烧制/铸造/镂空/描金/贴花/累丝/錾刻/..."],
        "motif": ["纹饰题材列表，如 龙/凤/花鸟/人物/山水/瑞兽/狮子/佛教/吉祥纹/..."],
        "form": ["器型列表，如 碗/瓶/盘/屏风/砚/盒/钟/壶/罐/像/炉/杯/..."],
        "color": ["颜色特征，如 黑/金/白/青/蓝/红/彩/..."],
        "usage": ["用途，如 文房/祭祀/日用/外销/陈设/建筑装饰/..."],
        "era_hint": ["年代标签，如 唐代/宋代/明代/清代/民国/近代/..."],
        "style": ["风格标签，如 广彩/广绣/潮州/岭南画派/石湾窑/德化窑/龙泉窑/景德镇窑/..."],
        "region": ["地域标签，如 广东/广州/潮汕/客家/肇庆/佛山/海外/..."]
      },
      "aliases": ["游客可能的叫法，3-5个口语化别名"],
      "intro_keywords": ["介绍中抽取的关键词，5-8个，用于全文检索"]
    }
  ]
}

【各维度取值规范】
- material: 从 name/intro 中推断，不确定就空数组，不要编造
- technique: 提取工艺技法关键词
- motif: 提取核心纹饰、题材
- form: 提取器型、造型类别
- usage: 提取实际用途
- style: 提取窑口、流派、工艺风格
- region: 提取地域关联
- aliases: 模拟游客的口语叫法，不要写得太学术。例如:
  "白切鸡玉雕"、"能转的象牙球"、"外国人定制的盘子"、"潮汕的金色木雕"
- intro_keywords: 从 introduction 原文中提取最具辨别力的实词

【严格规则】
- 只根据提供的名称和介绍来提取，不要凭空编造
- 无对应特征的维度用空数组 []
- artifact_name 必须与输入的 name 完全一致
- items 数组的长度必须等于输入藏品数量"""


def build_user_prompt(batch: list[dict]) -> str:
    items_text = []
    for i, item in enumerate(batch, 1):
        intro = (item.get("introduction") or "")[:300]
        items_text.append(f"{i}. 名称: {item['name']}\n   介绍: {intro}")
    return "请为以下藏品提取特征:\n\n" + "\n\n".join(items_text)


# ============================================================
# API 调用（带重试）
# ============================================================

async def call_llm(
    session: aiohttp.ClientSession,
    batch: list[dict],
    batch_idx: int,
    total_batches: int,
) -> list[dict]:
    """调用 LLM 处理一个批次，失败自动重试。"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(batch)},
        ],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with session.post(
                f"{BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()

                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}: {data}")

                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                items = parsed.get("items", [])
                if not isinstance(items, list) or len(items) == 0:
                    raise ValueError(f"items 字段缺失或非数组: {content[:200]}")

                print(f"  第 {batch_idx}/{total_batches} 批完成，返回 {len(items)} 条")
                return items

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY ** attempt
                print(f"  第 {batch_idx} 批第 {attempt} 次失败，{delay}s 后重试: {e}")
                await asyncio.sleep(delay)
            else:
                print(f"  第 {batch_idx} 批 {MAX_RETRIES} 次全部失败: {e}")

    raise RuntimeError(
        f"批次 {batch_idx} 在 {MAX_RETRIES} 次重试后仍然失败。"
        f"最后错误: {last_error}"
    )


# ============================================================
# 主流程
# ============================================================

async def main():
    src_path = Path(__file__).parent / "有详细介绍的藏品.json"
    with open(src_path, "r", encoding="utf-8") as f:
        artifacts = json.load(f)

    print(f"读取到 {len(artifacts)} 件藏品")

    batches = [
        artifacts[i : i + BATCH_SIZE]
        for i in range(0, len(artifacts), BATCH_SIZE)
    ]
    total = len(batches)
    print(f"分成 {total} 批，每批 {BATCH_SIZE} 件，并发数 {MAX_CONCURRENT}")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    results: list[dict] = []
    dead_letter: list[dict] = []

    async def process_batch(
        session: aiohttp.ClientSession,
        idx: int,
        batch: list[dict],
    ):
        async with semaphore:
            print(f"  处理第 {idx}/{total} 批 ({len(batch)} 件)...")
            try:
                return await call_llm(session, batch, idx, total)
            except Exception:
                traceback.print_exc()
                dead_letter.extend(
                    {"name": item["name"], "error": "all retries exhausted"}
                    for item in batch
                )
                print(f"  !! 第 {idx} 批已加入死信队列，跳过")
                return []

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT + 5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [process_batch(session, i + 1, batch) for i, batch in enumerate(batches)]
        batch_results = await asyncio.gather(*tasks)

    for br in batch_results:
        results.extend(br)

    seen = set()
    unique_results = []
    for r in results:
        name = r.get("artifact_name", "")
        if name and name not in seen:
            seen.add(name)
            unique_results.append(r)

    print(f"\n处理完成: 成功 {len(unique_results)} 条, 死信 {len(dead_letter)} 条")

    out_path = Path(__file__).parent / "metadata_mapping.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique_results, f, ensure_ascii=False, indent=2)
    print(f"已保存到 {out_path}")

    if dead_letter:
        dl_path = Path(__file__).parent / "metadata_dead_letter.json"
        with open(dl_path, "w", encoding="utf-8") as f:
            json.dump(dead_letter, f, ensure_ascii=False, indent=2)
        print(f"死信已保存到 {dl_path}")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
