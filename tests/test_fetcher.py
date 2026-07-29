"""单元测试：清洗与 OData 解析（不连公司内网）。"""

from __future__ import annotations

from pathlib import Path

import responses

from andon_fetcher.cleaner import AndonEventCleaner, deduplicate_records
from andon_fetcher.config import ApiConfig, CleanConfig, load_config
from andon_fetcher.fetch import extract_records, fetch_latest_events
from andon_fetcher.http_session import build_headers
from andon_fetcher.pipeline import clean_records, export_knowledge_base


def test_api_config_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for key in (
        "ANDON_ODATA_BASE_URL",
        "ANDON_ENDPOINT",
        "ANDON_ENTITY_SET",
        "ANDON_API_KEY",
        "ANDON_AUTH_HEADER",
        "ANDON_TOP_N",
    ):
        monkeypatch.delenv(key, raising=False)
    app = load_config()
    assert app.api.base_url == "https://gongsi.com:8092/andon"
    assert app.api.endpoint == "o_d_andon_eventsrawdata_cur"
    assert app.api.auth_header == "gongsi-Key"
    assert app.api.top_n == 2000
    assert app.api.verify_ssl is False


def test_build_headers_uses_gongsi_key() -> None:
    cfg = ApiConfig(api_key="api-key3", auth_header="gongsi-Key")
    headers = build_headers(cfg)
    assert headers["gongsi-Key"] == "api-key3"
    assert headers["User-Agent"] == "Mozilla/5.0"
    assert headers["Accept"] == "*/*"


def test_extract_records_odata_value() -> None:
    rows = extract_records({"value": [{"linename": "A1"}, {"linename": "B1"}]})
    assert len(rows) == 2


def test_cleaner_generates_chunk() -> None:
    cleaner = AndonEventCleaner(CleanConfig())
    cleaned = cleaner.clean_record(
        {
            "id": "1",
            "linename": "SMT-A线",
            "stationname": "op10",
            "faulttype": "光电异常",
            "eventsdescription": "光幕触发，传感器信号异常",
            "reactionplan": "检查光幕",
            "begintime": "2026-07-28T01:00:00Z",
            "eventsname": "光幕报警",
            "stationno": "10",
        }
    )
    assert cleaned is not None
    assert cleaned["linename"] == "SMT-A"
    assert "线体:SMT-A" in cleaned["chunk"]
    assert "光电" in cleaned["keywords"] or "光电异常" in cleaned["keywords"]


def test_dedup_and_export(tmp_path: Path) -> None:
    raw = [
        {
            "id": "1",
            "linename": "L1",
            "stationname": "S1",
            "faulttype": "机械异常",
            "eventsdescription": "卡料导致停机",
            "reactionplan": "清料",
            "begintime": "t1",
            "eventsname": "卡料",
            "stationno": "1",
        },
        {
            "id": "2",
            "linename": "L1",
            "stationname": "S1",
            "faulttype": "机械异常",
            "eventsdescription": "卡料导致停机",
            "reactionplan": "清料",
            "begintime": "t2",
            "eventsname": "卡料",
            "stationno": "1",
        },
    ]
    cleaned = clean_records(raw)
    unique = deduplicate_records(cleaned)
    assert len(unique) == 1
    paths = export_knowledge_base(unique, raw, tmp_path)
    assert paths["csv"].exists()
    assert paths["raw"].exists()
    assert "chunk" in paths["csv"].read_text(encoding="utf-8")


@responses.activate
def test_fetch_latest_events_orderby_top() -> None:
    base = "https://gongsi.com:8092/andon"
    responses.add(
        responses.GET,
        f"{base}/o_d_andon_eventsrawdata_cur",
        json={
            "value": [
                {"linename": "A", "begintime": "2026-07-28T02:00:00Z"},
                {"linename": "B", "begintime": "2026-07-28T01:00:00Z"},
            ]
        },
        status=200,
    )
    cfg = ApiConfig(
        base_url=base,
        endpoint="o_d_andon_eventsrawdata_cur",
        api_key="api-key3",
        auth_header="gongsi-Key",
        top_n=2000,
        verify_ssl=False,
    )
    rows = fetch_latest_events(cfg)
    assert len(rows) == 2
    req = responses.calls[0].request
    assert req.headers.get("gongsi-Key") == "api-key3"
    assert "%24top=2000" in req.url or "$top=2000" in req.url
    assert "begintime" in req.url
