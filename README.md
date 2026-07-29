# 第一步：获取安灯原始数据

## 怎么跑（推荐）

在仓库根目录直接运行单文件脚本（结构与你的可运行脚本一致）：

```bat
cd C:\Users\CHJ1WUJ\personal\And_analyse\Dify
pip install requests urllib3
python fetch_andon_raw.py
```

脚本里改配置（与你给的一致）：

```python
api_config = ApiConfig(
    base_url="https://gongsi.com:8092/andon",
    endpoint="o_d_andon_eventsrawdata_cur",
    api_key="api-key3",
    auth_header="gongsi-Key",
    verify_ssl=False,
    top_n=2000,
)
```

输出目录：`data/raw/`

## 第一步结论

| 项 | 内容 |
|---|---|
| 存储 | 公司 OData API（非直连数据库） |
| 地址 | `https://gongsi.com:8092/andon` |
| 表/实体 | `o_d_andon_eventsrawdata_cur` |
| 鉴权 | Header `gongsi-Key: api-key3` |
| 关键实现 | `InsecureHTTPSAdapter` + `proxies=NO_PROXY` |

## 核心字段

`linename, stationname, faulttype, eventsname, begintime, responsetime, endtime, confirmtime, reactionplan, actions, remark, ischangeparameter, parametername, oldvalue, newvalue, ischangequipment, changeeventdesc, equipmentpn, responseduration, repairduration, downtimeduration, closeperson, responseperson`
