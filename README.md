# GLaDOS 自动签到

每天通过 GitHub Actions 打开 [签到页](https://glados.cloud/console/checkin) 对应的接口，完成 Daily Punch。

环境变量：

| 名称 | 是否必填 | 说明 |
| --- | --- | --- |
| `GLADOS_COOKIE` | 必填 | 登录后的完整 Cookie。多个账号用 `&` 或换行隔开 |
| `GLADOS_USER_AGENT` | 建议填写 | 获取上面这份 Cookie 时，同一个浏览器的 User-Agent |
| `PUSHPLUS_TOKEN` | 可选 | [PushPlus](https://www.pushplus.plus) 推送 |

Cookie 必须同时包含 `gld:sess` 和 `gld:sess.sig`。只保留旧的 `koa:sess` 时，接口会返回「没有权限」。

## 获取 Cookie 和 User-Agent

1. 用 Chrome 或 Edge 打开 https://glados.cloud ，退出后重新登录。
2. 进入 https://glados.cloud/console/checkin ，按 F12，打开 Network。
3. 刷新页面，点开一次成功的 `/api/user/status` 请求。
4. 在 Request Headers 里复制整行 `Cookie`。确认里面同时有 `gld:sess=` 和 `gld:sess.sig=`。
5. 地址栏打开 `chrome://version` 或 `edge://version`，复制「用户代理」的完整内容。

把 Cookie 存进 Secret `GLADOS_COOKIE`，把用户代理存进 Secret `GLADOS_USER_AGENT`。浏览器大版本更新后，如果再次出现「设备不一致」，重新登录并同时更新这两项。

## GitHub Actions

1. Fork 本仓库。
2. 打开 Settings → Secrets and variables → Actions，添加上面的 Secret。
3. 打开 Actions，启用工作流，并手动运行一次「开始每日签到」。
4. 成功后会在每天北京时间 9:30 自动运行。

## 青龙面板

把 `glados.py` 和 `glados_Qinglong.py` 放到同一目录，定时任务运行 `glados_Qinglong.py`。环境变量与上面相同。
