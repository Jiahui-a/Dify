"""配置加载：从环境变量 / .env 读取 OData 连接信息。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# 安灯核心字段（与业务约定对齐，大小写不敏感匹配）
CORE_FIELDS: tuple[str, ...] = (
    "linename",
    "stationname",
    "faulttype",
    "eventsname",
    "begintime",
    "responsetime",
    "endtime",
    "confirmtime",
    "reactionplan",
    "actions",
    "remark",
    "ischangeparameter",
    "parametername",
    "oldvalue",
    "newvalue",
    "ischangequipment",
    "changeeventdesc",
    "equipmentpn",
    "responseduration",
    "repairduration",
    "dowtimeduration",
    "closeperson",
    "responseperson",
)


@dataclass(frozen=True)
class AndonConfig:
    """安灯 OData 拉取配置。"""

    base_url: str
    entity_set: str
    api_key: str
    api_key_mode: str = "header_api_key"
    api_key_header: str | None = None
    page_size: int = 500
    timeout_seconds: float = 60.0
    verify_ssl: bool = True
    output_dir: Path = field(default_factory=lambda: Path("./data/raw"))
    odata_filter: str | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)
    select_fields: tuple[str, ...] = CORE_FIELDS

    @property
    def entity_url(self) -> str:
        base = self.base_url.rstrip("/")
        entity = self.entity_set.strip("/")
        return f"{base}/{entity}"


def _as_bool(value: str | None, default: bool = True) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_extra_params(raw: str | None) -> dict[str, Any]:
    if not raw or not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("ANDON_EXTRA_PARAMS 必须是 JSON 对象")
    return data


def load_config(env_file: str | Path | None = None) -> AndonConfig:
    """加载配置。优先读取指定 .env，其次当前目录 .env。"""
    if env_file:
        load_dotenv(env_file, override=False)
    else:
        load_dotenv(override=False)

    base_url = os.getenv("ANDON_ODATA_BASE_URL", "").strip()
    entity_set = os.getenv("ANDON_ENTITY_SET", "").strip()
    api_key = os.getenv("ANDON_API_KEY", "").strip()

    missing = [
        name
        for name, value in (
            ("ANDON_ODATA_BASE_URL", base_url),
            ("ANDON_ENTITY_SET", entity_set),
            ("ANDON_API_KEY", api_key),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "缺少必要配置: "
            + ", ".join(missing)
            + "。请复制 .env.example 为 .env 并填入公司服务器信息。"
        )

    filter_value = os.getenv("ANDON_FILTER", "").strip() or None
    select_raw = os.getenv("ANDON_SELECT_FIELDS", "").strip()
    select_fields = (
        tuple(part.strip() for part in select_raw.split(",") if part.strip())
        if select_raw
        else CORE_FIELDS
    )

    return AndonConfig(
        base_url=base_url,
        entity_set=entity_set,
        api_key=api_key,
        api_key_mode=os.getenv("ANDON_API_KEY_MODE", "header_api_key").strip(),
        api_key_header=os.getenv("ANDON_API_KEY_HEADER", "").strip() or None,
        page_size=int(os.getenv("ANDON_PAGE_SIZE", "500")),
        timeout_seconds=float(os.getenv("ANDON_TIMEOUT_SECONDS", "60")),
        verify_ssl=_as_bool(os.getenv("ANDON_VERIFY_SSL"), True),
        output_dir=Path(os.getenv("ANDON_OUTPUT_DIR", "./data/raw")),
        odata_filter=filter_value,
        extra_params=_parse_extra_params(os.getenv("ANDON_EXTRA_PARAMS")),
        select_fields=select_fields,
    )
