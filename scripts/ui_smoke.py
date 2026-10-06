import ctypes
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llm_gui as gui
from PIL import Image


def capture(app, path):
    # 只渲染本测试窗口，不截取桌面或其他应用。
    app.update()
    hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    import win32gui, win32ui
    dc = win32gui.GetWindowDC(hwnd)
    src = win32ui.CreateDCFromHandle(dc)
    dst = src.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(src, width, height)
    dst.SelectObject(bitmap)
    try:
        ok = ctypes.windll.user32.PrintWindow(hwnd, dst.GetSafeHdc(), 2)
        if not ok:
            raise RuntimeError('PrintWindow failed')
        bits = bitmap.GetBitmapBits(True)
        Image.frombuffer('RGB', (width, height), bits, 'raw', 'BGRX', 0, 1).save(path)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        dst.DeleteDC()
        src.DeleteDC()
        win32gui.ReleaseDC(hwnd, dc)


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    for name in ('DATA_FILE', 'LEGACY_CONFIG_FILE', 'LEGACY_PRESETS_FILE', 'LEGACY_DEFAULTS_FILE'):
        setattr(gui, name, str(root / (name + '.json')))
    models = root / 'models'
    models.mkdir()
    model = 'Qwen3-30B-A3B-Instruct-' + 'Long-Model-Name-' * 6 + 'Q4_K_M.gguf'
    (models / model).touch()
    config = {'models_dir': str(models), 'server_path': sys.executable,
              'remember_size': True, 'window_size': [1300, 650], 'sash_pos': 100,
              'hardware': {'vram_gb': 16, 'gpus': []}}
    remembered = '--remember-custom-size' in sys.argv
    if remembered:
        config.update(window_size=[1100, 700], window_layout_version=gui.WINDOW_LAYOUT_VERSION)
    gui.save_cfg(config)
    app = gui.App()
    errors = []
    app.report_callback_exception = lambda *args: errors.append(''.join(traceback.format_exception(*args)))

    def pump(seconds=0.2):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.update()
            time.sleep(0.01)

    pump(0.4)
    assert not errors, errors
    initial = app.geometry().split('+')[0]
    if remembered:
        assert initial == '1100x700', 'current layout forgot user-adjusted window size'
    else:
        assert initial != '1300x650', 'old wide window size overrode new layout'
    assert app.cfg['window_layout_version'] == gui.WINDOW_LAYOUT_VERSION
    if not remembered:
        assert app.pw.sashpos(0) > 100, 'old sash position overrode new layout'
    app.w_ngl.insert(0, '24')
    app.w_ngl._entry.focus_force()
    pump()
    app.w_ngl._entry.event_generate('<KeyRelease>', keysym='4')
    # 真实 Tk 事件验证原有上下文绑定未被手动标记覆盖。
    app.ctx_input.insert(0, '8192')
    app.ctx_input._entry.focus_force()
    pump()
    app.ctx_input._entry.event_generate('<KeyRelease>', keysym='2')
    pump()
    assert app.ctx_preset.get() == '8K', app.ctx_preset.get()
    assert app.read_params()['ctx'] == 8192
    app._q.put(('hardware', 12, ['0, NVIDIA GeForce RTX 5070 Ti Laptop GPU']))
    pump()
    assert app.w_ngl.get() == '24', 'hardware detection overwrote parameters'
    assert app.ctx_input.get() == '8192'
    output = Path('build/ui-preview')
    output.mkdir(parents=True, exist_ok=True)
    for size in (initial, '780x640'):
        app.geometry(size + '+50+50')
        pump()
        app._restore_default_sash()
        pump()
        for tab in app.param_frames:
            app.param_tabs.set(tab)
            pump()
            for widget in (app.start_btn, app.stop_btn, app.save_btn, app.rename_btn, app.del_btn, app.compute_btn):
                assert widget.winfo_rootx() >= app.winfo_rootx()
                assert widget.winfo_rootx() + widget.winfo_width() <= app.winfo_rootx() + app.winfo_width(), (size, widget)
        app.param_tabs.set('运行参数')
        pump()
        assert app.log_box.winfo_height() >= 28, (size, app.log_box.winfo_height())
        capture(app, output / (size + '.png'))
    app.geometry(initial + '+50+50')
    pump()
    app._restore_default_sash()
    app.w_port.delete(0, 'end')
    app.w_port.insert(0, 'bad-port')
    app.start()
    pump()
    assert app.param_tabs.get() == '服务连接'
    assert app.proc is None
    app.w_port.delete(0, 'end')
    app.w_port.insert(0, '8080')
    app.w_chat_template_kwargs.insert(0, '[]')
    app.save_preset()
    pump()
    assert app.param_tabs.get() == '视觉与模板'
    app.w_chat_template_kwargs.delete(0, 'end')
    app.preset_name.delete(0, 'end')
    app.preset_name.insert(0, '测试预设')
    app.save_preset()
    assert app.preset_sel.get() == '测试预设'
    assert app.del_btn.cget('state') == 'normal'
    confirmations = []
    original_confirm = app._confirm_dlg
    app._confirm_dlg = lambda title, message, callback: confirmations.append(callback)
    app.del_preset()
    assert '测试预设' in app.presets[model], 'preset deleted before confirmation'
    assert len(confirmations) == 1
    confirmations[0]()
    assert '测试预设' not in app.presets[model]
    app._confirm_dlg = original_confirm
    # 设置弹窗只保留一份；更改无关设置不会重置参数。
    app.open_settings()
    settings = app._settings_dlg
    pump()
    app.open_settings()
    assert app._settings_dlg is settings

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    save = next(w for w in descendants(settings) if isinstance(w, gui.ctk.CTkButton) and w.cget('text') == '保存')
    save.invoke()
    pump()
    assert app.w_ngl.get() == '24'
    assert app.ctx_input.get() == '8192'
    app.clear_log()
    app.param_tabs.set('运行参数')
    pump()
    # 使用真实受控子进程，仅模拟日志和退出，不加载模型、不访问网络。
    app.build_cmd = lambda model, params: [sys.executable, '-u', '-c',
                                          'import time; print("fixture ready"); time.sleep(30)']
    app.start()
    pump()
    assert app._service_state == 'running'
    assert app.start_btn.cget('state') == 'disabled'
    app.copy_api()
    assert app.clipboard_get() == 'http://127.0.0.1:8080'
    app.model_sel.set('Qwen3-30B-A3B-Instruct-Q4_K_M.gguf')
    app.preset_name.delete(0, 'end')
    app.preset_name.insert(0, '日常聊天')
    app.status_lab.configure(text='● 模拟进程运行中 · :8080')
    app.clear_log()
    app.append_log('>>> 界面验证：模拟模型与受控进程，不加载真实模型')
    app.append_log('>>> API 地址已复制：http://127.0.0.1:8080')
    for tab in app.param_frames:
        app.param_tabs.set(tab)
        pump()
        capture(app, output / (tab + '.png'))
    old_proc = app.proc
    started = time.monotonic()
    app.stop()
    assert time.monotonic() - started < 0.15, 'stop blocked UI'
    assert app._service_state == 'stopping'
    pump(0.6)
    assert app._service_state == 'idle'
    assert app.stop_btn.cget('state') == 'disabled'
    app.start()
    new_proc = app.proc
    app._q.put(('exited', old_proc, 0))
    pump()
    assert app.proc is new_proc, 'old exit event reset new process'
    app.on_close()
    end = time.monotonic() + 4
    while not app._closed and time.monotonic() < end:
        app.update()
        time.sleep(0.01)
    assert app._closed
    assert not errors, errors
    print(json.dumps({'ui_smoke': 'passed', 'sizes': [initial, '780x640'],
                      'process': 'controlled fixture', 'screenshots': str(output.resolve())}, ensure_ascii=False))
