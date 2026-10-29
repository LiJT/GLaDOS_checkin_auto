#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GLaDOS 每日签到。站点为 https://glados.cloud/console/checkin 。"""

import os
import re
import sys
import time
from datetime import datetime

import requests

BASE = "https://glados.cloud"
CHECKIN_URL = BASE + "/api/user/checkin"
STATUS_URL = BASE + "/api/user/status"
TIMEOUT = 20
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def log(message):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def cookie_names(cookie):
    names = set()
    for item in cookie.split(";"):
        name, separator, _value = item.strip().partition("=")
        if separator and name:
            names.add(name)
    return names


def session_kind(cookie):
    names = cookie_names(cookie)
    if {"gld:sess", "gld:sess.sig"} <= names:
        return "gld"
    if {"koa:sess", "koa:sess.sig"} <= names:
        return "koa"
    return None


def parse_cookies(raw):
    text = raw.strip()
    text = re.sub(r"^cookie\s*:\s*", "", text, flags=re.IGNORECASE)
    separator = "\n" if "\n" in text else "&"
    cookies = []
    for item in text.split(separator):
        cookie = item.strip().strip(";")
        if cookie:
            cookies.append(cookie)
    return cookies


def browser_headers(cookie):
    user_agent = os.environ.get("GLADOS_USER_AGENT", "").strip() or DEFAULT_UA
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": BASE,
        "Referer": BASE + "/console/checkin",
        "Cookie": cookie,
    }
    match = re.search(r"(?:Chrome|Chromium|Edg)/(\d+)", user_agent)
    if match:
        major = match.group(1)
        if "Edg/" in user_agent:
            brand = "Microsoft Edge"
        else:
            brand = "Google Chrome"
        headers["Sec-CH-UA"] = (
            f'"Chromium";v="{major}", "{brand}";v="{major}", "Not_A Brand";v="24"'
        )
        headers["Sec-CH-UA-Mobile"] = "?1" if "Mobile" in user_agent else "?0"
        if "Macintosh" in user_agent:
            platform = "macOS"
        elif "Android" in user_agent:
            platform = "Android"
        elif "Linux" in user_agent:
            platform = "Linux"
        else:
            platform = "Windows"
        headers["Sec-CH-UA-Platform"] = f'"{platform}"'
    return headers


def request_json(method, url, headers, payload=None):
    try:
        response = requests.request(
            method, url, headers=headers, json=payload, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        return None, f"网络错误: {type(exc).__name__}"
    try:
        body = response.json()
    except ValueError:
        return None, f"HTTP {response.status_code} 返回的不是 JSON"
    if not isinstance(body, dict):
        return None, f"HTTP {response.status_code} 响应格式异常"
    return body, None


def message_of(body):
    if not isinstance(body, dict):
        return ""
    return str(body.get("message") or body.get("msg") or "")


def is_success(body):
    text = message_of(body).lower()
    done_markers = (
        "checkin!",
        "checkin repeats",
        "observation logged",
        "return tomorrow for more points",
    )
    if any(marker in text for marker in done_markers):
        return True
    if "repeat" in text and "tomorrow" in text:
        return True
    return isinstance(body, dict) and body.get("code") == 0 and "checkin" in text


def describe(body, error):
    if error:
        return error
    if not isinstance(body, dict):
        return "无响应"
    text = message_of(body) or "无消息"
    code = body.get("code")
    reason = str(body.get("reason") or "")
    detail = text
    extras = []
    if code is not None:
        extras.append(f"code={code}")
    if reason:
        extras.append(f"reason={reason}")
    if extras:
        detail = f"{text} ({', '.join(extras)})"
    if code == 4 or reason == "device-mismatch":
        return (
            "登录设备与当前请求不一致。"
            "请用平时登录的浏览器重新登录 glados.cloud，"
            "更新 GLADOS_COOKIE，并把该浏览器的 User-Agent 写入 GLADOS_USER_AGENT。"
            f"接口返回: {detail}"
        )
    if "没有权限" in text or "permission" in text.lower():
        return (
            "登录已失效。请重新登录 https://glados.cloud/console/checkin ，"
            "从成功的 /api/user/status 请求里复制完整 Cookie，"
            "其中要同时有 gld:sess 和 gld:sess.sig。"
            f"接口返回: {detail}"
        )
    return detail


def account_status(headers):
    body, error = request_json("GET", STATUS_URL, headers)
    data = body.get("data") if isinstance(body, dict) else None
    if error or not isinstance(data, dict):
        return "?", "?"
    email = str(data.get("email") or "?")
    days = str(data.get("leftDays", "?")).split(".")[0]
    return email, days


def pushplus(token, title, content):
    if not token:
        return
    try:
        response = requests.post(
            "https://www.pushplus.plus/send",
            json={
                "token": token,
                "title": title,
                "content": content,
                "template": "txt",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in (None, 0, 200):
            log(f"PushPlus 返回异常: {payload.get('msg', payload.get('code'))}")
            return
        log("PushPlus 推送已发送")
    except (requests.RequestException, ValueError) as exc:
        log(f"PushPlus 推送失败: {type(exc).__name__}")


def checkin_account(index, cookie):
    kind = session_kind(cookie)
    if kind is None:
        line = f"账号 {index}: Cookie 不完整，需要成对的 sess 和 sess.sig"
        log(line)
        return False, line
    if kind == "koa":
        log(f"账号 {index}: Cookie 仍是旧版 koa:sess，当前接口需要 gld:sess")

    headers = browser_headers(cookie)
    body = None
    error = None
    for attempt in range(1, 3):
        body, error = request_json(
            "POST", CHECKIN_URL, headers, {"token": "glados.cloud"}
        )
        if error:
            log(f"账号 {index}: 第 {attempt} 次请求失败，{error}")
        elif is_success(body):
            break
        elif isinstance(body, dict) and (
            body.get("code") in (-2, 4) or body.get("reason") == "device-mismatch"
        ):
            break
        elif attempt == 1:
            log(f"账号 {index}: 结果不明确，5 秒后重试")
        if attempt == 1:
            time.sleep(5)

    email, days = account_status(headers)
    result = describe(body, error)
    success = is_success(body)
    state = "成功" if success else "失败"
    line = f"账号 {index} {email} {state}: {result}，剩余 {days} 天"
    log(line)
    return success, line


def main():
    raw = os.environ.get("GLADOS_COOKIE", "")
    if not isinstance(raw, str) or not raw.strip():
        log("未获取到 GLADOS_COOKIE")
        return 1

    cookies = parse_cookies(raw)
    if not cookies:
        log("GLADOS_COOKIE 里没有可用内容")
        return 1

    if not os.environ.get("GLADOS_USER_AGENT", "").strip():
        log("未配置 GLADOS_USER_AGENT，使用默认浏览器标识。若出现设备不一致，请补上登录时的 User-Agent")

    lines = []
    success_count = 0
    for index, cookie in enumerate(cookies, 1):
        success, line = checkin_account(index, cookie)
        lines.append(line)
        if success:
            success_count += 1

    title = f"GLaDOS签到 {success_count}/{len(cookies)}"
    pushplus(os.environ.get("PUSHPLUS_TOKEN", "").strip(), title, "\n".join(lines))
    return 0 if success_count == len(cookies) else 1


if __name__ == "__main__":
    sys.exit(main())
