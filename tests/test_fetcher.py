"""单元测试：字段映射与 OData 分页。"""

from __future__ import annotations

from pathlib import Path

import responses

from andon_fetcher.config import AndonConfig, CORE_FIELDS
from andon_fetcher.field_mapper import canonicalize_record
from andon_fetcher.odata_client import ODataClient


def test_canonicalize_record_aliases() -> None:
    raw = {
        "LineName": "L1",
        "station_name": "ST-01",
        "FaultType": "设备故障",
        "EventName": "急停",
        "BeginTime": "2026-07-01T08:00:00Z",
        "IsChangeEquipment": True,
        "DownTimeDuration": 120,
        "@odata.etag": "W/\"1\"",
    }
    mapped = canonicalize_record(raw)
    assert mapped["linename"] == "L1"
    assert mapped["stationname"] == "ST-01"
    assert mapped["faulttype"] == "设备故障"
    assert mapped["eventsname"] == "急停"
    assert mapped["begintime"] == "2026-07-01T08:00:00Z"
    assert mapped["ischangequipment"] is True
    assert mapped["dowtimeduration"] == 120
    assert set(CORE_FIELDS).issubset(mapped.keys())


@responses.activate
def test_odata_pagination_with_next_link(tmp_path: Path) -> None:
    base = "https://example.com/odata"
    config = AndonConfig(
        base_url=base,
        entity_set="AndonEvents",
        api_key="test-key",
        api_key_mode="header_api_key",
        page_size=2,
        output_dir=tmp_path,
        select_fields=("linename", "begintime"),
    )

    responses.add(
        responses.GET,
        f"{base}/AndonEvents",
        json={
            "value": [
                {"linename": "A", "begintime": "t1"},
                {"linename": "B", "begintime": "t2"},
            ],
            "@odata.nextLink": f"{base}/AndonEvents?$skiptoken=abc",
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{base}/AndonEvents",
        json={"value": [{"linename": "C", "begintime": "t3"}]},
        status=200,
        match=[responses.matchers.query_param_matcher({"$skiptoken": "abc"})],
    )

    client = ODataClient(config)
    rows = list(client.iter_records())
    assert [r["linename"] for r in rows] == ["A", "B", "C"]
    assert responses.calls[0].request.headers.get("api-key") == "test-key"


@responses.activate
def test_skip_top_fallback_pagination(tmp_path: Path) -> None:
    base = "https://example.com/odata"
    config = AndonConfig(
        base_url=base,
        entity_set="AndonEvents",
        api_key="k",
        api_key_mode="header_x_api_key",
        page_size=2,
        output_dir=tmp_path,
        select_fields=("linename",),
    )

    responses.add(
        responses.GET,
        f"{base}/AndonEvents",
        json={"value": [{"linename": "1"}, {"linename": "2"}], "@odata.count": 3},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{base}/AndonEvents",
        json={"value": [{"linename": "3"}]},
        status=200,
    )

    client = ODataClient(config)
    rows = list(client.iter_records())
    assert len(rows) == 3
    assert responses.calls[0].request.headers.get("X-API-Key") == "k"
