"""API / 清洗配置（对齐可运行脚本）。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class ApiConfig:
    """API 配置"""

    base_url: str = "https://gongsi.com:8092/andon"
    endpoint: str = "o_d_andon_eventsrawdata_cur"
    api_key: str = "API_KEY"
    auth_header: str = "gongsi-Key"
    user_agent: str = "Mozilla/5.0"
    verify_ssl: bool = False
    timeout_seconds: int = 120
    top_n: int = 2000

    @property
    def entity_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.endpoint.lstrip('/')}"


@dataclass
class CleanConfig:
    """清洗配置"""

    max_desc_length: int = 80
    max_plan_length: int = 60
    max_keywords: int = 3
    chunk_max_length: int = 150


@dataclass
class AppConfig:
    """运行时配置"""

    api: ApiConfig = field(default_factory=ApiConfig)
    clean: CleanConfig = field(default_factory=CleanConfig)
    output_dir: Path = field(default_factory=lambda: Path("./output"))


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config(env_file: str | Path | None = None) -> AppConfig:
    """从 .env / 环境变量加载配置。"""
    if env_file:
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        cwd_env = Path.cwd() / ".env"
        if cwd_env.is_file():
            load_dotenv(dotenv_path=cwd_env, override=False)

    defaults = ApiConfig()
    api = ApiConfig(
        base_url=os.getenv("ANDON_ODATA_BASE_URL", defaults.base_url).strip(),
        endpoint=(
            os.getenv("ANDON_ENDPOINT")
            or os.getenv("ANDON_ENTITY_SET")
            or defaults.endpoint
        ).strip(),
        api_key=os.getenv("ANDON_API_KEY", defaults.api_key).strip(),
        auth_header=(
            os.getenv("ANDON_AUTH_HEADER")
            or os.getenv("ANDON_API_KEY_HEADER")
            or defaults.auth_header
        ).strip(),
        user_agent=os.getenv("ANDON_USER_AGENT", defaults.user_agent).strip()
        or defaults.user_agent,
        verify_ssl=_as_bool(os.getenv("ANDON_VERIFY_SSL"), defaults.verify_ssl),
        timeout_seconds=int(
            os.getenv("ANDON_TIMEOUT_SECONDS", str(defaults.timeout_seconds))
        ),
        top_n=int(
            os.getenv("ANDON_TOP_N")
            or os.getenv("ANDON_PAGE_SIZE")
            or str(defaults.top_n)
        ),
    )
    return AppConfig(
        api=api,
        clean=CleanConfig(),
        output_dir=Path(os.getenv("ANDON_OUTPUT_DIR", "./output")),
    )


# 兼容旧导入名
AndonConfig = ApiConfig
