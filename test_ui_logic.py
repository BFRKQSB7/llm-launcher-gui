"""不依赖模型、显卡或真实 Tk 窗口的交互生命周期回归。"""
import io
import queue
import threading
import unittest
from unittest.mock import patch

import llm_gui


class Widget:
    def __init__(self, value=''):
        self.value = value
        self.options = {}

    def get(self):
        return self.value

    def configure(self, **options):
        self.options.update(options)

    def cget(self, key):
        return self.options.get(key)


class UiLifecycleTests(unittest.TestCase):
    def app(self):
        app = object.__new__(llm_gui.App)
        app._q = queue.Queue()
        app._closing = app._closed = False
        app._preset_locked = False
        app._service_state = 'idle'
        app._api_base = ''
        app.current_model = 'model.gguf'
        app.proc = None
        app.logs = []
        app.append_log = app.logs.append
        app.after = lambda *args: None
        app._set_param_src = lambda *args, **kwargs: None
        app._set_svc_idle = lambda: None
        for name in ('start_btn', 'stop_btn', 'save_btn', 'compute_btn', 'copy_api_btn', 'status_lab'):
            setattr(app, name, Widget())
        return app

    def test_disabled_actions_match_service_and_model_state(self):
        app = self.app()
        app.current_model = None
        app._sync_action_controls()
        self.assertEqual(app.start_btn.cget('state'), 'disabled')
        self.assertEqual(app.save_btn.cget('state'), 'disabled')
        app.current_model = 'model.gguf'
        app._set_service_state('running')
        self.assertEqual(app.start_btn.cget('state'), 'disabled')
        self.assertEqual(app.stop_btn.cget('state'), 'normal')
        app._set_service_state('stopping')
        self.assertEqual(app.stop_btn.cget('state'), 'disabled')
        self.assertEqual(app.stop_btn.cget('text'), '正在停止…')

    def test_old_exit_and_log_cannot_reset_new_process(self):
        app = self.app()
        old, current = object(), object()
        app.proc = current
        app._set_service_state('running')
        app._q.put(('log', old, 'old output'))
        app._q.put(('exited', old, 0))
        app._q.put(('log', current, 'current output'))
        app._poll_q()
        self.assertIs(app.proc, current)
        self.assertEqual(app._service_state, 'running')
        self.assertEqual(app.logs, ['current output'])
        app._q.put(('exited', current, 0))
        app._poll_q()
        self.assertIsNone(app.proc)
        self.assertEqual(app._service_state, 'idle')

    def test_reader_uses_captured_process_and_queue_only(self):
        app = self.app()
        app.after = lambda *args: self.fail('工作线程调用了 Tk after')
        app.proc = object()  # 新进程不应影响旧读取器持有的 stdout。
        proc = type('Process', (), {'stdout': io.StringIO('hello\n'), 'wait': lambda self: 7})()
        app._read(proc)
        self.assertEqual(app._q.get_nowait(), ('log', proc, 'hello'))
        self.assertEqual(app._q.get_nowait(), ('exited', proc, 7))
        self.assertTrue(proc.stdout.closed)

    def test_stop_returns_while_worker_waits_and_repeated_click_is_ignored(self):
        app = self.app()
        waiting, release = threading.Event(), threading.Event()

        class Process:
            returncode = 0

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout):
                waiting.set()
                if not release.wait(2):
                    raise RuntimeError('测试未释放等待')

        app.proc = Process()
        app._set_service_state('running')
        try:
            app.stop()
            self.assertTrue(waiting.wait(1))
            self.assertFalse(release.is_set())
            self.assertEqual(app._service_state, 'stopping')
            app.stop()
            self.assertEqual(app.logs.count('>>> 正在停止服务…'), 1)
        finally:
            release.set()
        _, proc, code = app._q.get(timeout=1)
        self.assertIs(proc, app.proc)
        self.assertEqual(code, 0)

    def test_hardware_refresh_preserves_edits_and_saves_on_ui_thread(self):
        app = self.app()
        app.cfg = {'last_model': 'model.gguf'}
        app.gpu_sel = Widget('0, NVIDIA')
        app.gpu_sel.options['values'] = ['自动', '0, NVIDIA']
        app.gpu_sel.set = lambda value: setattr(app.gpu_sel, 'value', value)
        app._apply_gpus = lambda values: None
        app._update_gpu_tip = lambda: None
        app._finish_hardware_check = lambda: None
        app.apply_computed_defaults = lambda *args: self.fail('检测覆盖了用户参数')
        app._mark_param_edited()
        app._q.put(('hardware', 16, ['0, NVIDIA']))
        with patch.object(llm_gui, 'save_cfg') as save:
            app._poll_q()
        self.assertTrue(app._preset_locked)
        self.assertEqual(app.gpu_sel.get(), '0, NVIDIA')
        self.assertEqual(app.cfg['hardware']['vram_gb'], 16)
        save.assert_called_once_with(app.cfg)


if __name__ == '__main__':
    unittest.main()
