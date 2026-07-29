# 第一步：获取安灯原始数据

## 你当前的报错结论

```
401 ... "API Key is not valid or is expired / revoked."
```

说明：

1. **网络 / SSL / 地址已经通了**（能打到 `wujlinvma016.apac.bosch.com:8092`）
2. **失败原因只有一个：API Key 无效、过期或已吊销**
3. 这不是 `$select`、不是代理、不是代码路径问题

请向接口管理员申请有效 Key，然后填进脚本。

## 正确连接信息

| 项 | 值 |
|---|---|
| 存储 | OData API（非直连数据库） |
| 地址 | `https://wujlinvma016.apac.bosch.com:8092/andon` |
| 表/实体 | `o_d_andon_eventsrawdata_cur` |
| 鉴权头 | `X-Api-Key` |

## 运行

1. 打开 `fetch_andon_raw.py`
2. 把 `api_key="在这里填入有效的API_KEY"` 换成真实 Key
3. 执行：

```bat
cd C:\Users\CHJ1WUJ\personal\And_analyse\Dify
git pull
pip install requests urllib3
python fetch_andon_raw.py
```

或：

```bat
set ANDON_API_KEY=你的有效密钥
python -m andon_fetcher probe
python fetch_andon_raw.py
```

原始数据输出到 `data/raw/`。
