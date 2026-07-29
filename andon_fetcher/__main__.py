"""命令行入口：拉取安灯 OData 原始数据。"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# 未 pip install 时，把仓库根目录加入 sys.path，避免 ModuleNotFoundError
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import click

from andon_fetcher.config import load_config
from andon_fetcher.exporter import save_csv, save_json
from andon_fetcher.field_mapper import canonicalize_records
from andon_fetcher.odata_client import ODataClient, ODataClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("andon_fetcher")


@click.group()
def cli() -> None:
    """安灯原始数据工具（OData + API Key）。"""


@cli.command("probe")
@click.option("--env-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--save-metadata", type=click.Path(dir_okay=False), default=None, help="保存 $metadata XML")
def probe(env_file: str | None, save_metadata: str | None) -> None:
    """探测服务：拉取 $metadata，并试拉 1 条记录，打印字段名。"""
    config = load_config(env_file)
    client = ODataClient(config)

    click.echo(f"Base URL    : {config.base_url}")
    click.echo(f"Endpoint    : {config.endpoint}")
    click.echo(f"Auth header : {config.auth_header} (mode={config.api_key_mode})")
    click.echo(f"User-Agent  : {config.user_agent}")
    click.echo(f"Verify SSL  : {config.verify_ssl}")

    try:
        metadata = client.get_metadata()
        click.echo(f"$metadata OK, length={len(metadata)}")
        if save_metadata:
            Path(save_metadata).write_text(metadata, encoding="utf-8")
            click.echo(f"已保存 metadata -> {save_metadata}")
    except ODataClientError as exc:
        click.echo(f"$metadata 不可用（部分网关会关闭）: {exc}", err=True)

    try:
        payload = client.fetch_page(top=1, select=None, filter_expr=config.odata_filter)
        rows = client._extract_value(payload)
        if not rows:
            click.echo("试拉成功，但 value 为空（可能无数据或 filter 过严）。")
            return
        sample = rows[0]
        click.echo("样例字段名:")
        for key in sample.keys():
            click.echo(f"  - {key}")
        click.echo("样例 JSON:")
        click.echo(json.dumps(sample, ensure_ascii=False, indent=2, default=str)[:2000])
    except ODataClientError as exc:
        click.echo(f"试拉失败: {exc}", err=True)
        sys.exit(1)


@cli.command("fetch")
@click.option("--env-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--max-records", type=int, default=None, help="最多拉取条数（调试用）")
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "both"]), default="both")
@click.option("--raw/--normalized", default=False, help="导出原始字段或归一化到核心字段")
@click.option("--keep-unknown", is_flag=True, default=False, help="归一化时保留未知字段")
@click.option("--no-select", is_flag=True, default=False, help="不传 $select，拉取实体全部字段")
@click.option("--filter", "filter_expr", default=None, help="覆盖 ANDON_FILTER 的 $filter")
def fetch(
    env_file: str | None,
    max_records: int | None,
    fmt: str,
    raw: bool,
    keep_unknown: bool,
    no_select: bool,
    filter_expr: str | None,
) -> None:
    """从公司安灯 OData 接口拉取原始数据并落盘。"""
    config = load_config(env_file)
    client = ODataClient(config)

    select = None if no_select or raw else config.select_fields
    logger.info("开始拉取: %s", config.entity_url)

    try:
        records = list(
            client.iter_records(
                max_records=max_records,
                select=select,
                filter_expr=filter_expr,
            )
        )
    except ODataClientError as exc:
        logger.error("拉取失败: %s", exc)
        sys.exit(1)

    logger.info("共拉取 %s 条", len(records))

    if not raw:
        records = canonicalize_records(records, keep_unknown=keep_unknown)

    prefix = "andon_raw" if raw else "andon"
    written: list[Path] = []
    if fmt in {"json", "both"}:
        written.append(save_json(records, config.output_dir, prefix=prefix))
    if fmt in {"csv", "both"}:
        written.append(save_csv(records, config.output_dir, prefix=prefix))

    for path in written:
        click.echo(f"已写入: {path}")


@cli.command("discover")
@click.option("--env-file", type=click.Path(exists=True, dir_okay=False), default=None)
def discover(env_file: str | None) -> None:
    """尝试列出服务文档中的实体集（GET 服务根）。"""
    config = load_config(env_file)
    client = ODataClient(config)
    headers, auth_params = client._auth_headers_and_params()
    response = client.session.get(
        config.base_url.rstrip("/"),
        headers=headers,
        params=auth_params,
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
    )
    if response.status_code >= 400:
        click.echo(f"服务根访问失败: HTTP {response.status_code} - {response.text[:500]}", err=True)
        sys.exit(1)

    try:
        payload = response.json()
    except ValueError:
        click.echo(response.text[:1000])
        return

    # OData v4 service document
    entities = []
    if isinstance(payload, dict):
        value = payload.get("value")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("name"):
                    entities.append(item.get("name"))
        # 部分网关
        if not entities and "EntitySets" in str(payload):
            click.echo(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])
            return

    if entities:
        click.echo("可用实体集:")
        for name in entities:
            click.echo(f"  - {name}")
    else:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    cli()
