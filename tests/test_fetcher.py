"""单元测试：字段映射与 OData 分页。"""

from __future__ import annotations

from pathlib import Path

import responses

from andon_fetcher.config import ApiConfig, CORE_FIELDS, load_config
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


def test_api_config_defaults_and_aliases(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANDON_ODATA_BASE_URL", raising=False)
    monkeypatch.delenv("ANDON_ENTITY_SET", raising=False)
    monkeypatch.delenv("ANDON_ENDPOINT", raising=False)
    monkeypatch.delenv("ANDON_API_KEY", raising=False)
    # 无 .env 时使用 ApiConfig 默认值
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.base_url == "https://gongsi.com:8092/andon"
    assert config.endpoint == "o_d_andon_eventsrawdata_cur"
    assert config.entity_set == "o_d_andon_eventsrawdata_cur"
    assert config.auth_header == "ABC"
    assert config.page_size == config.top_n == 500
    assert config.verify_ssl is False
    assert config.timeout_seconds == 120
    assert config.entity_url.endswith("/andon/o_d_andon_eventsrawdata_cur")


@responses.activate
def test_company_auth_header_abc(tmp_path: Path) -> None:
    base = "https://gongsi.com:8092/andon"
    config = ApiConfig(
        base_url=base,
        endpoint="o_d_andon_eventsrawdata_cur",
        api_key="SECRET",
        auth_header="ABC",
        user_agent="Mozilla/5.0",
        verify_ssl=False,
        top_n=2,
        output_dir=tmp_path,
        select_fields=("linename", "begintime"),
    )

    responses.add(
        responses.GET,
        f"{base}/o_d_andon_eventsrawdata_cur",
        json={"value": [{"linename": "A", "begintime": "t1"}]},
        status=200,
    )

    client = ODataClient(config)
    rows = list(client.iter_records())
    assert rows[0]["linename"] == "A"
    req = responses.calls[0].request
    assert req.headers.get("ABC") == "SECRET"
    assert req.headers.get("User-Agent") == "Mozilla/5.0"


@responses.activate
def test_odata_pagination_with_next_link(tmp_path: Path) -> None:
    base = "https://example.com/odata"
    config = ApiConfig(
        base_url=base,
        endpoint="AndonEvents",
        api_key="test-key",
        api_key_mode="header_api_key",
        top_n=2,
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
    config = ApiConfig(
        base_url=base,
        endpoint="AndonEvents",
        api_key="k",
        api_key_mode="header_x_api_key",
        top_n=2,
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
