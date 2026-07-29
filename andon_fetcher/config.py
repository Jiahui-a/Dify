"""API / 环境配置：对齐公司安灯 OData 连接方式。"""

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


@dataclass
class ApiConfig:
    """API 配置（与公司安灯网关约定一致）。"""

    base_url: str = "http://gongsi.com:8092/andon"
    endpoint: str = "o_d_andon_eventsrawdata_cur"
    api_key: str = "API_KEY"
    auth_header: str = "ABC"
    user_agent: str = "Mozilla/5.0"
    verify_ssl: bool = False
    timeout_seconds: int = 120
    top_n: int = 500
    output_dir: Path = field(default_factory=lambda: Path("./data/raw"))
    odata_filter: str | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)
    select_fields: tuple[str, ...] = CORE_FIELDS
    # 兼容旧模式；默认走自定义 Header（auth_header）
    api_key_mode: str = "header_custom"

    @property
    def entity_set(self) -> str:
        return self.endpoint

    @property
    def page_size(self) -> int:
        return self.top_n

    @property
    def api_key_header(self) -> str:
        return self.auth_header

    @property
    def entity_url(self) -> str:
        base = self.base_url.rstrip("/")
        entity = self.endpoint.strip("/")
        return f"{base}/{entity}"


# 向后兼容别名
AndonConfig = ApiConfig


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


def load_config(env_file: str | Path | None = None) -> ApiConfig:
    """加载配置。环境变量可覆盖 ApiConfig 默认值；未设置时使用公司默认连接。"""
    if env_file:
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        # 只读当前工作目录 .env，避免 find_dotenv 向上误读其它目录
        cwd_env = Path.cwd() / ".env"
        if cwd_env.is_file():
            load_dotenv(dotenv_path=cwd_env, override=False)

    defaults = ApiConfig()

    base_url = os.getenv("ANDON_ODATA_BASE_URL", defaults.base_url).strip()
    endpoint = (
        os.getenv("ANDON_ENTITY_SET")
        or os.getenv("ANDON_ENDPOINT")
        or defaults.endpoint
    ).strip()
    api_key = os.getenv("ANDON_API_KEY", defaults.api_key).strip()
    auth_header = (
        os.getenv("ANDON_API_KEY_HEADER")
        or os.getenv("ANDON_AUTH_HEADER")
        or defaults.auth_header
    ).strip()

    if not base_url or not endpoint or not api_key:
        raise ValueError(
            "缺少必要配置: base_url / endpoint / api_key。"
            "请复制 .env.example 为 .env 并填入公司服务器信息。"
        )

    filter_value = os.getenv("ANDON_FILTER", "").strip() or None
    select_raw = os.getenv("ANDON_SELECT_FIELDS", "").strip()
    select_fields = (
        tuple(part.strip() for part in select_raw.split(",") if part.strip())
        if select_raw
        else CORE_FIELDS
    )

    top_raw = os.getenv("ANDON_PAGE_SIZE") or os.getenv("ANDON_TOP_N")
    timeout_raw = os.getenv("ANDON_TIMEOUT_SECONDS")

    return ApiConfig(
        base_url=base_url,
        endpoint=endpoint,
        api_key=api_key,
        auth_header=auth_header,
        user_agent=os.getenv("ANDON_USER_AGENT", defaults.user_agent).strip()
        or defaults.user_agent,
        verify_ssl=_as_bool(os.getenv("ANDON_VERIFY_SSL"), defaults.verify_ssl),
        timeout_seconds=int(timeout_raw) if timeout_raw else defaults.timeout_seconds,
        top_n=int(top_raw) if top_raw else defaults.top_n,
        output_dir=Path(os.getenv("ANDON_OUTPUT_DIR", str(defaults.output_dir))),
        odata_filter=filter_value,
        extra_params=_parse_extra_params(os.getenv("ANDON_EXTRA_PARAMS")),
        select_fields=select_fields,
        api_key_mode=os.getenv("ANDON_API_KEY_MODE", defaults.api_key_mode).strip()
        or defaults.api_key_mode,
    )
