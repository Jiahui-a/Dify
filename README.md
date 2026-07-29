# 第一步：获取安灯原始数据

## 结论

| 项 | 内容 |
|---|---|
| 存储位置 | 公司 **OData API**（不是直连 MySQL/SQL Server/PostgreSQL） |
| 地址 | `https://gongsi.com:8092/andon`（按你环境改） |
| 表/实体 | `o_d_andon_eventsrawdata_cur` |
| 鉴权 | Header `X-Api-Key` |
| 脚本 | `fetch_andon_events.py` |

## 运行

```bat
pip install -r requirements.txt
python fetch_andon_events.py
```

在 `main()` 里保持你已跑通的 `base_url` / `api_key`。

输出（`output` 目录）：
- `andon_events_raw.json`：接口全量原始数据
- `andon_events_core.json` / `andon_events_core.csv`：重要字段
