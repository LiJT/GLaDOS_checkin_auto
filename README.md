# GLaDOS 自动签到

每天通过 GitHub Actions 打开 [签到页](https://glados.cloud/console/checkin) 对应的接口，完成 Daily Punch。

环境变量：

| 名称 | 是否必填 | 说明 |
| --- | --- | --- |
| `GLADOS_COOKIE` | 必填 | 登录后的完整 Cookie。多个账号用 `&` 或换行隔开 |
| `GLADOS_USER_AGENT` | 建议填写 | 获取上面这份 Cookie 时，同一个浏览器的 User-Agent |
| `PUSHPLUS_TOKEN` | 可选 | [PushPlus](https://www.pushplus.plus) 推送 |

Cookie 必须同时包含 `gld:sess` 和 `gld:sess.sig`。只保留旧的 `koa:sess` 时，接口会返回「没有权限」。

## 自动获取 Cookie

网站登录要邮箱验证码，脚本不能自己造一个新登录。本机 Chrome 登录一次之后，登录状态会留在单独的浏览器配置里。之后每天自动读取 Cookie，完成签到，并写回 GitHub。

```bash
python -m pip install playwright
python sync_cookie.py
```

弹出的窗口里登录 https://glados.cloud 。成功后脚本会签到，并把 `GLADOS_COOKIE` 和 `GLADOS_USER_AGENT` 写入 GitHub Actions。同时会创建本机任务「GLaDOS每日签到」，每天 9:00 再跑一次。

登录过期时，再执行一次不带参数的 `python sync_cookie.py`。

## GitHub Actions

1. Fork 本仓库。
2. 打开 Settings → Secrets and variables → Actions，添加上面的 Secret。
3. 打开 Actions，启用工作流，并手动运行一次「开始每日签到」。
4. 成功后会在每天北京时间 9:30 自动运行。

## 青龙面板

把 `glados.py` 和 `glados_Qinglong.py` 放到同一目录，定时任务运行 `glados_Qinglong.py`。环境变量与上面相同。
