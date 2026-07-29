"""从 OData API 拉取最新 N 条安灯事件。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urljoin

import requests

from andon_fetcher.config import ApiConfig
from andon_fetcher.http_session import fetch_json


def extract_records(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """从 OData 响应中提取记录列表。"""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if "value" in payload and isinstance(payload["value"], list):
        return [row for row in payload["value"] if isinstance(row, dict)]
    raise ValueError("Unexpected API payload shape: expected OData `value` array.")


def fetch_latest_events(config: ApiConfig) -> list[dict[str, Any]]:
    """拉取最新 N 条安灯事件数据（$top + begintime desc）。"""
    params = {
        "$top": str(config.top_n),
        "$orderby": "begintime desc",
    }
    base_url = urljoin(f"{config.base_url.rstrip('/')}/", config.endpoint.lstrip("/"))
    url = f"{base_url}?{urlencode(params)}"

    print(f"[fetch] 请求: {url}")
    print(f"[fetch] 拉取最新 {config.top_n} 条数据")
    print(f"[fetch] Header: {config.auth_header}=***")

    try:
        payload = fetch_json(config, url)
        records = extract_records(payload)
        print(f"[fetch] 共拉取 {len(records)} 条安灯事件记录")
        return records
    except requests.exceptions.HTTPError as exc:
        print(f"[fetch] HTTP 错误: {exc}")
        if getattr(exc, "response", None) is not None:
            print(f"[fetch] 状态码: {exc.response.status_code}")
            print(f"[fetch] 响应内容: {exc.response.text[:500]}")
        raise
    except Exception as exc:
        print(f"[fetch] 拉取失败: {exc}")
        raise
