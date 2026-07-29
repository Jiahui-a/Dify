# 第一步：获取安灯原始数据

## 目标

能够从公司安灯系统拉取**原始数据**（本步不做清洗、不做知识库）。

## 数据存在哪里？

| 项 | 结论 |
|---|---|
| 存储形态 | **不是**直连 MySQL/SQL Server/PostgreSQL |
| 访问方式 | 公司服务器 **OData API** + **API Key** |
| 地址 | `https://gongsi.com:8092/andon` |
| 核心表/实体 | `o_d_andon_eventsrawdata_cur`（报警/事件原始表） |
| 鉴权 | Header：`gongsi-Key: <api_key>` |
| SSL | 内网自签，`verify_ssl=false` + InsecureHTTPSAdapter |
| 代理 | 禁用系统代理，避免内网请求被拐走 |

## 核心字段

`linename`, `stationname`, `faulttype`, `eventsname`, `begintime`, `responsetime`, `endtime`, `confirmtime`, `reactionplan`, `actions`, `remark`, `ischangeparameter`, `parametername`, `oldvalue`, `newvalue`, `ischangequipment`, `changeeventdesc`, `equipmentpn`, `responseduration`, `repairduration`, `dowtimeduration`, `closeperson`, `responseperson`

## 配置 `.env`

```env
ANDON_ODATA_BASE_URL=https://gongsi.com:8092/andon
ANDON_ENDPOINT=o_d_andon_eventsrawdata_cur
ANDON_API_KEY=api-key3
ANDON_AUTH_HEADER=gongsi-Key
ANDON_VERIFY_SSL=false
ANDON_TOP_N=2000
ANDON_OUTPUT_DIR=./data/raw
```

## 运行（Windows）

```bat
cd C:\Users\CHJ1WUJ\personal\And_analyse\Dify
pip install -e .
python -m andon_fetcher probe
python -m andon_fetcher fetch
```

| 命令 | 作用 |
|---|---|
| `probe` | 试拉 1 条，检查核心字段是否齐全 |
| `fetch` | 拉最新 N 条原始数据，写入 `data/raw/` |

输出文件：

- `andon_raw_full_*.json`：接口返回全量
- `andon_raw_core_*.json` / `andon_raw_core_*.csv`：仅核心字段

```bat
python -m andon_fetcher fetch --top 2000
python -m andon_fetcher fetch --no-select
```
