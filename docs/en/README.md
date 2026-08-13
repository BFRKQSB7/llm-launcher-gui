# LLM GUI

A local desktop launcher for Windows that manages `llama-server` with a GUI — start local LLM inference with point-and-click.

> [中文](../README.md)

## Features

- Scans `models/` for local GGUF models, starts / stops `llama-server` in one click
- Per-model presets: pick model → load preset → start; hover tooltips on every parameter
- Custom context length + presets (4K ~ 64K); parallel requests auto-compute per-worker context
- Model category (chat / translation / roleplay / creative writing…) → auto-computes defaults from VRAM + model size
- Thinking mode toggle: reasoning models (Murasaki / Qwen3 / DeepSeek…) can turn thinking output on/off (`--reasoning on/off`), default on, saved as a preset parameter
- Multimodal toggle: vision models (Qwen2.5-VL / LLaVA / MiniCPM-V…) launch with `--mmproj`, auto-matching the mmproj projector file in `models/`
- Gemma model option: uses the dedicated chat template and suggests a low temperature (a preset parameter; falls back to filename detection when omitted)
- All parameters can be left empty: empty fields are not passed to llama-server, which then uses its own defaults
- llama-server.exe path is a global setting (choose it in Settings; leave empty for same-folder)
- GPU dropdown (auto-detected via `nvidia-smi`); listen on localhost / LAN; KV cache precision options
- Live logs + persistent display of model name and API endpoints (e.g. `/v1/chat/completions`)
- Single-file exe, no Python installation needed

## Screenshot

![LLM GUI](../../screenshot.jpg)

## Quick Start

1. Download the Windows CUDA build of [llama.cpp](https://github.com/ggml-org/llama.cpp/releases), put `llama-server.exe` and its DLLs next to the program
2. Put GGUF models into a `models/` subdirectory next to the program
3. Run `LLMGUI.exe`, or run `python llm_gui.py`

> Gemma models need `gemma_chat_template.jinja` (bundled in this repo).

## Usage

- **Presets**: tune parameters then click "存为预设" to save; each model can have multiple presets (stored locally in `llm_presets.json`, a personal file not committed to the repo). Every settable parameter is saved into the preset (including thinking / Gemma); empty values are not passed to llama-server (llama defaults apply)
- **Auto-compute**: pick a "模型定位" (category) then click "⚙ 计算默认"; the program computes `ctx / ngl / temp…` from your VRAM and model size (results stored locally in `llm_default_presets.json`, machine-specific, not committed)
- **Gemma**: check the "Gemma 模型" box in the parameters area to launch with `--chat-template-file` and low-temperature auto-compute; saved as a preset parameter, falls back to filename detection when omitted
- **Thinking mode**: the "思考模式" checkbox in the parameters area defaults to on → launch with `--reasoning on` (reasoning models think first, e.g. Murasaki's chain-of-thought / Qwen3); uncheck → `--reasoning off` (direct answer). Saved as a preset parameter (treated as on when omitted)
- **Multimodal**: check the "多模态" box → launch with `--mmproj`, auto-matching the mmproj projector file in `models/` (logs a warning when none is found); saved as a preset parameter, default off
- **llama path**: defaults to `llama-server.exe` next to the program; a different path can be set globally in Settings (not part of presets)
- **API address**: after startup, the model name and `http://127.0.0.1:<port>` endpoints are shown persistently above the log

## Files

| File | Description |
|------|-------------|
| `llm_gui.py` | Program source |
| `gemma_chat_template.jinja` | Chat template for Gemma models |
| `presets_template.json` | Preset template (commented JSONC). **Kept in the repo — download it yourself if needed**; copy to `llm_presets.json` or import it via Settings → Import presets |
| `app.ico` | Program icon |
| `维护清单.md` | File maintenance checklist (project structure & search anchors, for maintainers) |

> Release packages ship `LLMGUI.exe` only by default; `presets_template.json` lives at the repo root for users who need it to download.

Files auto-generated locally at runtime (personal, not committed): `llm_presets.json` (presets), `llm_default_presets.json` (auto-computed params), `llm_gui_config.json` (local config).

## Build the exe

```bat
pyinstaller --onefile --windowed --name LLMGUI --icon=app.ico --collect-all customtkinter llm_gui.py
```

## Version

- v1.2.0 (2026-08-14) Consolidated update (everything since v1.1.4, none released separately):
  - New: thinking-mode toggle (default on, `--reasoning on/off`); multimodal toggle (vision models → `--mmproj`, auto-matching the projector file in `models/`)
  - Refactor: thinking / Gemma / multimodal are now **preset parameters** (saved into `llm_presets.json`); **every parameter can be left empty** — empty fields are not passed to llama-server, which uses its own defaults (dropdowns gained a "（默认）" blank option); the llama-server path is now a **global setting** (moved into the Settings dialog, with a browse button)
  - New: `presets_template.json` — a commented preset template; preset files now support JSONC comments
- v1.1.4 (2026-08-12) New: remember the last selected model and auto-select it on next launch (falls back to the first if the model was deleted)
- v1.1.3 (2026-08-12) Fix: input box reverts to the model name when selecting "no preset" or switching to a model without presets (no longer keeps the previous preset name)
- v1.1.2 (2026-08-12) Optimization: when a model has usable presets, apply the preset first (last-selected > "默认" > first), auto-compute only when there is no preset; clicking "compute defaults" / changing category / toggling Gemma actively overrides
- v1.1.1 (2026-08-12) Polish: delete-preset button turns vivid when enabled / tooltips left-aligned below source (auto right-align near right edge) / dialogs use app icon and center on main window / Gemma checkbox moved under max output / rename uses the input box text / loading a preset fills the input box with its name
- v1.1.0 (2026-08-12) Initial release: presets / auto-compute defaults from VRAM / GPU detection / persistent API address (selectable & copyable) / Gemma model option (auto-generates missing chat template) / parameter source marker / remember last selected preset per model / rename presets / remember window size & splitter / preset health check in settings (keep/delete/export) / import presets (choose overwrite/keep on conflicts) / batch preset management / silent llama process launch
