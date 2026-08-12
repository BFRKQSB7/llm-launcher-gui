# LLM GUI

Windows 本地桌面启动器 —— 用图形界面管理 `llama-server`，启动本地大模型推理服务。

> [English](docs/en/README.md)

## 特性

- 扫描 `models/` 列出本地 GGUF 模型，一键启动 / 停止 `llama-server`
- 每模型多套预设：选模型 → 加载预设 → 启动；参数悬浮即有解释
- 上下文长度自定义 + 预设档（4K ~ 64K）；并发请求自动计算每线程上下文
- 模型定位（聊天 / 翻译 / 角色扮演 / 文学创作…）→ 按显存 + 模型大小自动计算默认参数
- Gemma 模型选项：勾选后使用专用聊天模板并建议低温（替代按文件名猜测）
- GPU 下拉（`nvidia-smi` 自动检测）；监听地址本机 / 局域网；KV 缓存精度档位
- 实时日志 + 常驻显示模型名与 API 地址（含 `/v1/chat/completions` 等端点）
- 单文件 exe，无需安装 Python

## 快速开始

1. 下载 [llama.cpp](https://github.com/ggml-org/llama.cpp/releases) Windows CUDA 版，将 `llama-server.exe` 及其 DLL 放到程序同目录
2. 把 GGUF 模型放入程序同目录的 `models/` 子目录
3. 运行 `LLMGUI.exe`，或直接用 Python 运行 `python llm_gui.py`

> Gemma 模型需要 `gemma_chat_template.jinja`（已随仓库提供）。

## 使用说明

- **预设**：选好模型和参数后点「存为预设」；每个模型可有多套预设（数据存本地 `llm_presets.json`，属个人文件，不入库）
- **自动计算**：选「模型定位」后点「⚙ 计算默认」，程序按本机显存 + 模型大小算出 `ctx / ngl / temp…`（结果存本地 `llm_default_presets.json`，机器相关，不入库）
- **Gemma 模型**：勾选参数区的「Gemma 模型」复选框，启动会带 `--chat-template-file` 且自动计算采用低温度；默认按文件名自动判断，可手动覆盖并按模型记住
- **API 地址**：启动后日志上方常驻显示 `http://127.0.0.1:<端口>` 与常用端点，方便接入翻译工具等

## 文件结构

| 文件 | 说明 |
|------|------|
| `llm_gui.py` | 程序源码 |
| `gemma_chat_template.jinja` | Gemma 聊天模板 |
| `app.ico` | 程序图标 |

本地运行后自动生成（个人文件，不入库）：`llm_presets.json`（预设）、`llm_default_presets.json`（自动计算参数）、`llm_gui_config.json`（本机配置）。

## 打包 exe

```bat
pyinstaller --onefile --windowed --name LLMGUI --icon=app.ico --collect-all customtkinter llm_gui.py
```

## 版本

- v1.0.0（2026-08-12）首版：预设 / 自动计算 / GPU 检测 / 常驻 API 地址 / Gemma 选项 / 版本号与 About
