"""命令行：第一步获取安灯原始数据。"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import click

from andon_fetcher.config import CORE_FIELDS, load_config
from andon_fetcher.fetch import fetch_raw_events, project_core_fields
from andon_fetcher.raw_export import run_step1


@click.group()
def cli() -> None:
    """第一步：从公司安灯 OData API 拉取原始数据。"""


@cli.command("probe")
@click.option("--env-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--top", type=int, default=1, show_default=True)
def probe(env_file: str | None, top: int) -> None:
    """试拉，确认连接与字段是否包含核心字段。"""
    app = load_config(env_file)
    app.api.top_n = top
    click.echo(f"存储方式 : OData API（API Key）")
    click.echo(f"地址     : {app.api.base_url}")
    click.echo(f"表/实体  : {app.api.endpoint}")
    click.echo(f"鉴权头   : {app.api.auth_header}")
    try:
        rows = fetch_raw_events(app.api)
    except Exception as exc:
        click.echo(f"试拉失败: {exc}", err=True)
        traceback.print_exc()
        sys.exit(1)
    if not rows:
        click.echo("返回为空")
        return

    keys = {str(k).lower() for k in rows[0].keys()}
    click.echo("返回字段:")
    for key in rows[0].keys():
        click.echo(f"  - {key}")

    missing = [f for f in CORE_FIELDS if f.lower() not in keys]
    present = [f for f in CORE_FIELDS if f.lower() in keys]
    click.echo(f"\n核心字段命中: {len(present)}/{len(CORE_FIELDS)}")
    if missing:
        click.echo("缺失核心字段: " + ", ".join(missing))
    click.echo("\n样例（核心字段）:")
    click.echo(json.dumps(project_core_fields(rows[0]), ensure_ascii=False, indent=2, default=str))


@cli.command("fetch")
@click.option("--env-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--top", type=int, default=None, help="覆盖 ANDON_TOP_N")
@click.option("--output-dir", type=click.Path(file_okay=False), default=None)
@click.option("--no-select", is_flag=True, default=False, help="不传 $select，拉全字段后本地裁剪")
def fetch(
    env_file: str | None,
    top: int | None,
    output_dir: str | None,
    no_select: bool,
) -> None:
    """拉取原始数据并保存到 data/raw（JSON + CSV）。"""
    app = load_config(env_file)
    if top is not None:
        app.api.top_n = top
    if output_dir:
        app.output_dir = Path(output_dir)
    if no_select:
        app.api.use_select = False
    try:
        run_step1(app)
    except Exception as exc:
        click.echo(f"失败: {exc}", err=True)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
