# 安灯原始数据拉取（OData + API Key）→ 清洗 → Dify 知识库 CSV

对齐你本地可运行脚本：

- `InsecureHTTPSAdapter`（内网自签证书）
- `proxies` 禁用公司外网代理
- 鉴权头：`gongsi-Key: <api_key>`
- `$top=2000` + `$orderby=begintime desc`
- 清洗后导出知识库 CSV

## 配置（`.env`）

```env
ANDON_ODATA_BASE_URL=https://gongsi.com:8092/andon
ANDON_ENDPOINT=o_d_andon_eventsrawdata_cur
ANDON_API_KEY=api-key3
ANDON_AUTH_HEADER=gongsi-Key
ANDON_VERIFY_SSL=false
ANDON_TOP_N=2000
ANDON_OUTPUT_DIR=./output
```

## Windows 运行

```bat
cd C:\Users\CHJ1WUJ\personal\And_analyse\Dify
python -m venv .venv
.venv\Scripts\activate
pip install -e .

copy .env.example .env
python -m andon_fetcher probe
python -m andon_fetcher fetch
```

或：`scripts\andon.bat probe` / `scripts\andon.bat fetch`

## 命令说明

| 命令 | 作用 |
|---|---|
| `probe` | 试拉 1 条，确认鉴权与字段 |
| `fetch` | 拉最新 2000 条 → 清洗去重 → 写出 Dify 知识库文件 |

`fetch` 输出到 `./output/`：

- `andon_events_knowledge_base.csv` ← 上传 Dify 知识库
- `andon_events_cleaned.json`
- `chunks_only.txt`
- `line_dict.json`
- `andon_events_raw.json`

可覆盖条数/目录：

```bat
python -m andon_fetcher fetch --top 2000 --output-dir .\output
```

## 测试

```bat
pip install -e ".[dev]"
pytest -q
```
