"""导出安灯原始/归一化数据。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from andon_fetcher.config import CORE_FIELDS


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(records: Iterable[dict[str, Any]], output_dir: Path, prefix: str = "andon") -> Path:
    output_dir = ensure_output_dir(output_dir)
    path = output_dir / f"{prefix}_{_timestamp()}.json"
    rows = list(records)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2, default=str)
    return path


def save_csv(records: Iterable[dict[str, Any]], output_dir: Path, prefix: str = "andon") -> Path:
    output_dir = ensure_output_dir(output_dir)
    path = output_dir / f"{prefix}_{_timestamp()}.csv"
    rows = list(records)
    if not rows:
        df = pd.DataFrame(columns=list(CORE_FIELDS))
    else:
        df = pd.DataFrame(rows)
        # 核心字段靠前
        ordered = [c for c in CORE_FIELDS if c in df.columns] + [
            c for c in df.columns if c not in CORE_FIELDS
        ]
        df = df[ordered]
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path
