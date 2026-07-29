"""安灯事件清洗：生成 Dify 知识库字段。"""

from __future__ import annotations

import re
from typing import Any, Optional

from andon_fetcher.config import CleanConfig


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
            desc = record.get("eventsdescription", "") or ""
            if desc:
                faulttype = self._generate_fault_code(str(desc))
            else:
                return None

        stationname = self._clean_stationname(record.get("stationname", ""))
        eventsdesc = self._clean_description(
            record.get("eventsdescription", "")
            or record.get("eventsname", "")
            or "未知故障"
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
            "keywords": "/".join(keywords[: self.config.max_keywords]),
            "begintime": record.get("begintime", ""),
            "stationno": record.get("stationno", ""),
            "eventsname": record.get("eventsname", ""),
            "original_id": record.get("id", ""),
        }

    def _clean_linename(self, value: Any) -> str:
        if not value or str(value).strip() in self.invalid_values:
            return ""
        value = str(value).strip().upper()
        value = re.sub(r"线$", "", value)
        value = re.sub(r"[^\w\-]", "", value)
        return value

    def _clean_faulttype(self, value: Any) -> str:
        if not value or str(value).strip() in self.invalid_values:
            return ""
        value = str(value).strip().upper()
        value = re.sub(r"\s+", "_", value)
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
        value = re.sub(r"\s+", " ", value)
        if len(value) > self.config.max_desc_length:
            value = value[: self.config.max_desc_length] + "..."
        return value

    def _clean_plan(self, value: Any) -> str:
        if not value or str(value).strip() in self.invalid_values:
            return "暂无处理方案"
        value = str(value).strip()
        if len(value) > self.config.max_plan_length:
            value = value[: self.config.max_plan_length] + "..."
        return value

    def _extract_keywords(self, text: str) -> list[str]:
        keywords: set[str] = set()
        for keyword, patterns in self.synonym_map.items():
            if any(p in text for p in patterns):
                keywords.add(keyword)
        if not keywords:
            short = text[:10]
            if short:
                keywords.add(short)
        return list(keywords)[: self.config.max_keywords]

    def _build_chunk(
        self,
        linename: str,
        stationname: str,
        faulttype: str,
        keywords: list[str],
        description: str,
    ) -> str:
        parts = [f"线体:{linename}"]
        if stationname:
            parts.append(f"工站:{stationname}")
        if faulttype:
            parts.append(f"故障码:{faulttype}")
        if keywords:
            parts.append(f"现象:{'/'.join(keywords[: self.config.max_keywords])}")
        parts.append(f"描述:{description}")
        chunk = " | ".join(parts)
        if len(chunk) > self.config.chunk_max_length:
            chunk = chunk[: self.config.chunk_max_length]
        return chunk


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in records:
        key = f"{item['linename']}_{item['faulttype']}_{item['eventsdescription'][:15]}"
        if key not in seen:
            seen.add(key)
            unique.append(item)
    print(f"[dedup] 去重前: {len(records)} 条，去重后: {len(unique)} 条")
    return unique


def print_statistics(records: list[dict[str, Any]]) -> None:
    if not records:
        return
    print("\n" + "=" * 60)
    print("数据统计")
    print("=" * 60)

    dates = [item.get("begintime", "") for item in records if item.get("begintime")]
    if dates:
        print(f"日期范围: {min(dates)} ~ {max(dates)}")

    line_counts: dict[str, int] = {}
    for item in records:
        line = item.get("linename", "未知") or "未知"
        line_counts[line] = line_counts.get(line, 0) + 1
    print(f"总记录数: {len(records)}")
    print(f"涉及的线体数: {len(line_counts)}")

    print("\n线体分布 Top 10:")
    sorted_lines = sorted(line_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (line, count) in enumerate(sorted_lines[:10], 1):
        print(f"   {i}. {line}: {count} 条")

    fault_counts: dict[str, int] = {}
    for item in records:
        fault = item.get("faulttype", "未知") or "未知"
        fault_counts[fault] = fault_counts.get(fault, 0) + 1
    print(f"\n故障类型数: {len(fault_counts)}")
    sorted_faults = sorted(fault_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (fault, count) in enumerate(sorted_faults[:5], 1):
        print(f"   {i}. {fault}: {count} 条")
