import json
from pathlib import Path
from typing import Iterable, TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


def read_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as file:
        value = json.load(file)
    if not isinstance(value, list):
        raise ValueError(f"{path.name} 的顶层必须是数组")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")


def write_jsonl(path: Path, values: Iterable[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for value in values:
            file.write(value.model_dump_json(exclude_none=True))
            file.write("\n")


def read_jsonl(path: Path, model: type[ModelT]) -> list[ModelT]:
    values = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                values.append(model.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number} 数据无效") from exc
    return values

