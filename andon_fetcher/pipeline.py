"""拉取 → 清洗 → 导出 Dify 知识库文件。"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from andon_fetcher.cleaner import AndonEventCleaner, deduplicate_records, print_statistics
from andon_fetcher.config import AppConfig, CleanConfig
from andon_fetcher.fetch import fetch_latest_events


KB_FIELDS = [
    "chunk",
    "linename",
    "stationname",
    "faulttype",
    "eventsdescription",
    "reactionplan",
    "keywords",
    "begintime",
    "stationno",
    "eventsname",
    "original_id",
]


def clean_records(
    raw_records: list[dict[str, Any]], clean_config: CleanConfig | None = None
) -> list[dict[str, Any]]:
    cleaner = AndonEventCleaner(clean_config or CleanConfig())
    cleaned: list[dict[str, Any]] = []
    skipped = 0
    for record in raw_records:
        item = cleaner.clean_record(record)
        if item:
            cleaned.append(item)
        else:
            skipped += 1
    print(f"[clean] 保留 {len(cleaned)} 条，跳过 {skipped} 条")
    return cleaned


def export_knowledge_base(
    unique_records: list[dict[str, Any]],
    raw_records: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    csv_file = output_dir / "andon_events_knowledge_base.csv"
    if unique_records:
        with open(csv_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=KB_FIELDS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(unique_records)
        print(f"CSV: {csv_file} ({len(unique_records)} 条)")
        paths["csv"] = csv_file

    json_file = output_dir / "andon_events_cleaned.json"
    with open(json_file, "w", encoding="utf-8") as fh:
        json.dump(unique_records, fh, ensure_ascii=False, indent=2)
    print(f"JSON: {json_file}")
    paths["json"] = json_file

    chunk_file = output_dir / "chunks_only.txt"
    with open(chunk_file, "w", encoding="utf-8") as fh:
        for item in unique_records:
            fh.write(item["chunk"] + "\n")
    print(f"Chunk文本: {chunk_file}")
    paths["chunks"] = chunk_file

    lines = sorted({item["linename"] for item in unique_records if item.get("linename")})
    line_dict_file = output_dir / "line_dict.json"
    with open(line_dict_file, "w", encoding="utf-8") as fh:
        json.dump(lines, fh, ensure_ascii=False, indent=2)
    print(f"线体字典: {line_dict_file} (共 {len(lines)} 个)")
    paths["lines"] = line_dict_file

    raw_file = output_dir / "andon_events_raw.json"
    with open(raw_file, "w", encoding="utf-8") as fh:
        json.dump(raw_records, fh, ensure_ascii=False, indent=2)
    print(f"原始数据: {raw_file}")
    paths["raw"] = raw_file

    return paths


def run_pipeline(app: AppConfig) -> dict[str, Path]:
    """拉取最新 top_n → 清洗去重 → 导出知识库文件。"""
    print("=" * 60)
    print("拉取最新安灯事件数据")
    print("=" * 60)

    raw_records = fetch_latest_events(app.api)
    if not raw_records:
        print("未拉取到任何数据")
        return {}

    print("\n[clean] 开始清洗...")
    cleaned = clean_records(raw_records, app.clean)
    unique = deduplicate_records(cleaned)
    print_statistics(unique)

    paths = export_knowledge_base(unique, raw_records, app.output_dir)

    print("\n" + "=" * 60)
    print("导入 Dify 知识库")
    print("=" * 60)
    if "csv" in paths:
        print(f"上传文件: {paths['csv']}")
    print("=" * 60)
    return paths
