"""字段归一化：将 OData 返回字段映射到约定的核心字段名。"""

from __future__ import annotations

from typing import Any

from andon_fetcher.config import CORE_FIELDS


def _normalize_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


# 常见别名 -> 标准字段
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for field in CORE_FIELDS:
    _ALIAS_TO_CANONICAL[_normalize_key(field)] = field

# 补充常见拼写/大小写/业务别名
_EXTRA_ALIASES = {
    "line": "linename",
    "linename": "linename",
    "line_name": "linename",
    "station": "stationname",
    "station_name": "stationname",
    "fault_type": "faulttype",
    "faulttypename": "faulttype",
    "eventname": "eventsname",
    "event_name": "eventsname",
    "events_name": "eventsname",
    "begin_time": "begintime",
    "starttime": "begintime",
    "start_time": "begintime",
    "response_time": "responsetime",
    "end_time": "endtime",
    "confirm_time": "confirmtime",
    "reaction_plan": "reactionplan",
    "action": "actions",
    "is_change_parameter": "ischangeparameter",
    "parameter_name": "parametername",
    "old_value": "oldvalue",
    "new_value": "newvalue",
    # 原始字段名本身就是 ischangequipment（拼写保持业务约定）
    "ischangeequipment": "ischangequipment",
    "is_change_equipment": "ischangequipment",
    "is_change_quipment": "ischangequipment",
    "change_event_desc": "changeeventdesc",
    "equipment_pn": "equipmentpn",
    "response_duration": "responseduration",
    "repair_duration": "repairduration",
    "downtime_duration": "dowtimeduration",
    "downtimeduration": "dowtimeduration",
    "close_person": "closeperson",
    "response_person": "responseperson",
}
for alias, canonical in _EXTRA_ALIASES.items():
    _ALIAS_TO_CANONICAL[_normalize_key(alias)] = canonical


def canonicalize_record(raw: dict[str, Any], *, keep_unknown: bool = False) -> dict[str, Any]:
    """
    将一条原始 OData 记录映射为标准字段字典。

    - 大小写不敏感
    - 忽略下划线/连字符差异
    - 标准字段缺失时填 None
    - keep_unknown=True 时保留未映射字段（加 raw_ 前缀避免冲突）
    """
    mapped: dict[str, Any] = {field: None for field in CORE_FIELDS}
    unknown: dict[str, Any] = {}

    for key, value in raw.items():
        if key.startswith("@odata") or key.startswith("odata."):
            continue
        canonical = _ALIAS_TO_CANONICAL.get(_normalize_key(key))
        if canonical:
            mapped[canonical] = value
        elif keep_unknown:
            unknown[f"raw_{key}"] = value

    if keep_unknown:
        mapped.update(unknown)
    return mapped


def canonicalize_records(
    rows: list[dict[str, Any]], *, keep_unknown: bool = False
) -> list[dict[str, Any]]:
    return [canonicalize_record(row, keep_unknown=keep_unknown) for row in rows]
