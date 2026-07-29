"""第一步：原始数据落盘（JSON / CSV）。"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from andon_fetcher.config import CORE_FIELDS, AppConfig
from andon_fetcher.fetch import fetch_raw_events, project_core_fields


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def save_raw(records: list[dict[str, Any]], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    core_rows = [project_core_fields(row) for row in records]

    full_json = output_dir / f"andon_raw_full_{stamp}.json"
    with full_json.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2, default=str)

    core_json = output_dir / f"andon_raw_core_{stamp}.json"
    with core_json.open("w", encoding="utf-8") as fh:
        json.dump(core_rows, fh, ensure_ascii=False, indent=2, default=str)

    core_csv = output_dir / f"andon_raw_core_{stamp}.csv"
    with core_csv.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CORE_FIELDS))
        writer.writeheader()
        writer.writerows(core_rows)

    print(f"[step1] 全量原始 JSON: {full_json}")
    print(f"[step1] 核心字段 JSON: {core_json}")
    print(f"[step1] 核心字段 CSV : {core_csv}")
    return {"full_json": full_json, "core_json": core_json, "core_csv": core_csv}


def run_step1(app: AppConfig) -> dict[str, Path]:
    """第一步：拉取安灯原始数据并落盘。"""
    print("=" * 60)
    print("第一步：获取安灯原始数据")
    print("=" * 60)
    records = fetch_raw_events(app.api)
    if not records:
        print("[step1] 未拉到数据")
        return {}
    paths = save_raw(records, app.output_dir)
    print("=" * 60)
    print(f"[step1] 完成，共 {len(records)} 条")
    print("=" * 60)
    return paths
