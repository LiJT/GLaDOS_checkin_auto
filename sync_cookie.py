#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用本机 Chrome 登录一次，之后自动读取 Cookie、签到，并更新 GitHub Secret。"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import glados

HOME = Path.home() / ".glados-checkin"
PROFILE = HOME / "chrome-profile"
UA_FILE = HOME / "user-agent.txt"
LOG_FILE = HOME / "sync.log"
REPO = "LiJT/GLaDOS_checkin_auto"
SESSION_NAMES = ("gld:sess", "gld:sess.sig", "koa:sess", "koa:sess.sig")
TASK_NAME = "GLaDOS每日签到"


def log(message):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    HOME.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def saved_user_agent():
    if UA_FILE.is_file():
        return UA_FILE.read_text(encoding="utf-8").strip()
    return ""


def launch_browser(playwright, headless):
    kwargs = {
        "user_data_dir": str(PROFILE),
        "headless": headless,
        "ignore_default_args": ["--enable-automation"],
        "args": ["--disable-blink-features=AutomationControlled"],
        "viewport": {"width": 1100, "height": 800},
    }
    user_agent = saved_user_agent()
    if user_agent:
        kwargs["user_agent"] = user_agent
    last_error = None
    for channel in ("chrome", "msedge"):
        try:
            return playwright.chromium.launch_persistent_context(channel=channel, **kwargs)
        except Exception as exc:
            last_error = exc
            log(f"无法用 {channel} 启动浏览器: {type(exc).__name__}")
    raise RuntimeError("没有找到 Chrome 或 Edge") from last_error


def session_status(page):
    try:
        payload = page.evaluate(
            """async () => {
                const response = await fetch('/api/user/status', {
                    headers: {accept: 'application/json'}
                });
                return await response.json();
            }"""
        )
    except Exception:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(payload, dict) and payload.get("code") == 0 and isinstance(data, dict):
        return payload
    return None


def wait_for_login(page, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = session_status(page)
        if status:
            return status
        time.sleep(2)
    return None


def cookie_header(context):
    found = {}
    for item in context.cookies("https://glados.cloud"):
        if item.get("name") in SESSION_NAMES and item.get("value"):
            found[item["name"]] = item["value"]
    if "gld:sess" not in found or "gld:sess.sig" not in found:
        return ""
    return "; ".join(f"{name}={found[name]}" for name in SESSION_NAMES if name in found)


def checkin_in_browser(page):
    return page.evaluate(
        """async () => {
            const response = await fetch('/api/user/checkin', {
                method: 'POST',
                headers: {
                    accept: 'application/json',
                    'content-type': 'application/json;charset=UTF-8'
                },
                body: JSON.stringify({token: 'glados.cloud'})
            });
            return await response.json();
        }"""
    )


def update_secret(name, value):
    completed = subprocess.run(
        ["gh", "secret", "set", name, "--repo", REPO],
        input=value,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or f"gh secret set {name} 失败")


def install_daily_task():
    HOME.mkdir(parents=True, exist_ok=True)
    runner = HOME / "run_checkin.cmd"
    runner.write_text(
        "\r\n".join(
            [
                "@echo off",
                f'"{sys.executable}" "{Path(__file__).resolve()}" --headless',
                "",
            ]
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/F",
            "/TN",
            TASK_NAME,
            "/SC",
            "DAILY",
            "/ST",
            "09:00",
            "/RL",
            "LIMITED",
            "/TR",
            str(runner),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        log(f"每天 9:00 的本机定时任务没有建成: {detail}")
        return False
    log("已创建本机定时任务，每天 9:00 自动签到并更新 Cookie")
    return True


def main():
    parser = argparse.ArgumentParser(description="自动获取 GLaDOS Cookie 并签到")
    parser.add_argument("--headless", action="store_true", help="不弹出窗口，供每天的定时任务使用")
    parser.add_argument("--install-task", action="store_true", help="只创建每天 9:00 的本机定时任务")
    args = parser.parse_args()
    if args.install_task:
        return 0 if install_daily_task() else 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("缺少 playwright。请先运行: python -m pip install playwright")
        return 1

    HOME.mkdir(parents=True, exist_ok=True)
    PROFILE.mkdir(parents=True, exist_ok=True)
    timeout_seconds = 30 if args.headless else 600
    if not args.headless:
        log("请在弹出的浏览器里登录 https://glados.cloud 。验证码登录完成后会自动签到，不用复制 Cookie")

    with sync_playwright() as playwright:
        context = launch_browser(playwright, args.headless)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://glados.cloud/console/checkin", wait_until="domcontentloaded", timeout=60000)
            status = wait_for_login(page, timeout_seconds)
            if not status:
                if args.headless:
                    log("保存的登录已失效。请再运行一次 python sync_cookie.py ，在弹出的窗口里重新登录")
                else:
                    log("等待登录超时。重新运行 python sync_cookie.py 后再登录一次")
                return 1

            user_agent = page.evaluate("() => navigator.userAgent")
            UA_FILE.write_text(user_agent, encoding="utf-8")
            header = cookie_header(context)
            if not header:
                log("已经登录，但没有读到 gld:sess。请退出后重新登录再运行一次")
                return 1

            result = checkin_in_browser(page)
            data = status.get("data") or {}
            email = str(data.get("email") or "?")
            days = str(data.get("leftDays", "?")).split(".")[0]
            state = "成功" if glados.is_success(result) else "失败"
            log(f"{email} 签到{state}: {glados.describe(result, None)}，剩余 {days} 天")

            try:
                update_secret("GLADOS_COOKIE", header)
                update_secret("GLADOS_USER_AGENT", user_agent)
                log("已把新的 Cookie 和浏览器标识写入 GitHub Actions Secrets")
            except RuntimeError as exc:
                log(f"签到已完成，但写入 GitHub Secret 失败: {exc}")
                return 1
            if not args.headless:
                install_daily_task()
                page.evaluate(
                    "message => alert(message)",
                    f"签到{state}。Cookie 已自动保存，以后不用再复制。\n{glados.describe(result, None)}",
                )
            return 0 if glados.is_success(result) else 1
        finally:
            context.close()


if __name__ == "__main__":
    sys.exit(main())
