#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM GUI — 本地 llama-server 桌面启动器（customtkinter 原生窗口，不依赖浏览器）

- 扫描 models/ 列模型；每模型多套预设；模型下拉右侧「刷新」按钮可强制重新扫描
- 上下文长度：自定义 + 右侧预设下拉（4K~64K）
- 并发请求 1/2/4/8/16 → 自动算每线程上下文（并发=1 不显示）
- 思考模式开关（默认开，存为预设参数）：on→--reasoning on / off→--reasoning off（Murasaki/Qwen3/DeepSeek 等推理模型）
- GPU 下拉（自动检测 + 手动刷新）→ --main-gpu
- 监听地址带 [本机]/[局域网] 提示
- 所有参数可留空：空字段 = 不传给 llama-server，用 llama 默认值（llama 路径为「设置」里的全局项）
- 启动/停止 llama-server 子进程，日志实时滚动
打包：pyinstaller --onefile --windowed --name LLMGUI --collect-all customtkinter llm_gui.py
"""

# ==================== 维护目录（改动前先读；检索锚点 = 精确搜索串） ====================
# 文件组织：单文件 llm_gui.py。自上而下：常量 → 文件读写 → 硬件检测 → ToolTip → App 类 → main。
#
# 一、全局常量（改默认值/路径先搜这里）
#   - 路径：MODELS_DIR / DATA_FILE / LEGACY_* / SERVER_EXE / JINJA
#     → 检索「MODELS_DIR =」
#   - CTX_PRESETS（上下文档 4K~64K）/ PARALLEL_OPTS（并发档）→ 检索「CTX_PRESETS =」
#   - PARAMS：参数表（ngl/flash/cache/temp/top_p/n_predict/port），布局由 _build_ui 的 positions 映射到标签页
#     → 检索「PARAMS =」「positions =」；新增参数需同步布局映射与读写
#   - GEMMA_JINJA_TEMPLATE / VERSION / GITHUB_* → 检索「GEMMA_JINJA_TEMPLATE =」「VERSION =」
#
# 二、数据文件（与程序同目录 JSON，个人文件 gitignore 不入库）
#   - llm_gui_data.json：config（窗口/硬件/全局设置）+ presets（用户预设）+ defaults（自动计算缓存）
#   - 首次启动自动整合旧 llm_gui_config.json / llm_presets.json / llm_default_presets.json
#     并在整合成功后删除旧文件；预设导入仍支持 JSONC（模板见 presets_template.json）
#   → 读写函数检索「def load_cfg」「def load_presets」「def _strip_jsonc」
#
# 三、顶层函数 / 类
#   _lan_ip() 局域网IP / detect_gpus() 显卡列表 / detect_vram_gb() 显存GB → 检索「def detect_」
#   ToolTip 悬浮提示（place 到主窗，无独立窗口）→ 检索「class ToolTip」
#
# 四、App 类（主窗口，方法按功能分组）
#   - 初始化/生命周期：__init__ / _build_ui（全部 UI 在此构建）/ on_close → 检索「def _build_ui」
#   - 参数区：CTkTabview 内各有独立 CTkScrollableFrame；field() 创建标签与控件
#       运行参数：上下文/并行/GPU/缓存/批次；采样与推理：采样/输出/思考
#       视觉与模板：多模态/投影/图像 token/Gemma；服务连接：地址/端口/CORS
#       positions 字典定义 PARAMS 的页签与位置；_field_tabs/_field_labels 用于错误定位
#   - 模型数据：models_list / load_models / on_model_change（切模型刷新全部状态）
#     refresh_models（⟳ 按钮，异步重扫 models/，保留当前选中；期间按钮禁用）→ 检索「def refresh_models」
#     is_gemma（gemma 自动判断覆盖，按模型存 cfg）→ 检索「def on_model_change」「def is_gemma」
#     思考模式/多模态 thinking/mm 已是预设参数（thinking 默认开、mm 默认关）
#   - 多模态投影：find_mmproj（models/ 里按文件名 token 匹配 mmproj 投影文件；单个直接用、多个选最像的、都不像返回 None）；参数区「投影文件」下拉可手动指定（按模型存 cfg['mmproj']，优先于自动匹配）→ 检索「def find_mmproj」「def refresh_mmproj_menu」
#   - 显示名：clean_model_display（去目录/去 .gguf，仅显示用，不动 current_model）→ 检索「def clean_model_display」
#   - 默认参数：compute_defaults（用途预设，硬件拟合交给 llama.cpp --fit）/ apply_computed_defaults（主线程即时应用）
#     → 检索「def compute_defaults」
#   - 预设：save_preset / del_preset / rename_preset / on_preset_load / refresh_preset_menu
#     import_presets / export_presets / 孤儿预设 manage_orphan_presets / 批量 manage_presets_all
#     → 检索「def save_preset」「def import_presets」「def manage_orphan_presets」
#   - 参数读写：set_params（UI←参数）/ read_params（UI→参数）→ 检索「def set_params」「def read_params」
#     加新参数必须在 set_params / read_params / build_cmd 三处同步（及 presets_template.json）
#   - 命令组装与启停：build_cmd（llama-server 命令行，新 CLI 参数只在此加）
#     start / stop / _read / _mark_stopped → 检索「def build_cmd」「def start」
#   - 后台线程：_poll_q 队列分发（hardware/models/log/exited/stop_error 等；每轮有上限）→ 检索「def _poll_q」
#   - 日志/服务信息：append_log / clear_log / update_svc_info / _set_svc_idle / _svc_*
#   - 弹窗：open_settings / confirm_overwrite / _import_conflict_dialog / manage_* 等
#   - 自动更新：纯函数（normalize/compare/parse_release/find_asset/verify_sha256/build_update_bat）
#     在模块顶部；App 侧 _start_update_check→_handle_update_result→_show_update_dialog→
#     _start_update_download→_on_update_downloaded→_apply_pending_update_and_exit
#     → 检索「def _start_update_check」「def build_update_bat」
# ================================================================================
import codecs, hashlib, json, os, queue, re, socket, struct, subprocess, sys, tempfile, threading, traceback, webbrowser
import urllib.error, urllib.request
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk

APP_ICON_B64 = "AAABAAMAEBAAAAEAIAAoBAAANgAAACAgAAABACAAKBAAAF4EAAAwMAAAAQAgACgkAACGFAAAKAAAABAAAAAgAAAAAQAgAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAoAAAAIAAAAEAAAAABACAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAAAAAAAAAAAAAAAAAACgAAAAwAAAAYAAAAAEAIAAAAAAAACQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP9PjP//T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/T4z//0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/0+M//8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAJCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8AAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAkJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/yQkJP8kJCT/JCQk/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

MODELS_DIR = os.path.join(BASE, 'models')
DATA_FILE = os.path.join(BASE, 'llm_gui_data.json')
LEGACY_PRESETS_FILE = os.path.join(BASE, 'llm_presets.json')
LEGACY_CONFIG_FILE = os.path.join(BASE, 'llm_gui_config.json')
LEGACY_DEFAULTS_FILE = os.path.join(BASE, 'llm_default_presets.json')
SERVER_EXE = os.path.join(BASE, 'llama-server.exe')
JINJA = os.path.join(BASE, 'gemma_chat_template.jinja')

CTX_PRESETS = {'4K': 4096, '8K': 8192, '12K': 12288, '16K': 16384, '24K': 24576, '32K': 32768, '48K': 49152, '64K': 65536}
PARALLEL_OPTS = ['1', '2', '4', '8', '16']

# 模型定位：用户未指定 = 通用（旧「未指定」已删除）
FIM_CATEGORY = '代码补全 / FIM'
CATEGORIES = ['通用', '聊天', '翻译', '角色扮演', '文学创作', '编程', FIM_CATEGORY, 'Agent']


def validate_fim_cache_reuse(category, cache_reuse, n_predict):
    """llama.vim 的 FIM 约束；普通服务器用途不强加此限制。"""
    if (category == FIM_CATEGORY and cache_reuse not in ('', 0)
            and n_predict != '' and cache_reuse <= n_predict):
        raise ValueError('代码补全 / FIM 模式下，缓存复用必须为 0（关闭）或严格大于最大输出')


API_SUFFIXES = ['/v1/chat/completions', '/v1/completions', '/v1/embeddings', '/health']

DEFAULT_SASH_POS = 370   # 新布局为日志预留可读空间，实际位置按窗口高度约束
DEFAULT_WINDOW_SIZE = (940, 880)   # 接近方形，给较大的参数控件与日志留出纵向空间
WINDOW_LAYOUT_VERSION = 1         # 首次使用新比例时重置旧尺寸/分割线，之后仍记住用户调整

UI = dict(bg='#101827', panel='#182233', field='#25344a', border='#506078',
          text='#f8fafc', muted='#c0ccdc', accent='#2563eb', hover='#1d4ed8',
          success='#6ee7b7', warning='#fbbf24', danger='#f87171')

# 操作颜色：常态 / 悬停 / 禁用。禁用时保留色相但降低亮度，避免误判为可点击。
BUTTON_COLORS = {
    'blue': ('#1d4ed8', '#2563eb', '#253956'),
    'green': ('#15803d', '#166534', '#243d32'),
    'purple': ('#6d28d9', '#7c3aed', '#34304d'),
    'teal': ('#0f766e', '#115e59', '#253e43'),
    'red': ('#b91c1c', '#991b1b', '#472f38'),
    'amber': ('#a16207', '#854d0e', '#423a2a'),
    'neutral': ('#3c506b', '#4b6385', '#2b3648'),
}

GEMMA_JINJA_TEMPLATE = """{{ bos_token }}{% for message in messages %}{% if message['role'] == 'user' %}<start_of_turn>user
{{ message['content'] }}<end_of_turn>
{% elif message['role'] == 'assistant' %}<start_of_turn>model
{{ message['content'] }}<end_of_turn>
{% endif %}{% endfor %}{% if add_generation_prompt %}<start_of_turn>model
{% endif %}
"""

VERSION = '1.12.0'
GITHUB_USER = 'BFRKQSB7'
GITHUB_REPO = 'llm-launcher-gui'
UPDATE_API_URL = f'https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest'
RELEASE_PAGE_URL = f'https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/latest'
UPDATE_ASSET_NAME = 'LLMGUI.exe'
UPDATE_USER_AGENT = f'LLMGUI-Updater/{VERSION}'
UPDATE_API_TIMEOUT = 6      # 版本检查快速失败，不能拖住启动
UPDATE_API_RETRY = 3        # 下载：有限次数短间隔重试（配合断点续传）
UPDATE_RETRY_DELAY = 1.0
GITHUB_URL = f'https://github.com/{GITHUB_USER}/{GITHUB_REPO}'
_SRC_MAX = 42   # 来源标识独占一行，长名称仍截断并保留完整悬浮提示
GPU_BOX_PAD = 58   # 显卡下拉箭头区 + 左右内边距（逻辑 px）；裁剪文本可用宽度 = 盒子宽 - 此值
GPU_BOX_MAX = 180  # 显卡下拉逻辑宽度上限：保证右侧「检查配置」按钮不被压缩顶没（rowg 最大 180+8+68=256 < col1 最小 ~284）
MMPROJ_BOX_PAD = 58   # 投影文件下拉箭头区 + 左右内边距（逻辑 px）；裁剪文本可用宽度 = 盒子宽 - 此值
MMPROJ_BOX_MAX = 240  # 投影文件下拉逻辑宽度上限：默认 dynamic_resizing=True 会被长文件名撑到近千 px（实测 958），关闭后按本函数自适应、超宽截断，全名见右侧小字/悬浮提示


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

# 简单字段：key / 标签 / 解释 / 可选选项（「（默认）」= 留空不传，用 llama 默认值）
PARAMS = [
    dict(k='ngl', t='GPU 层数', tip='卸载到 GPU 的层数。999=全部（最快最占显存）；0=纯 CPU（不占显存，可与其他 GPU 任务同时运行）；留空=用 llama 默认。'),
    dict(k='flash', t='Flash Attention', tip='闪存注意力。N 卡 20/30/40/50 系建议 on，加速且省显存。新版 llama 要带值 on/off/auto。留空（默认）=不传该参数。', sel=['（默认）', 'on', 'off', 'auto']),
    dict(k='cache', t='KV 缓存精度', tip='KV Cache 精度。q8_0=8bit 量化显存减半、质量几乎无损（推荐）；fp16=高精度占显存；q4_0=更省但轻微下降。留空（默认）=不传。', sel=['（默认）', 'q8_0', 'fp16', 'q4_0']),
    dict(k='temp', t='温度 temp', tip='采样温度。越低越确定/保守（翻译 0.1~0.3），越高越随机。留空=用 llama 默认。'),
    dict(k='top_p', t='top-p', tip='核采样阈值。越低越保守，越高越多样。留空=用 llama 默认。'),
    dict(k='n_predict', t='最大输出', tip='单次请求最多生成的 token 数。翻译 4096 够；提示词转换 512 足够。留空=不限。'),
    dict(k='port', t='端口', tip='llama-server 监听端口。留空=用 llama 默认 8080（可在「设置」设默认端口）；与已运行的其他实例错开，避免端口冲突。'),
]


def _strip_jsonc(text):
    """去掉 // 和 /* */ 注释（字符串内保留原样）。支持预设模板 JSONC（带说明注释）。"""
    out, i, n = [], 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == '\\':
                i += 1
                if i < n:
                    out.append(text[i])
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c); i += 1; continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            while i < n and text[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            i += 2
            while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i = min(i + 2, n)
            continue
        out.append(c); i += 1
    return ''.join(out)


def _load_jsonc(path):
    """读取 JSON/JSONC 文件；解析失败返回 None。"""
    try:
        with open(path, encoding='utf-8') as f:
            return json.loads(_strip_jsonc(f.read()))
    except Exception:
        return None


_DATA_LOCK = threading.RLock()
_DATA_SECTIONS = ('config', 'presets', 'defaults')


def _empty_data():
    return {key: {} for key in _DATA_SECTIONS}


def _write_data(data):
    """同目录临时文件落盘后原子替换，避免中途退出留下半截 JSON。"""
    tmp = DATA_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, DATA_FILE)


def _load_data():
    """读取统一数据；首次运行自动迁移三个旧文件。"""
    with _DATA_LOCK:
        current = _load_jsonc(DATA_FILE) if os.path.exists(DATA_FILE) else None
        if isinstance(current, dict) and all(isinstance(current.get(k, {}), dict) for k in _DATA_SECTIONS):
            data = {key: current.get(key, {}) for key in _DATA_SECTIONS}
            # 统一文件已有效时，旧文件只可能是迁移后的残留；尽力清理，不再让旧数据反向覆盖新数据。
            for path in (LEGACY_CONFIG_FILE, LEGACY_PRESETS_FILE, LEGACY_DEFAULTS_FILE):
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
            return data

        data = _empty_data()
        found_legacy = False
        for section, path in (
            ('config', LEGACY_CONFIG_FILE),
            ('presets', LEGACY_PRESETS_FILE),
            ('defaults', LEGACY_DEFAULTS_FILE),
        ):
            if not os.path.exists(path):
                continue
            legacy = _load_jsonc(path)
            if isinstance(legacy, dict):
                data[section] = legacy
                found_legacy = True

        if found_legacy or not os.path.exists(DATA_FILE):
            _write_data(data)
            for path in (LEGACY_CONFIG_FILE, LEGACY_PRESETS_FILE, LEGACY_DEFAULTS_FILE):
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
        return data


def _save_section(section, value):
    with _DATA_LOCK:
        data = _load_data()
        data[section] = value
        _write_data(data)


def load_presets():
    return _load_data()['presets']


def load_defaults():
    return _load_data()['defaults']


def save_defaults(d):
    _save_section('defaults', d)


def save_presets(d):
    _save_section('presets', d)


def load_cfg():
    cfg = _load_data()['config']
    return cfg if cfg else {'overwrite_ask': True}


def save_cfg(c):
    _save_section('config', c)


# ==================== 自动更新（检查 / 下载 / 校验 / 辅助替换） ====================
# 拆分原则：纯函数（版本比较、asset 查找、digest 解析、文件校验、脚本生成）不碰 Tk，
# 便于单元测试；网络与子进程替换集中在少量函数里。所有网络/磁盘工作都在后台线程执行，
# 结果只通过 self._q 回主线程，禁止工作线程直接操作 tkinter 控件。

def normalize_version(tag):
    """把 GitHub tag 规范化为可比较版本串：v1.12.0 → 1.12.0，去空白与首尾 v/V。"""
    return re.sub(r'^[vV]\s*', '', str(tag or '').strip())


def _parse_version_tuple(text):
    """数字版本比较用；无法解析返回 None。'1.10.10' → (1, 10, 10)。"""
    m = re.match(r'^(\d+(?:\.\d+)*)', normalize_version(text))
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split('.'))


def compare_versions(a, b):
    """返回 (是否 a>b, 是否 a<b)。数字逐段比较，缺失段按 0；1.10.10 > 1.10.2。

    任一侧无法解析时视为无法比较（都返回 False），避免把垃圾 tag 当成新版本。
    """
    ta, tb = _parse_version_tuple(a), _parse_version_tuple(b)
    if ta is None or tb is None:
        return False, False
    n = max(len(ta), len(tb))
    va = ta + (0,) * (n - len(ta))
    vb = tb + (0,) * (n - len(tb))
    return va > vb, va < vb


def parse_sha256_digest(digest):
    """解析 asset 的 digest 字段。返回小写十六进制串或 None。"""
    if not digest or not isinstance(digest, str):
        return None
    text = digest.strip().lower()
    if text.startswith('sha256:'):
        text = text[len('sha256:'):].strip()
    if re.fullmatch(r'[0-9a-f]{64}', text):
        return text
    return None


def find_asset(assets, name=UPDATE_ASSET_NAME):
    """从 release assets 中找指定文件名（大小写不敏感），无则返回 None。"""
    for a in assets or []:
        if not isinstance(a, dict):
            continue
        if str(a.get('name') or '').strip().lower() == name.lower():
            return a
    return None


def sha256_file(path, chunk_size=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(chunk_size), b''):
            h.update(blk)
    return h.hexdigest()


def verify_sha256(path, digest):
    """返回 (是否校验通过, 计算值)。digest 为空(无校验值)时视为通过。"""
    actual = sha256_file(path)
    want = parse_sha256_digest(digest)
    if want is None:
        return True, actual
    return actual == want, actual


def default_auto_check_updates(cfg):
    """旧用户无该字段时默认开；显式关闭才不自动检查。"""
    return bool(cfg.get('auto_check_updates', True))


def parse_release(api_json):
    """把 releases/latest 响应转成更新信息 dict；非可用正式版返回 None。

    过滤 draft / prerelease；规范化 tag；找不到 LLMGUI.exe asset 时仍返回信息
    （只用于提示），是否可一键更新由 asset 是否为 None 决定。
    """
    if not isinstance(api_json, dict):
        return None
    if api_json.get('draft') or api_json.get('prerelease'):
        return None
    tag = str(api_json.get('tag_name') or '').strip()
    if not tag:
        return None
    asset = find_asset(api_json.get('assets'))
    info = {
        'tag': tag,
        'version': normalize_version(tag),
        'name': api_json.get('name') or '',
        'body': api_json.get('body') or '',
        'html_url': api_json.get('html_url') or RELEASE_PAGE_URL,
        'asset_name': None,
        'asset_url': None,
        'digest': None,
        'size': None,
    }
    if asset:
        info['asset_name'] = asset.get('name')
        info['asset_url'] = asset.get('browser_download_url')
        info['digest'] = parse_sha256_digest(asset.get('digest'))
        info['size'] = asset.get('size')
    return info


def is_update_available(local_version, remote_version):
    """远端严格大于本地才提示。"""
    newer, _older = compare_versions(remote_version, local_version)
    return newer


def _console_encoding():
    """Windows 控制台/批处理默认代码页（中文 GBK=936）；非 Windows 退 UTF-8。"""
    if os.name == 'nt':
        return codecs.lookup('mbcs').name   # open()/str.encode 只接受编码名字符串
    return 'utf-8'


def quote_cmd_arg(arg):
    """给 Windows 命令行参数加引号，路径含空格/中文/特殊目录也能正确传递。"""
    s = str(arg).replace('"', '""')
    return '"' + s + '"'


def build_update_bat(new_exe, target_exe, pid, bat_path=None, relaunch=True, log_path=None):
    """生成替换辅助 .bat 的内容（不落盘，便于测试）。

    - 等待旧进程（按 PID）退出；tasklist/powershell 双探针，最多约 30 秒，绝不无限循环
    - 覆盖失败时短间隔重试（应对 Defender/杀软短暂占用），有限次数
    - 覆盖成功后删除已失效的临时新版，再启动新版，最后自删除
    """
    target_exe = os.path.abspath(target_exe)
    new_exe = os.path.abspath(new_exe)
    target_dir = os.path.dirname(target_exe)
    if bat_path is None or log_path is None:
        stem = os.path.basename(bat_path or 'llmgui-update.bat')
        stem = os.path.splitext(stem)[0]
        tmpdir = os.path.dirname(new_exe)
        bat_path = bat_path or os.path.join(tmpdir, stem + '.bat')
        log_path = log_path or os.path.join(tmpdir, stem + '.log')
    lines = [
        '@echo off',
        'setlocal enableextensions',
        'rem LLM GUI 自动更新辅助脚本 —— 由程序生成，退出后替换 EXE 并重启新版',
        f'set "TARGET={target_exe}"',
        f'set "NEWEXE={new_exe}"',
        f'set "PID={int(pid)}"',
        f'set "WAITLOOP=0"',
        ':waitloop',
        f'set /a WAITLOOP+=1',
        f'if %WAITLOOP% GTR 30 goto killcheck_done',
        # 用 %SystemRoot% 下的 findstr 全路径：PATH 里 Git 版 find.exe 会抢占裸 find，
        # 导致把 PID 当文件名、errorlevel=1 误判“进程已退出”，从而跳过等待循环。
        'tasklist /FI "PID eq %PID%" /NH 2>nul | "%SystemRoot%\\System32\\findstr.exe" /c:"%PID%" >nul',
        'if errorlevel 1 goto job_start',
        'powershell -NoProfile -ExecutionPolicy Bypass -Command '
        '"if (Get-Process -Id %PID% -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }" >nul 2>nul',
        'if errorlevel 1 (',
        '  ping -n 2 127.0.0.1 >nul',
        '  goto waitloop',
        ')',
        ':killcheck_done',
        ':job_start',
        'rem 文件可能被系统短暂占用，做有限次数短间隔重试',
        'set "TRY=0"',
        ':copyloop',
        f'set /a TRY+=1',
        f'copy /y "%NEWEXE%" "%TARGET%" >> "{log_path}" 2>&1',
        'if not errorlevel 1 goto launched',
        'if %TRY% GEQ 15 goto giveup',
        'ping -n 2 127.0.0.1 >nul',
        'goto copyloop',
        ':launched',
        'del /f /q "%NEWEXE%" >> "' + log_path + '" 2>&1',
    ]
    if relaunch:
        self_dir = os.path.dirname(bat_path)
        lines += [
            f'cd /d "{self_dir}"',
            f'start "" "%TARGET%"',
        ]
    lines += [
        ':giveup',
        'rem 自删除：cmd 退出后由 powershell 删除本脚本与日志',
        f'start "" /b powershell -NoProfile -ExecutionPolicy Bypass -Command '
        f'"Start-Sleep -Milliseconds 600; Remove-Item -Force -LiteralPath {quote_cmd_arg(bat_path)},'
        f'{quote_cmd_arg(log_path)} -ErrorAction SilentlyContinue" >nul 2>&1',
        'endlocal',
    ]
    return '\r\n'.join(lines) + '\r\n'


def write_update_bat(bat_path, content):
    """以系统控制台代码页写入 .bat，保证含中文路径时 cmd 能正确解析。"""
    with open(bat_path, 'w', encoding=_console_encoding(), errors='replace', newline='') as f:
        f.write(content)


def spawn_detached(argv):
    """无窗口地启动辅助脚本/命令，避免随启动器退出被回收。

    重要：这里**不能**用 DETACHED_PROCESS。实测它会让 cmd.exe 拿不到控制台，
    `cmd /c xxx.bat` 直接静默退出（一行都不执行），导致“点了立即更新没反应”。
    CREATE_NO_WINDOW 已经能隐藏窗口；CREATE_NEW_PROCESS_GROUP 用于减少被
    父进程控制台事件（如 Ctrl+C）牵连的概率。CREATE_BREAKAWAY_FROM_JOB 仅在
    进程处于 Job 中且已放行时可用，故失败时回退，不让更新流程中断。
    """
    if os.name != 'nt':
        return subprocess.Popen(argv, close_fds=True,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    base = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    breakaway = getattr(subprocess, 'CREATE_BREAKAWAY_FROM_JOB', 0)
    try:
        return subprocess.Popen(argv, close_fds=True, creationflags=base | breakaway,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError:
        # 当前进程不在 Job 中（或 Job 不允许 breakaway）时，WinError 5 会被抛出，回退即可。
        return subprocess.Popen(argv, close_fds=True, creationflags=base,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)


def _short_error(exc):
    """把网络/HTTP 异常压成一句可读中文，供弹窗与日志使用。"""
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        if code == 404:
            return '更新源返回 404（尚未发布正式 Release）'
        if code == 403:
            return '更新源拒绝访问（可能是 API 限流，请稍后重试）'
        if 500 <= code < 600:
            return f'更新服务器错误（HTTP {code}）'
        return f'更新请求失败（HTTP {code}）'
    if isinstance(exc, urllib.error.URLError):
        return '网络不可用或无法连接更新源'
    if isinstance(exc, TimeoutError):
        return '更新检查超时'
    return str(exc) or exc.__class__.__name__


def _http_get_json(url, timeout=UPDATE_API_TIMEOUT):
    """请求 GitHub API 并解析 JSON；任何失败都抛异常由调用方处理。"""
    req = urllib.request.Request(url, headers={
        'User-Agent': UPDATE_USER_AGENT,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode('utf-8', 'replace'))


def fetch_latest_release(timeout=UPDATE_API_TIMEOUT):
    """获取最新正式 Release 信息（已过滤 draft/prerelease），无可用版本返回 None。"""
    return parse_release(_http_get_json(UPDATE_API_URL, timeout=timeout))


def download_asset(url, dest, expected_size=None, on_progress=None, on_phase=None):
    """下载 asset 到 dest（临时文件）。返回下载字节数。支持断点续传与有限重试。

    只使用标准库；Content-Length 可得时按百分比回调 on_progress(done, total)。
    校验不在此函数内做，交由调用方 verify_sha256。
    """
    total = int(expected_size) if expected_size else None
    last_err = None
    done = 0
    for attempt in range(UPDATE_API_RETRY):
        try:
            resume_from = os.path.getsize(dest) if (attempt > 0 and os.path.exists(dest)) else 0
            if attempt > 0 and resume_from == 0:
                try:
                    os.remove(dest)
                except OSError:
                    pass
            headers = {'User-Agent': UPDATE_USER_AGENT}
            if resume_from:
                headers['Range'] = f'bytes={resume_from}-'
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=max(UPDATE_API_TIMEOUT, 30)) as resp:
                if total is None:
                    cl = resp.headers.get('Content-Length')
                    if cl and cl.isdigit():
                        total = (resume_from + int(cl)) if resume_from else int(cl)
                mode = 'ab' if resume_from else 'wb'
                done = resume_from
                with open(dest, mode) as f:
                    if on_phase:
                        on_phase('downloading')
                    while True:
                        chunk = resp.read(1 << 16)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if on_progress:
                            on_progress(done, total)
            return done
        except Exception as e:   # 网络中断 / HTTP 错误 / 磁盘错误，统一有限重试
            last_err = e
            if attempt >= UPDATE_API_RETRY - 1:
                break
            import time as _time
            _time.sleep(UPDATE_RETRY_DELAY)
    raise last_err if last_err else RuntimeError('下载失败')

# ================================================================================


# mmproj 文件名里的量化/精度后缀 token，不参与身份匹配（否则短数字会误匹配进 f16/q8_0 等）
_MMPROJ_NOISE = {'f16', 'f32', 'bf16', 'fp16', 'gguf', 'i8',
                 'q8_0', 'q4_0', 'q4_1', 'q5_0', 'q5_1', 'q6_k', 'q5_k', 'q4_k', 'q3_k', 'q2_k'}


def _mmproj_tokens(name):
    """mmproj 匹配用规范化 token：小写、去目录/.gguf/去 mmproj- 前缀、按非字母数字切分、去量化后缀。"""
    n = os.path.basename(name or '').lower()
    if n.endswith('.gguf'):
        n = n[:-5]
    if n.startswith('mmproj-'):
        n = n[len('mmproj-'):]
    n = re.sub(r'[^a-z0-9]+', ' ', n)
    return [t for t in n.split(' ') if t and t not in _MMPROJ_NOISE]


def _is_size_token(t):
    """尺寸类 token（7b/13b/2b 或纯数字），系列内区分不同尺寸的关键。"""
    return (len(t) >= 2 and t.endswith('b') and t[:-1].isdigit()) or t.isdigit()


def find_mmproj(model):
    """在 models/ 里找与当前模型匹配的多模态投影文件（文件名含 mmproj 的 .gguf）。
    - 只有一个 mmproj → 直接用（无从混淆，mmproj-F16 这类通用名也能配）
    - 多个 → 按文件名 token 重叠度选最像的（尺寸 token 加权），至少命中 2 个才算匹配，否则 None（启动时提示）
    拿不准时可在参数区「投影文件」手动指定（按模型记忆，优先于自动匹配）。
    含 mmproj 的文件不作为可选模型（见 models_list）。"""
    try:
        files = os.listdir(MODELS_DIR)
    except Exception:
        return None
    cands = sorted(f for f in files if f.lower().endswith('.gguf') and 'mmproj' in f.lower())
    if not cands:
        return None
    if len(cands) == 1:
        return os.path.join(MODELS_DIR, cands[0])

    mt = _mmproj_tokens(model)
    if not mt:
        return None
    best = None   # (文件名, 命中模型 token 数, 加权分)
    for c in cands:
        ct = _mmproj_tokens(c)
        matched = [t for t in mt if any(t in u for u in ct)]
        n = len(matched)
        if n == 0:
            continue
        score = sum(2 if _is_size_token(t) else 1 for t in matched)
        if best is None or n > best[1] or (n == best[1] and score > best[2]):
            best = (c, n, score)
    # 多个候选：至少命中 2 个模型 token 才算匹配，否则宁可提示，避免挂错 mmproj
    if best and best[1] >= 2:
        return os.path.join(MODELS_DIR, best[0])
    return None


def clean_model_display(name):
    """显示用模型名：去目录、去 .gguf 后缀（current_model 仍保留完整文件名作路径/预设键）。"""
    n = os.path.basename(name or '')
    if n.lower().endswith('.gguf'):
        n = n[:-5]
    return n


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



# ---------- GGUF 元数据解析（保留的只读工具；自动计算已改用 llama.cpp --fit） ----------

def _read_gguf_val(f, vtype):
    """按 GGUF spec 读一个元数据值；字符串/数组递归。类型码：8=string、9=array、0~7/10~12=数字。"""
    if vtype == 8:
        n = struct.unpack('<Q', f.read(8))[0]
        return f.read(n).decode('utf-8', 'replace')
    if vtype == 9:
        et = struct.unpack('<I', f.read(4))[0]
        cnt = struct.unpack('<Q', f.read(8))[0]
        return [_read_gguf_val(f, et) for _ in range(min(cnt, 1000000))]
    if vtype == 0: return struct.unpack('<B', f.read(1))[0]
    if vtype == 1: return struct.unpack('<b', f.read(1))[0]
    if vtype == 2: return struct.unpack('<H', f.read(2))[0]
    if vtype == 3: return struct.unpack('<h', f.read(2))[0]
    if vtype == 4: return struct.unpack('<I', f.read(4))[0]
    if vtype == 5: return struct.unpack('<i', f.read(4))[0]
    if vtype == 6: return struct.unpack('<f', f.read(4))[0]
    if vtype == 7: return bool(struct.unpack('<B', f.read(1))[0])
    if vtype == 10: return struct.unpack('<Q', f.read(8))[0]
    if vtype == 11: return struct.unpack('<q', f.read(8))[0]
    if vtype == 12: return struct.unpack('<d', f.read(8))[0]
    raise ValueError(vtype)


def read_gguf_meta(path):
    """解析 GGUF 文件头元数据（magic+版本+KV 表，不读权重）。异常/非 GGUF 返回 None。"""
    try:
        with open(path, 'rb') as f:
            if f.read(4) != b'GGUF':
                return None
            struct.unpack('<I', f.read(4))   # version
            struct.unpack('<Q', f.read(8))   # tensor count（不需读 tensor info）
            n_kv = struct.unpack('<Q', f.read(8))[0]
            meta = {}
            for _ in range(min(n_kv, 10000)):
                klen = struct.unpack('<Q', f.read(8))[0]
                if klen > 1 << 20:   # 防御异常大 key
                    return None
                key = f.read(klen).decode('utf-8', 'replace')
                meta[key] = _read_gguf_val(f, struct.unpack('<I', f.read(4))[0])
            return meta
    except Exception:
        return None


def read_model_arch(path):
    """从 GGUF 元数据提取架构参数：{n_layers, kv_per_token, is_moe}。
    kv_per_token = q8_0 KV 缓存每 token 字节数（2×层×KV头×头维，MLA 用压缩维）。
    读不到返回 None（调用方用启发式兜底）。"""
    meta = read_gguf_meta(path)
    if not meta:
        return None

    def get(*suffixes):
        for k, v in meta.items():
            if k.endswith(suffixes):
                return v
        return None

    n_layers = get('.block_count')
    n_kv = get('.attention.head_count_kv') or get('.attention.head_count')
    key_len = get('.attention.key_length')
    val_len = get('.attention.value_length')
    n_heads = get('.attention.head_count')
    n_embd = get('.embedding_length')
    kv_lora = get('.attention.kv_lora_rank')
    qk_rope = get('.attention.qk_rope_head_dim')
    n_experts = get('.expert_count')
    if not n_layers:
        return None
    if kv_lora:   # MLA 模型（DeepSeek V2/V3 等）：K 压缩 + 旋转、V 压缩
        kv_per_token = n_layers * (2 * kv_lora + (qk_rope or 0))
    else:
        head_dim = key_len or val_len
        if head_dim is None and n_embd and n_heads:
            head_dim = n_embd // n_heads
        if not (n_kv and head_dim):
            return None
        kv_per_token = 2 * n_layers * n_kv * head_dim   # q8_0 ≈ 1 字节/元素
    return {'n_layers': n_layers, 'kv_per_token': kv_per_token,
            'is_moe': bool(n_experts and n_experts > 1)}


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
        mx = self.master.winfo_width()
        x = self.widget.winfo_rootx() - self.master.winfo_rootx() + 2
        y = self.widget.winfo_rooty() - self.master.winfo_rooty() + self.widget.winfo_height() + 12
        tw = self.lab.winfo_reqwidth()
        if x + tw > mx - 6:   # 超出右缘 → 右对齐（如靠右的按钮）
            x = max(4, mx - tw - 6)
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
        try:
            if self.lab.winfo_exists() and self.lab.winfo_ismapped():
                self.lab.place_forget()
        except tk.TclError:
            pass


class ParameterError(ValueError):
    def __init__(self, label, message):
        super().__init__(message)
        self.label = label


class App(ctk.CTk):
    # ---------- 自动更新（后台网络/替换 + 主线程 UI 调度） ----------
    def _start_update_check(self, manual=False):
        """启动后台更新检查；结果经队列回主线程。manual=用户手动触发（失败会提示）。"""
        threading.Thread(target=self._update_check_work, args=(manual,), daemon=True).start()

    def _update_check_work(self, manual):
        try:
            info = fetch_latest_release()
            self._q.put(('update_result', info, None, manual, True))
        except Exception as e:
            self._q.put(('update_result', None, _short_error(e), manual, False))

    def _handle_update_result(self, info, err, manual, ok):
        """主线程：处理检查结果。自动检查失败静默；手动检查明确反馈。"""
        if not ok:
            if manual:
                self._show_info('检查更新', err or '网络异常，未能检查更新')
            return
        if not info or not info.get('version'):
            if manual:
                self._show_info('检查更新', '更新源暂无正式版本信息')
            return
        if not is_update_available(VERSION, info['version']):
            if manual:
                self._show_info('检查更新', f'当前已是最新版本 v{VERSION}')
            return
        if not manual and self._update_prompted:
            return
        self._update_prompted = True
        self._show_update_dialog(info)

    def _show_update_dialog(self, info):
        old = getattr(self, '_update_dlg', None)
        if old is not None and old.winfo_exists():
            old.lift(); old.focus_force(); return
        dlg = ctk.CTkToplevel(self)
        self._update_dlg = dlg
        self._apply_icon(dlg)
        dlg.title(f'发现新版本 v{info["version"]}')
        dlg.geometry('540x460')
        dlg.minsize(440, 320)
        dlg.resizable(True, True)
        dlg.transient(self)
        dlg.grab_set()
        dlg.after(10, lambda: self._center_on_main(dlg))
        dlg.attributes('-topmost', True)
        ctk.CTkLabel(dlg, text=f'发现新版本 v{info["version"]}',
                     font=('Microsoft YaHei', 18, 'bold')).pack(pady=(16, 4))
        ctk.CTkLabel(dlg, text=f'当前版本：v{VERSION}    最新版本：v{info["version"]}',
                     text_color=UI['muted']).pack(pady=(0, 8))
        ctk.CTkLabel(dlg, text='更新说明：', anchor='w').pack(fill='x', padx=18)
        box = ctk.CTkTextbox(dlg, height=180, wrap='word', font=('Microsoft YaHei', 13))
        box.pack(fill='both', expand=True, padx=18, pady=(2, 6))
        box.insert('1.0', info.get('body') or '（本次发布未提供更新说明）')
        box.configure(state='disabled')
        can_update = bool(info.get('asset_url'))
        if not can_update:
            ctk.CTkLabel(dlg, text='本次 Release 未提供 LLMGUI.exe，仅能前往发布页下载。',
                         text_color=UI['warning'], anchor='w').pack(fill='x', padx=18)
        prog = ctk.CTkProgressBar(dlg, mode='determinate')
        prog.set(0)
        prog.pack(fill='x', padx=18, pady=(2, 2))
        status = ctk.CTkLabel(dlg, text='', anchor='w', text_color=UI['muted'], height=22)
        status.pack(fill='x', padx=18, pady=(0, 6))
        btns = ctk.CTkFrame(dlg, fg_color='transparent')
        btns.pack(pady=(0, 4))
        update_btn = ctk.CTkButton(btns, height=38, text='立即更新', width=110,
                                   fg_color=BUTTON_COLORS['blue'][0], hover_color=BUTTON_COLORS['blue'][1])
        page_btn = ctk.CTkButton(btns, height=38, text='前往发布页', width=110,
                                 command=lambda: webbrowser.open(info.get('html_url') or RELEASE_PAGE_URL))
        later_btn = ctk.CTkButton(btns, height=38, text='稍后', width=90, command=dlg.destroy)
        update_btn.pack(side='left', padx=6)
        page_btn.pack(side='left', padx=6)
        later_btn.pack(side='left', padx=6)
        ctk.CTkLabel(dlg, text='本次运行最多提示一次；可在「设置」手动检查或关闭自动检查。',
                     text_color=UI['muted'], font=('Microsoft YaHei', 11)).pack(pady=(0, 10))
        state = {'run': False}
        self._update_ui = {'btn': update_btn, 'later': later_btn, 'status': status, 'prog': prog}

        def on_update():
            if state['run']:
                return
            if not can_update:
                webbrowser.open(info.get('html_url') or RELEASE_PAGE_URL)
                return
            if not getattr(sys, 'frozen', False):
                self._show_info('源码运行模式',
                                '源码运行模式不支持直接覆盖更新，请前往 Release 下载正式版本。\n'
                                f'远端版本：v{info["version"]}（当前 v{VERSION}）')
                webbrowser.open(info.get('html_url') or RELEASE_PAGE_URL)
                return
            self._confirm_replace(info, state)

        update_btn.configure(command=on_update)

    def _confirm_replace(self, info, state):
        """覆盖前二次确认（置顶单例）；确认后启动后台下载。"""
        if not getattr(sys, 'frozen', False):
            return
        target = self._update_target_path()
        base_dir = os.path.dirname(target)
        if not base_dir or not os.path.isdir(base_dir) or not os.access(base_dir, os.W_OK):
            self._show_info('无法自动更新',
                            '程序所在目录不可写：\n' + base_dir +
                            '\n请将程序移到有写入权限的目录，或前往发布页手动下载。')
            webbrowser.open(info.get('html_url') or RELEASE_PAGE_URL)
            return

        def go():
            state['run'] = True
            state['btn'].configure(state='disabled')
            state['later'].configure(state='disabled')
            self._start_update_download(info, state, target, base_dir)
        self._confirm_dlg('确认更新',
                          f'将下载并替换当前程序为 v{info["version"]}，'
                          '期间会停止正在运行的服务并重启程序。是否继续？',
                          go, parent=self._update_dlg, yes_text='开始更新')

    def _start_update_download(self, info, state, target, base_dir):
        try:
            fd, tmp_path = tempfile.mkstemp(prefix='LLMGUI-update-', suffix='.exe.tmp', dir=base_dir)
            os.close(fd)
            os.remove(tmp_path)   # 仅用于获得唯一名称，下载时重新创建
        except OSError as e:
            self._update_failed(state, f'无法创建临时文件：{e}')
            return
        try:
            state['status'].configure(text='正在下载更新…', text_color=UI['muted'])
            state['prog'].set(0)
        except Exception:
            pass

        def work():
            try:
                download_asset(info['asset_url'], tmp_path, expected_size=info.get('size'),
                               on_progress=lambda d, t: self._q.put(('update_progress', d, t)))
                self._q.put(('update_phase', 'verifying', None))
                ok, _actual = verify_sha256(tmp_path, info.get('digest'))
                if not ok:
                    raise ValueError('更新文件校验失败（SHA-256 不匹配）')
                self._q.put(('update_downloaded', dict(info), tmp_path, target))
            except Exception as e:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                self._q.put(('update_error', _short_error(e)))
        threading.Thread(target=work, daemon=True).start()

    def _update_target_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.abspath(sys.executable)
        return os.path.abspath(os.path.join(BASE, 'LLMGUI.exe'))

    def _update_failed(self, state, message):
        self.append_log('!!! 更新失败：' + message)
        btn = (state or {}).get('btn')
        st = (state or {}).get('status')
        try:
            if st is not None and st.winfo_exists():
                st.configure(text='更新失败：' + message, text_color=UI['danger'])
            if btn is not None and btn.winfo_exists():
                btn.configure(state='normal', text='重试')
                later = (state or {}).get('later')
                if later is not None and later.winfo_exists():
                    later.configure(state='normal')
        except Exception:
            pass
        if isinstance(state, dict):
            state['run'] = False

    def _poll_update_progress(self, done, total):
        ui = getattr(self, '_update_ui', None)
        if not ui:
            return
        try:
            if total and total > 0:
                frac = min(1.0, done / total)
                ui['prog'].set(frac)
                ui['status'].configure(text=f'正在下载更新… {int(frac * 100)}%')
            else:
                ui['prog'].set(0)
                ui['status'].configure(text=f'正在下载更新… {done // 1024} KB')
        except Exception:
            pass

    def _on_update_downloaded(self, info, tmp_path, target):
        try:
            self._write_and_launch_updater(tmp_path, target)
        except Exception as e:
            self._update_failed(getattr(self, '_update_ui', {}), f'创建更新辅助脚本失败：{e}')
            return
        ui = getattr(self, '_update_ui', None)
        try:
            if ui:
                ui['status'].configure(text='更新已下载，程序即将重启…', text_color=UI['success'])
        except Exception:
            pass
        self._apply_pending_update_and_exit()

    def _write_and_launch_updater(self, tmp_path, target):
        bat_dir = os.path.dirname(target) or BASE
        try:
            fd, bat_path = tempfile.mkstemp(prefix='LLMGUI-update-', suffix='.bat', dir=bat_dir)
            os.close(fd)
        except OSError:
            bat_path = os.path.join(tempfile.gettempdir(), f'LLMGUI-update-{os.getpid()}-{id(tmp_path):x}.bat')
        log_path = (bat_path[:-4] + '.log') if bat_path.lower().endswith('.bat') else (bat_path + '.log')
        content = build_update_bat(tmp_path, target, os.getpid(), bat_path=bat_path, log_path=log_path)
        write_update_bat(bat_path, content)
        spawn_detached(['cmd', '/c', bat_path])

    def _apply_pending_update_and_exit(self):
        """下载校验完成后的收尾：先安全停止由本程序启动的服务，再让辅助脚本替换并重启。"""
        if self._closing:
            return
        if self.proc and self.proc.poll() is None:
            self.append_log('>>> 正在停止服务以完成更新…')
            self._closing = True
            self._update_pending = True
            self._set_service_state('stopping')
            threading.Thread(target=self._terminate_process, args=(self.proc,), daemon=True).start()
            self.after(4000, self._force_apply_pending)
        else:
            self._finish_close()

    def _force_apply_pending(self):
        if self._closed:
            return
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.kill()
            except Exception:
                pass
        self._finish_close()

    def _maybe_auto_check_update(self, delay_ms=1800):
        if not default_auto_check_updates(self.cfg):
            return
        self.after(delay_ms, lambda: self._start_update_check(manual=False))

    def _check_update_manual(self):
        self._start_update_check(manual=True)

    def _show_info(self, title, message):
        """应用风格的信息弹窗，替代系统原生 messagebox（保持一致视觉与置顶行为）。"""
        dlg = ctk.CTkToplevel(self)
        self._apply_icon(dlg)
        dlg.title(title)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.attributes('-topmost', True)
        ctk.CTkLabel(dlg, text=message, font=('Microsoft YaHei', 14), wraplength=420,
                     justify='left').pack(pady=(22, 10), padx=22)
        ctk.CTkButton(dlg, height=38, text='知道了', width=100,
                      command=dlg.destroy).pack(pady=(0, 18))
        try:
            dlg.update_idletasks()
            w = max(320, int(dlg.winfo_reqwidth() / dlg._get_window_scaling()))
            h = int(dlg.winfo_reqheight() / dlg._get_window_scaling()) + 8
            dlg.geometry(f'{w}x{h}')
        except Exception:
            pass
        dlg.after(10, lambda: self._center_on_main(dlg))
        dlg.grab_set()

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')
        # 使用一致的中文字体与中性输入底色，操作按钮按功能配色。
        ctk.ThemeManager.theme['CTkFont']['family'] = 'Microsoft YaHei'
        ctk.ThemeManager.theme['CTkFont']['size'] = 15
        ctk.ThemeManager.theme['CTkOptionMenu'].update(
            fg_color=UI['field'], button_color=UI['border'], button_hover_color=UI['hover'],
            text_color=UI['text'], text_color_disabled='#8798af')
        ctk.ThemeManager.theme['CTkEntry'].update(fg_color=UI['field'], border_color=UI['border'],
                                                text_color=UI['text'], placeholder_text_color=UI['muted'])
        ctk.ThemeManager.theme['CTkCheckBox'].update(fg_color=UI['accent'], hover_color=UI['hover'],
                                                   text_color=UI['text'])
        ctk.ThemeManager.theme['CTkLabel']['text_color'] = UI['text']
        ctk.ThemeManager.theme['CTkButton'].update(text_color=UI['text'], text_color_disabled='#8798af')
        ctk.ThemeManager.theme['CTkToplevel']['fg_color'] = UI['panel']
        self.configure(fg_color=UI['bg'])
        self.title(f'LLM GUI — llama-server 启动器 · v{VERSION}')
        self.geometry(f'{DEFAULT_WINDOW_SIZE[0]}x{DEFAULT_WINDOW_SIZE[1]}')
        self.minsize(780, 640)
        self._set_window_icon()
        self.proc = None
        self._q = queue.Queue()
        self._preset_locked = False
        self._closing = False
        self._closed = False
        self._service_state = 'idle'
        self._hardware_busy = False
        # 自动更新状态：_update_prompted 保证同一次运行最多自动提示一次；
        # _update_pending 标记「本次关闭是为了让辅助脚本替换 EXE」。
        self._update_prompted = False
        self._update_pending = False
        self._api_base = ''
        self.current_model = None
        self.presets = load_presets()
        self.cfg = load_cfg()
        # 模型文件夹可自定义（空=程序同目录 models）；其余文件（presets/config/llama.exe/JINJA）仍留程序目录
        global MODELS_DIR
        MODELS_DIR = self.cfg.get('models_dir') or os.path.join(BASE, 'models')
        # Windows 的 Tk 屏幕尺寸可能缓存了启用 DPI 感知前的值，使用工作区实时像素。
        scale = self._get_window_scaling()
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            work_area = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(work_area), 0):
                screen_w = work_area.right - work_area.left
                screen_h = work_area.bottom - work_area.top
        max_w = max(1, int(screen_w / scale) - 40)
        max_h = max(1, int(screen_h / scale) - 40)
        min_w, min_h = min(780, max_w), min(640, max_h)
        self.minsize(min_w, min_h)
        reset_layout = self.cfg.get('window_layout_version') != WINDOW_LAYOUT_VERSION
        ws = self.cfg.get('window_size') if not reset_layout and self.cfg.get('remember_size', True) else None
        try:
            w, h = (int(ws[0]), int(ws[1])) if isinstance(ws, list) and len(ws) == 2 else DEFAULT_WINDOW_SIZE
        except (TypeError, ValueError, OverflowError):
            w, h = DEFAULT_WINDOW_SIZE
        w, h = max(min_w, min(w, max_w)), max(min_h, min(h, max_h))
        self.geometry(f'{w}x{h}')
        if reset_layout:
            self.cfg['window_size'] = [w, h]
            self.cfg.pop('sash_pos', None)
        self.cfg['window_layout_version'] = WINDOW_LAYOUT_VERSION
        self._build_ui()
        self.load_models()
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        sp = self.cfg.get('sash_pos')
        if self.cfg.get('remember_size', True) and isinstance(sp, int):
            self.after(100, lambda: self._restore_sash(sp))
        else:
            self.after(100, self._restore_default_sash)
        self.after(100, self.on_model_change)
        self.after(250, self._check_server)
        self.after(150, self._poll_q)
        self._maybe_auto_check_update()
        self.after(250, self._check_server)
        self.after(150, self._poll_q)

    def _restore_sash(self, pos):
        try:
            scale = self._get_window_scaling()
            height = self.pw.winfo_height()
            self.pw.sashpos(0, max(1, min(max(int(230 * scale), pos), height - int(130 * scale))))
        except Exception:
            pass

    def _restore_default_sash(self):
        try:
            target = max(int(DEFAULT_SASH_POS * self._get_window_scaling()), int(self.pw.winfo_height() * 0.66))
            self._restore_sash(target)
        except Exception:
            pass

    def _on_pane_resize(self, event=None):
        if self._closing or self._closed:
            return
        try:
            self._restore_sash(self.pw.sashpos(0))
        except tk.TclError:
            pass

    def _set_window_icon(self):
        try:
            import base64, tempfile
            fd, path = tempfile.mkstemp(suffix='.ico')
            with os.fdopen(fd, 'wb') as f:
                f.write(base64.b64decode(APP_ICON_B64))
            self._icon_path = path
            self.iconbitmap(path)
        except Exception:
            pass

    def _apply_icon(self, w):
        try:
            if getattr(self, '_icon_path', None):
                w.iconbitmap(self._icon_path)
        except Exception:
            pass

    def _center_on_main(self, w):
        try:
            w.update_idletasks()
            size = w.geometry().split('+')[0]   # 如 '420x560'
            W, H = map(int, size.split('x'))
            x = self.winfo_rootx() + max(0, (self.winfo_width() - W) // 2)
            y = self.winfo_rooty() + max(0, (self.winfo_height() - H) // 2)
            w.geometry(f'{size}+{x}+{y}')
        except Exception:
            pass

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._param_widgets = []
        self._field_tabs = {}
        self._field_labels = {}

        def button(parent, text, command, width=80, role='neutral', **kwargs):
            colors = BUTTON_COLORS[role]
            widget = ctk.CTkButton(parent, text=text, command=command, width=width, height=40,
                corner_radius=8, fg_color=colors[0], hover_color=colors[1],
                text_color=UI['text'], text_color_disabled='#a7b5c8', **kwargs)
            widget._action_colors = colors
            return widget

        self.top_frame = ctk.CTkFrame(self, fg_color=UI['panel'], corner_radius=12)
        self.top_frame.grid(row=0, column=0, sticky='ew', padx=16, pady=(16, 8))
        self.top_frame.grid_columnconfigure(0, weight=1)
        title = ctk.CTkFrame(self.top_frame, fg_color='transparent')
        title.grid(row=0, column=0, sticky='ew', padx=16, pady=(10, 4))
        ctk.CTkLabel(title, text='LLM GUI', font=('Microsoft YaHei', 22, 'bold'),
                     text_color=UI['text']).pack(side='left')
        ctk.CTkLabel(title, text='本地模型工作台', text_color=UI['muted']).pack(side='left', padx=12)
        button(title, '设置', self.open_settings, 64).pack(side='right')

        model_row = ctk.CTkFrame(self.top_frame, fg_color='transparent')
        model_row.grid(row=1, column=0, sticky='ew', padx=16, pady=5)
        model_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(model_row, text='模型', width=42, anchor='w').grid(row=0, column=0)
        self.model_sel = ctk.CTkOptionMenu(model_row, values=['（暂无模型）'], width=140,
            dynamic_resizing=False, command=lambda _: self.on_model_change(), height=40)
        self.model_sel.grid(row=0, column=1, sticky='ew', padx=(0, 6))
        self._model_tooltip = ToolTip(self.model_sel, '选择 GGUF 模型')
        self.refresh_btn = button(model_row, '刷新', self.refresh_models, 54, role='teal')
        self.refresh_btn.grid(row=0, column=2)
        ToolTip(self.refresh_btn, '重新扫描模型文件夹，保留当前选择与参数')
        self.cat_sel = ctk.CTkOptionMenu(model_row, values=CATEGORIES, width=140, height=40,
                                       dynamic_resizing=False, command=lambda _: self.on_category_change())
        self.cat_sel.grid(row=0, column=3, padx=(12, 6))
        ToolTip(self.cat_sel, '模型用途：切换后会应用对应的默认参数')
        self.compute_btn = button(model_row, '应用默认', lambda: self.apply_computed_defaults(force=True), 86, role='purple')
        self.compute_btn.grid(row=0, column=4)
        ToolTip(self.compute_btn, '按用途重置当前参数；上下文与 GPU 层数交给 llama.cpp 启动时拟合')

        preset_row = ctk.CTkFrame(self.top_frame, fg_color='transparent')
        preset_row.grid(row=2, column=0, sticky='ew', padx=16, pady=5)
        preset_row.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(preset_row, text='预设', width=42, anchor='w').grid(row=0, column=0)
        self.preset_sel = ctk.CTkOptionMenu(preset_row, values=['（无预设）'], width=155, height=40,
                                          dynamic_resizing=False, command=lambda _: self.on_preset_load())
        self.preset_sel.grid(row=0, column=1, padx=(0, 8))
        self.preset_name = ctk.CTkEntry(preset_row, placeholder_text='输入预设名称', width=120, height=40)
        self.preset_name.grid(row=0, column=2, sticky='ew', padx=(0, 8))
        self.save_btn = button(preset_row, '保存预设', self.save_preset, 82, role='blue')
        self.save_btn.grid(row=0, column=3)
        self.rename_btn = button(preset_row, '重命名', self.rename_preset, 66, role='amber')
        self.rename_btn.grid(row=0, column=4, padx=6)
        self.del_btn = button(preset_row, '删除', self.del_preset, 54, role='red')
        self.del_btn.grid(row=0, column=5)
        ToolTip(self.save_btn, '将当前全部参数保存到左侧名称；Ctrl+S 保存')
        ToolTip(self.rename_btn, '把选中的预设改为输入框里的名称')
        ToolTip(self.del_btn, '删除当前选中的预设，删除前会确认')
        self.preset_name.bind('<Return>', lambda _: self.save_preset())
        self.param_src_lab = ctk.CTkLabel(self.top_frame, text='', text_color=UI['muted'],
                                         anchor='w', height=26, font=('Microsoft YaHei', 13))
        self.param_src_lab.grid(row=3, column=0, sticky='ew', padx=58, pady=(0, 8))

        style = ttk.Style(self)
        style.configure('Workspace.Vertical.TPanedwindow', background=UI['bg'])
        self.pw = ttk.Panedwindow(self, orient='vertical', style='Workspace.Vertical.TPanedwindow')
        self.pw.bind('<Configure>', self._on_pane_resize)
        self.pw.grid(row=1, column=0, sticky='nsew', padx=16, pady=0)
        f1 = tk.Frame(self.pw, bg=UI['bg'])
        self.pw.add(f1, weight=3)
        self.param_tabs = ctk.CTkTabview(f1, fg_color=UI['panel'], corner_radius=12,
            segmented_button_fg_color=UI['field'], segmented_button_unselected_color=UI['field'],
            segmented_button_selected_color=UI['accent'], segmented_button_selected_hover_color=UI['hover'],
            text_color=UI['text'])
        self.param_tabs.pack(fill='both', expand=True)
        self.param_frames = {}
        for name in ('运行参数', '采样与推理', '视觉与模板', '服务连接'):
            tab = self.param_tabs.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(1, weight=1)
            hints = {'运行参数': '留空使用引擎默认值；上下文与 GPU 层数留空可在启动时自动拟合。',
                     '采样与推理': '控制回答风格、输出长度和思考方式；悬停字段名称查看说明。',
                     '视觉与模板': '视觉模型需要投影文件；旧版 Gemma 可启用外部聊天模板。',
                     '服务连接': '连接配置在下次启动时生效；运行中的 API 地址显示在日志上方。'}
            ctk.CTkLabel(tab, text=hints[name], text_color=UI['muted'], anchor='w',
                         font=('Microsoft YaHei', 13)).grid(row=0, column=0, sticky='ew', padx=10)
            pf = ctk.CTkScrollableFrame(tab, fg_color=UI['panel'], corner_radius=0)
            pf.grid(row=1, column=0, sticky='nsew', padx=2, pady=(4, 2))
            pf.grid_columnconfigure((0, 1), weight=1, uniform='fields')
            self.param_frames[name] = pf
        self.param_frame = self.param_frames['运行参数']

        def field(tab, row, col, label, tip, attr=None, values=None, placeholder='留空使用默认值', span=1):
            box = ctk.CTkFrame(self.param_frames[tab], fg_color='transparent')
            box.grid(row=row, column=col, columnspan=span, sticky='nsew', padx=10, pady=(4, 8))
            lab = ctk.CTkLabel(box, text=label, anchor='w', height=28, text_color=UI['text'])
            lab.pack(fill='x', pady=(0, 4))
            ToolTip(lab, tip)
            if attr:
                if values:
                    widget = ctk.CTkOptionMenu(box, values=values, dynamic_resizing=False, height=40)
                else:
                    widget = ctk.CTkEntry(box, placeholder_text=placeholder, height=40,
                                           fg_color=UI['field'], border_color=UI['border'])
                widget.pack(fill='x')
                setattr(self, attr, widget)
                self._param_widgets.append(widget)
                self._field_tabs[attr] = tab
                self._field_labels[label] = attr
                return widget
            return box

        basic, sampling, vision, service = tuple(self.param_frames)
        box = field(basic, 0, 0, '上下文长度', '输入 token 数或选择快捷值。留空由 llama.cpp 在启动时自动拟合。')
        row = ctk.CTkFrame(box, fg_color='transparent')
        row.pack(fill='x')
        self.ctx_input = ctk.CTkEntry(row, width=100, height=40, placeholder_text='留空自动拟合')
        self.ctx_input.pack(side='left', fill='x', expand=True)
        self.ctx_input.bind('<KeyRelease>', lambda _: self.sync_ctx_preset())
        self.ctx_preset = ctk.CTkOptionMenu(row, values=['自定义'] + list(CTX_PRESETS), width=96,
                                           height=40, dynamic_resizing=False, command=lambda _: self.on_ctx_preset())
        self.ctx_preset.pack(side='left', padx=(8, 0))
        box = field(basic, 0, 1, '并行请求', '同时处理的请求数；上下文由各请求共享。')
        self.parallel_sel = ctk.CTkOptionMenu(box, values=['（默认）'] + PARALLEL_OPTS,
                                             height=40, command=lambda _: self.update_calc())
        self.parallel_sel.pack(fill='x')
        self.per_worker_lab = ctk.CTkLabel(box, text='', height=18, anchor='w', text_color=UI['success'])
        self.per_worker_lab.pack(fill='x')
        positions = {'ngl': (basic, 1, 0), 'flash': (basic, 1, 1), 'cache': (basic, 2, 0),
                     'temp': (sampling, 0, 0), 'top_p': (sampling, 0, 1),
                     'n_predict': (sampling, 2, 0), 'port': (service, 0, 1)}
        for pp in PARAMS:
            tab, r, c = positions[pp['k']]
            field(tab, r, c, pp['t'], pp['tip'], 'w_' + pp['k'], pp.get('sel'))

        box = field(basic, 2, 1, '推理显卡', '自动由引擎选择，也可指定主显卡；检测不会覆盖当前参数。')
        rowg = ctk.CTkFrame(box, fg_color='transparent')
        rowg.pack(fill='x')
        self.gpu_sel = ctk.CTkOptionMenu(rowg, values=['自动'], width=GPU_BOX_MAX,
            dynamic_resizing=False, height=40, command=lambda _: self._update_gpu_tip())
        self.gpu_sel.pack(side='left')
        self.gpu_tip = ToolTip(self.gpu_sel, '自动选择显卡')
        self.recheck_btn = button(rowg, '检测硬件', self.recheck_hardware, 74, role='teal')
        self.recheck_btn.pack(side='left', padx=(8, 0))
        field(basic, 3, 0, '批处理大小', '逻辑批次大小（--batch-size），留空交给引擎。', 'w_n_batch')
        field(basic, 3, 1, '物理批次大小', '物理计算批次上限（--ubatch-size），通常不大于逻辑批次。', 'w_n_ubatch')
        field(basic, 4, 0, '缓存复用', '提示缓存的最小复用 token 块（--cache-reuse）；0=关闭。', 'w_cache_reuse')
        box = field(basic, 4, 1, 'KV 缓存位置', '勾选后 KV 缓存留在系统内存，为模型权重释放显存。')
        self.no_kv_chk = ctk.CTkCheckBox(box, height=36, checkbox_width=26, checkbox_height=26, text='保留在系统内存', command=self.on_no_kv_toggle)
        self.no_kv_chk.pack(anchor='w', pady=4)
        field(sampling, 1, 0, 'top-k', '只从概率最高的 K 个候选采样；0=关闭。', 'w_top_k')
        field(sampling, 1, 1, 'min-p', '按最高候选概率动态缩放过滤阈值；0=关闭。', 'w_min_p')
        box = field(sampling, 2, 1, '思考模式', '控制 --reasoning on/off，保存到预设。')
        self.think_chk = ctk.CTkCheckBox(box, height=36, checkbox_width=26, checkbox_height=26, text='启用思考', command=self.on_thinking_toggle)
        self.think_chk.pack(anchor='w', pady=4)
        field(sampling, 3, 0, '推理预算', '思考 token 上限：-1=不限，0=立即结束思考。', 'w_reasoning_budget')
        field(sampling, 3, 1, '思考格式', 'API 中思考内容的返回格式（--reasoning-format）。',
              'w_reasoning_format', ['（默认）', 'auto', 'none', 'deepseek', 'deepseek-legacy'])
        box = field(vision, 0, 0, '多模态', '视觉模型启用 --mmproj；下方可选择投影文件。')
        self.mm_chk = ctk.CTkCheckBox(box, height=36, checkbox_width=26, checkbox_height=26, text='启用图像输入', command=self.on_mm_toggle)
        self.mm_chk.pack(anchor='w', pady=4)
        field(vision, 0, 1, '图像 Min Tokens', '每幅图像最少 token 数，越大细节越多、显存占用越高。', 'w_image_min_tokens')
        box = field(vision, 1, 0, '投影文件', '自动按文件名匹配，或手动指定当前模型的投影文件。', span=2)
        self.mmproj_sel = ctk.CTkOptionMenu(box, values=['（自动）'], width=240, height=40,
                                           dynamic_resizing=False, command=lambda _: self.on_mmproj_pick())
        self.mmproj_sel.pack(anchor='w')
        self.mmproj_hint = tk.Label(box, text='', fg=UI['muted'], bg=UI['panel'],
                                    font=('Microsoft YaHei', 12), anchor='w', width=1)
        self.mmproj_hint.pack(fill='x', pady=(4, 0))
        self._mmproj_hint_tt = ToolTip(self.mmproj_hint, '')
        field(vision, 2, 0, '模板额外参数', '合法 JSON 对象，例如 {"enable_thinking":false}。',
              'w_chat_template_kwargs', placeholder='如 {"enable_thinking":false}', span=2)
        box = field(vision, 3, 0, 'Gemma 兼容模板', '只有旧版 Gemma 需要外部模板，新版自带模板无需勾选。', span=2)
        self.gemma_chk = ctk.CTkCheckBox(box, height=36, checkbox_width=26, checkbox_height=26, text='使用旧版 Gemma 外部模板', command=self.on_gemma_toggle)
        self.gemma_chk.pack(anchor='w', pady=4)
        box = field(service, 0, 0, '监听地址', '127.0.0.1 仅本机；0.0.0.0 允许局域网访问（配合防火墙）。')
        self.host_sel = ctk.CTkOptionMenu(box, values=['（默认）', '127.0.0.1', '0.0.0.0'],
                                         height=40, command=lambda _: self.update_host_hint())
        self.host_sel.pack(fill='x')
        self.host_hint = ctk.CTkLabel(box, text='', height=18, text_color=UI['muted'], anchor='w')
        self.host_hint.pack(fill='x')
        field(service, 1, 0, 'CORS 允许源', '跨域访问允许的来源，多个用逗号分隔；留空不传。',
              'w_cors', placeholder='* 或 http://localhost:3000', span=2)
        self._field_tabs.update(ctx_input=basic, parallel_sel=basic, host_sel=service)
        self._field_labels.update({'上下文长度': 'ctx_input', '并行请求': 'parallel_sel',
                                   '温度': 'w_temp', '监听地址': 'host_sel'})

        f2 = tk.Frame(self.pw, bg=UI['panel'])
        log_head = ctk.CTkFrame(f2, fg_color='transparent')
        log_head.pack(fill='x', padx=12, pady=(8, 0))
        ctk.CTkLabel(log_head, text='运行日志', anchor='w', font=('Microsoft YaHei', 15, 'bold')).pack(side='left')
        self.clear_btn = button(log_head, '清空', self.clear_log, 54)
        self.clear_btn.pack(side='right')
        self.copy_api_btn = button(log_head, '复制 API', self.copy_api, 82, role='teal')
        self.copy_api_btn.pack(side='right', padx=6)
        self.svc_info = tk.Text(f2, wrap='word', height=1, bd=0, highlightthickness=0,
            relief='flat', padx=2, pady=2, bg=UI['panel'], fg=UI['muted'], font=('Microsoft YaHei', 12), takefocus=0)
        self.svc_info.pack(fill='x', padx=12, pady=(4, 6))
        self.svc_info.bind('<Key>', self._svc_readonly)
        self.svc_info.bind('<Configure>', lambda _: self._svc_sync_height())
        self.log_box = ctk.CTkTextbox(f2, state='disabled', wrap='word', font=('Microsoft YaHei', 14),
                                      fg_color=UI['bg'], text_color=UI['text'], corner_radius=8)
        self.log_box.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self.pw.add(f2, weight=2)
        self._set_svc_idle()

        self.bar = ctk.CTkFrame(self, fg_color=UI['panel'], corner_radius=12)
        self.bar.grid(row=2, column=0, sticky='ew', padx=16, pady=(8, 16))
        self.bar.grid_columnconfigure(0, weight=1)
        self.status_lab = ctk.CTkLabel(self.bar, text='● 未运行', text_color=UI['muted'], anchor='w')
        self.status_lab.grid(row=0, column=0, sticky='ew', padx=16, pady=12)
        self.stop_btn = button(self.bar, '停止服务', self.stop, 100, role='red')
        self.stop_btn.configure(height=44)
        self.stop_btn.grid(row=0, column=1, padx=8, pady=12)
        self.start_btn = button(self.bar, '启动服务', self.start, 120, role='green')
        self.start_btn.configure(height=44)
        self.start_btn.grid(row=0, column=2, padx=(0, 16), pady=12)
        ToolTip(self.start_btn, '启动当前模型；Ctrl+Enter 启动')
        self._bind_param_edit_marker()
        self.bind('<Control-s>', lambda _: self.save_preset())
        self.bind('<Control-Return>', lambda _: self.start())
        self._sync_action_controls()

    def _bind_param_edit_marker(self):
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
                self._mark_param_edited()
            menu.configure(command=handler)

        for w in [self.ctx_input, self.parallel_sel, self.host_sel, self.gpu_sel, self.w_n_batch, self.w_n_ubatch,
                   self.w_reasoning_budget, self.w_reasoning_format, self.mmproj_sel, self.w_cors,
                   self.w_image_min_tokens, self.w_top_k, self.w_min_p, self.w_cache_reuse,
                   self.w_chat_template_kwargs]:
            if isinstance(w, ctk.CTkEntry):
                w.bind('<KeyRelease>', self._mark_param_edited, add='+')
            elif isinstance(w, ctk.CTkOptionMenu):
                wrap(w)
        for pp in PARAMS:
            w = getattr(self, 'w_' + pp['k'], None)
            if isinstance(w, ctk.CTkEntry):
                w.bind('<KeyRelease>', self._mark_param_edited, add='+')
            elif isinstance(w, ctk.CTkOptionMenu):
                wrap(w)
        wrap(self.ctx_preset)

    def _mark_param_edited(self, event=None):
        if event is not None and event.keysym in ('Tab', 'Shift_L', 'Shift_R', 'Control_L',
                                                   'Control_R', 'Left', 'Right', 'Up', 'Down'):
            return
        self._preset_locked = True
        self._set_param_src('✏ 手动调整 · 保存预设以保留', UI['warning'])

    def _sync_action_controls(self):
        active = self._closing or self._service_state in ('running', 'stopping')
        has_model = bool(self.current_model)
        self._set_button_state(self.start_btn, not active and has_model)
        self._set_button_state(self.stop_btn, self._service_state == 'running',
                               text='正在停止…' if self._service_state == 'stopping' else '停止服务')
        self._set_button_state(self.compute_btn, has_model)
        self._set_button_state(self.save_btn, has_model)
        self._set_button_state(self.copy_api_btn, bool(self._api_base))

    @staticmethod
    def _set_button_state(widget, enabled, **options):
        colors = getattr(widget, '_action_colors', None)
        if colors:
            options['fg_color'] = colors[0] if enabled else colors[2]
        widget.configure(state='normal' if enabled else 'disabled', **options)

    def _set_service_state(self, state, text=None):
        self._service_state = state
        color = UI['success'] if state == 'running' else UI['warning'] if state == 'stopping' else UI['muted']
        self.status_lab.configure(text=text or {'idle': '● 未运行', 'running': '● 进程运行中',
                                                'stopping': '● 正在停止…'}[state], text_color=color)
        self._sync_action_controls()

    def copy_api(self):
        if self._api_base:
            self.clipboard_clear()
            self.clipboard_append(self._api_base)
            self.append_log('>>> API 地址已复制：' + self._api_base)

    def _show_parameter_error(self, error):
        self.append_log('!!! ' + str(error))
        attr = self._field_labels.get(getattr(error, 'label', ''))
        if attr:
            self.param_tabs.set(self._field_tabs[attr])
            widget = getattr(self, attr)
            # 滚动至出错字段，避免隐藏标签页中的输入错误只能从日志里猜。
            self.update_idletasks()
            pf = self.param_frames[self._field_tabs[attr]]
            y = widget.winfo_rooty() - pf.winfo_rooty()
            pf._parent_canvas.yview_moveto(max(0, y - 28) / max(1, pf.winfo_height()))
            widget.focus_set()
            if isinstance(widget, ctk.CTkEntry):
                widget.select_range(0, 'end')

    def _set_param_src(self, text, color, tip=None):
        """设置参数来源标识（⚡自动计算/📌预设/✏手动调整）。超长截断避免把
        「模型/模型定位」那行顶宽，完整内容（预设名/显存细节）放悬浮提示。"""
        if len(text) > _SRC_MAX:
            text = text[:_SRC_MAX - 1] + '…'
        self.param_src_lab.configure(text=text, text_color=color)
        tt = getattr(self, '_src_tooltip', None)
        if tip:
            if tt is None:
                self._src_tooltip = ToolTip(self.param_src_lab, tip)
            else:
                tt.text = tip
                tt.lab.configure(text=tip)
        elif tt is not None:
            tt.text = ''
            tt.lab.configure(text='')
            tt.lab.place_forget()

    # ---------- 数据 ----------
    def models_list(self):
        # mmproj 是多模态投影辅助文件，不作为可选模型
        return sorted(f for f in os.listdir(MODELS_DIR)
                      if f.lower().endswith('.gguf') and 'mmproj' not in f.lower()) if os.path.isdir(MODELS_DIR) else []

    def load_models(self):
        ms = self.models_list()
        self.model_sel.configure(values=ms if ms else ['（models 目录为空）'])
        last = self.cfg.get('last_model')
        m = last if (last and last in ms) else (ms[0] if ms else None)
        self.model_sel.set(m if m else '（models 目录为空）')
        self.current_model = m
        self._model_tooltip.text = m or '暂无模型，请在设置中选择模型文件夹'
        self._model_tooltip.lab.configure(text=self._model_tooltip.text)
        self._sync_action_controls()

    def refresh_models(self):
        """⟳ 按钮：强制重扫 models/ 目录。后台线程扫描，结果经 _q 回主线程，不阻塞 UI。"""
        if not os.path.isdir(MODELS_DIR):
            self.append_log('!!! models 目录不存在：' + os.path.normpath(MODELS_DIR))
            return
        if self.refresh_btn.cget('state') == 'disabled':
            return
        self._set_button_state(self.refresh_btn, False, text='扫描中')
        self.append_log('>>> 正在刷新模型列表…')

        def work():
            try:
                self._q.put(('models', self.models_list(), None))
            except Exception as e:
                self._q.put(('models', [], str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _apply_refreshed_models(self, ms, err):
        # 主线程：刷新完成。恢复按钮；当前选中的模型还在列表里就保持不变，否则回落第一个
        self._set_button_state(self.refresh_btn, True, text='刷新')
        if err:
            self.append_log('!!! 刷新模型列表失败: ' + err)
            return
        cur = self.current_model
        keep = cur if (cur and cur in ms) else None
        self.model_sel.configure(values=ms if ms else ['（models 目录为空）'])
        if keep:
            self.model_sel.set(keep)
            self.refresh_mmproj_menu()
            self.append_log(f'>>> 模型列表已刷新：{len(ms)} 个模型（保持选中 {keep}）')
        elif ms:
            self.model_sel.set(ms[0])
            self.current_model = ms[0]
            self.append_log(f'>>> 模型列表已刷新：{len(ms)} 个模型（原模型已移除，切到 {ms[0]}）')
            self.on_model_change()   # 同步预设 / mmproj / 自动计算
        else:
            self.model_sel.set('（models 目录为空）')
            self.current_model = None
            self.append_log('>>> 模型列表已刷新：models 目录为空')
            self.on_model_change()

    def on_model_change(self):
        m = self.model_sel.get()
        if not m or m.startswith('（'):
            self.current_model = None
            self._preset_locked = True
            self.refresh_preset_menu()
            self.refresh_mmproj_menu()
            self._set_param_src('暂无模型 · 请在设置中选择模型文件夹', UI['muted'])
            self._sync_action_controls()
            return
        self.current_model = m
        self._model_tooltip.text = m
        self._model_tooltip.lab.configure(text=m)
        self._sync_action_controls()
        stem = m[:-5] if m.lower().endswith('.gguf') else m
        self.refresh_preset_menu()
        self.cat_sel.set(self.get_category(m))
        self.gemma_chk.select() if self.is_gemma(m) else self.gemma_chk.deselect()
        self.refresh_mmproj_menu()
        # 有可用预设 → 优先用预设（上次选的 >「默认」> 第一个），都不动自动计算
        # （gemma/思考模式 均随预设加载，由 set_params 设置）
        ps = self.presets.get(m, {})
        if isinstance(ps, dict) and ps:
            last = self.cfg.get('last_preset', {}).get(m)
            pick = last if (last and last in ps) else ('默认' if '默认' in ps else next(iter(ps)))
            self.preset_sel.set(pick)
            self.set_params(ps[pick])
            self.preset_name.delete(0, 'end')
            self.preset_name.insert(0, pick)   # 输入框显示预设名
            self._set_param_src(f'📌 预设：{pick}', '#e8c468', tip=pick)
            self._preset_locked = True
            self.cfg.setdefault('last_preset', {})[m] = pick
            save_cfg(self.cfg)
        else:
            self._preset_locked = False
            self.preset_name.delete(0, 'end')
            self.preset_name.insert(0, stem)   # 无预设 → 输入框显示模型名
            self._set_param_src('', '#8ab4f8')
            self.apply_computed_defaults(m)
        self.update_preset_controls()   # 刷新删预设按钮状态/颜色（自动应用预设后要变鲜艳）

    def is_gemma(self, model):
        # 仅按用户勾选/预设；默认关（新 gemma3/4 自带模板无需外部 --chat-template-file）
        flags = self.cfg.get('gemma', {})
        return bool(flags.get(model, False))

    def on_gemma_toggle(self):
        m = self.current_model
        if not m:
            return
        checked = bool(self.gemma_chk.get())
        self.cfg.setdefault('gemma', {})[m] = checked
        save_cfg(self.cfg)
        if checked and not os.path.exists(JINJA):
            try:
                with open(JINJA, 'w', encoding='utf-8') as f:
                    f.write(GEMMA_JINJA_TEMPLATE)
                self.append_log(f'>>> 已自动生成 Gemma 聊天模板：{JINJA}')
            except Exception as e:
                self.append_log(f'!!! 生成 Gemma 聊天模板失败: {e}')
        self._mark_param_edited()
        self.append_log('>>> Gemma 兼容模板已更新；如需重置温度等参数，请点击「应用默认」')

    def on_thinking_toggle(self):
        self._mark_param_edited()
        checked = bool(self.think_chk.get())
        self.append_log(f'>>> 思考模式：{"开" if checked else "关"}（存为预设时随预设一起保存）')

    def on_mm_toggle(self):
        self._mark_param_edited()
        checked = bool(self.mm_chk.get())
        self.append_log(f'>>> 多模态：{"开" if checked else "关"}（存为预设时随预设一起保存）')

    def on_no_kv_toggle(self):
        self._mark_param_edited()
        checked = bool(self.no_kv_chk.get())
        self.append_log(f'>>> KV 不卸载到 GPU：{"开" if checked else "关"}（存为预设时随预设一起保存）')

    def refresh_mmproj_menu(self):
        """重建「投影文件」下拉（含 models/ 里全部 mmproj 文件）并恢复当前模型记忆的选择。"""
        files = []
        if os.path.isdir(MODELS_DIR):
            files = sorted(f for f in os.listdir(MODELS_DIR)
                           if f.lower().endswith('.gguf') and 'mmproj' in f.lower())
        vals = ['（自动）'] + files
        self.mmproj_sel.configure(values=vals)
        saved = self.cfg.get('mmproj', {}).get(self.current_model or '', '（自动）')
        self.mmproj_sel.set(saved if saved in vals else '（自动）')
        self._size_mmproj_box()
        self.update_mmproj_hint()

    def on_mmproj_pick(self):
        """手动选了具体 mmproj 或回到自动 → 按模型记住，刷新提示。"""
        m = self.current_model
        v = self.mmproj_sel.get()
        if m:
            self.cfg.setdefault('mmproj', {})[m] = v
            save_cfg(self.cfg)
            if v != '（自动）':
                self.append_log(f'>>> {m} 的 mmproj 已手动指定：{v}')
        self._size_mmproj_box()
        self.update_mmproj_hint()

    def update_mmproj_hint(self):
        """投影文件下拉旁的小字：手动/自动匹配到谁/没匹配到；悬浮可看完整文件名。"""
        if not hasattr(self, 'mmproj_sel'):
            return
        v = self.mmproj_sel.get()
        if v != '（自动）':
            self.mmproj_hint.configure(text=v, fg='#e8b04a')
            self._mmproj_hint_tt.lab.configure(text='已手动指定：' + v)
            return
        m = self.current_model
        if not m:
            self.mmproj_hint.configure(text='', fg='#9fd6a5')
            self._mmproj_hint_tt.lab.configure(text='')
            return
        mm = find_mmproj(m)
        if mm:
            fn = os.path.basename(mm)
            self.mmproj_hint.configure(text=fn, fg='#9fd6a5')
            self._mmproj_hint_tt.lab.configure(text='自动匹配：' + fn)
        else:
            self.mmproj_hint.configure(text='自动未匹配（可手动选）', fg='#e8b04a')
            self._mmproj_hint_tt.lab.configure(text='自动未匹配到合适的投影文件，可手动指定')

    def get_category(self, model):
        # 用户未指定 → 通用（旧「未指定」定位已删除，存量数据里的值统一回落通用）
        cat = self.cfg.get('categories', {}).get(model)
        return cat if cat in CATEGORIES else '通用'

    def set_category(self, model, cat):
        self.cfg.setdefault('categories', {})[model] = cat
        save_cfg(self.cfg)

    def compute_defaults(self, model, category, cur_port=''):
        """计算用途预设；显存、上下文与 GPU 卸载交给 llama.cpp --fit。"""
        cat = {
            '聊天':     {'temp': 0.7,  'top_p': 0.9,  'n_predict': 1024},
            '通用':     {'temp': 0.6,  'top_p': 0.9,  'n_predict': 2048},
            '翻译':     {'temp': 0.2,  'top_p': 0.8,  'n_predict': 4096},
            '角色扮演': {'temp': 0.8,  'top_p': 0.95, 'n_predict': 1024},
            '文学创作': {'temp': 0.75, 'top_p': 0.95, 'n_predict': 2048},
            '编程':     {'temp': 0.2,  'top_p': 0.9,  'n_predict': 4096},
            FIM_CATEGORY: {'temp': 0.0, 'top_p': 0.99, 'n_predict': 128},
            'Agent':    {'temp': 0.3,  'top_p': 0.9,  'n_predict': 2048},
        }.get(category, {'temp': 0.5, 'top_p': 0.9, 'n_predict': 2048})
        is_fim = category == FIM_CATEGORY
        if self.is_gemma(model) and not is_fim:
            # Gemma 特适配：低温度 + 长输出（需 --chat-template-file）
            cat = {'temp': 0.1, 'top_p': 0.9, 'n_predict': 4096}
        detail = 'ctx/ngl 留空，由 llama.cpp --fit 按启动时可用显存拟合'
        if is_fim:
            detail += '；FIM：batch 1024 / ubatch 512 / q8_0 KV / cache reuse 256'
        # 端口不随自动计算覆盖：保留当前输入；未设则用设置里的默认端口（兜底 llama 默认 8080）
        port = cur_port or str(self.cfg.get('default_port') or 8080)
        return ({'ctx': '', 'ngl': '', 'flash': 'auto', 'cache': 'q8_0' if is_fim else '',
                 'temp': cat['temp'], 'top_p': cat['top_p'], 'n_predict': cat['n_predict'],
                 'parallel': 1, 'port': port, 'host': '127.0.0.1',
                 'gpu': '自动', 'n_batch': 1024 if is_fim else '', 'n_ubatch': 512 if is_fim else '',
                 'thinking': not is_fim, 'gemma': self.is_gemma(model) and not is_fim,
                 'mm': False, 'cors': '', 'image_min_tokens': '', 'no_kv_offload': False,
                 'top_k': 40 if is_fim else '', 'min_p': '', 'cache_reuse': 256 if is_fim else '',
                 'chat_template_kwargs': '', 'reasoning_format': ''},
                detail)

    def _poll_q(self):
        # 主线程轮询工作线程结果（tkinter 的 after 不能从子线程调）
        if self._closed:
            return
        for _ in range(300):   # 连续日志输出时仍给鼠标、重绘和停止操作留出事件循环时间
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                break
            try:
                kind = item[0]
                if kind == 'gpus':
                    _, gpus = item
                    self._apply_gpus(gpus)
                elif kind == 'hardware':
                    _, vram, gpus = item
                    self.cfg['hardware'] = {'vram_gb': vram, 'gpus': gpus}
                    save_cfg(self.cfg)
                    selected = self.gpu_sel.get()
                    self._apply_gpus(gpus)
                    if selected in self.gpu_sel.cget('values'):
                        self.gpu_sel.set(selected)
                        self._update_gpu_tip()
                    self._finish_hardware_check()
                    self.append_log(f'>>> 硬件检测完成：{len(gpus)} 张显卡，显存 {vram:g} GB')
                elif kind == 'models':
                    _, ms, err = item
                    self._apply_refreshed_models(ms, err)
                elif kind == 'error':
                    self.append_log('!!! ' + item[1])
                elif kind == 'hardware_error':
                    self._finish_hardware_check()
                    self.append_log('!!! 检测本机硬件失败: ' + item[1])
                elif kind == 'log':
                    _, proc, line = item
                    if proc is self.proc:
                        self.append_log(line)
                elif kind == 'exited':
                    _, proc, code = item
                    if proc is self.proc:
                        self.append_log(f'>>> 服务进程已退出（退出码 {code}）')
                        self._mark_stopped(proc)
                        if self._closed:
                            return
                elif kind == 'stop_error':
                    _, proc, error = item
                    if proc is self.proc:
                        self.append_log('!!! 停止失败: ' + error)
                        self._closing = False
                        self._set_service_state('running')
                elif kind == 'update_result':
                    _, info, err, manual, ok = item
                    self._handle_update_result(info, err, manual, ok)
                elif kind == 'update_progress':
                    _, done, total = item
                    self._poll_update_progress(done, total)
                elif kind == 'update_phase':
                    _, phase, _extra = item
                    if phase == 'verifying':
                        ui = getattr(self, '_update_ui', None)
                        if ui:
                            try:
                                ui['status'].configure(text='下载完成，正在校验文件…')
                                ui['prog'].set(1)
                            except Exception:
                                pass
                elif kind == 'update_downloaded':
                    _, info, tmp_path, target = item
                    self._on_update_downloaded(info, tmp_path, target)
                elif kind == 'update_error':
                    _, msg = item
                    self._update_failed(getattr(self, '_update_ui', {}), msg)
            except Exception as e:
                if self._closed:
                    return
                if item[0] in ('hardware', 'hardware_error'):
                    self._finish_hardware_check()
                self.append_log(f'!!! 处理后台结果出错: {e}')
        if not self._closed:
            self.after(50, self._poll_q)

    def get_vram_gb(self):
        return self.cfg.get('hardware', {}).get('vram_gb', 0)

    def get_cached_gpus(self):
        return self.cfg.get('hardware', {}).get('gpus', [])

    def _finish_hardware_check(self):
        self._hardware_busy = False
        self._set_button_state(self.recheck_btn, True, text='检测硬件')

    def _detect_and_save_hardware(self):
        if self._hardware_busy:
            return
        self._hardware_busy = True
        self._set_button_state(self.recheck_btn, False, text='检测中…')
        def work():
            try:
                vram = detect_vram_gb()
                gpus = detect_gpus()
                self._q.put(('hardware', vram, gpus))
            except Exception as e:
                self._q.put(('hardware_error', str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _startup_hardware(self):
        # 首次打开才检测并写 json；之后用缓存，不重复跑 nvidia-smi / 不重复计算
        if self.cfg.get('hardware', {}).get('vram_gb'):
            self._apply_gpus(self.get_cached_gpus())
        else:
            self._detect_and_save_hardware()

    def _check_server(self):
        # 启动后检查 llama-server.exe：缺失不阻塞界面，只提示 + 记日志（可在「设置」里改路径）
        exe = self.cfg.get('server_path') or SERVER_EXE
        if os.path.exists(exe):
            return
        self.append_log('!!! 未找到 llama-server.exe（请在「设置」里配置路径，或放到程序同目录）')
        self._set_service_state('idle', '● 请在设置中选择 llama-server.exe')

    def recheck_hardware(self):
        self._detect_and_save_hardware()

    def apply_computed_defaults(self, model=None, force=False):
        model = model or self.current_model
        if not model:
            return
        if self._preset_locked and not force:
            return
        cat = self.get_category(model)
        # 用途预设只是字典计算，在主线程立即应用，避免延迟结果覆盖新的用户输入。
        try:
            params, detail = self.compute_defaults(model, cat, self.w_port.get().strip())
            self.set_params(params)
            self._preset_locked = False
            self._save_computed_defaults(model, params)
            self._set_param_src(f'⚡ 用途默认 · {cat}', UI['accent'], tip=detail)
            self.append_log(f'>>> 已应用用途预设（{cat}）：{detail}')
        except Exception as e:
            self.append_log(f'!!! 计算默认参数失败: {e}')

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
        enabled = bool(sel and sel != '（无预设）')
        self._set_button_state(self.del_btn, enabled)
        self._set_button_state(self.rename_btn, enabled)

    def on_preset_load(self):
        n = self.preset_sel.get()
        if n and n != '（无预设）' and self.current_model and n in self.presets.get(self.current_model, {}):
            self.set_params(self.presets[self.current_model][n])
            self._set_param_src(f'📌 预设：{n}', '#e8c468', tip=n)
            self._preset_locked = True   # 加载预设后，挂起的自动计算不覆盖用户预设参数
            self.cfg.setdefault('last_preset', {})[self.current_model] = n
            save_cfg(self.cfg)
            self.preset_name.delete(0, 'end')
            self.preset_name.insert(0, n)
        else:
            m = self.current_model   # 选「（无预设）」→ 输入框恢复模型名
            if m:
                stem = m[:-5] if m.lower().endswith('.gguf') else m
                self.preset_name.delete(0, 'end')
                self.preset_name.insert(0, stem)
                self._mark_param_edited()
        self.update_preset_controls()

    def set_params(self, p):
        if not p:
            return

        def set_entry(w, v):
            w.delete(0, 'end')
            if v not in (None, ''):
                w.insert(0, str(v))

        def set_menu(w, v):
            vals = w.cget('values') or []
            if v in (None, '', '（默认）'):
                w.set('（默认）' if '（默认）' in vals else (vals[0] if vals else ''))
            elif str(v) in vals:
                w.set(str(v))

        set_entry(self.ctx_input, p.get('ctx'))
        set_menu(self.parallel_sel, p.get('parallel'))
        set_menu(self.host_sel, p.get('host'))
        gv = p.get('gpu')
        if gv in (None, '', '自动'):
            self.gpu_sel.set('自动')
        else:
            s = self._clip_gpu_name(str(gv), GPU_BOX_MAX)
            if s not in self.gpu_sel.cget('values'):
                self.gpu_sel.configure(values=['自动'] + (self.gpu_sel.cget('values') or []))
            self.gpu_sel.set(s)
        self._update_gpu_tip()
        for pp in PARAMS:
            w = getattr(self, 'w_' + pp['k'], None)
            v = p.get(pp['k'])
            if w is None:
                continue
            if isinstance(w, ctk.CTkOptionMenu):
                set_menu(w, v)
            else:
                set_entry(w, v)
        set_entry(self.w_n_batch, p.get('n_batch'))
        set_entry(self.w_n_ubatch, p.get('n_ubatch'))
        set_entry(self.w_cors, p.get('cors'))   # CORS 缺省=留空=不传
        set_entry(self.w_reasoning_budget, p.get('reasoning_budget'))
        set_entry(self.w_image_min_tokens, p.get('image_min_tokens'))
        set_entry(self.w_top_k, p.get('top_k'))
        set_entry(self.w_min_p, p.get('min_p'))
        set_entry(self.w_cache_reuse, p.get('cache_reuse'))
        set_entry(self.w_chat_template_kwargs, p.get('chat_template_kwargs'))
        set_menu(self.w_reasoning_format, p.get('reasoning_format'))
        if p.get('thinking', True):
            self.think_chk.select()
        else:
            self.think_chk.deselect()
        gemma = p.get('gemma')
        if gemma is None:
            gemma = self.is_gemma(self.current_model or '')
        self.gemma_chk.select() if gemma else self.gemma_chk.deselect()
        self.mm_chk.select() if p.get('mm') else self.mm_chk.deselect()
        self.no_kv_chk.select() if p.get('no_kv_offload') else self.no_kv_chk.deselect()
        self.update_calc()
        self.update_host_hint()
        self.sync_ctx_preset()

    def read_params(self):
        def intv(k, v):
            if v in ('', '（默认）'):
                return ''
            try:
                return int(v)
            except (ValueError, TypeError):
                raise ParameterError(k, f'{k} 需要整数，当前值：{v!r}')

        def fltv(k, v):
            if v in ('', '（默认）'):
                return ''
            try:
                return float(v)
            except (ValueError, TypeError):
                raise ParameterError(k, f'{k} 需要数字，当前值：{v!r}')

        p = {
            'ctx': intv('上下文长度', self.ctx_input.get().strip()),
            'parallel': intv('并行请求', self.parallel_sel.get()),
            'port': intv('端口', self.w_port.get().strip()),
            'ngl': intv('GPU 层数', self.w_ngl.get().strip()),
            'n_predict': intv('最大输出', self.w_n_predict.get().strip()),
            'flash': '' if self.w_flash.get() == '（默认）' else self.w_flash.get(),
            'cache': '' if self.w_cache.get() == '（默认）' else self.w_cache.get(),
            'host': '' if self.host_sel.get() == '（默认）' else self.host_sel.get(),
            'gpu': self.gpu_sel.get(),
            'temp': fltv('温度', self.w_temp.get().strip()),
            'top_p': fltv('top-p', self.w_top_p.get().strip()),
            'n_batch': intv('批处理大小', self.w_n_batch.get().strip()),
            'n_ubatch': intv('物理批次大小', self.w_n_ubatch.get().strip()),
            'cors': self.w_cors.get().strip(),
            'reasoning_budget': intv('推理预算', self.w_reasoning_budget.get().strip()),
            'image_min_tokens': intv('图像 Min Tokens', self.w_image_min_tokens.get().strip()),
            'top_k': intv('top-k', self.w_top_k.get().strip()),
            'min_p': fltv('min-p', self.w_min_p.get().strip()),
            'cache_reuse': intv('缓存复用', self.w_cache_reuse.get().strip()),
            'chat_template_kwargs': self.w_chat_template_kwargs.get().strip(),
            'reasoning_format': '' if self.w_reasoning_format.get() == '（默认）' else self.w_reasoning_format.get(),
            'thinking': bool(self.think_chk.get()),
            'gemma': bool(self.gemma_chk.get()),
            'mm': bool(self.mm_chk.get()),
            'no_kv_offload': bool(self.no_kv_chk.get()),
        }
        if p['port'] != '' and not 1 <= p['port'] <= 65535:
            raise ParameterError('端口', '端口范围为 1～65535')
        if p['n_batch'] != '' and p['n_ubatch'] != '' and p['n_ubatch'] > p['n_batch']:
            raise ParameterError('物理批次大小', '物理批次大小不能大于批处理大小')
        if p['chat_template_kwargs']:
            try:
                kwargs = json.loads(p['chat_template_kwargs'])
            except ValueError:
                raise ParameterError('模板额外参数', '模板额外参数需要合法 JSON 对象，例如 {"enable_thinking":false}')
            if not isinstance(kwargs, dict):
                raise ParameterError('模板额外参数', '模板额外参数必须是 JSON 对象')
        try:
            validate_fim_cache_reuse(self.cat_sel.get(), p['cache_reuse'], p['n_predict'])
        except ValueError as e:
            raise ParameterError('缓存复用', str(e)) from e
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
        h = self.host_sel.get()
        self.host_hint.configure(text='[本机]' if h in ('127.0.0.1', '（默认）') else '[局域网]')

    def refresh_gpus(self):
        # 从缓存读显卡列表（首次由 _startup_hardware 检测并写入）
        self._apply_gpus(self.get_cached_gpus())

    def _clip_gpu_name(self, s, target=None):
        """超长显卡名截断为下拉可显示长度（保留前缀+省略号），避免撑宽整行顶掉右侧按钮。
        target：逻辑宽度（默认用当前盒子宽度）；盒子按 GPU_BOX_MAX 裁剪、再按实际文本自适应。"""
        try:
            lab = self.gpu_sel._text_label
            f = tkfont.Font(font=lab.cget('font'))
            avail = ((target if target is not None else self.gpu_sel._desired_width) - GPU_BOX_PAD) * self._get_window_scaling()
            if f.measure(s) <= avail:
                return s
            lo, hi = 1, len(s)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if f.measure(s[:mid] + '…') <= avail:
                    lo = mid
                else:
                    hi = mid - 1
            return s[:lo] + '…'
        except Exception:
            return s if len(s) <= 20 else s[:20] + '…'

    def _size_gpu_box(self):
        """显卡下拉按当前文本自适应宽度（'自动' 短框、长名封顶 GPU_BOX_MAX）。
        rowg = 下拉 + 8 + 检查配置按钮(68)，封顶后最大 256 < col1 最小 ~284，按钮恒全宽可见。"""
        try:
            f = tkfont.Font(font=self.gpu_sel._text_label.cget('font'))
            tw = f.measure(self.gpu_sel.get())
        except Exception:
            tw = 0
        try:
            w = min(max(int(tw / self._get_window_scaling()) + GPU_BOX_PAD, 90), GPU_BOX_MAX)
            if w != self.gpu_sel._desired_width:
                self.gpu_sel.configure(width=w)
        except Exception:
            pass

    def _size_mmproj_box(self):
        """投影文件下拉按当前文本自适应宽度（'（自动）' 短框、长文件名封顶 MMPROJ_BOX_MAX）。
        下拉 dynamic_resizing 已关，超宽文本自动截断，全名见右侧小字提示。参考显卡下拉 _size_gpu_box。"""
        try:
            f = tkfont.Font(font=self.mmproj_sel._text_label.cget('font'))
            tw = f.measure(self.mmproj_sel.get())
        except Exception:
            tw = 0
        try:
            w = min(max(int(tw / self._get_window_scaling()) + MMPROJ_BOX_PAD, 100), MMPROJ_BOX_MAX)
            if w != self.mmproj_sel._desired_width:
                self.mmproj_sel.configure(width=w)
        except Exception:
            pass

    def _update_gpu_tip(self):
        """显卡下拉悬浮提示显示完整显卡名（下拉内显示的是截断的识别名）；顺带按选项自适应盒子宽度。"""
        try:
            self._size_gpu_box()
            cur = self.gpu_sel.get()
            full_list = getattr(self, '_gpu_full', None)
            if cur and cur != '自动' and full_list:
                idx = cur.split(',')[0].strip()
                full = next((x for x in full_list if x.split(',')[0].strip() == idx), cur)
                txt = f'当前显卡：{full}\n（--main-gpu {idx}）\n「自动」不传该参数，由 llama 自行选择。'
            else:
                txt = '选择用于推理的显卡（--main-gpu）。「自动」不传该参数，由 llama 自行选择。'
            tip = getattr(self, 'gpu_tip', None)
            if tip is not None:
                tip.text = txt
                tip.lab.configure(text=txt)
        except Exception:
            pass

    def _apply_gpus(self, gpus):
        self._gpu_full = gpus or []
        self.gpu_sel.configure(width=GPU_BOX_MAX)   # 先按最大宽度裁剪名字（盒子可能已被缩到 '自动' 短框）
        short = ['自动'] + [self._clip_gpu_name(x) for x in (gpus or [])]
        self.gpu_sel.configure(values=short)
        cur = self.gpu_sel.get()
        self.gpu_sel.set(cur if cur in short else '自动')
        self._size_gpu_box()   # 按当前选项把盒子缩到合适宽度
        self._update_gpu_tip()
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
            self._show_parameter_error(e); return
        exists = name in self.presets.get(self.current_model, {})

        def do_save():
            self.presets.setdefault(self.current_model, {})[name] = params
            save_presets(self.presets)
            self.refresh_preset_menu()
            self.preset_sel.set(name)
            self.cfg.setdefault('last_preset', {})[self.current_model] = name
            save_cfg(self.cfg)
            self._set_param_src(f'📌 预设：{name}', '#e8c468', tip=name)
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
        model = self.current_model

        def delete():
            if n not in self.presets.get(model, {}):
                return
            del self.presets[model][n]
            save_presets(self.presets)
            if self.cfg.get('last_preset', {}).get(model) == n:
                self.cfg['last_preset'].pop(model, None)
                save_cfg(self.cfg)
            if self.current_model == model:
                self.refresh_preset_menu()
                self.on_preset_load()
            self.append_log(f'>>> 已删预设「{n}」')
        self._confirm_dlg('删除预设', f'确认删除预设「{n}」？', delete)

    def rename_preset(self):
        n = self.preset_sel.get()
        if not n or n == '（无预设）' or not self.current_model:
            self.append_log('!!! 先在下拉里选要重命名的预设')
            return
        new = self.preset_name.get().strip()
        if not new:
            self.append_log('!!! 先填新预设名（左边输入框）')
            return
        if new == n:
            self.append_log('!!! 新名字与原来相同')
            return
        if new in self.presets.get(self.current_model, {}):
            messagebox.showwarning('重命名预设', f'预设「{new}」已存在')
            return
        self.presets[self.current_model][new] = self.presets[self.current_model].pop(n)
        save_presets(self.presets)
        if self.cfg.get('last_preset', {}).get(self.current_model) == n:
            self.cfg['last_preset'][self.current_model] = new
            save_cfg(self.cfg)
        self.refresh_preset_menu()
        self.preset_sel.set(new)
        self.preset_name.delete(0, 'end')
        self.preset_name.insert(0, new)
        self._set_param_src(f'📌 预设：{new}', '#e8c468', tip=new)
        self.update_preset_controls()
        self.append_log(f'>>> 已重命名预设「{n}」→「{new}」')

    def find_orphan_presets(self):
        orphans = {}
        for model, ps in self.presets.items():
            if isinstance(ps, dict) and not os.path.exists(os.path.join(MODELS_DIR, model)):
                orphans[model] = ps
        return orphans

    def manage_orphan_presets(self):
        orphans = self.find_orphan_presets()
        dlg = ctk.CTkToplevel(self)
        self._apply_icon(dlg)
        dlg.title('缺失模型的预设')
        dlg.geometry('480x340')
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.after(10, lambda: self._center_on_main(dlg))
        dlg.attributes('-topmost', True)
        if not orphans:
            ctk.CTkLabel(dlg, text='没有缺失模型的预设，全部有效', font=('Microsoft YaHei', 13)).pack(pady=40)
            ctk.CTkButton(dlg, height=38, text='关闭', width=90, command=dlg.destroy).pack()
            return
        ctk.CTkLabel(dlg, text='以下模型的预设在本机 models/ 中不存在：', anchor='w',
                     font=('Microsoft YaHei', 12)).pack(pady=(14, 4), padx=16, anchor='w')
        box = ctk.CTkTextbox(dlg, state='disabled', wrap='none', font=('Consolas', 11))
        box.pack(fill='both', expand=True, padx=16, pady=4)
        box.configure(state='normal')
        for model, ps in orphans.items():
            box.insert('end', f'{model}  （预设：{"、".join(ps.keys())}）\n')
        box.configure(state='disabled')
        row = ctk.CTkFrame(dlg, fg_color='transparent')
        row.pack(pady=(8, 12))
        ctk.CTkButton(row, height=38, text='保留', width=82, command=dlg.destroy).pack(side='left', padx=4)
        ctk.CTkButton(row, height=38, text='删除无效', width=82, fg_color='#8a3f3f', hover_color='#9a4848',
                      command=lambda: self.delete_orphans(dlg)).pack(side='left', padx=4)
        ctk.CTkButton(row, height=38, text='导出有效', width=82,
                      command=lambda: self.export_presets(True, dlg)).pack(side='left', padx=4)
        ctk.CTkButton(row, height=38, text='导出无效', width=82,
                      command=lambda: self.export_presets(False, dlg)).pack(side='left', padx=4)

    def delete_orphans(self, dlg):
        orphans = self.find_orphan_presets()
        for m in orphans:
            self.presets.pop(m, None)
        save_presets(self.presets)
        if self.cfg.get('last_preset'):
            changed = False
            for m in orphans:
                if m in self.cfg['last_preset']:
                    del self.cfg['last_preset'][m]
                    changed = True
            if changed:
                save_cfg(self.cfg)
        self.append_log(f'>>> 已删除 {len(orphans)} 个缺失模型的预设')
        self.refresh_preset_menu()
        dlg.destroy()

    def export_presets(self, valid, dlg):
        if valid:
            target = {m: ps for m, ps in self.presets.items()
                      if isinstance(ps, dict) and os.path.exists(os.path.join(MODELS_DIR, m))}
            title, fname = '导出有效预设', 'presets_valid.json'
        else:
            target = {m: ps for m, ps in self.presets.items()
                      if isinstance(ps, dict) and not os.path.exists(os.path.join(MODELS_DIR, m))}
            title, fname = '导出无效预设', 'presets_invalid.json'
        path = filedialog.asksaveasfilename(parent=dlg, title=title, defaultextension='.json',
                                            initialfile=fname, filetypes=[('JSON', '*.json')])
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(target, f, ensure_ascii=False, indent=2)
        self.append_log(f'>>> 已导出 {len(target)} 条预设到 {path}')
        dlg.destroy()

    def import_presets(self):
        path = filedialog.askopenfilename(title='导入预设（合并）',
                                          defaultextension='.json', filetypes=[('JSON', '*.json')])
        if not path:
            return
        imported = _load_jsonc(path)
        if imported is None:
            messagebox.showerror('导入预设', '读取文件失败（不是合法 JSON/JSONC）')
            return
        if not isinstance(imported, dict):
            messagebox.showerror('导入预设', '文件格式不对，应为 {模型: {预设名: 参数}}')
            return
        added = 0
        conflicts = []   # (model, name, params) 同名冲突
        for model, ps in imported.items():
            if not isinstance(ps, dict):
                continue
            cur = self.presets.setdefault(model, {})
            if not isinstance(cur, dict):
                cur = {}
                self.presets[model] = cur
            for name, params in ps.items():
                if not isinstance(params, dict):
                    continue
                if name in cur:
                    conflicts.append((model, name, params))
                else:
                    cur[name] = params
                    added += 1
            if not cur:
                self.presets.pop(model, None)
        if not conflicts:
            save_presets(self.presets)
            self.refresh_preset_menu()
            self.append_log(f'>>> 导入预设：新增 {added} 条（无同名冲突）')
            messagebox.showinfo('导入预设', f'导入完成：新增 {added} 条预设。')
            return
        if not self.cfg.get('overwrite_ask', True):
            self._apply_import_conflicts(conflicts, 'overwrite', added)
            return
        self._import_conflict_dialog(conflicts, added)

    def _apply_import_conflicts(self, conflicts, mode, added):
        overwritten = skipped = 0
        for model, name, params in conflicts:
            if mode == 'overwrite':
                self.presets.setdefault(model, {})[name] = params
                overwritten += 1
            else:
                skipped += 1
        save_presets(self.presets)
        self.refresh_preset_menu()
        msg = f'导入完成：新增 {added} 条'
        if overwritten:
            msg += f'，覆盖 {overwritten} 条'
        if skipped:
            msg += f'，跳过 {skipped} 条'
        self.append_log(f'>>> 导入预设：{msg}')
        messagebox.showinfo('导入预设', msg + '。')

    def _import_conflict_dialog(self, conflicts, added):
        dlg = ctk.CTkToplevel(self)
        self._apply_icon(dlg)
        dlg.title('导入预设冲突')
        dlg.geometry('400x210')
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.after(10, lambda: self._center_on_main(dlg))
        dlg.attributes('-topmost', True)
        ctk.CTkLabel(dlg, text=f'导入发现 {len(conflicts)} 个同名预设', font=('Microsoft YaHei', 13)).pack(pady=(18, 4))
        noask = ctk.CTkCheckBox(dlg, text='以后同名预设不再提示（同名直接覆盖）')
        noask.pack(pady=4)

        def choose(mode):
            if noask.get():
                self.cfg['overwrite_ask'] = False
                save_cfg(self.cfg)
            dlg.destroy()
            self._apply_import_conflicts(conflicts, mode, added)

        row = ctk.CTkFrame(dlg, fg_color='transparent')
        row.pack(pady=10)
        ctk.CTkButton(row, height=38, text='覆盖导入的', width=110, command=lambda: choose('overwrite')).pack(side='left', padx=6)
        ctk.CTkButton(row, height=38, text='保留现有的', width=110, command=lambda: choose('skip')).pack(side='left', padx=6)

    def manage_presets_all(self):
        self._preset_chks = {}
        dlg = ctk.CTkToplevel(self)
        self._apply_icon(dlg)
        dlg.title('批量管理预设')
        dlg.geometry('540x520')
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.after(10, lambda: self._center_on_main(dlg))
        dlg.attributes('-topmost', True)
        ctk.CTkLabel(dlg, text='按模型分组，勾选预设后可批量删除', anchor='w',
                     text_color=UI['muted'], font=('Microsoft YaHei', 11)).pack(pady=(14, 4), padx=16, anchor='w')
        sf = ctk.CTkScrollableFrame(dlg, width=500, height=380)
        sf.pack(fill='both', expand=True, padx=16, pady=4)
        for model in sorted(self.presets.keys()):
            ps = self.presets[model]
            if not isinstance(ps, dict) or not ps:
                continue
            ctk.CTkLabel(sf, text=f'▸ {model}', anchor='w',
                         font=('Microsoft YaHei', 12, 'bold')).pack(fill='x', pady=(10, 2), padx=4)
            for name in sorted(ps.keys()):
                row = ctk.CTkFrame(sf, fg_color='transparent')
                row.pack(fill='x', padx=18)
                chk = ctk.CTkCheckBox(row, text=name, width=16)
                chk.pack(side='left', anchor='w')
                self._preset_chks[(model, name)] = chk
        bar = ctk.CTkFrame(dlg, fg_color='transparent')
        bar.pack(fill='x', padx=16, pady=10)

        def set_all(val):
            for chk in self._preset_chks.values():
                chk.select() if val else chk.deselect()

        def invert():
            for chk in self._preset_chks.values():
                chk.toggle()

        ctk.CTkButton(bar, height=38, text='全选', width=70, command=lambda: set_all(True)).pack(side='left', padx=4)
        ctk.CTkButton(bar, height=38, text='反选', width=70, command=invert).pack(side='left', padx=4)
        ctk.CTkButton(bar, height=38, text='取消全选', width=90, command=lambda: set_all(False)).pack(side='left', padx=4)
        ctk.CTkButton(bar, height=38, text='导出选中', width=90, fg_color='#3d6e5a', hover_color='#477a66',
                      command=lambda: self.export_selected_presets(dlg)).pack(side='left', padx=4)
        ctk.CTkButton(bar, height=38, text='删除选中', width=90, fg_color='#8a3f3f', hover_color='#9a4848',
                      command=lambda: self.delete_selected_presets(dlg)).pack(side='right', padx=4)
        ctk.CTkButton(bar, height=38, text='关闭', width=70, command=dlg.destroy).pack(side='right', padx=4)

    def export_selected_presets(self, dlg):
        """批量管理：把勾选的预设导出为 JSON（与统一文件的 presets 分区同构，可再导入）。"""
        sel = [(m, n) for (m, n), chk in self._preset_chks.items() if chk.get()]
        if not sel:
            messagebox.showinfo('导出预设', '未勾选任何预设', parent=dlg)
            return
        target = {}
        for m, n in sel:
            if m in self.presets and isinstance(self.presets[m], dict) and n in self.presets[m]:
                target.setdefault(m, {})[n] = self.presets[m][n]
        path = filedialog.asksaveasfilename(parent=dlg, title='导出选中预设', defaultextension='.json',
                                            initialfile='presets_selected.json', filetypes=[('JSON', '*.json')])
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(target, f, ensure_ascii=False, indent=2)
        n_presets = sum(len(v) for v in target.values())
        self.append_log(f'>>> 已导出 {n_presets} 条选中预设到 {path}')

    def delete_selected_presets(self, dlg):
        sel = [(m, n) for (m, n), chk in self._preset_chks.items() if chk.get()]
        if not sel:
            messagebox.showinfo('删除预设', '未勾选任何预设')
            return
        self._confirm_dlg('删除预设', f'确认删除 {len(sel)} 条预设？',
                          lambda: self._do_delete_selected(dlg, sel), parent=dlg)

    def _do_delete_selected(self, dlg, sel):
        for m, n in sel:
            if m in self.presets and isinstance(self.presets[m], dict) and n in self.presets[m]:
                del self.presets[m][n]
                if not self.presets[m]:
                    del self.presets[m]
        lp = self.cfg.get('last_preset', {})
        changed = False
        for m, n in sel:
            if lp.get(m) == n:
                del lp[m]
                changed = True
        if changed:
            save_cfg(self.cfg)
        save_presets(self.presets)
        self.refresh_preset_menu()
        self.append_log(f'>>> 批量删除 {len(sel)} 条预设')
        dlg.destroy()

    def confirm_overwrite(self, name, callback):
        dlg = ctk.CTkToplevel(self)
        self._apply_icon(dlg)
        dlg.title('覆盖预设')
        dlg.geometry('380x190')
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.after(10, lambda: self._center_on_main(dlg))
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

        ctk.CTkButton(btns, height=38, text='覆盖', width=96, fg_color='#2f7a50', hover_color='#358a5c', command=ok).pack(side='left', padx=10)
        ctk.CTkButton(btns, height=38, text='取消', width=96, command=dlg.destroy).pack(side='left', padx=10)

    def _confirm_dlg(self, title, msg, on_yes, parent=None, yes_text='确认删除'):
        """二次确认弹窗：置顶居中 + 单例（已有确认窗则前置复用，不叠窗口）。

        用 CTkToplevel 而非 messagebox.askyesno——后者在父窗口 grab 下不置顶、
        抢不到焦点，用户连点删除按钮会叠出一堆确认窗。
        """
        old = getattr(self, '_confirm_open', None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.lift()
                    old.focus_force()
                    return
            except Exception:
                pass
        dlg = ctk.CTkToplevel(self)
        self._apply_icon(dlg)
        dlg.title(title)
        dlg.geometry('400x170')
        dlg.resizable(False, False)
        dlg.transient(parent or self)
        dlg.attributes('-topmost', True)
        dlg.after(10, lambda: self._center_on_main(dlg))
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=msg, font=('Microsoft YaHei', 14), wraplength=360).pack(pady=(24, 4))
        btns = ctk.CTkFrame(dlg, fg_color='transparent')
        btns.pack(pady=(12, 16))

        def close():
            self._confirm_open = None
            dlg.destroy()

        def yes():
            close()
            on_yes()

        def no():
            close()
            if parent is not None:
                try:   # 确认窗 grab 抢走了父窗 grab，取消后归还给父窗
                    if parent.winfo_exists():
                        parent.grab_set()
                except Exception:
                    pass

        ctk.CTkButton(btns, height=38, text=yes_text, width=110, fg_color='#8a3f3f',
                      hover_color='#9a4848', command=yes).pack(side='left', padx=8)
        ctk.CTkButton(btns, height=38, text='取消', width=90, command=no).pack(side='left', padx=8)
        self._confirm_open = dlg

    def open_settings(self):
        existing = getattr(self, '_settings_dlg', None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
        dlg = ctk.CTkToplevel(self)
        self._settings_dlg = dlg
        self._apply_icon(dlg)
        dlg.title('设置')
        dlg.geometry('460x560')   # 高度随后按内容自适应（auto-fit），此处仅给个保底
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.after(10, lambda: self._center_on_main(dlg))
        dlg.attributes('-topmost', True)
        ask = ctk.CTkCheckBox(dlg, text='保存预设时询问是否覆盖同名预设')
        if self.cfg.get('overwrite_ask', True):
            ask.select()
        ask.pack(pady=(14, 6), padx=24, anchor='w')
        sizebox = ctk.CTkCheckBox(dlg, text='记录窗口大小（下次启动恢复同样大小）')
        if self.cfg.get('remember_size', True):
            sizebox.select()
        sizebox.pack(pady=6, padx=24, anchor='w')
        auto_upd = ctk.CTkCheckBox(dlg, text='启动时自动检查更新（GitHub Release）')
        if default_auto_check_updates(self.cfg):
            auto_upd.select()
        auto_upd.pack(pady=(0, 6), padx=24, anchor='w')

        # llama-server 路径（全局，不在预设里）
        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(8, 2))
        ctk.CTkLabel(dlg, text='llama-server.exe 路径（全局，留空=程序同目录）',
                     anchor='w').pack(padx=24, pady=(4, 2), anchor='w')
        spf = ctk.CTkFrame(dlg, fg_color='transparent')
        spf.pack(padx=24, pady=(0, 6), fill='x')
        sp_entry = ctk.CTkEntry(spf, height=38, placeholder_text='留空=程序同目录 llama-server.exe')
        sp_entry.pack(side='left', fill='x', expand=True)
        sp_entry.insert(0, self.cfg.get('server_path', ''))

        def browse_sp():
            cur = sp_entry.get().strip()
            init = os.path.dirname(cur) if cur and os.path.isabs(cur) else BASE
            p = filedialog.askopenfilename(parent=dlg, title='选择 llama-server.exe',
                                           initialdir=init, filetypes=[('llama-server', 'llama-server.exe'), ('可执行文件', '*.exe')])
            if p:
                sp_entry.delete(0, 'end')
                sp_entry.insert(0, p)

        ctk.CTkButton(spf, height=38, text='浏览…', width=70, command=browse_sp).pack(side='left', padx=(6, 0))

        # 模型文件夹（全局，留空=程序同目录 models）
        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(8, 2))
        ctk.CTkLabel(dlg, text='模型文件夹（全局，留空=程序同目录 models）',
                     anchor='w').pack(padx=24, pady=(4, 2), anchor='w')
        mdf = ctk.CTkFrame(dlg, fg_color='transparent')
        mdf.pack(padx=24, pady=(0, 6), fill='x')
        md_entry = ctk.CTkEntry(mdf, height=38, placeholder_text='留空=程序同目录 models')
        md_entry.pack(side='left', fill='x', expand=True)
        md_entry.insert(0, self.cfg.get('models_dir', ''))

        def browse_md():
            cur = md_entry.get().strip()
            init = cur if cur and os.path.isdir(cur) else BASE
            p = filedialog.askdirectory(parent=dlg, title='选择模型文件夹', initialdir=init)
            if p:
                md_entry.delete(0, 'end')
                md_entry.insert(0, p)

        ctk.CTkButton(mdf, height=38, text='浏览…', width=70, command=browse_md).pack(side='left', padx=(6, 0))

        # 默认端口（全局）：无预设自动计算时保留当前端口；未设端口时用它兜底
        dpf = ctk.CTkFrame(dlg, fg_color='transparent')
        dpf.pack(padx=24, pady=(8, 6), fill='x')
        ctk.CTkLabel(dpf, text='默认端口（全局）', width=130, anchor='w').pack(side='left')
        dp_entry = ctk.CTkEntry(dpf, height=38, placeholder_text='留空=8080')
        dp_entry.pack(side='left', padx=(8, 0), fill='x', expand=True)
        dp_entry.insert(0, str(self.cfg.get('default_port', '')))

        def save():
            md = md_entry.get().strip()
            dp = dp_entry.get().strip()
            if dp:
                try:
                    dp = int(dp)
                except ValueError:
                    messagebox.showwarning('设置', '默认端口需为整数', parent=dlg)
                    return
                if not 1 <= dp <= 65535:
                    messagebox.showwarning('设置', '默认端口范围为 1～65535', parent=dlg)
                    return
                self.cfg['default_port'] = dp
            else:
                self.cfg.pop('default_port', None)
            self.cfg['overwrite_ask'] = bool(ask.get())
            self.cfg['auto_check_updates'] = bool(auto_upd.get())
            self.cfg['remember_size'] = bool(sizebox.get())
            self.cfg['server_path'] = sp_entry.get().strip()
            self.cfg['models_dir'] = md
            save_cfg(self.cfg)
            global MODELS_DIR
            new_dir = md or os.path.join(BASE, 'models')
            if os.path.normcase(os.path.abspath(new_dir)) != os.path.normcase(os.path.abspath(MODELS_DIR)):
                MODELS_DIR = new_dir
                self.load_models()
                self.on_model_change()
                self.append_log('>>> 模型文件夹已切换：' + os.path.normpath(MODELS_DIR))
            self.append_log('>>> 设置已保存')
            dlg.destroy()

        # 保存按钮并入默认端口行（避免端口框过长、也省一整行高度）
        ctk.CTkButton(dpf, height=38, text='保存', width=90, command=save).pack(side='left', padx=(8, 0))

        # 预设健康检查（打开设置即自动检查缺失模型的预设）
        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(8, 2))
        n_orphan = len(self.find_orphan_presets())
        ctk.CTkLabel(dlg, text=f'预设健康检查：缺失模型的预设 {n_orphan} 个',
                     text_color='#e8b04a' if n_orphan else '#7fd9a0').pack(pady=(2, 4))
        ctk.CTkButton(dlg, height=38, text='管理（保留 / 删除 / 导出有效 / 导出无效）', width=280,
                      command=self.manage_orphan_presets).pack(pady=(0, 6))
        btns = ctk.CTkFrame(dlg, fg_color='transparent')
        btns.pack(pady=(0, 8))
        ctk.CTkButton(btns, height=38, text='导入预设（合并）', width=132, command=self.import_presets).pack(side='left', padx=4)
        ctk.CTkButton(btns, height=38, text='批量管理预设', width=132, command=self.manage_presets_all).pack(side='left', padx=4)

        # 模型清单（弹出独立窗口）
        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(8, 2))
        ctk.CTkButton(dlg, height=38, text='📦 模型清单', width=200, command=self.show_model_list).pack(pady=(0, 6))

        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(6, 2))
        ctk.CTkLabel(dlg, text=f'LLM GUI · v{VERSION}', font=('Microsoft YaHei', 14, 'bold')).pack()
        ctk.CTkLabel(dlg, text='llama-server 本地桌面启动器', text_color=UI['muted']).pack(pady=(2, 0))
        ctk.CTkLabel(dlg, text=f'GitHub：{GITHUB_USER}', text_color=UI['muted']).pack(pady=(8, 0))
        link = ctk.CTkLabel(dlg, text=GITHUB_URL, text_color='#7db4ff', cursor='hand2', font=('Consolas', 11))
        link.pack(pady=(2, 0))
        link.bind('<Button-1>', lambda _: webbrowser.open(GITHUB_URL))
        # 手动「检查更新」：与启动自动检查共用 _start_update_check 核心逻辑；关于区保持不破坏主界面布局
        upd_row = ctk.CTkFrame(dlg, fg_color='transparent')
        upd_row.pack(pady=(8, 0))
        ctk.CTkButton(upd_row, height=38, text='检查更新', width=120,
                      command=self._check_update_manual).pack(side='left', padx=4)
        ctk.CTkButton(upd_row, height=38, text='前往发布页', width=120,
                      command=lambda: webbrowser.open(RELEASE_PAGE_URL)).pack(side='left', padx=4)

        # 高度按内容自适应（逻辑高 = 物理 reqheight / 窗口缩放），消除仓库链接下方留白
        try:
            dlg.update_idletasks()
            h = int(dlg.winfo_reqheight() / dlg._get_window_scaling()) + 8
            dlg.geometry(f'460x{h}')
        except Exception:
            pass

    def show_model_list(self):
        """弹出模型清单窗口：models/ 下所有 .gguf（模型 + mmproj 投影文件）+ 大小 + 总占用"""
        dlg = ctk.CTkToplevel(self)
        self._apply_icon(dlg)
        dlg.title('模型清单')
        dlg.geometry('480x520')
        dlg.resizable(True, True)
        dlg.transient(self)
        dlg.grab_set()
        dlg.after(10, lambda: self._center_on_main(dlg))
        dlg.attributes('-topmost', True)
        files = []
        if os.path.isdir(MODELS_DIR):
            files = sorted(f for f in os.listdir(MODELS_DIR) if f.lower().endswith('.gguf'))
        n_mm = sum(1 for f in files if 'mmproj' in f.lower())
        header = f'models/ 目录（{os.path.normpath(MODELS_DIR)}）共 {len(files)} 个'
        if n_mm:
            header += f'（含 mmproj 投影文件 {n_mm} 个）'
        ctk.CTkLabel(dlg, text=header + '：', anchor='w',
                     font=('Microsoft YaHei', 12)).pack(pady=(14, 4), padx=16, anchor='w')
        box = ctk.CTkTextbox(dlg, state='disabled', wrap='none', font=('Consolas', 12))
        box.pack(fill='both', expand=True, padx=16, pady=4)
        lines = []
        total = 0
        for f in files:
            try:
                sz = os.path.getsize(os.path.join(MODELS_DIR, f))
            except OSError:
                sz = 0
            total += sz
            size_s = f'{sz / (1024 ** 3):.2f} GB' if sz >= 1024 ** 3 else f'{sz / (1024 ** 2):.0f} MB'
            mark = '  ← 投影文件' if 'mmproj' in f.lower() else ''
            lines.append(f'{clean_model_display(f):<42}{size_s:>9}{mark}')
        if files:
            total_s = f'{total / (1024 ** 3):.2f} GB' if total >= 1024 ** 3 else f'{total / (1024 ** 2):.0f} MB'
            lines.append('-' * 51)
            lines.append('总占用' + ' ' * 36 + f'{total_s:>9}')   # 3 个中文=显示宽 6，补 36 空格对齐 42 列
        box.configure(state='normal')
        box.insert('1.0', '\n'.join(lines) if lines else '（models 目录为空）')
        box.configure(state='disabled')
        ctk.CTkButton(dlg, height=38, text='关闭', width=90, command=dlg.destroy).pack(pady=10)

    def append_log(self, line):
        follow = self.log_box._textbox.yview()[1] >= 0.98
        self.log_box.configure(state='normal')
        self.log_box.insert('end', line + '\n')
        # 限制长期运行的日志内存；查看历史时保留阅读位置。
        count = int(self.log_box.index('end-1c').split('.')[0])
        if count > 6000:
            self.log_box.delete('1.0', f'{count - 5000}.0')
        if follow:
            self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def clear_log(self):
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        self.log_box.configure(state='disabled')

    def update_svc_info(self, model, p):
        host = p.get('host') or '127.0.0.1'
        port = p.get('port') or 8080
        self._api_base = f'http://127.0.0.1:{port}' if host == '0.0.0.0' else f'http://{host}:{port}'
        self._sync_action_controls()
        if host == '0.0.0.0':
            hosts = ['127.0.0.1']
            ip = _lan_ip()
            if ip:
                hosts.append(ip)
        else:
            hosts = [host]

        def tag(h):
            return '（本机）' if h == '127.0.0.1' else '（局域网）'

        base = ' · '.join(f'http://{h}:{port}{tag(h)}' for h in hosts)
        self.svc_info.delete('1.0', 'end')
        self.svc_info.insert('1.0', f'API：{base}\n端点：' + ' · '.join(API_SUFFIXES))
        self.svc_info.tag_configure('body', foreground=UI['success'])
        self.svc_info.tag_add('body', '1.0', 'end')
        self._svc_sync_height()

    def _set_svc_idle(self):
        self._api_base = ''
        self._set_button_state(self.copy_api_btn, False)
        self.svc_info.delete('1.0', 'end')
        self.svc_info.insert('1.0', '启动服务后显示 API 地址 · 可直接复制用于客户端连接')
        self.svc_info.tag_configure('idle', foreground=UI['muted'])
        self.svc_info.tag_add('idle', '1.0', 'end')
        self._svc_sync_height()

    def _svc_readonly(self, event):
        if event.state & 0x4 and event.keysym.lower() in ('c', 'a'):   # 允许 Ctrl+C / Ctrl+A
            return None
        return 'break'   # 其余按键拦截：只读但可选中复制

    def _svc_sync_height(self):
        try:
            text = self.svc_info.get('1.0', 'end-1c')
            if not text:
                self.svc_info.configure(height=1)
                return
            lines = text.split('\n')
            font = tkfont.Font(font=self.svc_info.cget('font'))
            w = max(200, self.svc_info.winfo_width() - 12)
            wrap = 0
            for l in lines:
                pw = font.measure(l)
                if pw > w:
                    wrap += (pw + w - 1) // w - 1
            self.svc_info.configure(height=max(1, len(lines) + wrap))
        except Exception:
            pass

    def build_cmd(self, model, p):
        exe = self.cfg.get('server_path') or SERVER_EXE

        def val(v):
            return v is not None and v != ''

        args = [exe, '-m', os.path.join(MODELS_DIR, model),
                '--alias', clean_model_display(model)]   # API 上报用干净模型名（无目录/无 .gguf）
        if val(p.get('ngl')):
            args += ['-ngl', str(p['ngl'])]
        if val(p.get('ctx')):
            args += ['-c', str(p['ctx'])]
        if val(p.get('flash')):
            args += ['--flash-attn', str(p['flash'])]
        if val(p.get('cache')):
            args += ['-ctk', str(p['cache']), '-ctv', str(p['cache'])]
        if val(p.get('n_predict')):
            args += ['-n', str(p['n_predict'])]
        if val(p.get('parallel')):
            args += ['--parallel', str(p['parallel'])]
        if val(p.get('temp')):
            args += ['--temp', str(p['temp'])]
        if val(p.get('top_p')):
            args += ['--top-p', str(p['top_p'])]
        if val(p.get('top_k')):
            args += ['--top-k', str(p['top_k'])]
        if val(p.get('min_p')):
            args += ['--min-p', str(p['min_p'])]
        if val(p.get('host')):
            args += ['--host', str(p['host'])]
        if val(p.get('port')):
            args += ['--port', str(p['port'])]
        if val(p.get('cors')):
            args += ['--cors', str(p['cors'])]
        gpu = p.get('gpu')
        if val(gpu) and gpu != '自动':
            args += ['--main-gpu', gpu.split(',')[0].strip()]
        if val(p.get('n_batch')):
            args += ['--batch-size', str(p['n_batch'])]
        if val(p.get('n_ubatch')):
            args += ['--ubatch-size', str(p['n_ubatch'])]
        if val(p.get('cache_reuse')):
            args += ['--cache-reuse', str(p['cache_reuse'])]
        if val(p.get('reasoning_budget')):
            args += ['--reasoning-budget', str(p['reasoning_budget'])]
        if val(p.get('reasoning_format')):
            args += ['--reasoning-format', str(p['reasoning_format'])]
        if val(p.get('chat_template_kwargs')):
            args += ['--chat-template-kwargs', str(p['chat_template_kwargs'])]
        if val(p.get('image_min_tokens')):
            args += ['--image-min-tokens', str(p['image_min_tokens'])]
        if p.get('no_kv_offload'):
            args += ['--no-kv-offload']
        args += ['--reasoning', 'on' if p.get('thinking', True) else 'off']
        gemma = p.get('gemma')
        if gemma is None:
            gemma = self.is_gemma(model)
        if gemma and os.path.exists(JINJA):
            args += ['--chat-template-file', JINJA]
        if p.get('mm'):
            manual = self.cfg.get('mmproj', {}).get(model, '（自动）')
            if manual != '（自动）' and os.path.exists(os.path.join(MODELS_DIR, manual)):
                mm = os.path.join(MODELS_DIR, manual)   # 参数区「投影文件」手动指定优先
            else:
                mm = find_mmproj(model)
            if mm:
                args += ['--mmproj', mm]
            else:
                self.append_log('!!! 多模态已勾选，但没找到匹配当前模型的 mmproj 投影文件（可在参数区「投影文件」手动指定），未加 --mmproj')
        return args

    def start(self):
        if self._closing or self._service_state == 'stopping':
            return
        if self.proc and self.proc.poll() is None:
            self.append_log('!!! 已有实例在运行，先停止'); return
        if not self.current_model or self.current_model.startswith('（'):
            self.append_log('!!! 没有可选模型'); return
        if not os.path.exists(os.path.join(MODELS_DIR, self.current_model)):
            self.append_log('!!! 模型文件不存在：' + self.current_model + '（以后下回来即可用）'); return
        exe = self.cfg.get('server_path') or SERVER_EXE
        if not os.path.exists(exe):
            self.append_log('!!! 未找到 llama-server.exe：' + os.path.normpath(exe)
                            + '（请在「设置」里选择 llama 路径）')
            return
        try:
            p = self.read_params()
        except ValueError as e:
            self._show_parameter_error(e); return
        args = self.build_cmd(self.current_model, p)
        self.append_log('>>> 启动: ' + ' '.join(args))
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, encoding='utf-8', errors='replace', bufsize=1,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except Exception as e:
            self.append_log('!!! 启动失败: ' + str(e)); return
        # 状态文本截断模型名：长名会把右侧「设置」按钮顶出窗口
        mname = clean_model_display(self.current_model)
        if len(mname) > 24: mname = mname[:22] + '…'
        self._set_service_state('running', f'● 进程运行中 · {mname} · :{p.get("port") or 8080}')
        self.update_svc_info(self.current_model, p)
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _read(self, proc):
        # 工作线程只写队列，固定进程引用，旧进程退出不会改写新实例的状态。
        try:
            with proc.stdout:
                for line in proc.stdout:
                    if line:
                        self._q.put(('log', proc, line.rstrip('\n')))
            code = proc.wait()
            self._q.put(('exited', proc, code))
        except Exception as e:
            self._q.put(('log', proc, '!!! 读取服务日志失败: ' + str(e)))
            # 即使日志管道异常，仍等进程退出后再允许启动新实例。
            self._q.put(('exited', proc, proc.wait()))

    def _mark_stopped(self, proc):
        if proc is not self.proc:
            return
        self.proc = None
        self._set_service_state('idle')
        self._set_svc_idle()
        if self._closing:
            self._finish_close()

    def stop(self):
        if self._service_state == 'stopping':
            return
        if self.proc and self.proc.poll() is None:
            proc = self.proc
            self._set_service_state('stopping')
            self.append_log('>>> 正在停止服务…')
            threading.Thread(target=self._terminate_process, args=(proc,), daemon=True).start()
        else:
            self._mark_stopped(self.proc)

    def _terminate_process(self, proc):
        try:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            self._q.put(('exited', proc, proc.returncode))
        except Exception as e:
            self._q.put(('stop_error', proc, str(e)))

    def on_close(self):
        if self._closing:
            return
        if self.proc and self.proc.poll() is None:
            self._closing = True
            self.stop()
        else:
            self._finish_close()

    def _finish_close(self):
        self._closing = True
        if self.cfg.get('remember_size', True):
            try:
                wxh = self.geometry().split('+')[0]   # 逻辑尺寸（反向缩放），避免 winfo×缩放复合放大
                w, h = wxh.split('x')
                self.cfg['window_size'] = [int(w), int(h)]
                self.cfg['sash_pos'] = int(self.pw.sashpos(0))
                save_cfg(self.cfg)
            except Exception:
                pass
        if self.current_model:   # 记住上次选的模型，下次启动恢复
            self.cfg['last_model'] = self.current_model
            save_cfg(self.cfg)
        self._closed = True
        # 停止 tooltip、DPI 与队列计时器，避免销毁窗口后留下 Tcl 回调。
        for callback in self.tk.call('after', 'info'):
            # 只撤销计划，注册的 Tcl 命令由各自控件在 destroy 时清理。
            self.tk.call('after', 'cancel', callback)
        self.destroy()


def main():
    try:
        # 不再阻塞启动：即使 llama-server.exe 缺失也要打开界面，用户才能进「设置」配置路径
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
