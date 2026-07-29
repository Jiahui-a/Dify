# 安灯原始数据拉取（OData + API Key）

第一步：从公司服务器通过 **OData API** 拉取安灯原始数据。  
鉴权方式为 **API Key**（非直连 MySQL/SQL Server）。

## 公司 ApiConfig（已对齐）

```python
class ApiConfig:
    base_url: str = "https://gongsi.com:8092/andon"
    endpoint: str = "o_d_andon_eventsrawdata_cur"
    api_key: str = "API_KEY"          # 换成真实密钥
    auth_header: str = "ABC"          # 请求头: ABC: <api_key>
    user_agent: str = "Mozilla/5.0"
    verify_ssl: bool = False
    timeout_seconds: int = 120
    top_n: int = 500                  # OData $top 分页大小
```

完整请求 URL：

`https://gongsi.com:8092/andon/o_d_andon_eventsrawdata_cur`

| ApiConfig | 环境变量 |
|---|---|
| `base_url` | `ANDON_ODATA_BASE_URL` |
| `endpoint` | `ANDON_ENDPOINT` / `ANDON_ENTITY_SET` |
| `api_key` | `ANDON_API_KEY` |
| `auth_header` | `ANDON_AUTH_HEADER`（模式 `header_custom`） |
| `user_agent` | `ANDON_USER_AGENT` |
| `verify_ssl` | `ANDON_VERIFY_SSL=false` |
| `timeout_seconds` | `ANDON_TIMEOUT_SECONDS=120` |
| `top_n` | `ANDON_TOP_N` / `ANDON_PAGE_SIZE` |

```bash
python -m andon_fetcher discover
python -m andon_fetcher probe
```

`probe` 会试拉 1 条并打印真实字段名，便于对齐核心字段。

## 核心字段

拉取后会归一化为以下字段（大小写/下划线不敏感）：

`linename`, `stationname`, `faulttype`, `eventsname`, `begintime`, `responsetime`, `endtime`, `confirmtime`, `reactionplan`, `actions`, `remark`, `ischangeparameter`, `parametername`, `oldvalue`, `newvalue`, `ischangequipment`, `changeeventdesc`, `equipmentpn`, `responseduration`, `repairduration`, `dowtimeduration`, `closeperson`, `responseperson`

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入公司服务器地址、实体集、API Key

# 探测实体与字段
python -m andon_fetcher discover
python -m andon_fetcher probe

# 拉取全量（分页自动处理 @odata.nextLink / $skip）
python -m andon_fetcher fetch

# 只拉 100 条调试
python -m andon_fetcher fetch --max-records 100

# 保留接口原始字段名
python -m andon_fetcher fetch --raw

# 按时间过滤（OData $filter）
python -m andon_fetcher fetch --filter "begintime ge 2026-07-01T00:00:00Z"
```

结果默认写入 `./data/raw/`（CSV + JSON）。

## API Key 模式

公司默认：`ANDON_API_KEY_MODE=header_custom` + `ANDON_AUTH_HEADER=ABC`  
→ 实际发送 `ABC: <API_KEY>`，并带 `User-Agent: Mozilla/5.0`。

其他可选模式：

| 模式 | 实际发送 |
|---|---|
| `header_custom`（默认） | `<ANDON_AUTH_HEADER>: <key>` |
| `header_api_key` | `api-key: <key>` |
| `header_x_api_key` | `X-API-Key: <key>` |
| `header_authorization_apikey` | `Authorization: ApiKey <key>` |
| `header_authorization_bearer` | `Authorization: Bearer <key>` |
| `query_api_key` | `?api-key=<key>` |
| `query_apikey` | `?apiKey=<key>` |

内网自签证书：`ANDON_VERIFY_SSL=false`。

## 无内网时本地 Mock 联调

```bash
python scripts/mock_odata_server.py
```

另开终端：

```bash
cat > .env <<'EOF'
ANDON_ODATA_BASE_URL=http://127.0.0.1:8765/odata
ANDON_ENTITY_SET=AndonEvents
ANDON_API_KEY=demo-key
ANDON_API_KEY_MODE=header_api_key
ANDON_VERIFY_SSL=true
ANDON_OUTPUT_DIR=./data/raw
EOF

python -m andon_fetcher probe
python -m andon_fetcher fetch
```

## 在 Dify 中使用（HTTP 请求节点）

可将同一 OData 接口配成 Dify 工具/工作流 HTTP 节点：

- **Method**: `GET`
- **URL**: `{{ANDON_ODATA_BASE_URL}}/{{ANDON_ENTITY_SET}}`
- **Headers**: `api-key: {{ANDON_API_KEY}}`，`Accept: application/json`
- **Query**: `$top=100`，`$select=linename,stationname,...`，可选 `$filter=...`

完整字段列表示例见 `dify/andon_http_tool.example.json`。  
大批量分页建议仍用本仓库 CLI（自动跟随 `@odata.nextLink`），Dify 适合按条件抽样子集。

## 目录结构

```
andon_fetcher/          # 拉取核心库
  config.py             # 环境变量与核心字段
  odata_client.py       # OData + API Key 客户端
  field_mapper.py       # 字段归一化
  exporter.py           # CSV/JSON 导出
  __main__.py           # CLI: discover / probe / fetch
scripts/mock_odata_server.py
dify/andon_http_tool.example.json
tests/
```

## 测试

```bash
pip install -r requirements.txt
pytest -q
```
