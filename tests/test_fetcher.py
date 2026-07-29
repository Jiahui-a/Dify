"""第一步：原始数据拉取相关测试。"""

from __future__ import annotations

from pathlib import Path

import responses

from andon_fetcher.config import CORE_FIELDS, ApiConfig, load_config
from andon_fetcher.fetch import extract_records, fetch_raw_events, project_core_fields
from andon_fetcher.http_session import build_headers
from andon_fetcher.raw_export import save_raw


def test_step1_config_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for key in (
        "ANDON_ODATA_BASE_URL",
        "ANDON_ENDPOINT",
        "ANDON_ENTITY_SET",
        "ANDON_API_KEY",
        "ANDON_AUTH_HEADER",
        "ANDON_TOP_N",
        "ANDON_OUTPUT_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    app = load_config()
    assert app.api.endpoint == "o_d_andon_eventsrawdata_cur"
    assert app.api.auth_header == "gongsi-Key"
    assert app.output_dir == Path("./data/raw")
    assert "linename" in CORE_FIELDS
    assert "responseperson" in CORE_FIELDS
    assert len(CORE_FIELDS) == 23


def test_build_headers() -> None:
    headers = build_headers(ApiConfig(api_key="api-key3", auth_header="gongsi-Key"))
    assert headers["gongsi-Key"] == "api-key3"


def test_project_core_fields_case_insensitive() -> None:
    raw = {
        "LineName": "L1",
        "StationName": "OP10",
        "FaultType": "设备",
        "EventsName": "急停",
        "BeginTime": "t1",
        "extra": "ignore-me",
    }
    projected = project_core_fields(raw)
    assert projected["linename"] == "L1"
    assert projected["stationname"] == "OP10"
    assert projected["eventsname"] == "急停"
    assert set(projected.keys()) == set(CORE_FIELDS)
    assert "extra" not in projected


def test_extract_and_save(tmp_path: Path) -> None:
    rows = extract_records(
        {
            "value": [
                {
                    "linename": "A",
                    "stationname": "S1",
                    "faulttype": "F",
                    "eventsname": "E",
                    "begintime": "t",
                }
            ]
        }
    )
    paths = save_raw(rows, tmp_path)
    assert paths["core_csv"].exists()
    text = paths["core_csv"].read_text(encoding="utf-8-sig")
    assert "linename" in text
    assert "A" in text


@responses.activate
def test_fetch_raw_events_selects_core_fields() -> None:
    base = "https://gongsi.com:8092/andon"
    responses.add(
        responses.GET,
        f"{base}/o_d_andon_eventsrawdata_cur",
        json={"value": [{"linename": "A", "begintime": "t1"}]},
        status=200,
    )
    cfg = ApiConfig(
        base_url=base,
        endpoint="o_d_andon_eventsrawdata_cur",
        api_key="api-key3",
        auth_header="gongsi-Key",
        top_n=2000,
        use_select=True,
    )
    rows = fetch_raw_events(cfg)
    assert len(rows) == 1
    req = responses.calls[0].request
    assert req.headers.get("gongsi-Key") == "api-key3"
    assert "linename" in req.url
    assert "%24top=2000" in req.url or "$top=2000" in req.url
