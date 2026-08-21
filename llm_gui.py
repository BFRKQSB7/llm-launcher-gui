#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM GUI — 本地 llama-server 桌面启动器（customtkinter 原生窗口，不依赖浏览器）

- 扫描 models/ 列模型；每模型多套预设；模型下拉右侧 ⟳ 按钮可强制重新扫描
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
#   - 路径：MODELS_DIR / PRESETS_FILE / CONFIG_FILE / DEFAULTS_FILE / SERVER_EXE / JINJA
#     → 检索「MODELS_DIR =」
#   - CTX_PRESETS（上下文档 4K~64K）/ PARALLEL_OPTS（并发档）→ 检索「CTX_PRESETS =」
#   - PARAMS：参数表（ngl/flash/cache/temp/top_p/n_predict/port）。UI 按此表自动排两列（左列 row2 起、右列 row0 起）；推理预算为独立字段（row4,col2）
#     → 检索「PARAMS =」；加新简单参数只需在此表加一条，UI 行号自动推
#   - GEMMA_JINJA_TEMPLATE / VERSION / GITHUB_* → 检索「GEMMA_JINJA_TEMPLATE =」「VERSION =」
#
# 二、数据文件（与程序同目录 JSON，个人文件 gitignore 不入库）
#   - llm_gui_config.json：窗口/sash、硬件缓存、categories、server_path（llama 路径，全局）、
#     gemma（自动判断覆盖）、last_model/last_preset、overwrite_ask/remember_size
#   - llm_presets.json：{模型: {预设名: 参数}}（支持 JSONC 注释；模板见 presets_template.json）
#     llm_default_presets.json：自动计算缓存
#   → 读写函数检索「def load_cfg」「def load_presets」「def _strip_jsonc」
#
# 三、顶层函数 / 类
#   _lan_ip() 局域网IP / detect_gpus() 显卡列表 / detect_vram_gb() 显存GB → 检索「def detect_」
#   ToolTip 悬浮提示（place 到主窗，无独立窗口）→ 检索「class ToolTip」
#
# 四、App 类（主窗口，方法按功能分组）
#   - 初始化/生命周期：__init__ / _build_ui（全部 UI 在此构建）/ on_close → 检索「def _build_ui」
#   - 参数区网格行号表（CTkScrollableFrame；改布局先看这）：
#       row0 上下文长度(col0) / Flash(col2) | row1 并行请求 / 温度(col2)
#       row2 GPU层数(col0) / 最大输出(col2) | row3 KV缓存 / 思考模式(col2)
#       row4 top-p(col0) / 推理预算(col2) | row5 端口(col0) / 思考格式(col2)
#       row6 监听地址(col0) / 多模态+投影文件(col2) | row7 显卡(col0) / 图像 Min Tokens(col2)
#       row8 批处理大小(col0) / Gemma(col2) | row9 CORS(col0) / KV 不卸载(col2)
#       row10 min-p(col0) | row11 模板额外参数(col0)
#     base = 2+(len(PARAMS)+1)//2 = 6；PARAMS 左列 row2 起、右列 row0 起（右列与左列顶部对齐）；
#     思考模式(row3,2)、推理预算(row4,2)、思考格式(row5,2)、多模态+投影文件(row6,2)、图像 Min Tokens(row7,2)、
#     Gemma(row8,2)、KV 不卸载(row9,2)、min-p(row10,0)、模板额外参数(row11,0) 为硬编码，增删 PARAMS 项后须手动检查
#   - 模型数据：models_list / load_models / on_model_change（切模型刷新全部状态）
#     refresh_models（⟳ 按钮，异步重扫 models/，保留当前选中；期间按钮禁用）→ 检索「def refresh_models」
#     is_gemma（gemma 自动判断覆盖，按模型存 cfg）→ 检索「def on_model_change」「def is_gemma」
#     思考模式/多模态 thinking/mm 已是预设参数（thinking 默认开、mm 默认关）
#   - 多模态投影：find_mmproj（models/ 里按文件名 token 匹配 mmproj 投影文件；单个直接用、多个选最像的、都不像返回 None）；参数区「投影文件」下拉可手动指定（按模型存 cfg['mmproj']，优先于自动匹配）→ 检索「def find_mmproj」「def refresh_mmproj_menu」
#   - 显示名：clean_model_display（去目录/去 .gguf，仅显示用，不动 current_model）→ 检索「def clean_model_display」
#   - 默认参数：compute_defaults（显存+模型大小）/ apply_computed_defaults（后台线程计算）
#     → 检索「def compute_defaults」
#   - 预设：save_preset / del_preset / rename_preset / on_preset_load / refresh_preset_menu
#     import_presets / export_presets / 孤儿预设 manage_orphan_presets / 批量 manage_presets_all
#     → 检索「def save_preset」「def import_presets」「def manage_orphan_presets」
#   - 参数读写：set_params（UI←参数）/ read_params（UI→参数）→ 检索「def set_params」「def read_params」
#     加新参数必须在 set_params / read_params / build_cmd 三处同步（及 presets_template.json）
#   - 命令组装与启停：build_cmd（llama-server 命令行，新 CLI 参数只在此加）
#     start / stop / _read / _mark_stopped → 检索「def build_cmd」「def start」
#   - 后台线程：_poll_q 队列分发（kind=params/gpus/hardware/error）→ 检索「def _poll_q」
#   - 日志/服务信息：append_log / clear_log / update_svc_info / _set_svc_idle / _svc_*
#   - 弹窗：open_settings / confirm_overwrite / _import_conflict_dialog / manage_* 等
# ================================================================================
import json, os, queue, re, socket, struct, subprocess, sys, threading, traceback, webbrowser
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
PRESETS_FILE = os.path.join(BASE, 'llm_presets.json')
CONFIG_FILE = os.path.join(BASE, 'llm_gui_config.json')
DEFAULTS_FILE = os.path.join(BASE, 'llm_default_presets.json')
SERVER_EXE = os.path.join(BASE, 'llama-server.exe')
JINJA = os.path.join(BASE, 'gemma_chat_template.jinja')

CTX_PRESETS = {'4K': 4096, '8K': 8192, '12K': 12288, '16K': 16384, '24K': 24576, '32K': 32768, '48K': 49152, '64K': 65536}
PARALLEL_OPTS = ['1', '2', '4', '8', '16']

# 模型定位：用户未指定 = 通用（旧「未指定」已删除）；新增 编程 / Agent
CATEGORIES = ['通用', '聊天', '翻译', '角色扮演', '文学创作', '编程', 'Agent']

API_SUFFIXES = ['/v1/chat/completions', '/v1/completions', '/v1/embeddings', '/health']

DEFAULT_SASH_POS = 537   # 参数区/日志区默认分割位置（用户当前窗口状态）

GEMMA_JINJA_TEMPLATE = """{{ bos_token }}{% for message in messages %}{% if message['role'] == 'user' %}<start_of_turn>user
{{ message['content'] }}<end_of_turn>
{% elif message['role'] == 'assistant' %}<start_of_turn>model
{{ message['content'] }}<end_of_turn>
{% endif %}{% endfor %}{% if add_generation_prompt %}<start_of_turn>model
{% endif %}
"""

VERSION = '1.9.0'
GITHUB_USER = 'BFRKQSB7'
GITHUB_REPO = 'llm-launcher-gui'
GITHUB_URL = f'https://github.com/{GITHUB_USER}/{GITHUB_REPO}'
_SRC_MAX = 10   # 参数来源标识最大显示字符数；超出截断 + 完整内容进悬浮提示（防顶宽）
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


def load_presets():
    if os.path.exists(PRESETS_FILE):
        d = _load_jsonc(PRESETS_FILE)
        if isinstance(d, dict):
            return d
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


# ---------- GGUF 元数据解析（只读文件头，供自动计算精确估 KV/层数） ----------

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
        # 模型文件夹可自定义（空=程序同目录 models）；其余文件（presets/config/llama.exe/JINJA）仍留程序目录
        global MODELS_DIR
        MODELS_DIR = self.cfg.get('models_dir') or os.path.join(BASE, 'models')
        ws = self.cfg.get('window_size')
        if self.cfg.get('remember_size', True) and isinstance(ws, list) and len(ws) == 2:
            try:
                w, h = int(ws[0]), int(ws[1])
                w = max(780, min(w, self.winfo_screenwidth() - 40))
                h = max(580, min(h, self.winfo_screenheight() - 80))
                self.geometry(f'{w}x{h}')
            except (TypeError, ValueError):
                pass
        self._build_ui()
        self.load_models()
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        sp = self.cfg.get('sash_pos')
        if self.cfg.get('remember_size', True) and isinstance(sp, int):
            self.after(100, lambda: self._restore_sash(sp))
        else:
            self.after(100, self._restore_default_sash)
        self.after(100, self.on_model_change)
        self.after(200, self._startup_hardware)
        self.after(250, self._check_server)
        self._q = queue.Queue()
        self._preset_locked = False
        self.after(150, self._poll_q)

    def _restore_sash(self, pos):
        try:
            self.pw.sashpos(0, pos)
        except Exception:
            pass

    def _restore_default_sash(self):
        try:
            self.pw.sashpos(0, DEFAULT_SASH_POS)
        except Exception:
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

        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, sticky='ew', padx=12, pady=(12, 4))
        self.top_frame.grid_columnconfigure(1, weight=1)
        # 第一行：模型 + 模型定位 + 计算默认
        ctk.CTkLabel(self.top_frame, text='模型').grid(row=0, column=0, padx=(12, 6), pady=6)
        rowm = ctk.CTkFrame(self.top_frame, fg_color='transparent')
        rowm.grid(row=0, column=1, padx=6, pady=6, sticky='ew')
        rowm.grid_columnconfigure(0, weight=1)
        self.model_sel = ctk.CTkOptionMenu(rowm, values=[], command=lambda _: self.on_model_change(), width=260)
        self.model_sel.grid(row=0, column=0, sticky='ew')
        self.refresh_btn = ctk.CTkButton(rowm, text='⟳', width=32, command=self.refresh_models,
                                         fg_color='#3a3f4b', hover_color='#4a5263')
        ToolTip(self.refresh_btn, '刷新模型列表：重新扫描 models/ 目录下的模型文件')
        self.refresh_btn.grid(row=0, column=1, padx=(6, 0))
        ctk.CTkLabel(self.top_frame, text='模型定位').grid(row=0, column=2, padx=(20, 6), pady=6)
        self.cat_sel = ctk.CTkOptionMenu(self.top_frame, values=CATEGORIES, width=110,
                                         command=lambda _: self.on_category_change())
        self.cat_sel.grid(row=0, column=3, padx=6, pady=6, sticky='w')
        self.compute_btn = ctk.CTkButton(self.top_frame, text='⚙ 计算默认', width=84, command=lambda: self.apply_computed_defaults(force=True))
        ToolTip(self.compute_btn, '按本机显存 + 模型大小，自动计算当前模型的默认参数')
        self.compute_btn.grid(row=0, column=4, padx=(10, 12), pady=6)
        self.param_src_lab = ctk.CTkLabel(self.top_frame, text='', text_color='#8ab4f8', font=('Microsoft YaHei', 11))
        self.param_src_lab.grid(row=0, column=5, padx=(0, 12), pady=6, sticky='w')
        # 第二行：预设
        ctk.CTkLabel(self.top_frame, text='预设').grid(row=1, column=0, padx=(12, 6), pady=6)
        self.preset_sel = ctk.CTkOptionMenu(self.top_frame, values=['（无预设）'], command=lambda _: self.on_preset_load(), width=160)
        self.preset_sel.grid(row=1, column=1, padx=6, pady=6, sticky='w')
        self.preset_name = ctk.CTkEntry(self.top_frame, placeholder_text='新预设名（默认=模型名）')
        self.preset_name.grid(row=1, column=2, columnspan=2, padx=6, pady=6, sticky='ew')
        self.save_btn = ctk.CTkButton(self.top_frame, text='存为预设', width=80, command=self.save_preset)
        ToolTip(self.save_btn, '把当前参数保存为预设（名称用左边输入框的文字）')
        self.save_btn.grid(row=1, column=4, padx=6, pady=6)
        self.del_btn = ctk.CTkButton(self.top_frame, text='删预设', width=70, fg_color='#7a4a4a', hover_color='#8a5555', command=self.del_preset)
        ToolTip(self.del_btn, '删除下拉中当前选中的预设')
        self.del_btn.grid(row=1, column=5, padx=(6, 12), pady=6)
        self.rename_btn = ctk.CTkButton(self.top_frame, text='重命名', width=70, fg_color='#4a5568', hover_color='#556271', command=self.rename_preset)
        ToolTip(self.rename_btn, '把下拉中选中的预设，改名为左边输入框里的文字')
        self.rename_btn.grid(row=1, column=6, padx=(6, 12), pady=6)

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
        row0.grid(row=0, column=1, sticky='ew', padx=(6, 14), pady=5)
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
        row1.grid(row=1, column=1, sticky='ew', padx=(6, 14), pady=5)
        self.parallel_sel = ctk.CTkOptionMenu(row1, values=['（默认）'] + PARALLEL_OPTS, width=80, command=lambda _: self.update_calc())
        self.parallel_sel.pack(side='left')
        self.per_worker_lab = ctk.CTkLabel(row1, text='', text_color='#9fd6a5', width=220)
        self.per_worker_lab.pack(side='left', padx=(12, 0))

        # 其余简单字段两列排：左列 row2 起、右列 row0 起（右列与左列顶部对齐，Flash 与上下文长度同行）
        simple = PARAMS
        r = 2
        for i, pp in enumerate(simple):
            if i % 2:
                row, col = i // 2, 2
            else:
                row, col = r + i // 2, 0
            w = ctk.CTkOptionMenu(pf, values=pp['sel'], width=170) if pp.get('sel') else ctk.CTkEntry(pf, width=170)
            add_pair(row, col, pp['t'], pp['tip'], w)
            setattr(self, 'w_' + pp['k'], w)

        # 推理预算（--reasoning-budget）：思考 token 上限，配思考模式用（Murasaki/Qwen3/DeepSeek 等推理模型）
        self.w_reasoning_budget = ctk.CTkEntry(pf, width=170, placeholder_text='留空=不限')
        add_pair(4, 2, '推理预算', '推理模型在「思考」阶段最多花费的 token（--reasoning-budget）。-1=不限，0=立即结束思考，N=预算。留空=不传（llama 默认 -1 不限）。', self.w_reasoning_budget)

        # 思考格式（--reasoning-format）：控制思考内容在 API 返回里的呈现（配思考模式用）
        self.w_reasoning_format = ctk.CTkOptionMenu(pf, values=['（默认）', 'auto', 'none', 'deepseek', 'deepseek-legacy'], width=170)
        add_pair(5, 2, '思考格式', '控制思考内容在 API 返回里怎么呈现（--reasoning-format）。none=思考留在 message.content；deepseek=进 message.reasoning_content；deepseek-legacy=保留 <think> 标签同时进 reasoning_content；auto=自动。留空=不传（llama 默认 auto）。配「思考模式」用。', self.w_reasoning_format)

        # 监听地址 + 提示
        base = r + (len(simple) + 1) // 2
        lab = ctk.CTkLabel(pf, text='监听地址', anchor='w', width=110)
        lab.grid(row=base, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '127.0.0.1=仅本机访问；0.0.0.0=局域网可访问（配合防火墙）。')
        rowh = ctk.CTkFrame(pf, fg_color='transparent')
        rowh.grid(row=base, column=1, sticky='w', padx=(6, 14), pady=5)
        self.host_sel = ctk.CTkOptionMenu(rowh, values=['（默认）', '127.0.0.1', '0.0.0.0'], width=130, command=lambda _: self.update_host_hint())
        self.host_sel.pack(side='left')
        self.host_hint = ctk.CTkLabel(rowh, text='', text_color='#9fd6a5')
        self.host_hint.pack(side='left', padx=(8, 0))

        # GPU 选择 + 刷新
        lab = ctk.CTkLabel(pf, text='显卡', anchor='w', width=110)
        lab.grid(row=base + 1, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '选择用于推理的显卡（--main-gpu）。「自动」不传该参数，由 llama 自行选择。')
        rowg = ctk.CTkFrame(pf, fg_color='transparent')
        rowg.grid(row=base + 1, column=1, sticky='w', padx=(6, 14), pady=5)
        self.gpu_sel = ctk.CTkOptionMenu(rowg, values=['自动'], width=GPU_BOX_MAX,
                                         command=lambda _: self._update_gpu_tip())
        self.gpu_sel.pack(side='left')
        self.gpu_tip = ToolTip(self.gpu_sel, '选择用于推理的显卡（--main-gpu）。「自动」不传该参数，由 llama 自行选择。')
        self.recheck_btn = ctk.CTkButton(rowg, text='检查配置', width=68, command=self.recheck_hardware)
        ToolTip(self.recheck_btn, '重新检测本机显卡与显存')
        self.recheck_btn.pack(side='left', padx=(8, 0))

        # 可选参数：批处理大小
        lab = ctk.CTkLabel(pf, text='批处理大小', anchor='w', width=110)
        lab.grid(row=base + 2, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '可选（--batch-size）。留空则不传该参数，使用 llama 默认值。一般无需手动设置。')
        self.w_n_batch = ctk.CTkEntry(pf, width=170, placeholder_text='留空=不传')
        self.w_n_batch.grid(row=base + 2, column=1, padx=(6, 14), pady=5, sticky='w')

        # CORS 允许源（--cors）：浏览器跨域访问 API 的来源白名单
        lab = ctk.CTkLabel(pf, text='CORS 允许源', anchor='w', width=110)
        lab.grid(row=base + 3, column=0, padx=(14, 6), pady=5, sticky='w')
        ToolTip(lab, '浏览器跨域访问 API 时校验的来源（--cors）。*=允许任意来源；也可写具体来源，多个用逗号分隔，如 http://localhost:3000,http://localhost:5173。留空 = 不传（llama 不启用 CORS）。')
        self.w_cors = ctk.CTkEntry(pf, width=220, placeholder_text='* 或 http://localhost:3000')
        self.w_cors.grid(row=base + 3, column=1, padx=(6, 14), pady=5, sticky='w')

        # min-p 采样（--min-p）：动态按最高候选概率缩放过滤，比 top-p 更顺滑
        self.w_min_p = ctk.CTkEntry(pf, width=170, placeholder_text='留空=llama 默认 0.05')
        add_pair(10, 0, 'min-p', 'min-p 采样（--min-p）。按当前最高候选概率动态缩放过滤阈值，比 top-p 更顺滑、少一刀切。越小越接近贪心，越大越多样；0=关（用 llama 默认 0.05）。留空=不传。', self.w_min_p)

        # 模板额外参数（--chat-template-kwargs）：给 Jinja 模板传额外 JSON 对象参数
        self.w_chat_template_kwargs = ctk.CTkEntry(pf, width=220, placeholder_text='如 {"enable_thinking":false}')
        add_pair(11, 0, '模板额外参数', '给聊天模板传额外 JSON 参数（--chat-template-kwargs），必须是合法 JSON 对象字符串，如 {"enable_thinking":false}。对 Qwen3 系填 enable_thinking:false 可真正关闭思考（模板级，比 --reasoning off 更直接）；对不读该变量的模型无效。留空=不传。', self.w_chat_template_kwargs)

        # 思考模式开关（预设参数，默认开；on→--reasoning on，off→--reasoning off；Murasaki/Qwen3/DeepSeek 等推理模型用）
        self.think_chk = ctk.CTkCheckBox(pf, text='思考模式', command=self.on_thinking_toggle)
        self.think_chk.grid(row=3, column=2, columnspan=2, padx=(14, 6), pady=5, sticky='w')
        ToolTip(self.think_chk, '推理模型（Murasaki/Qwen3/DeepSeek 等）开=先思考再答，关=直出答案（--reasoning off）。默认开，存为预设参数；预设省略时按开处理。')

        # 多模态 + 投影文件（同一行，跨两列宽度；文件名提示吃满剩余宽度，长名也尽量显示完整）
        rowmm = ctk.CTkFrame(pf, fg_color='transparent')
        rowmm.grid(row=6, column=2, columnspan=2, sticky='ew', padx=(14, 14), pady=5)
        rowmm.grid_columnconfigure(2, weight=1)
        self.mm_chk = ctk.CTkCheckBox(rowmm, text='多模态', command=self.on_mm_toggle)
        self.mm_chk.grid(row=0, column=0, sticky='w')
        ToolTip(self.mm_chk, '视觉/多模态模型（Qwen2.5-VL / LLaVA / MiniCPM-V 等）勾选后启动带 --mmproj，自动在 models/ 里按文件名匹配投影文件（也可用旁边下拉手动指定）。默认关，存为预设参数。')
        self.mmproj_sel = ctk.CTkOptionMenu(rowmm, values=['（自动）'], width=100, dynamic_resizing=False,
                                            command=lambda _: self.on_mmproj_pick())
        self.mmproj_sel.grid(row=0, column=1, sticky='w', padx=(8, 0))
        ToolTip(self.mmproj_sel, '当前模型用的多模态投影文件（--mmproj）。「（自动）」= 按文件名自动匹配（右侧小字显示自动选中谁）；选具体文件 = 手动指定，按模型记住。自动匹配不到时启动会在日志提示。')
        self.mmproj_hint = tk.Label(rowmm, text='', fg='#9fd6a5', bg='#2b2b2b',
                                    font=('Microsoft YaHei', 9), anchor='w')
        self.mmproj_hint.grid(row=0, column=2, sticky='ew', padx=(8, 0))
        self._mmproj_hint_tt = ToolTip(self.mmproj_hint, '')

        # 图像 Min Tokens（--image-min-tokens）：视觉模型动态分辨率下每个图像最少 token 数（多模态下方）
        self.w_image_min_tokens = ctk.CTkEntry(pf, width=170, placeholder_text='留空=llama 默认')
        add_pair(7, 2, '图像 Min Tokens', '视觉/多模态模型（动态分辨率）每个图像最少生成的 token 数（--image-min-tokens）。值越小图像细节越少、越省显存/越快；越大越清晰、越占显存。留空=不传（llama 从模型读取默认）。存为预设参数。', self.w_image_min_tokens)

        # Gemma 模型（可选勾选，替代仅按文件名判断；多模态/图像 Min Tokens 下方一格）
        self.gemma_chk = ctk.CTkCheckBox(pf, text='Gemma 模型', command=self.on_gemma_toggle)
        self.gemma_chk.grid(row=8, column=2, columnspan=2, padx=(14, 6), pady=5, sticky='w')
        ToolTip(self.gemma_chk, '旧版 Gemma（gemma-2b/7b、translategemma 等）需要外部 --chat-template-file（gemma_chat_template.jinja），且建议低温；新 gemma3/4 自带模板、无需勾选。默认关，勾过一次按模型记住；存为预设参数。')

        # KV 不卸载到 GPU（--no-kv-offload）：默认关；勾选后 KV 留系统内存，腾显存给模型层/上下文
        self.no_kv_chk = ctk.CTkCheckBox(pf, text='KV 不卸载到 GPU', command=self.on_no_kv_toggle)
        self.no_kv_chk.grid(row=9, column=2, columnspan=2, padx=(14, 6), pady=5, sticky='w')
        ToolTip(self.no_kv_chk, '勾选 = 启动带 --no-kv-offload：KV 缓存不卸载到 GPU（留在系统内存），腾出显存给更多模型层或更大上下文——MoE 模型、显存紧张时用。默认不勾选（KV 在显存，速度最快）。存为预设参数。')

        self.bar = ctk.CTkFrame(self)
        self.bar.grid(row=2, column=0, sticky='ew', padx=12, pady=6)
        self.bar.grid_columnconfigure(3, weight=1)
        ctk.CTkButton(self.bar, text='▶ 启动', fg_color='#2f7a50', hover_color='#358a5c', width=110, command=self.start).grid(row=0, column=0, padx=12, pady=10)
        ctk.CTkButton(self.bar, text='■ 停止', fg_color='#8a3f3f', hover_color='#9a4848', width=110, command=self.stop).grid(row=0, column=1, padx=6, pady=10)
        ctk.CTkButton(self.bar, text='清屏', fg_color='#3d4552', hover_color='#4a5464', width=110, command=self.clear_log).grid(row=0, column=2, padx=6, pady=10)
        self.status_lab = ctk.CTkLabel(self.bar, text='● 未运行', text_color='#e07070')
        self.status_lab.grid(row=0, column=4, padx=12, pady=10, sticky='e')
        ctk.CTkButton(self.bar, text='⚙ 设置', width=64, fg_color='#4a5568', hover_color='#556271', command=self.open_settings).grid(row=0, column=6, padx=(4, 12), pady=10)

        f2 = tk.Frame(self.pw, bg='#242424')
        log_head = tk.Frame(f2, bg='#242424')
        log_head.pack(fill='x')
        ctk.CTkLabel(log_head, text='日志', anchor='w', text_color='#8a93a6', font=('Microsoft YaHei', 12)).pack(side='left', padx=(8, 0))
        self.svc_info = tk.Text(f2, wrap='word', height=1, bd=0, highlightthickness=0,
                                relief='flat', padx=2, pady=1, bg='#242424', fg='#9aa4b8',
                                font=('Consolas', 11), takefocus=0)
        self.svc_info.pack(fill='x', padx=8, pady=(4, 2))
        self.svc_info.bind('<Key>', self._svc_readonly)
        self.svc_info.bind('<Configure>', lambda _: self._svc_sync_height())
        self._set_svc_idle()
        self.log_box = ctk.CTkTextbox(f2, state='disabled', wrap='none', font=('Consolas', 12))
        self.log_box.pack(fill='both', expand=True)
        self.pw.add(f2, weight=1)
        self._bind_param_edit_marker()

    def _bind_param_edit_marker(self):
        def mark(_=None):
            self._set_param_src('✏ 手动调整', '#e8b04a')

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

        for w in [self.ctx_input, self.parallel_sel, self.host_sel, self.gpu_sel, self.w_n_batch,
                  self.w_reasoning_budget, self.w_reasoning_format, self.mmproj_sel, self.w_cors,
                  self.w_image_min_tokens, self.w_min_p, self.w_chat_template_kwargs]:
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

    def refresh_models(self):
        """⟳ 按钮：强制重扫 models/ 目录。后台线程扫描，结果经 _q 回主线程，不阻塞 UI。"""
        if not os.path.isdir(MODELS_DIR):
            self.append_log('!!! models 目录不存在：' + os.path.normpath(MODELS_DIR))
            return
        self.refresh_btn.configure(state='disabled', text='⏳')
        self.append_log('>>> 正在刷新模型列表…')

        def work():
            try:
                self._q.put(('models', self.models_list(), None))
            except Exception as e:
                self._q.put(('models', [], str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _apply_refreshed_models(self, ms, err):
        # 主线程：刷新完成。恢复按钮；当前选中的模型还在列表里就保持不变，否则回落第一个
        self.refresh_btn.configure(state='normal', text='⟳')
        if err:
            self.append_log('!!! 刷新模型列表失败: ' + err)
            return
        cur = self.current_model
        keep = cur if (cur and cur in ms) else None
        self.model_sel.configure(values=ms if ms else ['（models 目录为空）'])
        if keep:
            self.model_sel.set(keep)
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

    def on_model_change(self):
        m = self.model_sel.get()
        if not m or m.startswith('（'):
            return
        self.current_model = m
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
        self._preset_locked = False   # 用户主动切换 → 重新按 gemma 计算
        self.apply_computed_defaults()   # gemma 会影响温度/输出长度

    def on_thinking_toggle(self):
        checked = bool(self.think_chk.get())
        self.append_log(f'>>> 思考模式：{"开" if checked else "关"}（存为预设时随预设一起保存）')

    def on_mm_toggle(self):
        checked = bool(self.mm_chk.get())
        self.append_log(f'>>> 多模态：{"开" if checked else "关"}（存为预设时随预设一起保存）')

    def on_no_kv_toggle(self):
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
        """按本机显存 + 模型大小（+ GGUF 架构元数据）自动计算默认参数。返回 (params, 说明)。
        - 模型整体装得下 → ngl=999，按剩余显存 ÷ KV每token 精确算上下文
        - 模型大于显存 → 部分卸载（能装下的层数进 GPU，MoE 尤其受益），比纯 CPU 快很多
        - KV 每 token 字节数优先从 GGUF 元数据算（q8_0=1 字节/元素），读不到用 0.5GB/4K 启发式"""
        vram_gb = self.get_vram_gb()
        path = os.path.join(MODELS_DIR, model)
        try:
            model_gb = os.path.getsize(path) / (1024 ** 3)
        except Exception:
            model_gb = 0
        arch = read_model_arch(path)
        kv_per_token = arch['kv_per_token'] if arch else 0
        if not kv_per_token:
            kv_per_token = int(0.5 * (1024 ** 3) / 4096)   # 启发式兜底：0.5GB/4K（q8_0 粗估）
        reserve = 1.5   # 预留显存：计算缓冲 / 激活 / 碎片
        ngl, ctx = 0, 32768
        detail = '（缺显存/模型信息，回退保守参数）'
        if vram_gb > 0 and model_gb > 0:
            if model_gb + reserve <= vram_gb:
                ngl = 999
                kv_budget = max(0.5, vram_gb - model_gb - reserve)
                ctx = int(kv_budget * (1024 ** 3) / kv_per_token)
                ctx = max(2048, min(65536, ctx))
                detail = f'模型 {model_gb:.1f}G 可整体进显存，KV 预算 {kv_budget:.1f}G'
            else:
                # 模型 > 显存：部分卸载。目标 ctx 下 KV 随层均分 GPU，算能装下的层数
                nl = arch['n_layers'] if arch else 0
                target_ctx = 8192
                if nl and nl > 1:
                    kv_gb = target_ctx * kv_per_token / (1024 ** 3)
                    denom = model_gb + kv_gb + reserve
                    frac = (vram_gb - reserve) / denom if denom > 0 else 0
                    frac = min(0.999, max(0.05, frac))
                    ngl = max(1, min(int(frac * nl), nl - 1))
                    ctx = target_ctx
                    detail = f'模型 {model_gb:.1f}G > 显存 {vram_gb:.1f}G，部分卸载 {ngl}/{nl} 层'
                    if arch['is_moe']:
                        detail += '（MoE，KV 小、卸载效率高）'
                else:
                    detail = f'模型 {model_gb:.1f}G > 显存 {vram_gb:.1f}G，无法读层数，回退纯 CPU'
        cat = {
            '聊天':     {'temp': 0.7,  'top_p': 0.9,  'n_predict': 1024},
            '通用':     {'temp': 0.6,  'top_p': 0.9,  'n_predict': 2048},
            '翻译':     {'temp': 0.2,  'top_p': 0.8,  'n_predict': 4096},
            '角色扮演': {'temp': 0.8,  'top_p': 0.95, 'n_predict': 1024},
            '文学创作': {'temp': 0.75, 'top_p': 0.95, 'n_predict': 2048},
            '编程':     {'temp': 0.2,  'top_p': 0.9,  'n_predict': 4096},
            'Agent':    {'temp': 0.3,  'top_p': 0.9,  'n_predict': 2048},
        }.get(category, {'temp': 0.5, 'top_p': 0.9, 'n_predict': 2048})
        if self.is_gemma(model):
            # Gemma 特适配：低温度 + 长输出（需 --chat-template-file）
            cat = {'temp': 0.1, 'top_p': 0.9, 'n_predict': 4096}
        # 端口不随自动计算覆盖：保留当前输入；未设则用设置里的默认端口（兜底 llama 默认 8080）
        port = cur_port or str(self.cfg.get('default_port') or 8080)
        return ({'ctx': ctx, 'ngl': ngl, 'flash': 'on', 'cache': 'q8_0',
                 'temp': cat['temp'], 'top_p': cat['top_p'], 'n_predict': cat['n_predict'],
                 'parallel': 1, 'port': port, 'host': '127.0.0.1',
                 'gpu': '自动', 'n_batch': '', 'thinking': True, 'gemma': self.is_gemma(model),
                 'mm': False, 'cors': '', 'image_min_tokens': '', 'no_kv_offload': False,
                 'min_p': '', 'chat_template_kwargs': '', 'reasoning_format': ''},
                detail)

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
                    _, model, cat, params, vram, force, detail = item
                    self._save_computed_defaults(model, params)
                    if self.current_model == model and (force or not self._preset_locked):
                        self.set_params(params)
                        self._set_param_src('⚡ 自动计算', '#8ab4f8', tip=f'{vram}G 显存 + 模型大小 自动计算\n{detail}')
                        self.append_log(f'>>> 按显存 {vram}G + 模型大小计算默认参数（{cat}）：{detail}')
                elif kind == 'gpus':
                    _, gpus = item
                    self._apply_gpus(gpus)
                elif kind == 'hardware':
                    _, vram, gpus, then_compute = item
                    self._apply_gpus(gpus)
                    if then_compute:
                        self.apply_computed_defaults()
                elif kind == 'models':
                    _, ms, err = item
                    self._apply_refreshed_models(ms, err)
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

    def _check_server(self):
        # 启动后检查 llama-server.exe：缺失不阻塞界面，只提示 + 记日志（可在「设置」里改路径）
        exe = self.cfg.get('server_path') or SERVER_EXE
        if os.path.exists(exe):
            return
        msg = ('未找到 llama-server.exe\n请在「设置」里选择 llama 路径，'
               '或把它放到程序同目录：\n' + os.path.normpath(BASE))
        self.append_log('!!! 未找到 llama-server.exe（请在「设置」里配置路径，或放到程序同目录）')
        messagebox.showwarning('LLM GUI', msg)

    def recheck_hardware(self):
        self._detect_and_save_hardware(then_compute=True)

    def apply_computed_defaults(self, model=None, force=False):
        model = model or self.current_model
        if not model:
            return
        cat = self.get_category(model)
        cur_port = self.w_port.get().strip()   # 主线程读端口再传后台线程（widget 不能跨线程访问）

        def work():
            try:
                params, detail = self.compute_defaults(model, cat, cur_port)
                self._q.put(('params', model, cat, params, self.get_vram_gb(), force, detail))
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
        enabled = bool(sel and sel != '（无预设）')
        self.del_btn.configure(state='normal' if enabled else 'disabled')
        if enabled:
            self.del_btn.configure(fg_color='#c0392b', hover_color='#e74c3c')   # 可用：鲜艳红
        else:
            self.del_btn.configure(fg_color='#7a4a4a', hover_color='#8a5555')   # 不可用：暗红

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
        set_entry(self.w_cors, p.get('cors'))   # CORS 缺省=留空=不传
        set_entry(self.w_reasoning_budget, p.get('reasoning_budget'))
        set_entry(self.w_image_min_tokens, p.get('image_min_tokens'))
        set_entry(self.w_min_p, p.get('min_p'))
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
                raise ValueError(f'{k} 需要整数，当前值：{v!r}')

        def fltv(k, v):
            if v in ('', '（默认）'):
                return ''
            try:
                return float(v)
            except (ValueError, TypeError):
                raise ValueError(f'{k} 需要数字，当前值：{v!r}')

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
            'n_batch': self.w_n_batch.get().strip(),
            'cors': self.w_cors.get().strip(),
            'reasoning_budget': intv('推理预算', self.w_reasoning_budget.get().strip()),
            'image_min_tokens': intv('图像 Min Tokens', self.w_image_min_tokens.get().strip()),
            'min_p': fltv('min-p', self.w_min_p.get().strip()),
            'chat_template_kwargs': self.w_chat_template_kwargs.get().strip(),
            'reasoning_format': '' if self.w_reasoning_format.get() == '（默认）' else self.w_reasoning_format.get(),
            'thinking': bool(self.think_chk.get()),
            'gemma': bool(self.gemma_chk.get()),
            'mm': bool(self.mm_chk.get()),
            'no_kv_offload': bool(self.no_kv_chk.get()),
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
            self.append_log('!!! ' + str(e)); return
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
        if n in self.presets.get(self.current_model, {}):
            del self.presets[self.current_model][n]
            save_presets(self.presets)
            if self.cfg.get('last_preset', {}).get(self.current_model) == n:
                self.cfg['last_preset'].pop(self.current_model, None)
                save_cfg(self.cfg)
            self.refresh_preset_menu()
            self.append_log(f'>>> 已删预设「{n}」')

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
            ctk.CTkButton(dlg, text='关闭', width=90, command=dlg.destroy).pack()
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
        ctk.CTkButton(row, text='保留', width=82, command=dlg.destroy).pack(side='left', padx=4)
        ctk.CTkButton(row, text='删除无效', width=82, fg_color='#8a3f3f', hover_color='#9a4848',
                      command=lambda: self.delete_orphans(dlg)).pack(side='left', padx=4)
        ctk.CTkButton(row, text='导出有效', width=82,
                      command=lambda: self.export_presets(True, dlg)).pack(side='left', padx=4)
        ctk.CTkButton(row, text='导出无效', width=82,
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
        ctk.CTkButton(row, text='覆盖导入的', width=110, command=lambda: choose('overwrite')).pack(side='left', padx=6)
        ctk.CTkButton(row, text='保留现有的', width=110, command=lambda: choose('skip')).pack(side='left', padx=6)

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
                     text_color='#9aa4b8', font=('Microsoft YaHei', 11)).pack(pady=(14, 4), padx=16, anchor='w')
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

        ctk.CTkButton(bar, text='全选', width=70, command=lambda: set_all(True)).pack(side='left', padx=4)
        ctk.CTkButton(bar, text='反选', width=70, command=invert).pack(side='left', padx=4)
        ctk.CTkButton(bar, text='取消全选', width=90, command=lambda: set_all(False)).pack(side='left', padx=4)
        ctk.CTkButton(bar, text='导出选中', width=90, fg_color='#3d6e5a', hover_color='#477a66',
                      command=lambda: self.export_selected_presets(dlg)).pack(side='left', padx=4)
        ctk.CTkButton(bar, text='删除选中', width=90, fg_color='#8a3f3f', hover_color='#9a4848',
                      command=lambda: self.delete_selected_presets(dlg)).pack(side='right', padx=4)
        ctk.CTkButton(bar, text='关闭', width=70, command=dlg.destroy).pack(side='right', padx=4)

    def export_selected_presets(self, dlg):
        """批量管理：把勾选的预设导出为 JSON（与 llm_presets.json 同构，可再导入）。"""
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

        ctk.CTkButton(btns, text='覆盖', width=96, fg_color='#2f7a50', hover_color='#358a5c', command=ok).pack(side='left', padx=10)
        ctk.CTkButton(btns, text='取消', width=96, command=dlg.destroy).pack(side='left', padx=10)

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

        ctk.CTkButton(btns, text=yes_text, width=110, fg_color='#8a3f3f',
                      hover_color='#9a4848', command=yes).pack(side='left', padx=8)
        ctk.CTkButton(btns, text='取消', width=90, command=no).pack(side='left', padx=8)
        self._confirm_open = dlg

    def open_settings(self):
        dlg = ctk.CTkToplevel(self)
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

        # llama-server 路径（全局，不在预设里）
        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(8, 2))
        ctk.CTkLabel(dlg, text='llama-server.exe 路径（全局，留空=程序同目录）',
                     anchor='w').pack(padx=24, pady=(4, 2), anchor='w')
        spf = ctk.CTkFrame(dlg, fg_color='transparent')
        spf.pack(padx=24, pady=(0, 6), fill='x')
        sp_entry = ctk.CTkEntry(spf, placeholder_text='留空=程序同目录 llama-server.exe')
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

        ctk.CTkButton(spf, text='浏览…', width=70, command=browse_sp).pack(side='left', padx=(6, 0))

        # 模型文件夹（全局，留空=程序同目录 models）
        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(8, 2))
        ctk.CTkLabel(dlg, text='模型文件夹（全局，留空=程序同目录 models）',
                     anchor='w').pack(padx=24, pady=(4, 2), anchor='w')
        mdf = ctk.CTkFrame(dlg, fg_color='transparent')
        mdf.pack(padx=24, pady=(0, 6), fill='x')
        md_entry = ctk.CTkEntry(mdf, placeholder_text='留空=程序同目录 models')
        md_entry.pack(side='left', fill='x', expand=True)
        md_entry.insert(0, self.cfg.get('models_dir', ''))

        def browse_md():
            cur = md_entry.get().strip()
            init = cur if cur and os.path.isdir(cur) else BASE
            p = filedialog.askdirectory(parent=dlg, title='选择模型文件夹', initialdir=init)
            if p:
                md_entry.delete(0, 'end')
                md_entry.insert(0, p)

        ctk.CTkButton(mdf, text='浏览…', width=70, command=browse_md).pack(side='left', padx=(6, 0))

        # 默认端口（全局）：无预设自动计算时保留当前端口；未设端口时用它兜底
        dpf = ctk.CTkFrame(dlg, fg_color='transparent')
        dpf.pack(padx=24, pady=(8, 6), fill='x')
        ctk.CTkLabel(dpf, text='默认端口（全局）', width=130, anchor='w').pack(side='left')
        dp_entry = ctk.CTkEntry(dpf, placeholder_text='留空=8080')
        dp_entry.pack(side='left', padx=(8, 0), fill='x', expand=True)
        dp_entry.insert(0, str(self.cfg.get('default_port', '')))

        def save():
            self.cfg['overwrite_ask'] = bool(ask.get())
            self.cfg['remember_size'] = bool(sizebox.get())
            self.cfg['server_path'] = sp_entry.get().strip()
            md = md_entry.get().strip()
            self.cfg['models_dir'] = md   # 空=默认程序同目录 models
            dp = dp_entry.get().strip()
            if dp:
                try:
                    dp = int(dp)
                except ValueError:
                    messagebox.showwarning('设置', '默认端口需为整数', parent=dlg)
                    return
                self.cfg['default_port'] = dp
            else:
                self.cfg.pop('default_port', None)
            save_cfg(self.cfg)
            global MODELS_DIR
            MODELS_DIR = md or os.path.join(BASE, 'models')
            self.load_models()
            self.refresh_mmproj_menu()
            self.append_log('>>> 模型文件夹已切换：' + os.path.normpath(MODELS_DIR))
            dlg.destroy()

        # 保存按钮并入默认端口行（避免端口框过长、也省一整行高度）
        ctk.CTkButton(dpf, text='保存', width=90, command=save).pack(side='left', padx=(8, 0))

        # 预设健康检查（打开设置即自动检查缺失模型的预设）
        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(8, 2))
        n_orphan = len(self.find_orphan_presets())
        ctk.CTkLabel(dlg, text=f'预设健康检查：缺失模型的预设 {n_orphan} 个',
                     text_color='#e8b04a' if n_orphan else '#7fd9a0').pack(pady=(2, 4))
        ctk.CTkButton(dlg, text='管理（保留 / 删除 / 导出有效 / 导出无效）', width=280,
                      command=self.manage_orphan_presets).pack(pady=(0, 6))
        btns = ctk.CTkFrame(dlg, fg_color='transparent')
        btns.pack(pady=(0, 8))
        ctk.CTkButton(btns, text='导入预设（合并）', width=132, command=self.import_presets).pack(side='left', padx=4)
        ctk.CTkButton(btns, text='批量管理预设', width=132, command=self.manage_presets_all).pack(side='left', padx=4)

        # 模型清单（弹出独立窗口）
        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(8, 2))
        ctk.CTkButton(dlg, text='📦 模型清单', width=200, command=self.show_model_list).pack(pady=(0, 6))

        ctk.CTkLabel(dlg, text='─' * 36, text_color='#556271').pack(pady=(6, 2))
        ctk.CTkLabel(dlg, text=f'LLM GUI · v{VERSION}', font=('Microsoft YaHei', 14, 'bold')).pack()
        ctk.CTkLabel(dlg, text='llama-server 本地桌面启动器', text_color='#9aa4b8').pack(pady=(2, 0))
        ctk.CTkLabel(dlg, text=f'GitHub：{GITHUB_USER}', text_color='#9aa4b8').pack(pady=(8, 0))
        link = ctk.CTkLabel(dlg, text=GITHUB_URL, text_color='#7db4ff', cursor='hand2', font=('Consolas', 11))
        link.pack(pady=(2, 0))
        link.bind('<Button-1>', lambda _: webbrowser.open(GITHUB_URL))

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
        ctk.CTkButton(dlg, text='关闭', width=90, command=dlg.destroy).pack(pady=10)

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
        host = p.get('host') or '127.0.0.1'
        port = p.get('port') or 8080
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
        urls = ' · '.join(f'http://{h}:{port}{s}' for h in hosts for s in API_SUFFIXES)
        self.svc_info.delete('1.0', 'end')
        self.svc_info.insert('1.0', f'模型：{clean_model_display(model)}\nAPI：{base}\n{urls}')
        self.svc_info.tag_configure('body', foreground='#7fd9a0')
        self.svc_info.tag_add('body', '1.0', 'end')
        self._svc_sync_height()

    def _set_svc_idle(self):
        self.svc_info.delete('1.0', 'end')
        self.svc_info.insert('1.0', '（未运行）')
        self.svc_info.tag_configure('idle', foreground='#9aa4b8')
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
            self.append_log('!!! ' + str(e)); return
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
        self.status_lab.configure(text=f'● 运行中 · {mname} · :{p.get("port") or 8080}', text_color='#7fd9a0')
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
        self._set_svc_idle()

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
