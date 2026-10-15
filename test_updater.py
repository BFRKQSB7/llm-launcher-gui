"""自动更新回归测试：版本比较、Release 解析、asset 查找、SHA-256、配置默认、替换脚本。

不联网、不触碰真实运行 EXE；把下载与替换拆成纯函数后逐一验证。
"""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import llm_gui


def make_release(tag='v1.12.0', draft=False, prerelease=False, assets=None, body='release notes'):
    return {
        'tag_name': tag,
        'name': tag,
        'body': body,
        'html_url': f'https://github.com/BFRKQSB7/llm-launcher-gui/releases/tag/{tag}',
        'draft': draft,
        'prerelease': prerelease,
        'assets': assets if assets is not None else [
            {'name': 'LLMGUI.exe', 'browser_download_url': 'https://example.invalid/LLMGUI.exe',
             'digest': 'sha256:' + 'a' * 64, 'size': 1234},
        ],
    }


class VersionTests(unittest.TestCase):
    def test_normalizes_leading_v(self):
        self.assertEqual(llm_gui.normalize_version('v1.12.0'), '1.12.0')
        self.assertEqual(llm_gui.normalize_version(' V1.12.0 '), '1.12.0')

    def test_numeric_comparison_not_string(self):
        self.assertTrue(llm_gui.compare_versions('1.11.0', '1.10.9')[0])
        self.assertTrue(llm_gui.compare_versions('1.10.10', '1.10.2')[0])
        self.assertTrue(llm_gui.compare_versions('1.10.2', '1.10.10')[1])
        self.assertEqual(llm_gui.compare_versions('1.11.0', '1.11.0'), (False, False))

    def test_unparsable_is_not_newer(self):
        self.assertFalse(llm_gui.is_update_available('1.11.0', 'nightly'))
        newer, older = llm_gui.compare_versions('abc', '1.0.0')
        self.assertEqual((newer, older), (False, False))

    def test_update_available(self):
        self.assertTrue(llm_gui.is_update_available('1.11.0', '1.12.0'))
        self.assertFalse(llm_gui.is_update_available('1.11.0', '1.11.0'))
        self.assertFalse(llm_gui.is_update_available('1.11.0', '1.10.9'))


class ReleaseParseTests(unittest.TestCase):
    def test_parses_fields_and_asset(self):
        info = llm_gui.parse_release(make_release())
        self.assertEqual(info['version'], '1.12.0')
        self.assertEqual(info['tag'], 'v1.12.0')
        self.assertEqual(info['asset_name'], 'LLMGUI.exe')
        self.assertEqual(info['asset_url'], 'https://example.invalid/LLMGUI.exe')
        self.assertEqual(info['digest'], 'a' * 64)
        self.assertEqual(info['size'], 1234)
        self.assertEqual(info['body'], 'release notes')

    def test_filters_draft_and_prerelease(self):
        self.assertIsNone(llm_gui.parse_release(make_release(draft=True)))
        self.assertIsNone(llm_gui.parse_release(make_release(prerelease=True)))

    def test_missing_fields_tolerated(self):
        self.assertIsNone(llm_gui.parse_release({'draft': False, 'prerelease': False}))  # 无 tag
        info = llm_gui.parse_release({'tag_name': 'v2.0.0'})
        self.assertEqual(info['version'], '2.0.0')
        self.assertIsNone(info['asset_name'])
        self.assertIsNone(info['asset_url'])
        self.assertIsNone(info['digest'])
        self.assertEqual(info['body'], '')

    def test_non_dict_returns_none(self):
        self.assertIsNone(llm_gui.parse_release(None))
        self.assertIsNone(llm_gui.parse_release([]))


class AssetTests(unittest.TestCase):
    def test_find_asset_case_insensitive(self):
        assets = [{'name': 'readme.txt'}, {'name': 'llmgui.EXE', 'browser_download_url': 'u'}]
        found = llm_gui.find_asset(assets)
        self.assertEqual(found['browser_download_url'], 'u')

    def test_find_asset_missing(self):
        self.assertIsNone(llm_gui.find_asset([{'name': 'other.exe'}]))
        self.assertIsNone(llm_gui.find_asset(None))

    def test_release_without_asset_has_no_download_url(self):
        info = llm_gui.parse_release(make_release(assets=[{'name': 'notes.txt'}]))
        self.assertIsNotNone(info)
        self.assertIsNone(info['asset_url'])


class DigestTests(unittest.TestCase):
    def test_digest_parsing(self):
        self.assertEqual(llm_gui.parse_sha256_digest('sha256:' + 'A' * 64), 'a' * 64)
        self.assertEqual(llm_gui.parse_sha256_digest('B' * 64), 'b' * 64)

    def test_bad_digest_is_none(self):
        self.assertIsNone(llm_gui.parse_sha256_digest(None))
        self.assertIsNone(llm_gui.parse_sha256_digest(''))
        self.assertIsNone(llm_gui.parse_sha256_digest('md5:abc'))
        self.assertIsNone(llm_gui.parse_sha256_digest('sha256:xyz'))

    def test_verify_matching_and_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'a.bin'
            f.write_bytes(b'hello world')
            good = hashlib.sha256(b'hello world').hexdigest()
            self.assertEqual(llm_gui.verify_sha256(f, 'sha256:' + good), (True, good))
            ok, actual = llm_gui.verify_sha256(f, 'sha256:' + '0' * 64)
            self.assertFalse(ok)
            self.assertEqual(actual, good)

    def test_verify_without_digest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'a.bin'
            f.write_bytes(b'data')
            ok, actual = llm_gui.verify_sha256(f, None)
            self.assertTrue(ok)
            self.assertEqual(actual, hashlib.sha256(b'data').hexdigest())


class ConfigDefaultTests(unittest.TestCase):
    def test_missing_field_defaults_on(self):
        self.assertTrue(llm_gui.default_auto_check_updates({}))

    def test_explicit_off(self):
        self.assertFalse(llm_gui.default_auto_check_updates({'auto_check_updates': False}))

    def test_explicit_on(self):
        self.assertTrue(llm_gui.default_auto_check_updates({'auto_check_updates': True}))


class UpdaterScriptTests(unittest.TestCase):
    def _write(self, content):
        tmp = tempfile.TemporaryDirectory()
        p = Path(tmp.name) / 'upd.bat'
        llm_gui.write_update_bat(str(p), content)
        return tmp, p

    def test_bat_ready_marker_before_launch(self):
        content = llm_gui.build_update_bat(
            r'C:\Program Files\LLMGUI-new.exe.tmp', r'C:\Program Files\LLMGUI.exe', 4242)
        self.assertIn(':copyloop', content)
        self.assertIn('if not errorlevel 1 goto launched', content)
        self.assertIn(':giveup', content)
        # 自删除命令必须排在启动新版之后
        self.assertLess(content.index('start "" "%TARGET%"'), content.index('Remove-Item'))

    def test_bat_pid_bound_and_quoted_paths(self):
        content = llm_gui.build_update_bat(
            r'C:\tmp\新 版 LLMGUI.exe.tmp', r'C:\dir with space\LLMGUI.exe', 777)
        self.assertIn('set "PID=777"', content)
        self.assertIn(r'set "TARGET=C:\dir with space\LLMGUI.exe"', content)
        self.assertIn('set "NEWEXE=C:\\tmp\\新 版 LLMGUI.exe.tmp"', content)
        self.assertIn('goto waitloop', content)

    def test_write_uses_console_encoding(self):
        content = llm_gui.build_update_bat(r'C:\t\新.tmp', r'C:\d\LLMGUI.exe', 1)
        tmp, p = self._write(content)
        try:
            raw = p.read_bytes()
            self.assertIn('新'.encode(llm_gui._console_encoding()), raw)
        finally:
            tmp.cleanup()

    def test_quote_cmd_arg(self):
        self.assertEqual(llm_gui.quote_cmd_arg(r'C:\a b\c'), '"C:\\a b\\c"')
        self.assertEqual(llm_gui.quote_cmd_arg('say "hi"'), '"say ""hi"""')


class SourceModeTests(unittest.TestCase):
    def test_source_mode_target_never_overwrites_python(self):
        app = object.__new__(llm_gui.App)
        with patch.object(llm_gui.sys, 'frozen', False, create=True), \
             patch.object(llm_gui, 'BASE', r'C:\somewhere'):
            target = app._update_target_path()
        self.assertTrue(target.endswith('LLMGUI.exe'))
        self.assertNotEqual(os.path.normcase(target), os.path.normcase(llm_gui.__file__))

    def test_frozen_mode_target_is_executable(self):
        app = object.__new__(llm_gui.App)
        with patch.object(llm_gui.sys, 'frozen', True, create=True), \
             patch.object(llm_gui.sys, 'executable', r'C:\Apps\LLMGUI.exe'):
            self.assertEqual(app._update_target_path(), r'C:\Apps\LLMGUI.exe')


class HandlerTests(unittest.TestCase):
    def _app(self):
        app = object.__new__(llm_gui.App)
        app._q = __import__('queue').Queue()
        app._update_prompted = False
        app.show_count = 0
        app.shown = []
        app._show_update_dialog = lambda info: (app.shown.append(info), setattr(app, 'show_count', app.show_count + 1))
        app._show_info = lambda title, msg: app.shown.append(('info', title, msg))
        return app

    def test_auto_silent_when_up_to_date(self):
        app = self._app()
        with patch.object(llm_gui, 'VERSION', '1.11.0'):
            app._handle_update_result({'version': '1.11.0'}, None, False, True)
        self.assertEqual(app.shown, [])

    def test_manual_reports_up_to_date(self):
        app = self._app()
        with patch.object(llm_gui, 'VERSION', '1.11.0'):
            app._handle_update_result({'version': '1.11.0'}, None, True, True)
        self.assertEqual(app.shown[0][:2], ('info', '检查更新'))

    def test_manual_reports_error(self):
        app = self._app()
        app._handle_update_result(None, '网络不可用', True, False)
        self.assertEqual(app.shown, [('info', '检查更新', '网络不可用')])

    def test_auto_error_is_silent(self):
        app = self._app()
        app._handle_update_result(None, '网络不可用', False, False)
        self.assertEqual(app.shown, [])

    def test_auto_prompts_once_per_run(self):
        app = self._app()
        with patch.object(llm_gui, 'VERSION', '1.11.0'):
            app._handle_update_result({'version': '1.12.0'}, None, False, True)
            app._handle_update_result({'version': '1.12.0'}, None, False, True)
        self.assertEqual(app.show_count, 1)

    def test_manual_can_reopen_after_prompt(self):
        app = self._app()
        with patch.object(llm_gui, 'VERSION', '1.11.0'):
            app._handle_update_result({'version': '1.12.0'}, None, False, True)
            app._handle_update_result({'version': '1.12.0'}, None, True, True)
        self.assertEqual(app.show_count, 2)


if __name__ == '__main__':
    unittest.main()
