"""第一步：从 OData API 拉取安灯原始事件。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urljoin

import requests

from andon_fetcher.config import CORE_FIELDS, ApiConfig
from andon_fetcher.http_session import fetch_json


def extract_records(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("value"), list):
        return [row for row in payload["value"] if isinstance(row, dict)]
    raise ValueError("Unexpected API payload shape: expected OData `value` array.")


def project_core_fields(record: dict[str, Any]) -> dict[str, Any]:
    """按核心字段裁剪；大小写不敏感匹配源字段名。"""
    lower_map = {str(k).lower(): v for k, v in record.items()}
    return {field: lower_map.get(field.lower()) for field in CORE_FIELDS}


def fetch_raw_events(config: ApiConfig) -> list[dict[str, Any]]:
    """拉取最新 N 条原始安灯事件（OData）。"""
    params: dict[str, str] = {
        "$top": str(config.top_n),
        "$orderby": "begintime desc",
    }
    if config.use_select:
        params["$select"] = ",".join(CORE_FIELDS)

    base_url = urljoin(f"{config.base_url.rstrip('/')}/", config.endpoint.lstrip("/"))
    url = f"{base_url}?{urlencode(params)}"

    print(f"[step1] 存储方式: 公司 OData API（非直连数据库）")
    print(f"[step1] 实体/表名: {config.endpoint}")
    print(f"[step1] 请求: {url}")
    print(f"[step1] 鉴权头: {config.auth_header}")
    print(f"[step1] 拉取最新 {config.top_n} 条")

    try:
        payload = fetch_json(config, url)
        records = extract_records(payload)
        print(f"[step1] 共拉取 {len(records)} 条原始记录")
        return records
    except requests.exceptions.HTTPError as exc:
        # 部分网关不支持 $select，自动降级重试
        if config.use_select and getattr(exc, "response", None) is not None:
            status = exc.response.status_code
            if status in {400, 404, 501}:
                print(f"[step1] $select 不被支持 (HTTP {status})，改为拉取全字段后本地裁剪")
                config.use_select = False
                return fetch_raw_events(config)
        print(f"[step1] HTTP 错误: {exc}")
        if getattr(exc, "response", None) is not None:
            print(f"[step1] 响应: {exc.response.text[:500]}")
        raise
    except Exception as exc:
        print(f"[step1] 拉取失败: {exc}")
        raise


# 兼容旧函数名
fetch_latest_events = fetch_raw_events
