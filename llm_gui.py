#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM GUI — 本地 llama-server 桌面启动器（customtkinter 原生窗口，不依赖浏览器）

- 扫描 models/ 列模型；每模型多套预设
- 上下文长度：自定义 + 右侧预设下拉（4K~64K）
- 并发请求 1/2/4/8/16 → 自动算每线程上下文（并发=1 不显示）
- GPU 下拉（自动检测 + 手动刷新）→ --main-gpu
- 监听地址带 [本机]/[局域网] 提示
- 可选参数（批处理大小 / 自定义 llama 路径）：留空不传给 llama-server
- 启动/停止 llama-server 子进程，日志实时滚动
打包：pyinstaller --onefile --windowed --name LLMGUI --collect-all customtkinter llm_gui.py
"""
import json, os, queue, socket, subprocess, sys, threading, traceback, webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

APP_ICON_B64 = "AAABAAMAEBAAAAEAIAAoBAAANgAAACAgAAABACAAKBAAAF4EAAAwMAAAAQAgACgkAACGFAAAKAAAABAAAAAgAAAAAQAgAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAoAAAAIAAAAEAAAAABACAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAAAAAAAAAAAAAAAAAACgAAAAwAAAAYAAAAAEAIAAAAAAAACQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

MODELS_DIR = os.path.join(BASE, 'models')
PRESETS_FILE = os.path.join(BASE, 'llm_presets.json')
CONFIG_FILE = os.path.join(BASE, 'llm_gui_config.json')
DEFAULTS_FILE = os.path.join(BASE, 'llm_default_presets.json')
SERVER_EXE = os.path.join(BASE, 'llama-server.exe')
JINJA = os.path.join(BASE, 'gemma_chat_template.jinja')

CTX_PRESETS = {'4K': 4096, '8K': 8192, '12K': 12288, '16K': 16384, '24K': 24576, '32K': 32768, '48K': 49152, '64K': 65536}
PARALLEL_OPTS = ['1', '2', '4', '8', '16']

API_SUFFIXES = ['/v1/chat/completions', '/v1/completions', '/v1/embeddings', '/health']

VERSION = '1.0.1'
GITHUB_USER = 'BFRKQSB7'
GITHUB_REPO = 'llm-launcher-gui'
GITHUB_URL = f'https://github.com/{GITHUB_USER}/{GITHUB_REPO}'


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

# 简单字段：key / 标签 / 解释 / 可选选项
PARAMS = [
    dict(k='ngl', t='GPU 层数', tip='卸载到 GPU 的层数。999=全部（最快最占显存）；0=纯 CPU（不占显存，可与其他 GPU 任务同时运行）。'),
    dict(k='flash', t='Flash Attention', tip='闪存注意力。N 卡 20/30/40/50 系建议 on，加速且省显存。新版 llama 要带值 on/off/auto。', sel=['on', 'off', 'auto']),
    dict(k='cache', t='KV 缓存精度', tip='KV Cache 精度。q8_0=8bit 量化显存减半、质量几乎无损（推荐）；fp16=高精度占显存；q4_0=更省但轻微下降。', sel=['q8_0', 'fp16', 'q4_0']),
    dict(k='temp', t='温度 temp', tip='采样温度。越低越确定/保守（翻译 0.1~0.3），越高越随机。'),
    dict(k='top_p', t='top-p', tip='核采样阈值。越低越保守，越高越多样。'),
    dict(k='n_predict', t='最大输出', tip='单次请求最多生成的 token 数。翻译 4096 够；提示词转换 512 足够。'),
    dict(k='port', t='端口', tip='llama-server 监听端口。与已运行的其他实例错开，避免端口冲突。'),
]


def load_presets():
    if os.path.exists(PRESETS_FILE):
        try:
            d = json.load(open(PRESETS_FILE, encoding='utf-8'))
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {}


def load_defaults():
    try:
        d = json.load(open(DEFAULTS_FILE, encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_defaults(d):
    with open(DEFAULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def save_presets(d):
    with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def load_cfg():
    try:
        return json.load(open(CONFIG_FILE, encoding='utf-8'))
    except Exception:
        return {'overwrite_ask': True}


def save_cfg(c):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=2)


def detect_gpus():
    """返回 ['0 NVIDIA ...', ...]；无 nvidia-smi 返回 []。"""
    try:
        out = subprocess.run(['nvidia-smi', '--query-gpu=index,name', '--format=csv,noheader'],
                             capture_output=True, text=True, timeout=10)
        gpus = [l.strip() for l in out.stdout.strip().splitlines() if l.strip()]
        return gpus
    except Exception:
        return []


def detect_vram_gb():
    """返回总显存 GB（整数向下取整）；检测失败返回 0。"""
    try:
        out = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                             capture_output=True, text=True, timeout=10)
        for line in out.stdout.strip().splitlines():
            s = line.strip()
            if s.isdigit():
                return max(1, round(int(s) / 1024))
    except Exception:
        pass
    return 0


class ToolTip:
    """悬浮提示：Label 直接 place 在主窗口上（无独立 Toplevel/置顶窗口，
    不会飘到别的窗口上残留）。轮询隐藏 + 10s 硬超时 + 窗口失活即隐藏。"""
    def __init__(self, widget, text):
        self.widget, self.text = widget, text
        self.master = widget.winfo_toplevel()
        self.lab = ctk.CTkLabel(self.master, text=text, wraplength=340, justify='left',
                                fg_color='#3a3a3a', corner_radius=8, text_color='#f0f0f0')
        self.lab.place_forget()
        widget.bind('<Enter>', self.show)
        self.master.bind('<<Deactivate>>', self.hide, add='+')
        self.master.bind('<FocusOut>', self.hide, add='+')

    @staticmethod
    def _in(x, y, rx, ry, rw, rh, tol):
        return rx - tol <= x <= rx + rw + tol and ry - tol <= y <= ry + rh + tol

    def show(self, e=None):
        if self.lab.winfo_ismapped():
            return
        x = self.widget.winfo_rootx() - self.master.winfo_rootx() + 18
        y = self.widget.winfo_rooty() - self.master.winfo_rooty() + 22
        self.lab.place_configure(x=x, y=y)
        self.lab.lift()
        self._start = __import__('time').time()
        self.widget.after(150, self._poll)

    def _poll(self):
        if not self.lab.winfo_ismapped():
            return
        try:
            if __import__('time').time() - self._start > 10:   # 硬超时兜底：绝不永久残留
                self.hide()
                return
            px, py = self.widget.winfo_pointerx(), self.widget.winfo_pointery()
            w = self.widget
            in_w = self._in(px, py, w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height(), 12)
            in_l = self._in(px, py, self.lab.winfo_rootx(), self.lab.winfo_rooty(),
                            self.lab.winfo_width(), self.lab.winfo_height(), 6)
            if in_w or in_l:
                self.widget.after(150, self._poll)
            else:
                self.hide()
        except Exception:
            self.hide()

    def hide(self, e=None):
        if self.lab.winfo_ismapped():
            self.lab.place_forget()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')
        self.title(f'LLM GUI — llama-server 启动器 · v{VERSION}')
        self.geometry('900x700')
        self.minsize(780, 580)
        self._set_window_icon()
        self.proc = None
        self.current_model = None
        self.presets = load_presets()
        self.cfg = load_cfg()
        self._build_ui()
        self.load_models()
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.after(100, self.on_model_change)
        self.after(200, self._startup_hardware)
        self._q = queue.Queue()
        self._preset_locked = False
        self.after(150, self._poll_q)

    def _set_window_icon(self):
        try:
            import base64, tempfile
            fd, path = tempfile.mkstemp(suffix='.ico')
            with os.fdopen(fd, 'wb') as f:
                f.write(base64.b64decode(APP_ICON_B64))
            self.iconbitmap(path)
        except Exception:
            pass

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, sticky='ew', padx=12, pady=(12, 4))
        self.top_frame.grid_columnconfigure(1, weight=1)
        # 第一行：模型 + 模型定位 + 计算默认
        ctk.CTkLabel(self.top_frame, text='模型').grid(row=0, column=0, padx=(12, 6), pady=6)
        self.model_sel = ctk.CTkOptionMenu(self.top_frame, values=[], command=lambda _: self.on_model_change(), width=260)
        self.model_sel.grid(row=0, column=1, padx=6, pady=6, sticky='ew')
        ctk.CTkLabel(self.top_frame, text='模型定位').grid(row=0, column=2, padx=(20, 6), pady=6)
        self.cat_sel = ctk.CTkOptionMenu(self.top_frame, values=['未指定', '聊天', '通用', '翻译', '角色扮演', '文学创作'], width=110,
                                         command=lambda _: self.on_category_change())
        self.cat_sel.grid(row=0, column=3, padx=6, pady=6, sticky='w')
        ctk.CTkButton(self.top_frame, text='⚙ 计算默认', width=84, command=lambda: self.apply_computed_defaults()).grid(row=0, column=4, padx=(10, 12), pady=6)
        self.param_src_lab = ctk.CTkLabel(self.top_frame, text='', text_color='#8ab4f8', font=('Microsoft YaHei', 11))
        self.param_src_lab.grid(row=0, column=5, padx=(0, 12), pady=6, sticky='w')
        # 第二行：预设
        ctk.CTkLabel(self.top_frame, text='预设').grid(row=1, column=0, padx=(12, 6), pady=6)
        self.preset_sel = ctk.CTkOptionMenu(self.top_frame, values=['（无预设）'], command=lambda _: self.on_preset_load(), width=160)
        self.preset_sel.grid(row=1, column=1, padx=6, pady=6, sticky='w')
        self.preset_name = ctk.CTkEntry(self.top_frame, placeholder_text='新预设名（默认=模型名）')
        self.preset_name.grid(row=1, column=2, columnspan=2, padx=6, pady=6, sticky='ew')
        ctk.CTkButton(self.top_frame, text='存为预设', width=80, command=self.save_preset).grid(row=1, column=4, padx=6, pady=6)
        self.del_btn = ctk.CTkButton(self.top_frame, text='删预设', width=70, fg_color='#7a4a4a', hover_color='#8a5555', command=self.del_preset)
        self.del_btn.grid(row=1, column=5, padx=(6, 12), pady=6)

        # 参数区 / 日志区 用 ttk.Panedwindow（sash 原生可拖，1:1 且顺滑）
        self.pw = ttk.Panedwindow(self, orient='vertical')
        _st = ttk.Style(self)
        _st.configure('Vertical.TPanedwindow', background='#242424')
        self.pw.grid(row=1, column=0, sticky='nsew', padx=12, pady=6)
        f1 = tk.Frame(self.pw, bg='#242424')
        pf = ctk.CTkScrollableFrame(f1, label_text='参数（悬停标签有解释）')
        self.param_frame = pf
        pf.pack(fill='both', expand=True)
        self.pw.add(f1, weight=1)
        pf.grid_columnconfigure(1, weight=1)
        pf.grid_columnconfigure(3, weight=1)

        def add_pair(row, col, label, tip, widget):
            lab = ctk.CTkLabel(pf, text=label, anchor='w', width=110)
            lab.grid(row=row, column=col, padx=(14, 6), pady=5, sticky='w')
            ToolTip(lab, tip)
            widget.grid(row=row, column=col + 1, padx=(6, 14), pady=5, sticky='w')

        # 上下文长度：输入 + 预设下拉
        lab = ctk.CTkLabel(pf, text='上下文长度', anchor='w', width=110)
        lab.grid(row=0, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '提示词上下文长度（token）。越长一次能处理越多文本，越占显存。右侧下拉可一键选预设（按最低 4G 显存起步）。')
        row0 = ctk.CTkFrame(pf, fg_color='transparent')
        row0.grid(row=0, column=1, columnspan=3, sticky='ew', padx=(6, 14), pady=5)
        self.ctx_input = ctk.CTkEntry(row0, width=120)
        self.ctx_input.pack(side='left')
        self.ctx_input.bind('<KeyRelease>', lambda _: self.sync_ctx_preset())
        self.ctx_preset = ctk.CTkOptionMenu(row0, values=['自定义'] + list(CTX_PRESETS.keys()), width=90, command=lambda _: self.on_ctx_preset())
        self.ctx_preset.pack(side='left', padx=(8, 0))

        # 并行请求 + 每线程上下文
        lab = ctk.CTkLabel(pf, text='并行请求', anchor='w', width=110)
        lab.grid(row=1, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '同时处理的请求数。选完后按 上下文÷并行 自动算每个工作线程的上下文（并行=1 时不计算）。')
        row1 = ctk.CTkFrame(pf, fg_color='transparent')
        row1.grid(row=1, column=1, columnspan=3, sticky='ew', padx=(6, 14), pady=5)
        self.parallel_sel = ctk.CTkOptionMenu(row1, values=PARALLEL_OPTS, width=80, command=lambda _: self.update_calc())
        self.parallel_sel.pack(side='left')
        self.per_worker_lab = ctk.CTkLabel(row1, text='', text_color='#9fd6a5', width=220)
        self.per_worker_lab.pack(side='left', padx=(12, 0))

        # 其余简单字段两列排
        simple = PARAMS
        r = 2
        for i, pp in enumerate(simple):
            row, col = r + i // 2, (i % 2) * 2
            w = ctk.CTkOptionMenu(pf, values=pp['sel'], width=170) if pp.get('sel') else ctk.CTkEntry(pf, width=170)
            add_pair(row, col, pp['t'], pp['tip'], w)
            setattr(self, 'w_' + pp['k'], w)

        # 监听地址 + 提示
        base = r + (len(simple) + 1) // 2
        lab = ctk.CTkLabel(pf, text='监听地址', anchor='w', width=110)
        lab.grid(row=base, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '127.0.0.1=仅本机访问；0.0.0.0=局域网可访问（配合防火墙）。')
        rowh = ctk.CTkFrame(pf, fg_color='transparent')
        rowh.grid(row=base, column=1, sticky='w', padx=(6, 14), pady=5)
        self.host_sel = ctk.CTkOptionMenu(rowh, values=['127.0.0.1', '0.0.0.0'], width=130, command=lambda _: self.update_host_hint())
        self.host_sel.pack(side='left')
        self.host_hint = ctk.CTkLabel(rowh, text='', text_color='#9fd6a5')
        self.host_hint.pack(side='left', padx=(8, 0))

        # GPU 选择 + 刷新
        lab = ctk.CTkLabel(pf, text='显卡', anchor='w', width=110)
        lab.grid(row=base + 1, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '选择用于推理的显卡（--main-gpu）。「自动」不传该参数，由 llama 自行选择。')
        rowg = ctk.CTkFrame(pf, fg_color='transparent')
        rowg.grid(row=base + 1, column=1, sticky='w', padx=(6, 14), pady=5)
        self.gpu_sel = ctk.CTkOptionMenu(rowg, values=['自动'], width=260)
        self.gpu_sel.pack(side='left')
        ctk.CTkButton(rowg, text='检查配置', width=68, command=self.recheck_hardware).pack(side='left', padx=(8, 0))

        # 可选参数：批处理大小
        lab = ctk.CTkLabel(pf, text='批处理大小', anchor='w', width=110)
        lab.grid(row=base + 2, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '可选（--batch-size）。留空则不传该参数，使用 llama 默认值。一般无需手动设置。')
        self.w_n_batch = ctk.CTkEntry(pf, width=170, placeholder_text='留空=不传')
        self.w_n_batch.grid(row=base + 2, column=1, padx=(6, 14), pady=5, sticky='w')

        # 可选参数：自定义 llama 路径
        lab = ctk.CTkLabel(pf, text='llama 路径', anchor='w', width=110)
        lab.grid(row=base + 3, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '可选。覆盖默认的 llama-server.exe 路径；留空用程序同目录下的 llama-server.exe。')
        self.w_server_path = ctk.CTkEntry(pf, width=170, placeholder_text='留空=默认')
        self.w_server_path.grid(row=base + 3, column=1, padx=(6, 14), pady=5, sticky='w')

        # Gemma 模型（可选勾选，替代仅按文件名判断）
        self.gemma_chk = ctk.CTkCheckBox(pf, text='Gemma 模型（专用聊天模板 + 建议低温）', command=self.on_gemma_toggle)
        self.gemma_chk.grid(row=base + 4, column=0, columnspan=3, padx=(14, 6), pady=5, sticky='w')
        ToolTip(self.gemma_chk, 'Gemma 系列需要 --chat-template-file（gemma_chat_template.jinja），且建议低温度。默认按文件名自动判断，可手动勾选/取消覆盖；按模型记住。')

        self.bar = ctk.CTkFrame(self)
        self.bar.grid(row=2, column=0, sticky='ew', padx=12, pady=6)
        self.bar.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(self.bar, text='▶ 启动', fg_color='#2f7a50', hover_color='#358a5c', width=110, command=self.start).grid(row=0, column=0, padx=12, pady=10)
        ctk.CTkButton(self.bar, text='■ 停止', fg_color='#8a3f3f', hover_color='#9a4848', width=110, command=self.stop).grid(row=0, column=1, padx=6, pady=10, sticky='w')
        self.status_lab = ctk.CTkLabel(self.bar, text='● 未运行', text_color='#e07070')
        self.status_lab.grid(row=0, column=2, padx=12, pady=10, sticky='e')
        ctk.CTkLabel(self.bar, text='首页参数=临时调试；合适就存预设').grid(row=0, column=3, padx=8, pady=10, sticky='e')
        ctk.CTkButton(self.bar, text='⚙ 设置', width=64, fg_color='#4a5568', hover_color='#556271', command=self.open_settings).grid(row=0, column=4, padx=(4, 12), pady=10)

        f2 = tk.Frame(self.pw, bg='#242424')
        log_head = tk.Frame(f2, bg='#242424')
        log_head.pack(fill='x')
        ctk.CTkLabel(log_head, text='日志', anchor='w', text_color='#8a93a6', font=('Microsoft YaHei', 12)).pack(side='left', padx=(8, 0))
        ctk.CTkButton(log_head, text='清屏', width=56, height=24, font=('Microsoft YaHei', 11),
                      fg_color='#3d4552', hover_color='#4a5464', command=self.clear_log).pack(side='right', padx=(0, 8), pady=3)
        self.svc_info = ctk.CTkLabel(f2, justify='left', anchor='w', text='（未运行）', text_color='#9aa4b8', font=('Consolas', 11))
        self.svc_info.pack(fill='x', padx=8, pady=(4, 2))
        self.log_box = ctk.CTkTextbox(f2, state='disabled', wrap='none', font=('Consolas', 12))
        self.log_box.pack(fill='both', expand=True)
        self.pw.add(f2, weight=1)
        self._bind_param_edit_marker()

    def _bind_param_edit_marker(self):
        def mark(_=None):
            self.param_src_lab.configure(text='✏ 手动调整', text_color='#e8b04a')

        def wrap(menu):
            try:
                orig = menu.cget('command')
            except Exception:
                orig = None

            def handler(val):
                try:
                    if orig:
                        orig(val)
                except Exception:
                    pass
                mark()
            menu.configure(command=handler)

        for w in [self.ctx_input, self.parallel_sel, self.host_sel, self.gpu_sel,
                  self.w_n_batch, self.w_server_path]:
            if isinstance(w, ctk.CTkEntry):
                w.bind('<KeyRelease>', mark)
            elif isinstance(w, ctk.CTkOptionMenu):
                wrap(w)
        for pp in PARAMS:
            w = getattr(self, 'w_' + pp['k'], None)
            if isinstance(w, ctk.CTkEntry):
                w.bind('<KeyRelease>', mark)
            elif isinstance(w, ctk.CTkOptionMenu):
                wrap(w)

    # ---------- 数据 ----------
    def models_list(self):
        return sorted(f for f in os.listdir(MODELS_DIR) if f.lower().endswith('.gguf')) if os.path.isdir(MODELS_DIR) else []

    def load_models(self):
        ms = self.models_list()
        self.model_sel.configure(values=ms if ms else ['（models 目录为空）'])
        self.model_sel.set(ms[0] if ms else '（models 目录为空）')
        self.current_model = ms[0] if ms else None

    def on_model_change(self):
        m = self.model_sel.get()
        if not m or m.startswith('（'):
            return
        self.current_model = m
        stem = m[:-5] if m.lower().endswith('.gguf') else m
        self.preset_name.delete(0, 'end')
        self.preset_name.insert(0, stem)
        self.refresh_preset_menu()
        self.cat_sel.set(self.get_category(m))
        self.gemma_chk.select() if self.is_gemma(m) else self.gemma_chk.deselect()
        # 记住上次选的预设：切回该模型时自动应用
        last = self.cfg.get('last_preset', {}).get(m)
        if last and last in self.presets.get(m, {}):
            self.preset_sel.set(last)
            self.set_params(self.presets[m][last])
            self.param_src_lab.configure(text=f'📌 预设：{last}', text_color='#e8c468')
            self._preset_locked = True
        else:
            self._preset_locked = False
            self.param_src_lab.configure(text='')
            self.apply_computed_defaults(m)

    def is_gemma(self, model):
        flags = self.cfg.get('gemma', {})
        if model in flags:
            return bool(flags[model])
        return 'gemma' in model.lower()

    def on_gemma_toggle(self):
        m = self.current_model
        if not m:
            return
        self.cfg.setdefault('gemma', {})[m] = bool(self.gemma_chk.get())
        save_cfg(self.cfg)
        self.apply_computed_defaults()   # gemma 会影响温度/输出长度

    def get_category(self, model):
        return self.cfg.get('categories', {}).get(model, '未指定')

    def set_category(self, model, cat):
        self.cfg.setdefault('categories', {})[model] = cat
        save_cfg(self.cfg)

    def compute_defaults(self, model, category):
        vram_gb = self.get_vram_gb()
        try:
            model_gb = os.path.getsize(os.path.join(MODELS_DIR, model)) / (1024 ** 3)
        except Exception:
            model_gb = 0
        if vram_gb > 0 and model_gb > 0 and model_gb + 1.5 <= vram_gb:
            ngl = 999
            kv_budget = max(1.0, vram_gb - model_gb - 1.5)
            ctx = int(kv_budget / 0.5) * 4096   # 每 4K 上下文约 0.5GB KV（q8_0 估算）
            ctx = max(2048, min(65536, ctx))
        else:
            ngl = 0
            ctx = 32768                          # 模型装不进显存 → CPU 跑
        cat = {
            '未指定':   {'temp': 0.5,  'top_p': 0.9,  'n_predict': 2048},
            '聊天':     {'temp': 0.7,  'top_p': 0.9,  'n_predict': 1024},
            '通用':     {'temp': 0.6,  'top_p': 0.9,  'n_predict': 2048},
            '翻译':     {'temp': 0.2,  'top_p': 0.8,  'n_predict': 4096},
            '角色扮演': {'temp': 0.8,  'top_p': 0.95, 'n_predict': 1024},
            '文学创作': {'temp': 0.75, 'top_p': 0.95, 'n_predict': 2048},
        }.get(category, {'temp': 0.5, 'top_p': 0.9, 'n_predict': 2048})
        if self.is_gemma(model):
            # Gemma 特适配：低温度 + 长输出（需 --chat-template-file）
            cat = {'temp': 0.1, 'top_p': 0.9, 'n_predict': 4096}
        return {'ctx': ctx, 'ngl': ngl, 'flash': 'on', 'cache': 'q8_0',
                'temp': cat['temp'], 'top_p': cat['top_p'], 'n_predict': cat['n_predict'],
                'parallel': 1, 'port': 4000, 'host': '127.0.0.1',
                'gpu': '自动', 'n_batch': '', 'server_path': ''}

    def _poll_q(self):
        # 主线程轮询工作线程结果（tkinter 的 after 不能从子线程调）
        while True:
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                break
            try:
                kind = item[0]
                if kind == 'params':
                    _, model, cat, params, vram = item
                    self._save_computed_defaults(model, params)
                    if self.current_model == model and not self._preset_locked:
                        self.set_params(params)
                        self.param_src_lab.configure(text=f'⚡ 自动计算（{vram}G 显存 + 模型大小）', text_color='#8ab4f8')
                        self.append_log(f'>>> 按显存 {vram}G + 模型大小计算默认参数（{cat}）')
                elif kind == 'gpus':
                    _, gpus = item
                    self._apply_gpus(gpus)
                elif kind == 'hardware':
                    _, vram, gpus, then_compute = item
                    self._apply_gpus(gpus)
                    if then_compute:
                        self.apply_computed_defaults()
                elif kind == 'error':
                    self.append_log('!!! ' + item[1])
            except Exception as e:
                self.append_log(f'!!! 处理后台结果出错: {e}')
        self.after(100, self._poll_q)

    def get_vram_gb(self):
        return self.cfg.get('hardware', {}).get('vram_gb', 0)

    def get_cached_gpus(self):
        return self.cfg.get('hardware', {}).get('gpus', [])

    def _detect_and_save_hardware(self, then_compute=True):
        def work():
            try:
                vram = detect_vram_gb()
                gpus = detect_gpus()
                self.cfg['hardware'] = {'vram_gb': vram, 'gpus': gpus}
                save_cfg(self.cfg)
                self._q.put(('hardware', vram, gpus, then_compute))
            except Exception as e:
                self._q.put(('error', f'检测本机硬件失败: {e}'))
        threading.Thread(target=work, daemon=True).start()

    def _startup_hardware(self):
        # 首次打开才检测并写 json；之后用缓存，不重复跑 nvidia-smi / 不重复计算
        if self.cfg.get('hardware', {}).get('vram_gb'):
            self._apply_gpus(self.get_cached_gpus())
        else:
            self._detect_and_save_hardware(then_compute=True)

    def recheck_hardware(self):
        self._detect_and_save_hardware(then_compute=True)

    def apply_computed_defaults(self, model=None):
        model = model or self.current_model
        if not model:
            return
        cat = self.get_category(model)

        def work():
            try:
                params = self.compute_defaults(model, cat)
                self._q.put(('params', model, cat, params, self.get_vram_gb()))
            except Exception as e:
                self._q.put(('error', f'计算默认参数失败: {e}'))

        threading.Thread(target=work, daemon=True).start()

    def _save_computed_defaults(self, model, params):
        try:
            d = load_defaults()
            d[model] = params
            save_defaults(d)
        except Exception:
            pass

    def on_category_change(self):
        if not self.current_model:
            return
        self._preset_locked = False
        self.set_category(self.current_model, self.cat_sel.get())
        self.apply_computed_defaults()

    def refresh_preset_menu(self):
        ps = self.presets.get(self.current_model, {})
        names = list(ps.keys())
        self.preset_sel.configure(values=(names + ['（无预设）']) if names else ['（无预设）'])
        self.preset_sel.set('（无预设）')
        self.update_preset_controls()

    def update_preset_controls(self):
        sel = self.preset_sel.get()
        self.del_btn.configure(state='normal' if sel and sel != '（无预设）' else 'disabled')

    def on_preset_load(self):
        n = self.preset_sel.get()
        if n and n != '（无预设）' and self.current_model and n in self.presets.get(self.current_model, {}):
            self.set_params(self.presets[self.current_model][n])
            self.param_src_lab.configure(text=f'📌 预设：{n}', text_color='#e8c468')
            self._preset_locked = True   # 加载预设后，挂起的自动计算不覆盖用户预设参数
            self.cfg.setdefault('last_preset', {})[self.current_model] = n
            save_cfg(self.cfg)
        self.update_preset_controls()

    def set_params(self, p):
        if not p:
            return
        if p.get('ctx'):
            self.ctx_input.delete(0, 'end'); self.ctx_input.insert(0, str(p['ctx']))
        if p.get('parallel'):
            self.parallel_sel.set(str(p['parallel']))
        if p.get('host'):
            self.host_sel.set(str(p['host']))
        if p.get('gpu'):
            if str(p['gpu']) not in self.gpu_sel.cget('values'):
                self.gpu_sel.configure(values=['自动'] + (self.gpu_sel.cget('values') or []))
            self.gpu_sel.set(str(p['gpu']))
        for pp in PARAMS:
            w = getattr(self, 'w_' + pp['k'], None)
            v = p.get(pp['k'])
            if w is None or v is None:
                continue
            if isinstance(w, ctk.CTkOptionMenu):
                if str(v) in w.cget('values'):
                    w.set(str(v))
            else:
                w.delete(0, 'end'); w.insert(0, str(v))
        self.w_n_batch.delete(0, 'end'); self.w_n_batch.insert(0, str(p.get('n_batch') or ''))
        self.w_server_path.delete(0, 'end'); self.w_server_path.insert(0, str(p.get('server_path') or ''))
        self.update_calc()
        self.update_host_hint()
        self.sync_ctx_preset()

    def read_params(self):
        def num(k, v):
            try:
                return int(v)
            except (ValueError, TypeError):
                raise ValueError(f'{k} 需要整数，当前值：{v!r}')

        p = {
            'ctx': num('ctx', self.ctx_input.get()),
            'parallel': num('parallel', self.parallel_sel.get()),
            'port': num('port', self.w_port.get()),
            'ngl': num('ngl', self.w_ngl.get()),
            'n_predict': num('n_predict', self.w_n_predict.get()),
            'flash': self.w_flash.get(),
            'cache': self.w_cache.get(),
            'host': self.host_sel.get(),
            'gpu': self.gpu_sel.get(),
            'temp': float(self.w_temp.get()),
            'top_p': float(self.w_top_p.get()),
            'n_batch': self.w_n_batch.get().strip(),
            'server_path': self.w_server_path.get().strip(),
        }
        return p

    def on_ctx_preset(self):
        k = self.ctx_preset.get()
        if k in CTX_PRESETS:
            self.ctx_input.delete(0, 'end')
            self.ctx_input.insert(0, str(CTX_PRESETS[k]))
            self.update_calc()

    def sync_ctx_preset(self):
        try:
            v = int(self.ctx_input.get())
        except (ValueError, TypeError):
            self.ctx_preset.set('自定义')
            return
        for k, pv in CTX_PRESETS.items():
            if pv == v:
                self.ctx_preset.set(k)
                return
        self.ctx_preset.set('自定义')

    def update_calc(self):
        try:
            ctx = int(self.ctx_input.get())
            par = int(self.parallel_sel.get())
        except ValueError:
            self.per_worker_lab.configure(text='')
            return
        if par <= 1:
            self.per_worker_lab.configure(text='')
        else:
            self.per_worker_lab.configure(text=f'每线程上下文 ≈ {ctx // par}')

    def update_host_hint(self):
        self.host_hint.configure(text='[本机]' if self.host_sel.get() == '127.0.0.1' else '[局域网]')

    def refresh_gpus(self):
        # 从缓存读显卡列表（首次由 _startup_hardware 检测并写入）
        self._apply_gpus(self.get_cached_gpus())

    def _apply_gpus(self, gpus):
        self.gpu_sel.configure(values=['自动'] + gpus)
        cur = self.gpu_sel.get()
        self.gpu_sel.set(cur if cur in self.gpu_sel.cget('values') else '自动')
        self.append_log(f'>>> 检测到 {len(gpus)} 块显卡' if gpus else '>>> 未检测到 NVIDIA 显卡')

    def save_preset(self):
        if not self.current_model:
            return
        name = self.preset_name.get().strip()
        if not name:
            self.append_log('!!! 先填预设名'); return
        try:
            params = self.read_params()
        except ValueError as e:
            self.append_log('!!! ' + str(e)); return
        exists = name in self.presets.get(self.current_model, {})

        def do_save():
            self.presets.setdefault(self.current_model, {})[name] = params
            save_presets(self.presets)
            self.refresh_preset_menu()
            self.preset_sel.set(name)
            self.cfg.setdefault('last_preset', {})[self.current_model] = name
            save_cfg(self.cfg)
            self.param_src_lab.configure(text=f'📌 预设：{name}', text_color='#e8c468')
            self.update_preset_controls()
            self.append_log(f'>>> 已存预设「{name}」({self.current_model})')

        if exists and self.cfg.get('overwrite_ask', True):
            self.confirm_overwrite(name, do_save)
        else:
            do_save()

    def del_preset(self):
        n = self.preset_sel.get()
        if not n or n == '（无预设）' or not self.current_model:
            return
        if n in self.presets.get(self.current_model, {}):
            del self.presets[self.current_model][n]
            save_presets(self.presets)
            if self.cfg.get('last_preset', {}).get(self.current_model) == n:
                self.cfg['last_preset'].pop(self.current_model, None)
                save_cfg(self.cfg)
            self.refresh_preset_menu()
            self.append_log(f'>>> 已删预设「{n}」')

    def confirm_overwrite(self, name, callback):
        dlg = ctk.CTkToplevel(self)
        dlg.title('覆盖预设')
        dlg.geometry('380x190')
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.attributes('-topmost', True)
        ctk.CTkLabel(dlg, text=f'预设「{name}」已存在，覆盖吗？', font=('Microsoft YaHei', 14)).pack(pady=(20, 6))
        noask = ctk.CTkCheckBox(dlg, text='以后不再提示（同名直接覆盖，可在设置里重新开启）')
        noask.pack(pady=2)
        btns = ctk.CTkFrame(dlg)
        btns.pack(pady=(12, 14))

        def ok():
            if noask.get():
                self.cfg['overwrite_ask'] = False
                save_cfg(self.cfg)
            dlg.destroy()
            callback()

        ctk.CTkButton(btns, text='覆盖', width=96, fg_color='#2f7a50', hover_color='#358a5c', command=ok).pack(side='left', padx=10)
        ctk.CTkButton(btns, text='取消', width=96, command=dlg.destroy).pack(side='left', padx=10)

    def open_settings(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title('设置')
        dlg.geometry('400x340')
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.attributes('-topmost', True)
        ask = ctk.CTkCheckBox(dlg, text='保存预设时询问是否覆盖同名预设')
        if self.cfg.get('overwrite_ask', True):
            ask.select()
        ask.pack(pady=(22, 8), padx=24, anchor='w')

        def save():
            self.cfg['overwrite_ask'] = bool(ask.get())
            save_cfg(self.cfg)
            dlg.destroy()

        ctk.CTkButton(dlg, text='保存', width=90, command=save).pack(pady=6)

        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(12, 2))
        ctk.CTkLabel(dlg, text=f'LLM GUI · v{VERSION}', font=('Microsoft YaHei', 14, 'bold')).pack()
        ctk.CTkLabel(dlg, text='llama-server 本地桌面启动器', text_color='#9aa4b8').pack(pady=(2, 0))
        ctk.CTkLabel(dlg, text=f'GitHub：{GITHUB_USER}', text_color='#9aa4b8').pack(pady=(8, 0))
        link = ctk.CTkLabel(dlg, text=GITHUB_URL, text_color='#7db4ff', cursor='hand2', font=('Consolas', 11))
        link.pack(pady=(2, 0))
        link.bind('<Button-1>', lambda _: webbrowser.open(GITHUB_URL))

    def append_log(self, line):
        self.log_box.configure(state='normal')
        self.log_box.insert('end', line + '\n')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def clear_log(self):
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        self.log_box.configure(state='disabled')

    def update_svc_info(self, model, p):
        host = p.get('host', '127.0.0.1')
        port = p['port']
        if host == '0.0.0.0':
            ip = _lan_ip()
            base = f'http://127.0.0.1:{port}（本机）'
            if ip:
                base += f'  ·  http://{ip}:{port}（局域网）'
        else:
            base = f'http://{host}:{port}'
        body = '\n'.join('  ' + s for s in API_SUFFIXES)
        self.svc_info.configure(text=f'模型：{model}\nAPI：{base}\n{body}', text_color='#7fd9a0')

    def build_cmd(self, model, p):
        exe = p.get('server_path') or SERVER_EXE
        args = [exe, '-m', os.path.join(MODELS_DIR, model),
                '-ngl', str(p['ngl']), '-c', str(p['ctx']), '--flash-attn', p['flash'],
                '-ctk', p['cache'], '-ctv', p['cache'], '-n', str(p['n_predict']),
                '--parallel', str(p['parallel']), '--temp', str(p['temp']), '--top-p', str(p['top_p']),
                '--host', p['host'], '--port', str(p['port'])]
        if p.get('gpu') and p['gpu'] != '自动' and p['gpu']:
            args += ['--main-gpu', p['gpu'].split(',')[0].strip()]
        if p.get('n_batch'):
            args += ['--batch-size', p['n_batch']]
        if self.is_gemma(model) and os.path.exists(JINJA):
            args += ['--chat-template-file', JINJA]
        return args

    def start(self):
        if self.proc and self.proc.poll() is None:
            self.append_log('!!! 已有实例在运行，先停止'); return
        if not self.current_model or self.current_model.startswith('（'):
            self.append_log('!!! 没有可选模型'); return
        if not os.path.exists(os.path.join(MODELS_DIR, self.current_model)):
            self.append_log('!!! 模型文件不存在：' + self.current_model + '（以后下回来即可用）'); return
        try:
            p = self.read_params()
        except ValueError as e:
            self.append_log('!!! ' + str(e)); return
        args = self.build_cmd(self.current_model, p)
        self.append_log('>>> 启动: ' + ' '.join(args))
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, encoding='utf-8', errors='replace', bufsize=1)
        except Exception as e:
            self.append_log('!!! 启动失败: ' + str(e)); return
        self.status_lab.configure(text=f'● 运行中 · {self.current_model} · :{p["port"]}', text_color='#7fd9a0')
        self.update_svc_info(self.current_model, p)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in iter(self.proc.stdout.readline, ''):
            if line:
                self.after(0, self.append_log, line.rstrip('\n'))
        self.after(0, self.append_log, '>>> 服务进程已退出')
        self.after(0, self._mark_stopped)

    def _mark_stopped(self):
        self.status_lab.configure(text='● 未运行', text_color='#e07070')
        self.svc_info.configure(text='（未运行）', text_color='#9aa4b8')

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except Exception:
                self.proc.kill()
            self.append_log('>>> 已停止'); self._mark_stopped(); self.proc = None
        else:
            self.append_log('没有运行中的实例')

    def on_close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
        self.destroy()


def main():
    try:
        if not os.path.exists(SERVER_EXE):
            messagebox.showerror('LLM GUI', '未找到 llama-server.exe\n请把它放到：\n' + BASE)
            return
        App().mainloop()
    except Exception:
        tb = traceback.format_exc()
        try:
            with open(os.path.join(BASE, 'llm_gui_err.log'), 'w', encoding='utf-8') as f:
                f.write(tb)
        except Exception:
            pass
        raise


if __name__ == '__main__':
    main()
