"""
Metadata 清洗与校验脚本
读取 metadata_mapping.json → 统计分布 → 特征值归一化 → Pydantic 强校验 → 覆盖写入
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Pydantic Schema
# ============================================================

class ArtifactFeatures(BaseModel):
    material: list[str] = Field(default_factory=list)
    technique: list[str] = Field(default_factory=list)
    motif: list[str] = Field(default_factory=list)
    form: list[str] = Field(default_factory=list)
    color: list[str] = Field(default_factory=list)
    usage: list[str] = Field(default_factory=list)
    era_hint: list[str] = Field(default_factory=list)
    style: list[str] = Field(default_factory=list)
    region: list[str] = Field(default_factory=list)

    @field_validator("*", mode="before")
    @classmethod
    def ensure_list_of_str(cls, v: Any) -> list[str]:
        if v is None:
            return []
        return [str(x).strip() for x in v if x]


class MetadataRecord(BaseModel):
    artifact_name: str
    features: ArtifactFeatures
    aliases: list[str] = Field(default_factory=list)
    intro_keywords: list[str] = Field(default_factory=list)

    @field_validator("aliases", "intro_keywords", mode="before")
    @classmethod
    def ensure_str_list(cls, v: Any) -> list[str]:
        if v is None:
            return []
        return [str(x).strip() for x in v if x]


# ============================================================
# 特征值归一化映射表（同义词 → 规范词）
# ============================================================

MATERIAL_MAP = {
    "端石": "石",
    "寿山石": "石",
    "酸枝木": "木",
    "紫砂": "陶",
    "石青泥": "陶",
    "金线": "丝",
    "银线": "丝",
    "绒线": "丝",
    "丝线": "丝",
    "布": "丝",
    "绸": "丝",
    "珐琅": "瓷",
    "水晶": "宝石",
    "油彩": "颜料",
    "贝壳": "螺钿",
    "青铜": "铜",
    "骨角牙": "象牙",
    "牙骨角": "象牙",
    "木材": "木",
    "木质": "木",
    "木头": "木",
    "瓷器": "瓷",
    "陶瓷": "瓷",
    "宝玉石": "宝石",
}

TECHNIQUE_MAP = {
    "广彩": "釉上彩",
    "烧制": "烧造",
    "白釉": "施釉",
    "青釉": "施釉",
    "蓝釉": "施釉",
    "青花": "釉下彩",
    "釉下彩": "釉下彩",
    "釉上彩": "釉上彩",
    "白地黑花": "釉下彩绘",
    "褐彩": "釉下彩绘",
    "平绣": "刺绣",
    "垫绣": "刺绣",
    "钉金": "刺绣",
    "擞和针": "刺绣",
    "渗针": "刺绣",
    "扭针": "刺绣",
    "瓷塑": "雕塑",
    "陶塑": "雕塑",
    "塑造": "雕塑",
    "线刻": "刻划",
    "刻石": "雕刻",
    "刻划": "雕刻",
    "刻花": "雕刻",
    "暗花": "雕刻",
    "彩绘": "绘画",
    "设色": "绘画",
    "描金": "绘画",
    "拓印": "印刷",
}

COLOR_MAP = {
    "墨色": "黑",
    "墨": "黑",
    "银色": "银",
    "银白": "银",
    "胭脂": "红",
    "洋红": "红",
    "胭脂红": "红",
    "粉红": "红",
    "粉青": "青",
    "梅子青": "青",
    "天青": "青",
    "天蓝": "蓝",
    "玫瑰紫": "紫",
    "海棠红": "红",
    "青紫": "紫",
    "青灰": "灰",
    "青白": "白",
    "象牙白": "白",
    "蟹青": "青",
    "酱色": "褐",
    "金黄": "金",
    "深红": "红",
    "月白": "白",
    "开片纹": "青",  # 哥窑特征归类
    "七彩": "彩",
}

USAGE_MAP = {
    "外销艺术品": "外销",
    "外销瓷": "外销",
    "陈设器": "陈设",
    "日用器": "日用",
    "日用瓷": "日用",
    "茶具": "饮茶",
    "文房清供": "文房",
    "文房焚香": "文房",
    "艺术欣赏": "陈设",
    "观赏": "陈设",
    "摆件": "陈设",
    "室内装饰": "陈设",
    "建筑装饰": "建筑",
    "镇宅": "建筑",
    "佛教供奉": "祭祀",
    "宗教供养": "祭祀",
    "供奉": "祭祀",
    "礼乐": "祭祀",
    "礼器": "祭祀",
    "乐器": "礼乐",
    "斗茶": "饮茶",
    "焚香": "文房",
    "梳妆": "日用",
    "社交": "日用",
    "社交用品": "日用",
    "货币": "经济",
    "茶叶包装": "外销",
    "计时": "日用",
    "照容": "日用",
    "鉴藏": "文房",
    "书法艺术": "文房",
    "文献": "文房",
    "信札": "文房",
    "随葬品": "墓葬",
    "佛教经典": "文献",
    "娱乐": "日用",
    "宫廷用": "陈设",
    "贡瓷": "外销",
}

ERA_MAP = {
    "清": "清代",
    "明": "明代",
    "宋": "宋代",
    "元": "元代",
    "唐": "唐代",
    "汉": "汉代",
    "乾隆": "清乾隆",
    "清中期": "清代",
    "清前期": "清代",
    "清末": "清代",
    "清晚期": "清代",
    "明晚期": "明代",
    "明中期": "明代",
    "清光绪": "清代",
    "清康熙": "清代",
    "清嘉庆": "清代",
    "清雍正": "清代",
    "明万历": "明代",
    "明永乐": "明代",
    "万历": "明代",
    "清代中后期": "清代",
    "清康熙三十二年": "清代",
    "19世纪": "清代",
    "十九世纪": "清代",
    "十八世纪": "清代",
    "1845年": "清代",
    "隋大业五年": "隋代",
    "金代": "金代",
    "当代": "现代",
    "约1830年": "清代",
}

REGION_MAP = {
    "广东广州": "广州",
    "广州府": "广州",
    "广东佛山": "佛山",
    "佛山石湾": "佛山",
    "石湾": "佛山",
    "广东肇庆": "肇庆",
    "广东潮州": "潮州",
    "潮汕": "潮州",
    "广东客家地区": "梅州",
    "广东广宁": "肇庆",
    "广东番禺": "广州",
    "番禺": "广州",
    "十三行": "广州",
    "广东顺德": "佛山",
    "顺德": "佛山",
    "广东新会": "江门",
    "新会": "江门",
    "广东信宜": "茂名",
    "广东雷州": "湛江",
    "雷州": "湛江",
    "福建德化": "德化",
    "江西景德镇": "景德镇",
    "浙江龙泉": "龙泉",
    "河北邯郸": "邯郸",
    "河南禹州": "禹州",
    "河南临汝": "汝州",
    "江西吉安": "吉安",
    "陕西铜川": "铜川",
    "福建建阳": "建阳",
    "江苏苏州": "苏州",
    "云南": "云南",
    # 文物出土/来源地与产地分开标注，保留原文
}

# ============================================================
# 归一化逻辑
# ============================================================

def normalize_list(values: list[str], mapping: dict[str, str]) -> list[str]:
    """映射归一化 + 去重 + 排序，同时移除空值。"""
    result: list[str] = []
    seen: set[str] = set()
    for v in values:
        v = v.strip()
        if not v:
            continue
        normalized = mapping.get(v, v)
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return sorted(result)


def normalize_features(f: ArtifactFeatures) -> ArtifactFeatures:
    """逐维度归一化。"""
    f.material = normalize_list(f.material, MATERIAL_MAP)
    f.technique = normalize_list(f.technique, TECHNIQUE_MAP)
    f.color = normalize_list(f.color, COLOR_MAP)
    f.usage = normalize_list(f.usage, USAGE_MAP)
    f.era_hint = normalize_list(f.era_hint, ERA_MAP)
    f.region = normalize_list(f.region, REGION_MAP)
    # motif, form, style 不加映射，保持 LLM 原始输出
    return f


# ============================================================
# 统计报告
# ============================================================

def print_distribution(records: list[MetadataRecord], dim: str):
    counter: dict[str, int] = {}
    for r in records:
        vals = getattr(r.features, dim, [])
        for v in vals:
            counter[v] = counter.get(v, 0) + 1
    sorted_items = sorted(counter.items(), key=lambda x: -x[1])
    print(f"\n  [{dim}] {len(sorted_items)} 种取值:")
    for k, v in sorted_items[:25]:
        print(f"    {v:>4}  {k}")


# ============================================================
# 主流程
# ============================================================

def main():
    src = Path(__file__).parent / "metadata_mapping.json"
    with open(src, "r", encoding="utf-8") as f:
        raw = json.load(f)

    print(f"加载 {len(raw)} 条原始记录")

    # Pydantic 校验 + 清洗
    records: list[MetadataRecord] = []
    errors: list[tuple[int, str]] = []

    for i, item in enumerate(raw):
        try:
            records.append(MetadataRecord(**item))
        except Exception as e:
            errors.append((i, str(e)))

    if errors:
        print(f"\n=== Pydantic 校验失败 {len(errors)} 条 ===")
        for idx, err in errors[:10]:
            print(f"  [{idx}] {raw[idx].get('artifact_name', '?')}: {err}")
    else:
        print("Pydantic 校验全部通过")

    # 打印清洗前分布
    print("\n========== 清洗前分布 ==========")
    for dim in ["material", "technique", "color", "usage", "era_hint", "region"]:
        print_distribution(records, dim)

    # 归一化
    for r in records:
        r.features = normalize_features(r.features)

    print("\n========== 清洗后分布 ==========")
    for dim in ["material", "technique", "color", "usage", "era_hint", "region"]:
        print_distribution(records, dim)

    # 覆盖写入
    output = [r.model_dump() for r in records]
    with open(src, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n清洗完成，{len(records)} 条已覆盖写入 {src}")


if __name__ == "__main__":
    main()
