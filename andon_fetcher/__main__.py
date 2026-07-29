"""第一步：安灯原始数据拉取（与 fetch_andon_raw.py 同逻辑）。"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import click

# 直接复用根目录单文件脚本，避免两套实现
import fetch_andon_raw as raw


@click.group()
def cli() -> None:
    """第一步：获取安灯原始数据。"""


@cli.command("run")
def run() -> None:
    """等同于: python fetch_andon_raw.py"""
    raw.main()


@cli.command("probe")
@click.option("--top", default=1, show_default=True)
def probe(top: int) -> None:
    """只试拉 N 条并打印字段。"""
    cfg = raw.ApiConfig(
        base_url="https://gongsi.com:8092/andon",
        endpoint="o_d_andon_eventsrawdata_cur",
        api_key="api-key3",
        auth_header="gongsi-Key",
        verify_ssl=False,
        top_n=top,
    )
    rows = raw.fetch_latest_events(cfg)
    if not rows:
        click.echo("空结果")
        return
    for key in rows[0].keys():
        click.echo(f"  - {key}")


@cli.command("fetch")
def fetch() -> None:
    """拉取并保存原始数据。"""
    raw.main()


if __name__ == "__main__":
    cli()
