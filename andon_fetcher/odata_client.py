"""OData 客户端：API Key 鉴权 + 分页拉取。"""

from __future__ import annotations

import logging
from typing import Any, Iterator
from urllib.parse import urljoin, urlparse, urlunparse

import requests
import urllib3
from requests.exceptions import RequestException, SSLError

from andon_fetcher.config import AndonConfig

logger = logging.getLogger(__name__)


class ODataClientError(RuntimeError):
    """OData 请求失败。"""


def switch_scheme(url: str, scheme: str) -> str:
    """把 URL 的协议改成 http/https。"""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(scheme=scheme))


class ODataClient:
    """通用 OData v4 客户端，适配公司安灯 API-Key 鉴权。"""

    def __init__(self, config: AndonConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self._http_fallback_enabled = True
        if not config.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _auth_headers_and_params(self) -> tuple[dict[str, str], dict[str, str]]:
        mode = self.config.api_key_mode.lower()
        key = self.config.api_key
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.config.user_agent,
        }
        params: dict[str, str] = {}

        if mode == "header_api_key":
            headers["api-key"] = key
        elif mode == "header_x_api_key":
            headers["X-API-Key"] = key
        elif mode == "header_authorization_apikey":
            headers["Authorization"] = f"ApiKey {key}"
        elif mode == "header_authorization_bearer":
            headers["Authorization"] = f"Bearer {key}"
        elif mode in {"header_custom", "auth_header"}:
            # 公司网关：Header 名由 auth_header 指定，例如 ABC: <api_key>
            header_name = self.config.auth_header or self.config.api_key_header or "ABC"
            headers[header_name] = key
        elif mode == "query_api_key":
            params["api-key"] = key
        elif mode == "query_apikey":
            params["apiKey"] = key
        else:
            raise ValueError(f"不支持的 ANDON_API_KEY_MODE: {mode}")

        return headers, params

    def _build_query_params(
        self,
        *,
        top: int | None = None,
        skip: int | None = None,
        select: tuple[str, ...] | None = None,
        filter_expr: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _, auth_params = self._auth_headers_and_params()
        params: dict[str, Any] = dict(auth_params)

        if top is not None:
            params["$top"] = top
        if skip is not None:
            params["$skip"] = skip
        if select:
            params["$select"] = ",".join(select)
        if filter_expr:
            params["$filter"] = filter_expr

        # 请求 count，便于日志与断点核对
        params.setdefault("$count", "true")

        if extra:
            params.update(extra)
        if self.config.extra_params:
            params.update(self.config.extra_params)
        return params

    def _adopt_http_base(self) -> None:
        """HTTPS 握手失败时，把配置中的 base_url 永久切到 http。"""
        if self.config.base_url.lower().startswith("https://"):
            http_base = switch_scheme(self.config.base_url, "http")
            logger.warning(
                "HTTPS TLS/SSL 失败（常见于公司 8092 端口实际是 HTTP）。"
                "已自动改用: %s",
                http_base,
            )
            logger.warning(
                "请把 .env 中 ANDON_ODATA_BASE_URL 改成 http://... 以避免每次重试。"
            )
            self.config.base_url = http_base

    def _request_get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None,
    ) -> requests.Response:
        """
        发起 GET；若 https 出现 SSLError（如 ASN1 NOT_ENOUGH_DATA），
        自动用 http 重试一次。
        """
        try:
            return self.session.get(
                url,
                headers=headers,
                params=params if params else None,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl,
            )
        except SSLError as exc:
            can_fallback = (
                self._http_fallback_enabled
                and url.lower().startswith("https://")
            )
            if not can_fallback:
                raise ODataClientError(
                    "SSL 连接失败。"
                    "若公司安灯端口实际是 HTTP，请把 ANDON_ODATA_BASE_URL "
                    "改成 http://主机:8092/andon（不要用 https）。"
                    f" 原始错误: {exc}"
                ) from exc

            http_url = switch_scheme(url, "http")
            logger.warning("HTTPS SSLError，改用 HTTP 重试: %s", http_url)
            self._adopt_http_base()
            try:
                return self.session.get(
                    http_url,
                    headers=headers,
                    params=params if params else None,
                    timeout=self.config.timeout_seconds,
                    verify=False,
                )
            except RequestException as retry_exc:
                raise ODataClientError(
                    "HTTPS 与 HTTP 均请求失败。"
                    f" https错误={exc}; http错误={retry_exc}"
                ) from retry_exc
        except RequestException as exc:
            raise ODataClientError(f"网络请求失败: {exc}") from exc

    def get_metadata(self) -> str:
        """拉取 $metadata（XML），用于确认实体与字段名。"""
        headers, auth_params = self._auth_headers_and_params()
        url = f"{self.config.base_url.rstrip('/')}/$metadata"
        response = self._request_get(url, headers=headers, params=auth_params)
        if response.status_code >= 400:
            raise ODataClientError(
                f"获取 $metadata 失败: HTTP {response.status_code} - {response.text[:500]}"
            )
        return response.text

    def fetch_page(
        self,
        *,
        url: str | None = None,
        top: int | None = None,
        skip: int | None = None,
        select: tuple[str, ...] | None = None,
        filter_expr: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """拉取单页 OData JSON。"""
        headers, auth_params = self._auth_headers_and_params()
        target = url or self.config.entity_url
        following_next_link = url is not None

        if following_next_link:
            # nextLink 通常已含完整查询参数；query 鉴权模式仍需附带 api-key
            params: dict[str, Any] = dict(auth_params)
            if not target.startswith("http"):
                target = urljoin(self.config.base_url.rstrip("/") + "/", target.lstrip("/"))
            # 若已切到 http，把 nextLink 里残留的 https 一并改掉
            if self.config.base_url.lower().startswith("http://") and target.lower().startswith(
                "https://"
            ):
                target = switch_scheme(target, "http")
        else:
            params = self._build_query_params(
                top=top if top is not None else self.config.page_size,
                skip=skip,
                select=select if select is not None else self.config.select_fields,
                filter_expr=filter_expr
                if filter_expr is not None
                else self.config.odata_filter,
                extra=extra,
            )

        logger.debug(
            "GET %s params=%s",
            target,
            {k: v for k, v in params.items() if k not in {"api-key", "apiKey"}},
        )
        response = self._request_get(target, headers=headers, params=params)
        if response.status_code >= 400:
            raise ODataClientError(
                f"OData 请求失败: HTTP {response.status_code} - {response.text[:800]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ODataClientError(
                f"响应不是合法 JSON（OData 期望 application/json）: {response.text[:300]}"
            ) from exc

        if not isinstance(payload, dict):
            raise ODataClientError("OData 响应根节点必须是对象")
        return payload

    def iter_records(
        self,
        *,
        max_records: int | None = None,
        select: tuple[str, ...] | None = None,
        filter_expr: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        迭代全部记录。

        优先跟随 `@odata.nextLink`；若服务不返回 nextLink，则使用 $skip/$top 翻页。
        """
        yielded = 0
        skip = 0
        next_url: str | None = None
        page_index = 0

        while True:
            page_index += 1
            if next_url:
                payload = self.fetch_page(url=next_url)
            else:
                payload = self.fetch_page(
                    top=self.config.page_size,
                    skip=skip,
                    select=select,
                    filter_expr=filter_expr,
                )

            rows = self._extract_value(payload)
            count = payload.get("@odata.count")
            logger.info(
                "第 %s 页: 本页 %s 条%s",
                page_index,
                len(rows),
                f", 服务端 count={count}" if count is not None else "",
            )

            for row in rows:
                yield row
                yielded += 1
                if max_records is not None and yielded >= max_records:
                    return

            next_url = payload.get("@odata.nextLink") or payload.get("odata.nextLink")
            if next_url:
                continue

            # 无 nextLink：若本页不足 page_size，认为结束；否则继续 $skip
            if len(rows) < self.config.page_size:
                return
            skip += self.config.page_size

    @staticmethod
    def _extract_value(payload: dict[str, Any]) -> list[dict[str, Any]]:
        if "value" in payload and isinstance(payload["value"], list):
            return [row for row in payload["value"] if isinstance(row, dict)]
        # 少数网关会直接返回数组包装在 d.results（OData v2）
        d = payload.get("d")
        if isinstance(d, dict) and isinstance(d.get("results"), list):
            return [row for row in d["results"] if isinstance(row, dict)]
        if isinstance(d, list):
            return [row for row in d if isinstance(row, dict)]
        raise ODataClientError(
            "无法解析 OData 记录列表：未找到 value / d.results。"
            f" 顶层键: {list(payload.keys())}"
        )
