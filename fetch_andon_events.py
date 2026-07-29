"""
第一步：获取安灯原始数据

存储方式：公司 OData API（非直连 MySQL / SQL Server / PostgreSQL）
连接：base_url + endpoint + X-Api-Key
核心表/实体：o_d_andon_eventsrawdata_cur
"""

import json
import ssl
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 禁用代理，防止内网请求走公司外网代理
NO_PROXY = {"http": None, "https": None}

# 第一步约定的重要字段
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


@dataclass
class ApiConfig:
    """API 配置（连接信息）"""
    base_url: str = "https://gongsi.com:8092/andon"
    endpoint: str = "o_d_andon_eventsrawdata_cur"  # 核心表：安灯原始事件
    api_key: str = "API_KEY"
    auth_header: str = "X-Api-Key"
    user_agent: str = "Mozilla/5.0"
    verify_ssl: bool = False
    timeout_seconds: int = 120
    top_n: int = 2000          # 每页条数
    days_back: int = 30         # 近一个月（最近 N 天）


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
    if "value" in payload and isinstance(payload["value"], list):
        return payload["value"]
    if isinstance(payload, list):
        return payload
    raise ValueError("Unexpected API payload shape: expected OData `value` array.")


def _since_iso(days_back: int) -> str:
    """近 N 天起点（UTC）。"""
    start = datetime.now(timezone.utc) - timedelta(days=days_back)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_latest_events(config: ApiConfig) -> list[dict[str, Any]]:
    """拉取近一个月（days_back 天）安灯原始事件；按页 $skip 拉全。"""
    since = _since_iso(config.days_back)
    # OData 时间过滤：begintime >= 近一个月起点
    filter_expr = f"begintime ge {since}"

    base_url = urljoin(f"{config.base_url}/", config.endpoint.lstrip("/"))
    page_size = config.top_n
    skip = 0
    all_records: list[dict[str, Any]] = []

    print(f"[step1] 存储方式: OData API（API Key），非直连数据库")
    print(f"[step1] 地址: {config.base_url}")
    print(f"[step1] 表/实体: {config.endpoint}")
    print(f"[step1] 鉴权头: {config.auth_header}")
    print(f"[step1] 时间范围: begintime >= {since}（近 {config.days_back} 天）")
    print(f"[step1] 分页大小: {page_size}")

    try:
        page_no = 0
        while True:
            page_no += 1
            params = {
                "$top": str(page_size),
                "$skip": str(skip),
                "$orderby": "begintime desc",
                "$filter": filter_expr,
            }
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{base_url}?{query_string}"
            print(f"[step1] 第 {page_no} 页: $skip={skip}")
            print(f"[step1] 请求: {url}")

            payload = _fetch_json(config, url)
            page = extract_records(payload)
            print(f"[step1] 本页 {len(page)} 条")
            all_records.extend(page)

            if len(page) < page_size:
                break
            skip += page_size

        print(f"[step1] 共拉取 {len(all_records)} 条原始记录（近 {config.days_back} 天）")
        return all_records
    except requests.exceptions.HTTPError as e:
        print(f"[step1] HTTP 错误: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"[step1] 状态码: {e.response.status_code}")
            print(f"[step1] 响应内容: {e.response.text[:500]}")
            print(
                "[step1] 若 $filter 报错，可尝试把时间格式改成: "
                "begintime ge datetime'YYYY-MM-DDTHH:MM:SS'"
            )
        raise
    except Exception as e:
        print(f"[step1] 拉取失败: {e}")
        raise


def project_core_fields(record: dict[str, Any]) -> dict[str, Any]:
    """按重要字段裁剪（字段名大小写不敏感）"""
    lower_map = {str(k).lower(): v for k, v in record.items()}
    return {field: lower_map.get(field) for field in CORE_FIELDS}


def save_raw(records: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    core_rows = [project_core_fields(row) for row in records]

    raw_file = output_dir / "andon_events_raw.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)
    print(f"[step1] 全量原始 JSON: {raw_file}")

    core_json = output_dir / "andon_events_core.json"
    with open(core_json, "w", encoding="utf-8") as f:
        json.dump(core_rows, f, ensure_ascii=False, indent=2, default=str)
    print(f"[step1] 核心字段 JSON: {core_json}")

    core_csv = output_dir / "andon_events_core.csv"
    with open(core_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CORE_FIELDS)
        writer.writeheader()
        writer.writerows(core_rows)
    print(f"[step1] 核心字段 CSV : {core_csv}")


def main():
    print("=" * 60)
    print("第一步：获取安灯原始数据")
    print("=" * 60)

    # ===== 请修改以下配置（保持你已跑通的参数）=====
    api_config = ApiConfig(
        base_url="https://gongsi.com:8092/andon",
        endpoint="o_d_andon_eventsrawdata_cur",
        api_key="zidingyi",
        auth_header="X-Api-Key",
        verify_ssl=False,
        top_n=2000,    # 每页条数
        days_back=30,   # 近一个月
    )
    # ===== 配置结束 =====

    output_dir = Path(r"C:\Users\CHJ1WUJ\personal\api_anything\output")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        raw_records = fetch_latest_events(api_config)
        if not raw_records:
            print("\n未拉取到任何数据")
            return

        sample = raw_records[0]
        print("\n[step1] 样例字段名:")
        for key in sample.keys():
            print(f"  - {key}")

        keys_lower = {str(k).lower() for k in sample.keys()}
        missing = [f for f in CORE_FIELDS if f not in keys_lower]
        hit = len(CORE_FIELDS) - len(missing)
        print(f"[step1] 重要字段命中: {hit}/{len(CORE_FIELDS)}")
        if missing:
            print("[step1] 缺失字段: " + ", ".join(missing))

        save_raw(raw_records, output_dir)

        print("\n" + "=" * 60)
        print(f"第一步完成：{len(raw_records)} 条原始数据 -> {output_dir}")
        print("=" * 60)

    except Exception as e:
        print(f"\n失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
