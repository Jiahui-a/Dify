"""HTTP Session：内网自签证书 + 禁用公司代理。"""

from __future__ import annotations

import ssl
from typing import Any

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

from andon_fetcher.config import ApiConfig

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 禁用代理，防止内网请求走公司外网代理
NO_PROXY = {"http": None, "https": None}


class InsecureHTTPSAdapter(HTTPAdapter):
    """跳过主机名校验与证书校验的 HTTPS Adapter。"""

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # 兼容部分旧网关
        if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
            ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx,
            **pool_kwargs,
        )


def build_headers(config: ApiConfig) -> dict[str, str]:
    headers = {
        "Accept": "*/*",
        "User-Agent": config.user_agent,
    }
    if config.api_key:
        headers[config.auth_header] = config.api_key
    return headers


def create_session(config: ApiConfig) -> requests.Session:
    session = requests.Session()
    if not config.verify_ssl:
        session.mount("https://", InsecureHTTPSAdapter())
    return session


def fetch_json(config: ApiConfig, url: str) -> dict[str, Any]:
    """发送 HTTP 请求并解析 JSON。"""
    session = create_session(config)
    try:
        response = session.get(
            url,
            headers=build_headers(config),
            verify=False,
            proxies=NO_PROXY,
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
    finally:
        session.close()
