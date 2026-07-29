"""与 fetch_andon_raw.py 对齐的测试。"""

from __future__ import annotations

from pathlib import Path

import responses

import fetch_andon_raw as raw


def test_core_fields_count() -> None:
    assert len(raw.CORE_FIELDS) == 23
    assert "linename" in raw.CORE_FIELDS
    assert "responseperson" in raw.CORE_FIELDS


def test_build_headers() -> None:
    cfg = raw.ApiConfig(api_key="api-key3", auth_header="gongsi-Key")
    headers = raw._build_headers(cfg)
    assert headers["gongsi-Key"] == "api-key3"
    assert headers["Accept"] == "*/*"


def test_extract_records() -> None:
    rows = raw.extract_records({"value": [{"linename": "A"}]})
    assert rows[0]["linename"] == "A"


def test_save_raw(tmp_path: Path) -> None:
    raw.save_raw([{"linename": "L1", "begintime": "t1", "foo": 1}], tmp_path)
    files = list(tmp_path.glob("*.csv"))
    assert files
    assert "linename" in files[0].read_text(encoding="utf-8-sig")


@responses.activate
def test_fetch_latest_events() -> None:
    base = "https://gongsi.com:8092/andon"
    responses.add(
        responses.GET,
        f"{base}/o_d_andon_eventsrawdata_cur",
        json={"value": [{"linename": "A", "begintime": "t1"}]},
        status=200,
    )
    cfg = raw.ApiConfig(
        base_url=base,
        endpoint="o_d_andon_eventsrawdata_cur",
        api_key="api-key3",
        auth_header="gongsi-Key",
        top_n=2000,
        verify_ssl=False,
    )
    rows = raw.fetch_latest_events(cfg)
    assert len(rows) == 1
    assert responses.calls[0].request.headers.get("gongsi-Key") == "api-key3"
