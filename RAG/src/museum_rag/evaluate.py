from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, Field

from museum_rag.io import read_jsonl, write_json
from museum_rag.models import SearchFilters, SourceType
from museum_rag.retriever import Retriever


class EvaluationCase(BaseModel):
    id: str
    split: str = "dev"
    question: str
    answerable: bool = True
    expected_titles: list[str] = Field(default_factory=list)
    expected_source_types: list[SourceType] = Field(default_factory=list)
    filters: SearchFilters | None = None


def _relevant(case: EvaluationCase, title: str, source_type: SourceType) -> bool:
    title_matches = not case.expected_titles or title in case.expected_titles
    type_matches = not case.expected_source_types or source_type in case.expected_source_types
    return title_matches and type_matches


async def evaluate_retriever(
    retriever: Retriever,
    dataset_path: Path,
    report_path: Path,
    top_k: int = 5,
) -> dict:
    cases = read_jsonl(dataset_path, EvaluationCase)
    grouped: dict[str, list[dict]] = defaultdict(list)
    details = []
    for case in cases:
        response = await retriever.retrieve(case.question, top_k=top_k, filters=case.filters)
        rank = next(
            (
                index
                for index, hit in enumerate(response.hits, start=1)
                if _relevant(case, hit.title, hit.source_type)
            ),
            None,
        )
        item = {
            "id": case.id,
            "split": case.split,
            "answerable": case.answerable,
            "rank": rank,
            "top_score": response.hits[0].score if response.hits else 0.0,
            "predicted_insufficient": response.evidence_insufficient,
            "titles": [hit.title for hit in response.hits],
        }
        details.append(item)

    dev_items = [item for item in details if item["split"] == "dev"]
    threshold = calibrate_threshold(dev_items)
    for item in details:
        item["predicted_insufficient"] = item["top_score"] < threshold
        grouped[item["split"]].append(item)
    metrics = {split: _metrics(items) for split, items in grouped.items()}
    report = {
        "top_k": top_k,
        "recommended_score_threshold": threshold,
        "metrics": metrics,
        "details": details,
    }
    write_json(report_path, report)
    return report


def calibrate_threshold(items: list[dict]) -> float:
    if not items:
        return 0.0
    scores = sorted({float(item["top_score"]) for item in items})
    candidates = [0.0] + [(left + right) / 2 for left, right in zip(scores, scores[1:])]
    candidates.append(scores[-1] + 1e-9)
    best_threshold = 0.0
    best_f1 = -1.0
    answerable_count = sum(item["answerable"] for item in items)
    for threshold in candidates:
        trial = [
            {**item, "predicted_insufficient": item["top_score"] < threshold}
            for item in items
        ]
        false_rejections = sum(item["answerable"] and item["predicted_insufficient"] for item in trial)
        false_rejection_rate = false_rejections / answerable_count if answerable_count else 0.0
        if false_rejection_rate > 0.02:
            continue
        f1 = _abstention_f1(trial)
        if f1 > best_f1 or (f1 == best_f1 and threshold > best_threshold):
            best_f1 = f1
            best_threshold = threshold
    return best_threshold


def _metrics(items: list[dict]) -> dict[str, float | int]:
    answerable = [item for item in items if item["answerable"]]
    recall = sum(item["rank"] is not None for item in answerable) / len(answerable) if answerable else 0.0
    mrr = sum(1 / item["rank"] for item in answerable if item["rank"] is not None) / len(answerable) if answerable else 0.0
    f1 = _abstention_f1(items)
    return {
        "cases": len(items),
        "answerable_cases": len(answerable),
        "recall_at_k": round(recall, 4),
        "mrr": round(mrr, 4),
        "abstention_f1": round(f1, 4),
    }


def _abstention_f1(items: list[dict]) -> float:
    true_positive = sum(not item["answerable"] and item["predicted_insufficient"] for item in items)
    false_positive = sum(item["answerable"] and item["predicted_insufficient"] for item in items)
    false_negative = sum(not item["answerable"] and not item["predicted_insufficient"] for item in items)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall_abstention = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    return 2 * precision * recall_abstention / (precision + recall_abstention) if precision + recall_abstention else 0.0
