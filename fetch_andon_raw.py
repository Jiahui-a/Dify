"""
第一步：获取安灯原始数据
模仿可运行脚本：OData API + API Key + InsecureHTTPSAdapter + 禁用代理
拉取原始事件后保存 JSON/CSV（不做清洗、不做知识库）
"""

from __future__ import annotations

import csv
import json
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# 内网自签证书时关闭校验会触发警告，此处静默
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 禁用代理，防止内网请求走公司外网代理
NO_PROXY = {"http": None, "https": None}

# 第一步核心字段
CORE_FIELDS = [
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
]


# ========== 配置类 ==========
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


# ========== SSL 适配器 ==========
class InsecureHTTPSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx,
            **pool_kwargs,
        )


# ========== 辅助函数 ==========
def _build_headers(config: ApiConfig) -> dict[str, str]:
    headers = {
        "Accept": "*/*",
        "User-Agent": config.user_agent,
    }
    if config.api_key:
        headers[config.auth_header] = config.api_key
    return headers


def _create_session(config: ApiConfig) -> requests.Session:
    session = requests.Session()
    if not config.verify_ssl:
        session.mount("https://", InsecureHTTPSAdapter())
    return session


def _fetch_json(config: ApiConfig, url: str) -> dict[str, Any]:
    """发送 HTTP 请求并解析 JSON"""
    session = _create_session(config)
    try:
        response = session.get(
            url,
            headers=_build_headers(config),
            verify=False,
            proxies=NO_PROXY,
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
    finally:
        session.close()


def extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从 OData 响应中提取记录列表"""
    if "value" in payload and isinstance(payload["value"], list):
        return payload["value"]
    if isinstance(payload, list):
        return payload
    raise ValueError("Unexpected API payload shape: expected OData `value` array.")


# ========== 核心拉取函数 ==========
def fetch_latest_events(config: ApiConfig) -> list[dict[str, Any]]:
    """拉取最新 N 条安灯事件数据"""
    params = {
        "$top": str(config.top_n),
        "$orderby": "begintime desc",
    }

    base_url = urljoin(f"{config.base_url}/", config.endpoint.lstrip("/"))
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"{base_url}?{query_string}"

    print(f"[fetch] 请求: {url}")
    print(f"[fetch] 拉取最新 {config.top_n} 条数据")

    try:
        payload = _fetch_json(config, url)
        records = extract_records(payload)
        print(f"[fetch] 共拉取 {len(records)} 条安灯事件记录")
        return records
    except requests.exceptions.HTTPError as e:
        print(f"[fetch] HTTP 错误: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"[fetch] 状态码: {e.response.status_code}")
            print(f"[fetch] 响应内容: {e.response.text[:500]}")
        raise
    except Exception as e:
        print(f"[fetch] 拉取失败: {e}")
        raise


def _project_core_fields(record: dict[str, Any]) -> dict[str, Any]:
    lower_map = {str(k).lower(): v for k, v in record.items()}
    return {field: lower_map.get(field) for field in CORE_FIELDS}


def save_raw(records: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    core_rows = [_project_core_fields(row) for row in records]

    raw_json = output_dir / f"andon_events_raw_{stamp}.json"
    with open(raw_json, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)
    print(f"[save] 原始 JSON: {raw_json}")

    core_json = output_dir / f"andon_events_core_{stamp}.json"
    with open(core_json, "w", encoding="utf-8") as f:
        json.dump(core_rows, f, ensure_ascii=False, indent=2, default=str)
    print(f"[save] 核心字段 JSON: {core_json}")

    core_csv = output_dir / f"andon_events_core_{stamp}.csv"
    with open(core_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CORE_FIELDS)
        writer.writeheader()
        writer.writerows(core_rows)
    print(f"[save] 核心字段 CSV : {core_csv}")


# ========== 主函数 ==========
def main() -> None:
    print("=" * 60)
    print("第一步：获取安灯原始数据")
    print("=" * 60)

    # ===== 请修改以下配置（与你的可运行脚本一致）=====
    api_config = ApiConfig(
        base_url="https://gongsi.com:8092/andon",
        endpoint="o_d_andon_eventsrawdata_cur",
        api_key="api-key3",
        auth_header="gongsi-Key",
        user_agent="Mozilla/5.0",
        verify_ssl=False,
        timeout_seconds=120,
        top_n=2000,
    )
    # ===== 配置结束 =====

    # 输出目录：默认写到本脚本同级 data/raw
    output_dir = Path(__file__).resolve().parent / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        raw_records = fetch_latest_events(api_config)

        if not raw_records:
            print("\n未拉取到任何数据")
            return

        # 打印字段，便于核对核心字段
        sample = raw_records[0]
        print("\n[probe] 样例字段名:")
        for key in sample.keys():
            print(f"  - {key}")

        keys_lower = {str(k).lower() for k in sample.keys()}
        missing = [f for f in CORE_FIELDS if f not in keys_lower]
        print(f"[probe] 核心字段命中: {len(CORE_FIELDS) - len(missing)}/{len(CORE_FIELDS)}")
        if missing:
            print("[probe] 缺失核心字段: " + ", ".join(missing))

        save_raw(raw_records, output_dir)

        print("\n" + "=" * 60)
        print(f"完成：共 {len(raw_records)} 条原始数据 -> {output_dir}")
        print("=" * 60)

    except Exception as e:
        print(f"\n失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
