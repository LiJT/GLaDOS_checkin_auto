#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""青龙面板入口。请与 glados.py 放在同一目录。"""

from glados import main


def main_handler(event, context):
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
