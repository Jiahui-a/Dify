"""测试：鉴权头与 401 提示。"""

from __future__ import annotations

from pathlib import Path

import pytest
import responses

import fetch_andon_raw as raw


def test_defaults_match_company_log() -> None:
    cfg = raw.ApiConfig()
    assert "wujlinvma016.apac.bosch.com" in cfg.base_url
    assert cfg.endpoint == "o_d_andon_eventsrawdata_cur"
    assert cfg.auth_header == "X-Api-Key"
    assert len(raw.CORE_FIELDS) == 23


def test_build_headers_x_api_key() -> None:
    cfg = raw.ApiConfig(api_key="secret-key", auth_header="X-Api-Key")
    headers = raw._build_headers(cfg)
    assert headers["X-Api-Key"] == "secret-key"


@responses.activate
def test_401_raises_permission_error() -> None:
    base = "https://wujlinvma016.apac.bosch.com:8092/andon"
    responses.add(
        responses.GET,
        f"{base}/o_d_andon_eventsrawdata_cur",
        json={
            "message": "API Key is not valid or is expired / revoked.",
            "http_status_code": 401,
        },
        status=401,
    )
    cfg = raw.ApiConfig(
        base_url=base,
        api_key="bad-key",
        auth_header="X-Api-Key",
        top_n=1,
    )
    with pytest.raises(PermissionError, match="401"):
        raw.fetch_latest_events(cfg)


@responses.activate
def test_fetch_ok_and_save(tmp_path: Path) -> None:
    base = "https://wujlinvma016.apac.bosch.com:8092/andon"
    responses.add(
        responses.GET,
        f"{base}/o_d_andon_eventsrawdata_cur",
        json={"value": [{"linename": "A", "begintime": "t1", "eventsname": "e"}]},
        status=200,
    )
    cfg = raw.ApiConfig(
        base_url=base, api_key="good", auth_header="X-Api-Key", top_n=2000
    )
    rows = raw.fetch_latest_events(cfg)
    assert rows[0]["linename"] == "A"
    assert responses.calls[0].request.headers.get("X-Api-Key") == "good"
    raw.save_raw(rows, tmp_path)
    assert list(tmp_path.glob("*.csv"))
