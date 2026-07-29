"""第一步：获取安灯原始数据（调用根目录脚本）。"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import click

import fetch_andon_raw as raw


@click.group()
def cli() -> None:
    """第一步：从公司安灯 OData API 拉取原始数据。"""


@cli.command("probe")
@click.option("--top", default=1, show_default=True)
def probe(top: int) -> None:
    """试拉 N 条，确认鉴权与字段。"""
    cfg = raw.ApiConfig(
        base_url="https://wujlinvma016.apac.bosch.com:8092/andon",
        endpoint="o_d_andon_eventsrawdata_cur",
        api_key="在这里填入有效的API_KEY",
        auth_header="X-Api-Key",
        verify_ssl=False,
        top_n=top,
    )
    # 若用户已在脚本 main 里改过 key，优先读脚本内默认类字段无法拿到；
    # 直接提示去改 fetch_andon_raw.py，或传环境变量 ANDON_API_KEY。
    import os

    env_key = os.getenv("ANDON_API_KEY", "").strip()
    if env_key:
        cfg.api_key = env_key
    env_header = os.getenv("ANDON_AUTH_HEADER", "").strip()
    if env_header:
        cfg.auth_header = env_header
    env_base = os.getenv("ANDON_ODATA_BASE_URL", "").strip()
    if env_base:
        cfg.base_url = env_base

    click.echo(f"存储方式 : OData API（API Key）")
    click.echo(f"地址     : {cfg.base_url}")
    click.echo(f"表/实体  : {cfg.endpoint}")
    click.echo(f"鉴权头   : {cfg.auth_header}")

    if cfg.api_key in {"在这里填入有效的API_KEY", "API_KEY", "api-key3", ""}:
        click.echo(
            "\nAPI Key 未配置或仍是占位符。\n"
            "请设置环境变量 ANDON_API_KEY，或改 fetch_andon_raw.py 里的 api_key。\n"
            "401 的含义是：Key 无效/过期/已吊销（不是连接失败）。",
            err=True,
        )
        sys.exit(1)

    try:
        rows = raw.fetch_latest_events(cfg)
    except Exception as exc:
        click.echo(f"试拉失败: {exc}", err=True)
        sys.exit(1)

    if not rows:
        click.echo("返回为空")
        return
    click.echo("样例字段:")
    for key in rows[0].keys():
        click.echo(f"  - {key}")


@cli.command("fetch")
def fetch() -> None:
    """拉取并保存原始数据（等同 python fetch_andon_raw.py）。"""
    raw.main()


if __name__ == "__main__":
    cli()
