"""命令行入口。"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# 未 pip install 时把仓库根目录加入 path
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import click

from andon_fetcher.config import load_config
from andon_fetcher.fetch import fetch_latest_events
from andon_fetcher.pipeline import run_pipeline


@click.group()
def cli() -> None:
    """安灯 OData 拉取 + Dify 知识库清洗导出。"""


@cli.command("probe")
@click.option("--env-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--top", type=int, default=1, show_default=True, help="试拉条数")
def probe(env_file: str | None, top: int) -> None:
    """试拉几条，确认鉴权与字段。"""
    app = load_config(env_file)
    app.api.top_n = top
    click.echo(f"URL        : {app.api.entity_url}")
    click.echo(f"Auth header: {app.api.auth_header}")
    click.echo(f"Verify SSL : {app.api.verify_ssl}")
    try:
        rows = fetch_latest_events(app.api)
    except Exception as exc:
        click.echo(f"试拉失败: {exc}", err=True)
        traceback.print_exc()
        sys.exit(1)
    if not rows:
        click.echo("返回为空")
        return
    click.echo("样例字段:")
    for key in rows[0].keys():
        click.echo(f"  - {key}")
    import json

    click.echo(json.dumps(rows[0], ensure_ascii=False, indent=2, default=str)[:2000])


@cli.command("fetch")
@click.option("--env-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--top", type=int, default=None, help="覆盖 ANDON_TOP_N，默认 2000")
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="输出目录，默认 ./output",
)
def fetch(env_file: str | None, top: int | None, output_dir: str | None) -> None:
    """拉取最新 N 条，清洗后生成 Dify 知识库 CSV/JSON。"""
    app = load_config(env_file)
    if top is not None:
        app.api.top_n = top
    if output_dir:
        app.output_dir = Path(output_dir)
    try:
        run_pipeline(app)
    except Exception as exc:
        click.echo(f"失败: {exc}", err=True)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
