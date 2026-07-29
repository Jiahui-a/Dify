"""
Fetch latest 2000 Andon events from OData API.
拉取最新2000条安灯事件数据，清洗后生成 Dify 知识库 CSV
"""

import json
import ssl
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Dict, Optional, Set
from urllib.parse import urljoin

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# 内网自签证书时关闭校验会触发警告，此处静默
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 禁用代理，防止内网请求走公司外网代理
NO_PROXY = {"http": None, "https": None}


# ========== 配置类 ==========
@dataclass
class ApiConfig:
    """API 配置"""
    base_url: str = "https://gongsi.com:8092/andon"
    endpoint: str = "o_d_andon_eventsrawdata_cur"
    api_key: str = "API_KEY"
    auth_header: str = "X-Api-Key"
    user_agent: str = "Mozilla/5.0"
    verify_ssl: bool = False
    timeout_seconds: int = 120
    top_n: int = 2000


@dataclass
class CleanConfig:
    """清洗配置"""
    max_desc_length: int = 80
    max_plan_length: int = 60
    max_keywords: int = 3
    chunk_max_length: int = 150


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
        "$orderby": "begintime desc"
    }

    base_url = urljoin(f"{config.base_url}/", config.endpoint.lstrip("/"))
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"{base_url}?{query_string}"

    print(f"[fetch] 🔄 请求: {url}")
    print(f"[fetch] 📦 拉取最新 {config.top_n} 条数据")

    try:
        payload = _fetch_json(config, url)
        records = extract_records(payload)
        print(f"[fetch] ✅ 共拉取 {len(records)} 条安灯事件记录")
        return records
    except requests.exceptions.HTTPError as e:
        print(f"[fetch] ❌ HTTP 错误: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"[fetch] 状态码: {e.response.status_code}")
            print(f"[fetch] 响应内容: {e.response.text[:500]}")
        raise
    except Exception as e:
        print(f"[fetch] ❌ 拉取失败: {e}")
        raise


# ========== 数据清洗类 ==========
class AndonEventCleaner:
    """安灯事件数据清洗器"""

    def __init__(self, clean_config: CleanConfig):
        self.config = clean_config
        self.synonym_map = {
            "光电异常": ["光电", "光幕", "传感器", "信号", "灯", "检测", "感应"],
            "压力异常": ["压力", "超限", "过载", "压装", "加压", "保压", "过压"],
            "扫码异常": ["扫码", "条码", "二维码", "读码", "扫描", "识别"],
            "印刷异常": ["锡", "焊", "印刷", "钢网", "刮刀", "锡膏", "少锡", "缺锡"],
            "通讯异常": ["通讯", "网络", "连接", "超时", "断连"],
            "电气异常": ["电气", "电路", "电源", "电压", "电流", "短路", "断电"],
            "机械异常": ["机械", "卡住", "卡死", "卡料", "撞机", "磨损"],
            "软件异常": ["软件", "程序", "PLC", "系统", "死机", "重启"],
            "温度异常": ["温度", "过热", "高温", "冷却"],
            "物料异常": ["物料", "来料", "材料", "原料", "缺料"],
        }
        self.invalid_values = {"", "string", "null", "None", "undefined", " "}

    def clean_record(self, record: dict[str, Any]) -> Optional[dict[str, Any]]:
        linename = self._clean_linename(record.get("linename", ""))
        if not linename:
            return None

        faulttype = self._clean_faulttype(record.get("faulttype", ""))
        if not faulttype:
            desc = record.get("eventsdescription", "")
            if desc:
                faulttype = self._generate_fault_code(desc)
            else:
                return None

        stationname = self._clean_stationname(record.get("stationname", ""))
        eventsdesc = self._clean_description(
            record.get("eventsdescription", "") or record.get("eventsname", "") or "未知故障"
        )
        reactionplan = self._clean_plan(record.get("reactionplan", ""))
        keywords = self._extract_keywords(eventsdesc)
        if not keywords:
            keywords = [eventsdesc[:10]]
        chunk = self._build_chunk(linename, stationname, faulttype, keywords, eventsdesc)

        return {
            "chunk": chunk,
            "linename": linename,
            "stationname": stationname,
            "faulttype": faulttype,
            "eventsdescription": eventsdesc,
            "reactionplan": reactionplan,
            "keywords": "/".join(keywords[:self.config.max_keywords]),
            "begintime": record.get("begintime", ""),
            "stationno": record.get("stationno", ""),
            "eventsname": record.get("eventsname", ""),
            "original_id": record.get("id", "")
        }

    def _clean_linename(self, value: Any) -> str:
        if not value or str(value).strip() in self.invalid_values:
            return ""
        value = str(value).strip().upper()
        value = re.sub(r'线$', '', value)
        value = re.sub(r'[^\w\-]', '', value)
        return value

    def _clean_faulttype(self, value: Any) -> str:
        if not value or str(value).strip() in self.invalid_values:
            return ""
        value = str(value).strip().upper()
        value = re.sub(r'\s+', '_', value)
        return value

    def _generate_fault_code(self, description: str) -> str:
        for fault_type, patterns in self.synonym_map.items():
            if any(p in description for p in patterns):
                return fault_type.upper().replace("异常", "_ERR")
        return "UNKNOWN_ERR"

    def _clean_stationname(self, value: Any) -> str:
        if not value or str(value).strip() in self.invalid_values:
            return ""
        return str(value).strip().upper()

    def _clean_description(self, value: Any) -> str:
        if not value or str(value).strip() in self.invalid_values:
            return "未知故障"
        value = str(value).strip()
        value = re.sub(r'\s+', ' ', value)
        if len(value) > self.config.max_desc_length:
            value = value[:self.config.max_desc_length] + "..."
        return value

    def _clean_plan(self, value: Any) -> str:
        if not value or str(value).strip() in self.invalid_values:
            return "暂无处理方案"
        value = str(value).strip()
        if len(value) > self.config.max_plan_length:
            value = value[:self.config.max_plan_length] + "..."
        return value

    def _extract_keywords(self, text: str) -> List[str]:
        keywords = set()
        for keyword, patterns in self.synonym_map.items():
            if any(p in text for p in patterns):
                keywords.add(keyword)
        if not keywords:
            short = text[:10]
            if short:
                keywords.add(short)
        return list(keywords)[:self.config.max_keywords]

    def _build_chunk(self, linename: str, stationname: str, faulttype: str,
                     keywords: List[str], description: str) -> str:
        parts = [f"线体:{linename}"]
        if stationname:
            parts.append(f"工站:{stationname}")
        if faulttype:
            parts.append(f"故障码:{faulttype}")
        if keywords:
            parts.append(f"现象:{'/'.join(keywords[:self.config.max_keywords])}")
        parts.append(f"描述:{description}")
        chunk = " | ".join(parts)
        if len(chunk) > self.config.chunk_max_length:
            chunk = chunk[:self.config.chunk_max_length]
        return chunk


# ========== 去重 ==========
def deduplicate_records(records: List[dict[str, Any]]) -> List[dict[str, Any]]:
    seen: Set[str] = set()
    unique = []
    for item in records:
        key = f"{item['linename']}_{item['faulttype']}_{item['eventsdescription'][:15]}"
        if key not in seen:
            seen.add(key)
            unique.append(item)
    print(f"[dedup] 去重前: {len(records)} 条，去重后: {len(unique)} 条")
    return unique


# ========== 统计 ==========
def print_statistics(records: List[dict[str, Any]]):
    if not records:
        return
    print("\n" + "=" * 60)
    print("📊 数据统计")
    print("=" * 60)

    dates = [item.get("begintime", "") for item in records if item.get("begintime")]
    if dates:
        print(f"日期范围: {min(dates)} ~ {max(dates)}")

    line_counts = {}
    for item in records:
        line = item.get("linename", "未知")
        line_counts[line] = line_counts.get(line, 0) + 1
    print(f"总记录数: {len(records)}")
    print(f"涉及的线体数: {len(line_counts)}")

    print("\n📋 线体分布 Top 10:")
    sorted_lines = sorted(line_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (line, count) in enumerate(sorted_lines[:10], 1):
        print(f"   {i}. {line}: {count} 条")

    fault_counts = {}
    for item in records:
        fault = item.get("faulttype", "未知")
        fault_counts[fault] = fault_counts.get(fault, 0) + 1
    print(f"\n🔧 故障类型数: {len(fault_counts)}")
    sorted_faults = sorted(fault_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (fault, count) in enumerate(sorted_faults[:5], 1):
        print(f"   {i}. {fault}: {count} 条")


# ========== 主函数 ==========
def main():
    print("=" * 60)
    print("🔍 拉取最新安灯事件数据")
    print("=" * 60)

    # ===== 请修改以下配置 =====
    api_config = ApiConfig(
        base_url="https://gongsi.com:8092/andon",
        endpoint="o_d_andon_eventsrawdata_cur",
        api_key="zidingyi",
        verify_ssl=False,
        top_n=2000,
    )
    # ===== 配置结束 =====

    clean_config = CleanConfig()
    cleaner = AndonEventCleaner(clean_config)

    output_dir = Path(r"C:\Users\CHJ1WUJ\personal\api_anything\output")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        raw_records = fetch_latest_events(api_config)

        if not raw_records:
            print("\n⚠️ 未拉取到任何数据")
            return

        print("\n[clean] 🧹 开始清洗...")
        cleaned_records = []
        skipped = 0
        for record in raw_records:
            cleaned = cleaner.clean_record(record)
            if cleaned:
                cleaned_records.append(cleaned)
            else:
                skipped += 1
        print(f"[clean] ✅ 保留 {len(cleaned_records)} 条，跳过 {skipped} 条")

        unique_records = deduplicate_records(cleaned_records)
        print_statistics(unique_records)

        # 保存 CSV
        csv_file = output_dir / "andon_events_knowledge_base.csv"
        if unique_records:
            fieldnames = ["chunk", "linename", "stationname", "faulttype",
                         "eventsdescription", "reactionplan", "keywords",
                         "begintime", "stationno", "eventsname", "original_id"]
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerows(unique_records)
            print(f"\n✅ CSV: {csv_file} ({len(unique_records)} 条)")

        # 保存 JSON
        json_file = output_dir / "andon_events_cleaned.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(unique_records, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON: {json_file}")

        # 保存 Chunk 文本
        chunk_file = output_dir / "chunks_only.txt"
        with open(chunk_file, "w", encoding="utf-8") as f:
            for item in unique_records:
                f.write(item["chunk"] + "\n")
        print(f"✅ Chunk文本: {chunk_file}")

        # 线体字典
        lines = sorted(set(item["linename"] for item in unique_records if item["linename"]))
        line_dict_file = output_dir / "line_dict.json"
        with open(line_dict_file, "w", encoding="utf-8") as f:
            json.dump(lines, f, ensure_ascii=False, indent=2)
        print(f"✅ 线体字典: {line_dict_file} (共 {len(lines)} 个)")

        # 原始数据
        raw_file = output_dir / "andon_events_raw.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(raw_records, f, ensure_ascii=False, indent=2)
        print(f"✅ 原始数据: {raw_file}")

        print("\n" + "=" * 60)
        print("📘 导入 Dify 知识库")
        print("=" * 60)
        print(f"上传文件: {csv_file}")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
