"""Windows 冻结 EXE 隔离启动验证；不操作真实运行目录或加载模型。"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil
import win32con
import win32gui
import win32process


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exe', type=Path)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='llm-gui-frozen-') as temp:
        root = Path(temp)
        exe = root / 'LLMGUI.exe'
        shutil.copy2(args.exe, exe)
        models = root / 'models'
        models.mkdir()
        (models / 'fixture.gguf').touch()
        data = root / 'llm_gui_data.json'
        data.write_text(json.dumps({'config': {'models_dir': str(models), 'server_path': sys.executable,
            'remember_size': True, 'window_size': [1300, 650], 'hardware': {'vram_gb': 16, 'gpus': []}},
            'presets': {}, 'defaults': {}}), encoding='utf-8')
        proc = subprocess.Popen([str(exe)], cwd=root)
        hwnd = None
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f'EXE 提前退出：{proc.returncode}')
                pids = {proc.pid} | {p.pid for p in psutil.Process(proc.pid).children(recursive=True)}
                windows = []

                def collect(handle, _):
                    _, pid = win32process.GetWindowThreadProcessId(handle)
                    title = win32gui.GetWindowText(handle)
                    if pid in pids and win32gui.IsWindowVisible(handle) and title.startswith('LLM GUI —'):
                        windows.append((handle, title))

                win32gui.EnumWindows(collect, None)
                if windows:
                    hwnd, title = windows[0]
                    if not title.endswith('v' + args.version):
                        raise RuntimeError('窗口版本不一致：' + title)
                    break
                time.sleep(0.1)
            if hwnd is None:
                raise RuntimeError('25 秒内未出现冻结程序主窗口')
            time.sleep(0.6)
            rect = win32gui.GetClientRect(hwnd)
            if rect[2] < 600 or rect[3] < 600 or rect[2] / rect[3] > 1.2:
                raise RuntimeError(f'冻结窗口比例异常：{rect}')
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            proc.wait(timeout=10)
            if proc.returncode != 0 or (root / 'llm_gui_err.log').exists():
                raise RuntimeError('冻结程序退出异常或写入崩溃日志')
            config = json.loads(data.read_text(encoding='utf-8'))['config']
            if config.get('window_layout_version') != 1:
                raise RuntimeError('冻结程序未完成新窗口布局迁移')
            print(json.dumps({'frozen_smoke': 'passed', 'version': args.version,
                              'client_pixels': [rect[2], rect[3]],
                              'saved_logical_size': config['window_size'],
                              'real_inference': 'not performed'}, ensure_ascii=False))
        finally:
            if proc.poll() is None:
                children = psutil.Process(proc.pid).children(recursive=True)
                for child in children:
                    child.kill()
                proc.kill()
                proc.wait(timeout=5)


if __name__ == '__main__':
    main()
